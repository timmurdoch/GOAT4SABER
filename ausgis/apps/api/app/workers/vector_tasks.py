"""Vector overlay and geometry Celery tasks: clip, overlay, dissolve, centroid, convex hull, Voronoi."""
import uuid
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import geopandas as gpd
from shapely.ops import unary_union, voronoi_diagram as shapely_voronoi
from shapely.geometry import MultiPoint, GeometryCollection

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.models.analysis import AnalysisJob, JobStatus
from app.models.layer import Layer, SourceType


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


def _save_gdf(gdf, engine, project_id, name, geom_type, session, config, analysis_type):
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


@celery_app.task(bind=True, name="analysis.clip")
def run_clip(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        input_layer = session.get(Layer, config["input_layer_id"])
        clip_layer = session.get(Layer, config["clip_layer_id"])

        if not input_layer.table_name or not clip_layer.table_name:
            raise ValueError("Both layers must have spatial tables")

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table_name} AS
                SELECT
                    ST_Intersection(inp.geometry, ST_Union(clip.geometry)) AS geometry,
                    inp.*
                FROM "{input_layer.table_name}" inp
                JOIN "{clip_layer.table_name}" clip
                    ON ST_Intersects(inp.geometry, clip.geometry)
                GROUP BY inp.ctid, inp.geometry
            """))
            conn.execute(text(f"""
                DELETE FROM {table_name}
                WHERE geometry IS NULL OR ST_IsEmpty(geometry)
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            conn.commit()

        layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"{input_layer.name} (Clipped)",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type=input_layer.geom_type,
            srid=4326,
            feature_count=int(row_count or 0),
            metadata_={"analysis_type": "clip", "config": config},
        )
        session.add(layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data={"features_clipped": int(row_count or 0)}, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.overlay")
def run_overlay(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        layer_a = session.get(Layer, config["layer_a_id"])
        layer_b = session.get(Layer, config["layer_b_id"])
        operation = config.get("operation", "intersection")

        op_map = {
            "intersection": "ST_Intersection(a.geometry, b.geometry)",
            "union": "ST_Union(a.geometry, b.geometry)",
            "difference": "ST_Difference(a.geometry, b.geometry)",
            "symmetric_difference": "ST_SymDifference(a.geometry, b.geometry)",
        }
        geom_expr = op_map[operation]

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        with engine.connect() as conn:
            if operation == "union":
                conn.execute(text(f"""
                    CREATE TABLE {table_name} AS
                    SELECT {geom_expr} AS geometry
                    FROM "{layer_a.table_name}" a, "{layer_b.table_name}" b
                    LIMIT 1
                """))
            elif operation == "difference":
                conn.execute(text(f"""
                    CREATE TABLE {table_name} AS
                    SELECT
                        ST_Difference(a.geometry, ST_Union(b.geometry)) AS geometry
                    FROM "{layer_a.table_name}" a
                    CROSS JOIN "{layer_b.table_name}" b
                    GROUP BY a.ctid, a.geometry
                """))
            else:
                conn.execute(text(f"""
                    CREATE TABLE {table_name} AS
                    SELECT {geom_expr} AS geometry
                    FROM "{layer_a.table_name}" a
                    JOIN "{layer_b.table_name}" b ON ST_Intersects(a.geometry, b.geometry)
                """))
            conn.execute(text(f"""
                DELETE FROM {table_name}
                WHERE geometry IS NULL OR ST_IsEmpty(geometry)
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            conn.commit()

        geom_type = layer_a.geom_type or "polygon"
        layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"{operation.title()}: {layer_a.name} × {layer_b.name}",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type=geom_type,
            srid=4326,
            feature_count=int(row_count or 0),
            metadata_={"analysis_type": "overlay", "config": config},
        )
        session.add(layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data={"operation": operation, "features": int(row_count or 0)}, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.dissolve")
def run_dissolve(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        source_layer = session.get(Layer, config["layer_id"])
        dissolve_field = config.get("dissolve_field")
        aggregate_fields = config.get("aggregate_fields", {})

        agg_exprs = []
        for field, func in aggregate_fields.items():
            fn = {"sum": "SUM", "mean": "AVG", "count": "COUNT", "min": "MIN", "max": "MAX"}.get(func, "SUM")
            agg_exprs.append(f'{fn}("{field}") AS "{field}_{func}"')

        agg_sql = (", " + ", ".join(agg_exprs)) if agg_exprs else ""
        group_by_sql = f', "{dissolve_field}"' if dissolve_field else ""
        select_field = f', "{dissolve_field}"' if dissolve_field else ""

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table_name} AS
                SELECT
                    ST_Union(geometry) AS geometry
                    {select_field}
                    {agg_sql}
                FROM "{source_layer.table_name}"
                GROUP BY 1=1 {group_by_sql}
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            conn.commit()

        layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or (f"{source_layer.name} (Dissolved by {dissolve_field})" if dissolve_field else f"{source_layer.name} (Dissolved)"),
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type="polygon",
            srid=4326,
            feature_count=int(row_count or 0),
            metadata_={"analysis_type": "dissolve", "config": config},
        )
        session.add(layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data={"features_out": int(row_count or 0)}, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.centroid")
def run_centroid(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config
        source_layer = session.get(Layer, config["layer_id"])

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table_name} AS
                SELECT ST_Centroid(geometry) AS geometry, t.*
                FROM "{source_layer.table_name}" t
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            conn.commit()

        layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"{source_layer.name} (Centroids)",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type="point",
            srid=4326,
            feature_count=int(row_count or 0),
            metadata_={"analysis_type": "centroid", "config": config},
        )
        session.add(layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data={"centroids": int(row_count or 0)}, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.convex_hull")
def run_convex_hull(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        source_layer = session.get(Layer, config["layer_id"])
        per_feature = config.get("per_feature", False)

        table_name = f"layer_{uuid.uuid4().hex[:12]}"
        with engine.connect() as conn:
            if per_feature:
                conn.execute(text(f"""
                    CREATE TABLE {table_name} AS
                    SELECT ST_ConvexHull(geometry) AS geometry
                    FROM "{source_layer.table_name}"
                """))
            else:
                conn.execute(text(f"""
                    CREATE TABLE {table_name} AS
                    SELECT ST_ConvexHull(ST_Collect(geometry)) AS geometry
                    FROM "{source_layer.table_name}"
                """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"))
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            conn.commit()

        layer = Layer(
            project_id=job.project_id,
            name=config.get("result_name") or f"{source_layer.name} (Convex Hull)",
            source_type=SourceType.analysis,
            table_name=table_name,
            geom_type="polygon",
            srid=4326,
            feature_count=int(row_count or 0),
            metadata_={"analysis_type": "convex_hull", "config": config},
        )
        session.add(layer)
        session.flush()
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id, result_data={"hulls": int(row_count or 0)}, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.voronoi")
def run_voronoi(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        source_layer = session.get(Layer, config["layer_id"])
        clip_to_extent = config.get("clip_to_extent", True)

        with engine.connect() as conn:
            gdf = gpd.read_postgis(
                f'SELECT * FROM "{source_layer.table_name}"',
                conn, geom_col="geometry",
            )

        if len(gdf) < 3:
            raise ValueError("Voronoi requires at least 3 input points")

        # Use centroid for non-point geometries
        if gdf.geometry.geom_type.iloc[0] != "Point":
            gdf["geometry"] = gdf.geometry.centroid

        # Build Voronoi diagram using shapely
        mp = MultiPoint(list(gdf.geometry))
        envelope = mp.envelope.buffer(0.01)
        regions = shapely_voronoi(mp, envelope=envelope)

        polys = [g for g in regions.geoms if g.geom_type in ("Polygon", "MultiPolygon")]

        if clip_to_extent:
            polys = [p.intersection(envelope) for p in polys]

        voronoi_gdf = gpd.GeoDataFrame(
            {"geometry": polys, "region_id": range(len(polys))},
            crs="EPSG:4326",
        )

        layer = _save_gdf(voronoi_gdf, engine, job.project_id,
                          config.get("result_name") or f"{source_layer.name} (Voronoi)",
                          "polygon", session, config, "voronoi")
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id,
                    result_data={"regions": len(polys)}, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()
