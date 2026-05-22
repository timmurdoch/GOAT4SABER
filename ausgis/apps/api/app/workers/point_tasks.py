"""Point analysis Celery tasks: kernel density (KDE), DBSCAN clustering, hexagonal binning."""
import uuid
import math
from datetime import datetime, timezone

import numpy as np
from celery import Task
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import geopandas as gpd
from shapely.geometry import box as shapely_box, mapping
from shapely.ops import unary_union

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


@celery_app.task(bind=True, name="analysis.kernel_density")
def run_kernel_density(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        source_layer = session.get(Layer, config["layer_id"])
        resolution = min(int(config.get("grid_resolution", 60)), 200)
        bandwidth = config.get("bandwidth")
        weight_field = config.get("weight_field")
        percentiles = config.get("percentiles", [50, 75, 90, 95])

        with engine.connect() as conn:
            gdf = gpd.read_postgis(
                f'SELECT * FROM "{source_layer.table_name}"',
                conn, geom_col="geometry",
            )

        if len(gdf) < 5:
            raise ValueError("KDE requires at least 5 input points")

        # Use centroids for non-point geometries
        if gdf.geometry.geom_type.iloc[0] != "Point":
            gdf["geometry"] = gdf.geometry.centroid

        coords = np.array([[g.x, g.y] for g in gdf.geometry])
        weights = None
        if weight_field and weight_field in gdf.columns:
            weights = gdf[weight_field].fillna(0).values.astype(float)
            weights = np.maximum(weights, 0)

        from scipy.stats import gaussian_kde
        if weights is not None and weights.sum() > 0:
            kde = gaussian_kde(coords.T, bw_method=bandwidth, weights=weights)
        else:
            kde = gaussian_kde(coords.T, bw_method=bandwidth)

        # Evaluation grid over bounding box
        minx, miny, maxx, maxy = (
            coords[:, 0].min(), coords[:, 1].min(),
            coords[:, 0].max(), coords[:, 1].max(),
        )
        pad_x = (maxx - minx) * 0.1 or 0.05
        pad_y = (maxy - miny) * 0.1 or 0.05
        minx -= pad_x; maxx += pad_x; miny -= pad_y; maxy += pad_y

        x_grid = np.linspace(minx, maxx, resolution)
        y_grid = np.linspace(miny, maxy, resolution)
        xx, yy = np.meshgrid(x_grid, y_grid)
        positions = np.vstack([xx.ravel(), yy.ravel()])

        density = kde(positions).reshape(resolution, resolution)

        cell_w = (maxx - minx) / resolution
        cell_h = (maxy - miny) / resolution

        # Build polygon contours by merging cells above each percentile threshold
        features = []
        sorted_percentiles = sorted(percentiles, reverse=True)
        for p in sorted_percentiles:
            threshold = np.percentile(density, p)
            mask = density >= threshold

            cells = []
            for row_i in range(resolution):
                for col_i in range(resolution):
                    if mask[row_i, col_i]:
                        cx = x_grid[col_i]
                        cy = y_grid[row_i]
                        cells.append(shapely_box(
                            cx - cell_w / 2, cy - cell_h / 2,
                            cx + cell_w / 2, cy + cell_h / 2,
                        ))

            if cells:
                dissolved = unary_union(cells)
                if not dissolved.is_empty:
                    features.append({
                        "type": "Feature",
                        "geometry": mapping(dissolved),
                        "properties": {
                            "percentile": 100 - p,
                            "threshold": float(threshold),
                            "label": f"Top {100-p}%",
                        },
                    })

        if not features:
            raise ValueError("No density contours generated — check input data")

        gdf_out = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        layer = _save_gdf(
            gdf_out, engine, job.project_id,
            config.get("result_name") or f"{source_layer.name} (KDE)",
            "polygon", session, config, "kernel_density",
        )
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id,
                    result_data={"contour_levels": len(features), "point_count": len(gdf), "bw_method": str(kde.factor)},
                    completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="analysis.cluster")
def run_cluster(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        source_layer = session.get(Layer, config["layer_id"])
        eps_km = float(config.get("eps_km", 1.0))
        min_samples = int(config.get("min_samples", 5))

        with engine.connect() as conn:
            gdf = gpd.read_postgis(
                f'SELECT * FROM "{source_layer.table_name}"',
                conn, geom_col="geometry",
            )

        if len(gdf) < min_samples:
            raise ValueError(f"Need at least {min_samples} points for clustering")

        if gdf.geometry.geom_type.iloc[0] != "Point":
            gdf["geometry"] = gdf.geometry.centroid

        # Reproject to GDA2020 / MGA zone 55 (EPSG:7855) for metre-accurate distances
        gdf_proj = gdf.to_crs("EPSG:3857")
        coords = np.array([[g.x, g.y] for g in gdf_proj.geometry])

        from sklearn.cluster import DBSCAN
        eps_m = eps_km * 1000
        labels = DBSCAN(eps=eps_m, min_samples=min_samples, metric="euclidean", n_jobs=-1).fit_predict(coords)

        gdf["cluster_id"] = labels
        gdf["is_noise"] = labels == -1

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        noise_count = int((labels == -1).sum())

        # Assign colours for visualisation
        cluster_sizes = {}
        for lbl in set(labels):
            if lbl >= 0:
                cluster_sizes[int(lbl)] = int((labels == lbl).sum())

        layer = _save_gdf(
            gdf, engine, job.project_id,
            config.get("result_name") or f"{source_layer.name} (Clusters)",
            "point", session, config, "cluster",
        )
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id,
                    result_data={
                        "n_clusters": n_clusters,
                        "noise_points": noise_count,
                        "total_points": len(gdf),
                        "eps_km": eps_km,
                        "min_samples": min_samples,
                        "cluster_sizes": cluster_sizes,
                    }, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()


def _hex_grid(minx: float, miny: float, maxx: float, maxy: float, cell_size_deg: float):
    """Generate flat-top hexagon polygons covering a bounding box in geographic degrees."""
    dx = cell_size_deg * 1.5          # horizontal step (centre-to-centre)
    dy = cell_size_deg * math.sqrt(3) # vertical step (flat-top rows)

    from shapely.geometry import Polygon

    hexes = []
    row = 0
    y = miny
    while y <= maxy + cell_size_deg:
        x_offset = (cell_size_deg * 0.75) if row % 2 == 1 else 0.0
        x = minx - cell_size_deg
        while x <= maxx + cell_size_deg:
            cx, cy = x + x_offset, y
            # Flat-top hex: 6 vertices
            pts = [
                (cx + cell_size_deg * math.cos(math.radians(30 + 60 * i)),
                 cy + cell_size_deg * math.sin(math.radians(30 + 60 * i)) * 0.5)
                for i in range(6)
            ]
            hexes.append(Polygon(pts))
            x += dx
        y += dy / 2
        row += 1
    return hexes


@celery_app.task(bind=True, name="analysis.hexbin")
def run_hexbin(self: Task, job_id: str):
    session, engine = _sync_session()
    try:
        _update_job(session, job_id, JobStatus.running)
        job = session.get(AnalysisJob, job_id)
        config = job.config

        source_layer = session.get(Layer, config["layer_id"])
        cell_size_km = float(config.get("cell_size_km", 2.0))
        aggregate = config.get("aggregate", "count")
        attribute = config.get("attribute")

        # Approximate degrees per km at Australian latitudes (~-30°)
        cell_size_deg = cell_size_km / 110.0

        with engine.connect() as conn:
            gdf = gpd.read_postgis(
                f'SELECT * FROM "{source_layer.table_name}"',
                conn, geom_col="geometry",
            )

        if len(gdf) == 0:
            raise ValueError("Input layer has no features")

        if gdf.geometry.geom_type.iloc[0] != "Point":
            gdf["geometry"] = gdf.geometry.centroid

        coords = np.array([[g.x, g.y] for g in gdf.geometry])
        minx, miny = coords[:, 0].min(), coords[:, 1].min()
        maxx, maxy = coords[:, 0].max(), coords[:, 1].max()

        hexes = _hex_grid(minx, miny, maxx, maxy, cell_size_deg)
        hex_gdf = gpd.GeoDataFrame({"geometry": hexes, "hex_id": range(len(hexes))}, crs="EPSG:4326")

        # Spatial join: points to hexes
        joined = gpd.sjoin(gdf, hex_gdf, how="left", predicate="within")

        # Aggregate
        if aggregate == "count":
            agg_df = joined.groupby("hex_id").size().reset_index(name="value")
        elif attribute and attribute in gdf.columns:
            fn = "sum" if aggregate == "sum" else "mean"
            agg_df = joined.groupby("hex_id")[attribute].agg(fn).reset_index().rename(columns={attribute: "value"})
        else:
            agg_df = joined.groupby("hex_id").size().reset_index(name="value")

        result = hex_gdf.merge(agg_df, on="hex_id", how="inner")
        result = result[result["value"] > 0].copy()

        if len(result) == 0:
            raise ValueError("No points fell within any hex cell")

        layer = _save_gdf(
            result[["geometry", "hex_id", "value"]], engine, job.project_id,
            config.get("result_name") or f"{source_layer.name} (Hexbin {cell_size_km}km)",
            "polygon", session, config, "hexbin",
        )
        _update_job(session, job_id, JobStatus.completed, result_layer_id=layer.id,
                    result_data={
                        "cells_with_data": len(result),
                        "total_cells": len(hex_gdf),
                        "max_value": float(result["value"].max()),
                        "mean_value": round(float(result["value"].mean()), 2),
                        "aggregate": aggregate,
                    }, completed=True)

    except Exception as e:
        _update_job(session, job_id, JobStatus.failed, error=e, completed=True)
        raise
    finally:
        session.close()
