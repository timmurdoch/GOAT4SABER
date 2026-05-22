import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, create_engine
import geopandas as gpd
import io

from app.core.config import settings
from app.core.dependencies import DB, CurrentUser
from app.models.layer import Layer, LayerStyle
from app.models.project import Project, ProjectMember, ProjectRole
from app.schemas.layer import LayerResponse, LayerStyleUpdate, LayerStyleResponse, OGCConnectRequest
from app.services.ingest import ingest_file, SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/layers", tags=["layers"])


@router.get("", response_model=list[LayerResponse])
async def list_layers(project_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Layer).where(Layer.project_id == project_id).order_by(Layer.created_at.desc())
    )
    return result.scalars().all()


async def _require_layer_access(layer_id: str, user_id: str, db: DB, write: bool = False) -> Layer:
    result = await db.execute(select(Layer).where(Layer.id == layer_id))
    layer = result.scalar_one_or_none()
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")

    project_result = await db.execute(select(Project).where(Project.id == layer.project_id))
    project = project_result.scalar_one_or_none()
    if project.owner_id == user_id:
        return layer

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == layer.project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="No access")
    if write and member.role == ProjectRole.viewer:
        raise HTTPException(status_code=403, detail="Read-only access")
    return layer


@router.post("/upload", response_model=LayerResponse, status_code=status.HTTP_201_CREATED)
async def upload_layer(
    current_user: CurrentUser,
    db: DB,
    project_id: Annotated[str, Form()],
    name: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format. Supported: {SUPPORTED_EXTENSIONS}")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        sync_engine = create_engine(settings.SYNC_DATABASE_URL)
        ingest_result = ingest_file(tmp_path, file.filename, project_id, name, sync_engine)

        from app.models.layer import SourceType
        layer = Layer(
            project_id=project_id,
            name=name,
            source_type=SourceType.upload,
            **{k: v for k, v in ingest_result.items() if k != "metadata"},
            metadata_=ingest_result.get("metadata", {}),
        )
        db.add(layer)
        await db.flush()

        style = LayerStyle(layer_id=layer.id, style=_default_style(layer.geom_type))
        db.add(style)

        return layer
    finally:
        os.unlink(tmp_path)


def _default_style(geom_type: str | None) -> dict:
    if geom_type and "polygon" in str(geom_type).lower():
        return {"type": "fill", "paint": {"fill-color": "#3B82F6", "fill-opacity": 0.5, "fill-outline-color": "#1D4ED8"}}
    if geom_type and ("line" in str(geom_type).lower() or "string" in str(geom_type).lower()):
        return {"type": "line", "paint": {"line-color": "#3B82F6", "line-width": 2}}
    return {"type": "circle", "paint": {"circle-radius": 5, "circle-color": "#3B82F6"}}


@router.get("/{layer_id}", response_model=LayerResponse)
async def get_layer(layer_id: str, current_user: CurrentUser, db: DB):
    return await _require_layer_access(layer_id, current_user.id, db)


@router.delete("/{layer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_layer(layer_id: str, current_user: CurrentUser, db: DB):
    layer = await _require_layer_access(layer_id, current_user.id, db, write=True)
    await db.delete(layer)


@router.patch("/{layer_id}/style", response_model=LayerStyleResponse)
async def update_style(layer_id: str, payload: LayerStyleUpdate, current_user: CurrentUser, db: DB):
    layer = await _require_layer_access(layer_id, current_user.id, db, write=True)

    result = await db.execute(select(LayerStyle).where(LayerStyle.layer_id == layer_id))
    style = result.scalar_one_or_none()
    if style:
        style.style = payload.style
    else:
        style = LayerStyle(layer_id=layer_id, style=payload.style)
        db.add(style)
    await db.flush()
    return style


@router.get("/{layer_id}/export")
async def export_layer(layer_id: str, format: str = "geojson", current_user: CurrentUser = None, db: DB = None):
    layer = await _require_layer_access(layer_id, current_user.id, db)
    if not layer.table_name:
        raise HTTPException(status_code=400, detail="Layer has no spatial data table")

    sync_engine = create_engine(settings.SYNC_DATABASE_URL)
    gdf = gpd.read_postgis(f'SELECT * FROM "{layer.table_name}"', sync_engine, geom_col="geometry")

    if format == "geojson":
        content = gdf.to_json()
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="{layer.name}.geojson"'},
        )
    elif format == "csv":
        gdf["lon"] = gdf.geometry.x if gdf.geometry.geom_type.iloc[0] == "Point" else gdf.geometry.centroid.x
        gdf["lat"] = gdf.geometry.y if gdf.geometry.geom_type.iloc[0] == "Point" else gdf.geometry.centroid.y
        content = gdf.drop(columns="geometry").to_csv(index=False)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{layer.name}.csv"'},
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format. Use 'geojson' or 'csv'")


@router.post("/connect-ogc", response_model=LayerResponse, status_code=status.HTTP_201_CREATED)
async def connect_ogc(payload: OGCConnectRequest, current_user: CurrentUser, db: DB):
    from app.models.layer import SourceType
    source_type = SourceType.wms if payload.service_type.upper() == "WMS" else SourceType.wfs
    layer = Layer(
        project_id=payload.project_id,
        name=payload.name,
        source_type=source_type,
        storage_path=payload.url,
        metadata_={"service_type": payload.service_type, "layer_name": payload.layer_name, "url": payload.url},
    )
    db.add(layer)
    await db.flush()
    return layer
