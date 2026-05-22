from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Literal


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


# ── Network ───────────────────────────────────────────────────────────────────

class ShortestPathRequest(BaseModel):
    project_id: str
    origin: dict       # {"lat": float, "lng": float}
    destination: dict  # {"lat": float, "lng": float}
    mode: Literal["walk", "cycle", "drive"] = "walk"
    result_name: str | None = None


class ODMatrixRequest(BaseModel):
    project_id: str
    origins_layer_id: str
    destinations_layer_id: str
    mode: Literal["walk", "cycle", "drive"] = "walk"
    max_pairs: int = 500
    result_name: str | None = None

    @field_validator("max_pairs")
    @classmethod
    def cap_pairs(cls, v):
        return min(v, 2500)


class CatchmentPopulationRequest(BaseModel):
    project_id: str
    catchment_layer_id: str  # polygon layer (e.g. isochrone result)
    census_level: Literal["sa1", "sa2", "sa3", "sa4", "lga"] = "sa2"
    result_name: str | None = None


# ── Overlay / geometry ────────────────────────────────────────────────────────

class ClipRequest(BaseModel):
    project_id: str
    input_layer_id: str
    clip_layer_id: str   # must be polygon
    result_name: str | None = None


class OverlayRequest(BaseModel):
    project_id: str
    layer_a_id: str
    layer_b_id: str
    operation: Literal["intersection", "union", "difference", "symmetric_difference"] = "intersection"
    result_name: str | None = None


class DissolveRequest(BaseModel):
    project_id: str
    layer_id: str
    dissolve_field: str | None = None  # None = dissolve all into one
    aggregate_fields: dict[str, Literal["sum", "mean", "count", "min", "max"]] = {}
    result_name: str | None = None


class CentroidRequest(BaseModel):
    project_id: str
    layer_id: str
    result_name: str | None = None


class ConvexHullRequest(BaseModel):
    project_id: str
    layer_id: str
    per_feature: bool = False  # True = hull per feature, False = hull of entire layer
    result_name: str | None = None


class VoronoiRequest(BaseModel):
    project_id: str
    layer_id: str   # must be point layer
    clip_to_extent: bool = True
    result_name: str | None = None


# ── Point analysis ────────────────────────────────────────────────────────────

class KernelDensityRequest(BaseModel):
    project_id: str
    layer_id: str         # point layer
    bandwidth: float | None = None  # None = Scott's rule
    grid_resolution: int = 60       # cells per dimension (max 200)
    percentiles: list[int] = [50, 75, 90, 95]
    weight_field: str | None = None
    result_name: str | None = None

    @field_validator("grid_resolution")
    @classmethod
    def cap_resolution(cls, v):
        return min(v, 200)


class ClusterRequest(BaseModel):
    project_id: str
    layer_id: str          # point layer
    eps_km: float = 1.0    # DBSCAN neighbourhood radius in km
    min_samples: int = 5
    result_name: str | None = None


class HexbinRequest(BaseModel):
    project_id: str
    layer_id: str          # point layer
    cell_size_km: float = 2.0
    aggregate: Literal["count", "sum", "mean"] = "count"
    attribute: str | None = None
    result_name: str | None = None


# ── Response ──────────────────────────────────────────────────────────────────

class AnalysisJobResponse(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    config: dict
    result_layer_id: str | None
    result_data: dict | None = None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
