from fastapi import FastAPI
from app.tiles.router import router as tiles_router
from app.wms.router import router as wms_router
from app.wfs.router import router as wfs_router

app = FastAPI(title="AusGIS GeoAPI", description="Tile server and OGC services", version="1.0.0")

app.include_router(tiles_router)
app.include_router(wms_router)
app.include_router(wfs_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ausgis-geoapi"}
