from datetime import datetime
from pydantic import BaseModel
from app.models.layer import GeomType, SourceType


class LayerResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None
    geom_type: GeomType | None
    srid: int
    source_type: SourceType
    storage_path: str | None
    table_name: str | None
    feature_count: int | None
    metadata_: dict
    visible: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LayerStyleUpdate(BaseModel):
    style: dict


class LayerStyleResponse(BaseModel):
    layer_id: str
    style: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class OGCConnectRequest(BaseModel):
    project_id: str
    name: str
    url: str
    service_type: str  # "WMS" or "WFS"
    layer_name: str
