"""Celery tasks for spatial analysis jobs."""
import uuid
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import geopandas as gpd
from shapely.geometry import Point, mapping

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.models.analysis import AnalysisJob, JobStatus
from app.models.layer import Layer, SourceType


def _sync_session():
    engine = create_engine(settings.SYNC_DATABASE_URL)
    return Session(engine), engine


def _update_job(session: Session, job_id: str, status: JobStatus, result_layer_id=None, error=None, completed=False):
    job = session.get(AnalysisJob, job_id)
    if job:
        job.status = status
        if result_layer_id:
            job.result_layer_id = result_layer_id
        if error:
            job.error_message = str(error)
        if completed:
            job.completed_at = datetime.now(timezone.utc)
        session.commit()


@celery_app.task(bind=True, name="analysis.isochrone")
def run_isochrone(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        lat = config["origin"]["lat"]
        lng = config["origin"]["lng"]
        mode = config.get("mode", "walk")
        cutoffs = config.get("time_cutoffs", [5, 10, 15, 20])

        # Speed assumptions (km/h) → m/min
        speeds = {"walk": 80, "cycle": 250, "drive": 500}
        speed = speeds.get(mode, 80)

        features = []
        for minutes in sorted(cutoffs, reverse=True):
            distance_m = speed * minutes
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT ST_AsGeoJSON(
                        ST_Buffer(
                            ST_Transform(
                                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                                3857
                            ),
                            :distance
                        )::geography::geometry
                    ) as geom
                """), {"lat": lat, "lng": lng, "distance": distance_m})
                row = result.fetchone()
                if row:
                    import json
                    features.append({
                        "type": "Feature",
                        "geometry": json.loads(row[0]),
                        "properties": {"minutes": minutes, "mode": mode, "distance_m": distance_m},
                    })

        import json
        geojson = {"type": "FeatureCollection", "features": features}
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        with engine.connect() as conn:
            gdf.to_postgis(table_name, conn, if_exists="replace", index=False)
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            conn.commit()

        result_layer = Layer(
            project_id=job.project_id,
            name=f"Isochrone ({mode}, {max(cutoffs)} min)",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type="polygon",
            srid=4326,
            feature_count=len(features),
            metadata_={"analysis_type": "isochrone", "config": config},
        )
        session.add(result_layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=result_layer.id, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.buffer")
def run_buffer(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        source_layer = session.get(Layer, config["layer_id"])
        if not source_layer or not source_layer.table_name:
            raise ValueError("Source layer not found or has no spatial table")

        distance_m = config["distance_m"]
        table_name = f"layer_{uuid.uuid4().hex[:12]}"

        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table_name} AS
                SELECT
                    ST_Buffer(geometry::geography, :distance)::geometry AS geometry
                FROM "{source_layer.table_name}"
            """), {"distance": distance_m})
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            conn.commit()

        result_layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"{source_layer.name} Buffer {distance_m}m",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type="polygon",
            srid=4326,
            metadata_={"analysis_type": "buffer", "config": config},
        )
        session.add(result_layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=result_layer.id, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.point_in_polygon")
def run_point_in_polygon(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        points_layer = session.get(Layer, config["points_layer_id"])
        polygons_layer = session.get(Layer, config["polygons_layer_id"])

        if not points_layer.table_name or not polygons_layer.table_name:
            raise ValueError("Layers must have spatial tables")

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        aggregate = config.get("aggregate", "count")
        attribute = config.get("attribute")

        agg_expr = "COUNT(pts.*)" if aggregate == "count" or not attribute else (
            f"SUM(pts.\"{attribute}\")" if aggregate == "sum" else f"AVG(pts.\"{attribute}\")"
        )

        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table_name} AS
                SELECT
                    poly.geometry,
                    {agg_expr} AS value
                FROM "{polygons_layer.table_name}" poly
                LEFT JOIN "{points_layer.table_name}" pts
                    ON ST_Within(pts.geometry, poly.geometry)
                GROUP BY poly.geometry
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            conn.commit()

        result_layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"Point-in-Polygon Result",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type="polygon",
            srid=4326,
            metadata_={"analysis_type": "point_in_polygon", "config": config},
        )
        session.add(result_layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=result_layer.id, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.spatial_join")
def run_spatial_join(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        left = session.get(Layer, config["left_layer_id"])
        right = session.get(Layer, config["right_layer_id"])
        predicate = config.get("predicate", "intersects")

        predicate_map = {
            "intersects": "ST_Intersects(l.geometry, r.geometry)",
            "within": "ST_Within(l.geometry, r.geometry)",
            "contains": "ST_Contains(l.geometry, r.geometry)",
        }
        join_condition = predicate_map.get(predicate, "ST_Intersects(l.geometry, r.geometry)")

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table_name} AS
                SELECT l.*, r.geometry AS right_geom
                FROM "{left.table_name}" l
                JOIN "{right.table_name}" r ON {join_condition}
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            conn.commit()

        result_layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"Spatial Join Result",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type=left.geom_type,
            srid=4326,
            metadata_={"analysis_type": "spatial_join", "config": config},
        )
        session.add(result_layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=result_layer.id, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()
