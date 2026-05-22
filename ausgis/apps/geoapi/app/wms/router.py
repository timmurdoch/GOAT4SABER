"""Minimal WMS 1.3.0 endpoint — GetCapabilities and GetMap stub for QGIS compatibility."""
from fastapi import APIRouter, Query, HTTPException, Response
from app.db import get_pool

router = APIRouter(tags=["wms"])

WMS_CAPABILITIES_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
  <Service>
    <Name>WMS</Name>
    <Title>AusGIS WMS</Title>
    <Abstract>AusGIS Web Map Service</Abstract>
    <OnlineResource href="{base_url}/wms"/>
    <MaxWidth>4096</MaxWidth>
    <MaxHeight>4096</MaxHeight>
  </Service>
  <Capability>
    <Request>
      <GetCapabilities>
        <Format>text/xml</Format>
        <DCPType><HTTP><Get><OnlineResource href="{base_url}/wms"/></Get></HTTP></DCPType>
      </GetCapabilities>
      <GetMap>
        <Format>image/png</Format>
        <DCPType><HTTP><Get><OnlineResource href="{base_url}/wms"/></Get></HTTP></DCPType>
      </GetMap>
    </Request>
    <Layer queryable="1">
      <Title>AusGIS Layers</Title>
      <CRS>EPSG:4326</CRS>
      <CRS>EPSG:3857</CRS>
      {layers}
    </Layer>
  </Capability>
</WMS_Capabilities>"""


@router.get("/wms")
async def wms(
    SERVICE: str = Query("WMS"),
    REQUEST: str = Query("GetCapabilities"),
    LAYERS: str = Query(None),
    BBOX: str = Query(None),
    WIDTH: int = Query(256),
    HEIGHT: int = Query(256),
    FORMAT: str = Query("image/png"),
    CRS: str = Query("EPSG:4326"),
    VERSION: str = Query("1.3.0"),
):
    if REQUEST.upper() == "GETCAPABILITIES":
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name FROM layers WHERE table_name IS NOT NULL LIMIT 100")
        layers_xml = "\n".join(
            f'<Layer><Name>{r["id"]}</Name><Title>{r["name"]}</Title>'
            f'<BoundingBox CRS="EPSG:4326" minx="113" miny="-44" maxx="154" maxy="-10"/></Layer>'
            for r in rows
        )
        caps = WMS_CAPABILITIES_TEMPLATE.format(base_url="http://localhost:8100", layers=layers_xml)
        return Response(content=caps, media_type="text/xml")

    raise HTTPException(status_code=400, detail=f"WMS REQUEST={REQUEST} not supported. Use GetCapabilities.")
