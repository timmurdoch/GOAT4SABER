"""Minimal WFS 2.0 endpoint — GetCapabilities and GetFeature (GeoJSON output)."""
import json
from fastapi import APIRouter, Query, HTTPException, Response
from app.db import get_pool

router = APIRouter(tags=["wfs"])


@router.get("/wfs")
async def wfs(
    SERVICE: str = Query("WFS"),
    REQUEST: str = Query("GetCapabilities"),
    TYPENAMES: str = Query(None),
    COUNT: int = Query(1000),
    OUTPUTFORMAT: str = Query("application/json"),
    VERSION: str = Query("2.0.0"),
    BBOX: str = Query(None),
):
    pool = await get_pool()

    if REQUEST.upper() == "GETCAPABILITIES":
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name FROM layers WHERE table_name IS NOT NULL LIMIT 100")
        feature_types = "\n".join(
            f'<FeatureType><Name>{r["id"]}</Name><Title>{r["name"]}</Title>'
            f'<DefaultCRS>urn:ogc:def:crs:EPSG::4326</DefaultCRS></FeatureType>'
            for r in rows
        )
        caps = f"""<?xml version="1.0" encoding="UTF-8"?>
<WFS_Capabilities version="2.0.0" xmlns="http://www.opengis.net/wfs/2.0">
  <ServiceIdentification><Title>AusGIS WFS</Title></ServiceIdentification>
  <FeatureTypeList>{feature_types}</FeatureTypeList>
</WFS_Capabilities>"""
        return Response(content=caps, media_type="text/xml")

    if REQUEST.upper() == "GETFEATURE":
        if not TYPENAMES:
            raise HTTPException(status_code=400, detail="TYPENAMES required for GetFeature")

        layer_id = TYPENAMES.split(":")[-1]
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT table_name FROM layers WHERE id = $1", layer_id)
            if not row or not row["table_name"]:
                raise HTTPException(status_code=404, detail="Layer not found")

            table = row["table_name"]
            bbox_filter = ""
            params = [COUNT]
            if BBOX:
                try:
                    coords = list(map(float, BBOX.split(",")))
                    bbox_filter = f"WHERE ST_Intersects(geometry, ST_MakeEnvelope(${len(params)+1}, ${len(params)+2}, ${len(params)+3}, ${len(params)+4}, 4326))"
                    params.extend(coords[:4])
                except ValueError:
                    pass

            rows = await conn.fetch(f"""
                SELECT ST_AsGeoJSON(geometry)::json AS geom, row_to_json(t)::json AS props
                FROM "{table}" t
                {bbox_filter}
                LIMIT $1
            """, *params)

        features = [
            {"type": "Feature", "geometry": r["geom"], "properties": dict(r["props"])}
            for r in rows
        ]
        return Response(
            content=json.dumps({"type": "FeatureCollection", "features": features}),
            media_type="application/geo+json",
        )

    raise HTTPException(status_code=400, detail=f"WFS REQUEST={REQUEST} not supported")
