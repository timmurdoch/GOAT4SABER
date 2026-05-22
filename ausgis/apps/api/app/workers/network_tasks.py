"""Network analysis Celery tasks: shortest path, OD matrix, catchment population."""
import json
import uuid
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import geopandas as gpd
from shapely.geometry import LineString

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.models.analysis import AnalysisJob, JobStatus
from app.models.layer import Layer, SourceType

CENSUS_TABLES = {
    "sa1": ("abs_sa1_2021", "sa1_code_2021"),
    "sa2": ("abs_sa2_2021", "sa2_code_2021"),
    "sa3": ("abs_sa3_2021", "sa3_code_2021"),
    "sa4": ("abs_sa4_2021", "sa4_code_2021"),
    "lga": ("abs_lga_2023", "lga_code_2023"),
}

# Approximate metres-per-minute for straight-line fallback (no OSM network)
_SPEED_MPM = {"walk": 83, "cycle": 250, "drive": 583}


def _sync_session():
    engine = create_engine(settings.SYNC_DATABASE_URL)
    return Session(engine), engine


def _update_job(session, job_id, status, result_layer_id=None, result_data=None, error=None, completed=False):
    job = session.get(AnalysisJob, job_id)
    if not job:
        return
    job.status = status
    if result_layer_id:
        job.result_layer_id = result_layer_id
    if result_data is not None:
        job.result_data = result_data
    if error:
        job.error_message = str(error)
    if completed:
        job.completed_at = datetime.now(timezone.utc)
    session.commit()


def _save_gdf(gdf: gpd.GeoDataFrame, engine, project_id: str, name: str, geom_type: str, session: Session, config: dict, analysis_type: str) -> Layer:
    table_name = f"layer_{uuid.uuid4().hex[:12]}"
    with engine.connect() as conn:
        gdf.to_postgis(table_name, conn, if_exists="replace", index=False)
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
        conn.commit()
    layer = Layer(
        project_id=project_id,
        name=name,
        source_type=SourceType.analysis,
        table_name=table_name,
        geom_type=geom_type,
        srid=4326,
        feature_count=len(gdf),
        metadata_={"analysis_type": analysis_type, "config": config},
    )
    session.add(layer)
    session.flush()
    return layer


def _nearest_osm_node(conn, lng: float, lat: float) -> int | None:
    """Find the nearest pgRouting node to a lat/lng coordinate."""
    try:
        row = conn.execute(text("""
            SELECT id
            FROM osm_roads_aus_vertices_pgr
            ORDER BY ST_Distance(
                the_geom,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
            )
            LIMIT 1
        """), {"lng": lng, "lat": lat}).fetchone()
        return row[0] if row else None
    except Exception:
        return None


@celery_app.task(bind=True, name="analysis.shortest_path")
def run_shortest_path(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        o_lat, o_lng = config["origin"]["lat"], config["origin"]["lng"]
        d_lat, d_lng = config["destination"]["lat"], config["destination"]["lng"]
        mode = config.get("mode", "walk")
        speed_mpm = _SPEED_MPM.get(mode, 83)

        route_geom = None
        route_meta = {}

        with engine.connect() as conn:
            start_node = _nearest_osm_node(conn, o_lng, o_lat)
            end_node = _nearest_osm_node(conn, d_lng, d_lat)

            if start_node and end_node:
                try:
                    rows = conn.execute(text("""
                        SELECT
                            SUM(r.cost) AS total_cost,
                            ST_AsGeoJSON(
                                ST_LineMerge(ST_Collect(e.geometry ORDER BY r.seq))
                            ) AS route_geom
                        FROM pgr_dijkstra(
                            'SELECT id, source, target, cost, reverse_cost FROM osm_roads_aus',
                            :start, :end, directed := false
                        ) AS r
                        JOIN osm_roads_aus e ON r.edge = e.id
                    """), {"start": start_node, "end": end_node}).fetchone()

                    if rows and rows[0]:
                        distance_m = float(rows[0]) * 111_000  # cost is degrees → approx metres
                        route_geom = json.loads(rows[1])
                        route_meta = {
                            "distance_m": round(distance_m),
                            "duration_min": round(distance_m / speed_mpm),
                            "mode": mode,
                            "routing": "pgRouting",
                        }
                except Exception:
                    pass  # fall through to straight-line

        # Straight-line fallback when OSM network not loaded
        if not route_geom:
            from pyproj import Geod
            geod = Geod(ellps="WGS84")
            _, _, distance_m = geod.inv(o_lng, o_lat, d_lng, d_lat)
            route_geom = {
                "type": "LineString",
                "coordinates": [[o_lng, o_lat], [d_lng, d_lat]],
            }
            route_meta = {
                "distance_m": round(distance_m),
                "duration_min": round(distance_m / speed_mpm),
                "mode": mode,
                "routing": "straight_line",
                "note": "OSM road network not loaded — showing straight-line distance",
            }

        features = [{
            "type": "Feature",
            "geometry": route_geom,
            "properties": route_meta,
        }]
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        name = config.get("result_name") or f"Route ({mode}, {route_meta['distance_m']}m)"
        layer = _save_gdf(gdf, engine, job.project_id, name, "linestring", session, config, "shortest_path")
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data=route_meta, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.od_matrix")
def run_od_matrix(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        origins_layer = session.get(Layer, config["origins_layer_id"])
        destinations_layer = session.get(Layer, config["destinations_layer_id"])
        mode = config.get("mode", "walk")
        max_pairs = config.get("max_pairs", 500)
        speed_mpm = _SPEED_MPM.get(mode, 83)

        from pyproj import Geod
        geod = Geod(ellps="WGS84")

        with engine.connect() as conn:
            origins = conn.execute(text(f"""
                SELECT ST_X(ST_Centroid(geometry)) AS lng, ST_Y(ST_Centroid(geometry)) AS lat,
                       row_number() OVER () AS id
                FROM "{origins_layer.table_name}"
                LIMIT 50
            """)).fetchall()

            destinations = conn.execute(text(f"""
                SELECT ST_X(ST_Centroid(geometry)) AS lng, ST_Y(ST_Centroid(geometry)) AS lat,
                       row_number() OVER () AS id
                FROM "{destinations_layer.table_name}"
                LIMIT :lim
            """), {"lim": max(1, max_pairs // max(len(origins), 1))}).fetchall()

        features = []
        summary = {"pairs": 0, "mean_distance_m": 0, "max_distance_m": 0, "min_distance_m": float("inf")}
        distances = []

        for o in origins:
            for d in destinations:
                if len(features) >= max_pairs:
                    break
                _, _, dist = geod.inv(o[0], o[1], d[0], d[1])
                dur = dist / speed_mpm
                distances.append(dist)
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[o[0], o[1]], [d[0], d[1]]],
                    },
                    "properties": {
                        "origin_id": int(o[2]),
                        "destination_id": int(d[2]),
                        "distance_m": round(dist),
                        "duration_min": round(dur),
                        "mode": mode,
                    },
                })

        if distances:
            import numpy as np
            summary = {
                "pairs": len(distances),
                "mean_distance_m": round(float(np.mean(distances))),
                "max_distance_m": round(float(np.max(distances))),
                "min_distance_m": round(float(np.min(distances))),
                "mode": mode,
                "note": "Straight-line distances (load OSM network for routed times)",
            }

        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        name = config.get("result_name") or f"OD Matrix ({mode}, {len(features)} pairs)"
        layer = _save_gdf(gdf, engine, job.project_id, name, "linestring", session, config, "od_matrix")
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data=summary, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.catchment_population")
def run_catchment_population(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        catchment_layer = session.get(Layer, config["catchment_layer_id"])
        census_level = config.get("census_level", "sa2")
        census_table, code_col = CENSUS_TABLES[census_level]

        table_name = f"layer_{uuid.uuid4().hex[:12]}"

        # Intersect catchment with ABS boundaries, weight population by area fraction
        with engine.connect() as conn:
            # Check if the census table and SEIFA table have data
            abs_count = conn.execute(text(f"SELECT COUNT(*) FROM {census_table}")).scalar()
            seifa_available = False
            if abs_count and abs_count > 0:
                try:
                    conn.execute(text("SELECT 1 FROM abs_seifa_2021 LIMIT 1"))
                    seifa_available = True
                except Exception:
                    pass

            if abs_count and abs_count > 0:
                seifa_join = ""
                seifa_cols = ""
                if seifa_available and census_level == "sa2":
                    seifa_join = "LEFT JOIN abs_seifa_2021 s ON abs.{code_col} = s.sa2_code_2021".format(code_col=code_col)
                    seifa_cols = ", s.irsd_score, s.irsd_decile, s.irsad_score"

                conn.execute(text(f"""
                    CREATE TABLE {table_name} AS
                    WITH catchment_union AS (
                        SELECT ST_Union(geometry) AS geom
                        FROM "{catchment_layer.table_name}"
                    ),
                    intersected AS (
                        SELECT
                            abs.geometry AS geometry,
                            abs.{code_col} AS area_code,
                            ST_Area(ST_Intersection(abs.geometry::geography, cu.geom::geography)) AS intersect_area_m2,
                            ST_Area(abs.geometry::geography) AS total_area_m2
                        FROM {census_table} abs
                        JOIN catchment_union cu ON ST_Intersects(abs.geometry, cu.geom)
                    )
                    SELECT
                        i.geometry,
                        i.area_code,
                        ROUND((i.intersect_area_m2 / NULLIF(i.total_area_m2, 0))::numeric, 4) AS coverage_fraction,
                        ROUND(i.intersect_area_m2::numeric) AS intersect_area_m2,
                        ROUND(i.total_area_m2::numeric) AS total_area_m2
                        {seifa_cols}
                    FROM intersected i
                    {seifa_join}
                    WHERE i.intersect_area_m2 > 0
                """))
            else:
                # ABS data not loaded — return the catchment boundary itself
                conn.execute(text(f"""
                    CREATE TABLE {table_name} AS
                    SELECT geometry, 'ABS data not loaded' AS note
                    FROM "{catchment_layer.table_name}"
                """))

            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            conn.commit()

        result_data = {
            "area_units": census_level.upper(),
            "units_intersected": int(row_count or 0),
            "abs_data_loaded": bool(abs_count and abs_count > 0),
            "seifa_joined": seifa_available and census_level == "sa2",
        }

        layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"Catchment Population ({census_level.upper()})",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type="polygon",
            srid=4326,
            feature_count=int(row_count or 0),
            metadata_={"analysis_type": "catchment_population", "config": config},
        )
        session.add(layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data=result_data, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()
