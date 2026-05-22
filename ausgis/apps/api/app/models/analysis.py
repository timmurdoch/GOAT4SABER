import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class AnalysisType(str, enum.Enum):
    # Basic
    isochrone = "isochrone"
    buffer = "buffer"
    point_in_polygon = "point_in_polygon"
    spatial_join = "spatial_join"
    catchment = "catchment"
    # Network
    shortest_path = "shortest_path"
    od_matrix = "od_matrix"
    catchment_population = "catchment_population"
    # Overlay / geometry
    clip = "clip"
    overlay = "overlay"
    dissolve = "dissolve"
    centroid = "centroid"
    convex_hull = "convex_hull"
    voronoi = "voronoi"
    # Point
    kernel_density = "kernel_density"
    cluster = "cluster"
    hexbin = "hexbin"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # String(50) avoids PostgreSQL native enum — new values need no ALTER TYPE migration
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[JobStatus] = mapped_column(String(20), default=JobStatus.pending)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    result_layer_id: Mapped[str | None] = mapped_column(ForeignKey("layers.id"), nullable=True)
    result_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="analysis_jobs")
