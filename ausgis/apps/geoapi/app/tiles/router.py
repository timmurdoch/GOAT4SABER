"""MapLibre-compatible MVT tile endpoint using PostGIS ST_AsMVT."""
import math
from fastapi import APIRouter, HTTPException, Response
from app.db import get_pool

router = APIRouter(prefix="/tiles", tags=["tiles"])


def _tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Convert tile coords to Web Mercator (EPSG:3857) bbox."""
    n = 2 ** z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_min = math.degrees(lat_min_rad)
    lat_max = math.degrees(lat_max_rad)

    def to_merc(lon, lat):
        x_m = lon * 20037508.342789244 / 180.0
        y_m = math.log(math.tan((90 + lat) * math.pi / 360.0)) / (math.pi / 180.0)
        y_m = y_m * 20037508.342789244 / 180.0
        return x_m, y_m

    xmin, ymin = to_merc(lon_min, lat_min)
    xmax, ymax = to_merc(lon_max, lat_max)
    return xmin, ymin, xmax, ymax


@router.get("/{layer_id}/{z}/{x}/{y}.mvt")
async def get_tile(layer_id: str, z: int, x: int, y: int):
    if z < 0 or z > 22:
        raise HTTPException(status_code=400, detail="Invalid zoom level")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Look up the table name for this layer
        row = await conn.fetchrow(
            "SELECT table_name FROM layers WHERE id = $1", layer_id
        )
        if not row or not row["table_name"]:
            raise HTTPException(status_code=404, detail="Layer not found or has no tile data")

        table_name = row["table_name"]
        xmin, ymin, xmax, ymax = _tile_bounds(z, x, y)

        try:
            tile_data = await conn.fetchval(f"""
                WITH
                bounds AS (
                    SELECT ST_MakeEnvelope($1, $2, $3, $4, 3857) AS geom
                ),
                mvtgeom AS (
                    SELECT
                        ST_AsMVTGeom(
                            ST_Transform(t.geometry, 3857),
                            bounds.geom,
                            4096, 64, TRUE
                        ) AS geom,
                        row_to_json(t)::text AS props
                    FROM "{table_name}" t, bounds
                    WHERE ST_Intersects(t.geometry, ST_Transform(bounds.geom, 4326))
                )
                SELECT ST_AsMVT(mvtgeom.*, $5, 4096, 'geom') AS mvt
                FROM mvtgeom
            """, xmin, ymin, xmax, ymax, layer_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Tile generation failed: {str(e)}")

    if not tile_data:
        return Response(content=b"", media_type="application/x-protobuf", status_code=204)

    return Response(
        content=bytes(tile_data),
        media_type="application/x-protobuf",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/{layer_id}/tilejson.json")
async def tilejson(layer_id: str, request_base: str = "http://localhost:8100"):
    return {
        "tilejson": "3.0.0",
        "tiles": [f"{request_base}/tiles/{layer_id}/{{z}}/{{x}}/{{y}}.mvt"],
        "minzoom": 0,
        "maxzoom": 22,
        "bounds": [113.0, -44.0, 154.0, -10.0],
    }
