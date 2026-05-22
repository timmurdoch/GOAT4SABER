from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Literal
from app.models.analysis import AnalysisType, JobStatus


class IsochroneRequest(BaseModel):
    project_id: str
    origin: dict  # {"lat": float, "lng": float}
    mode: Literal["walk", "cycle", "drive"] = "walk"
    time_cutoffs: list[int] = [5, 10, 15, 20]
    network_layer: str = "osm_roads_aus"

    @field_validator("time_cutoffs")
    @classmethod
    def validate_cutoffs(cls, v):
        if not v or any(t <= 0 or t > 120 for t in v):
            raise ValueError("time_cutoffs must be between 1 and 120 minutes")
        return sorted(v)


class BufferRequest(BaseModel):
    project_id: str
    layer_id: str
    distance_m: float
    result_name: str | None = None


class PointInPolygonRequest(BaseModel):
    project_id: str
    points_layer_id: str
    polygons_layer_id: str
    aggregate: Literal["count", "sum", "mean"] = "count"
    attribute: str | None = None
    result_name: str | None = None


class SpatialJoinRequest(BaseModel):
    project_id: str
    left_layer_id: str
    right_layer_id: str
    predicate: Literal["intersects", "within", "contains", "nearest"] = "intersects"
    result_name: str | None = None


class AnalysisJobResponse(BaseModel):
    id: str
    project_id: str
    type: AnalysisType
    status: JobStatus
    config: dict
    result_layer_id: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
