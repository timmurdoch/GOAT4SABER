"""Layer ingestion: upload files into PostGIS via GDAL/GeoPandas."""
import os
import shutil
import tempfile
import uuid
import zipfile

import geopandas as gpd
from sqlalchemy import text

from app.core.config import settings
from app.services.storage import upload_file

SUPPORTED_EXTENSIONS = {".geojson", ".json", ".gpkg", ".kml", ".zip", ".csv"}


def _load_geodataframe(path: str, filename: str) -> gpd.GeoDataFrame:
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".zip":
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(tmpdir)
            shp_files = [f for f in os.listdir(tmpdir) if f.endswith(".shp")]
            if not shp_files:
                raise ValueError("No .shp file found in zip")
            return gpd.read_file(os.path.join(tmpdir, shp_files[0]))

    if ext == ".csv":
        import pandas as pd
        df = pd.read_csv(path)
        lat_col = next((c for c in df.columns if c.lower() in ("lat", "latitude", "y")), None)
        lon_col = next((c for c in df.columns if c.lower() in ("lon", "lng", "longitude", "x")), None)
        if not lat_col or not lon_col:
            raise ValueError("CSV must have lat/lon columns")
        return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon_col], df[lat_col]), crs="EPSG:4326")

    return gpd.read_file(path)


def ingest_file(
    file_path: str,
    filename: str,
    project_id: str,
    layer_name: str,
    sync_engine,
) -> dict:
    gdf = _load_geodataframe(file_path, filename)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    table_name = f"layer_{uuid.uuid4().hex[:12]}"

    with sync_engine.connect() as conn:
        gdf.to_postgis(
            table_name,
            conn,
            schema="public",
            if_exists="replace",
            index=False,
        )
        conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST (geometry)"
        ))
        conn.commit()

    object_key = f"uploads/{project_id}/{table_name}/{filename}"
    upload_file(file_path, object_key)

    geom_type = gdf.geometry.geom_type.iloc[0].lower() if len(gdf) > 0 else None

    return {
        "table_name": table_name,
        "storage_path": object_key,
        "geom_type": geom_type,
        "srid": 4326,
        "feature_count": len(gdf),
        "metadata": {
            "columns": list(gdf.columns.drop("geometry", errors="ignore")),
            "crs_original": str(gdf.crs) if gdf.crs else None,
        },
    }
