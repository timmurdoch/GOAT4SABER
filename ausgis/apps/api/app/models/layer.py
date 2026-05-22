import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Integer, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class GeomType(str, enum.Enum):
    point = "point"
    linestring = "linestring"
    polygon = "polygon"
    multipoint = "multipoint"
    multilinestring = "multilinestring"
    multipolygon = "multipolygon"
    raster = "raster"


class SourceType(str, enum.Enum):
    upload = "upload"
    wms = "wms"
    wfs = "wfs"
    analysis = "analysis"
    abs = "abs"


class Layer(Base):
    __tablename__ = "layers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    geom_type: Mapped[GeomType | None] = mapped_column(SAEnum(GeomType), nullable=True)
    srid: Mapped[int] = mapped_column(Integer, default=4326)
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), default=SourceType.upload)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    table_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    feature_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    visible: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project"] = relationship(back_populates="layers")
    style: Mapped["LayerStyle | None"] = relationship(back_populates="layer", uselist=False, cascade="all, delete-orphan")


class LayerStyle(Base):
    __tablename__ = "layer_styles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    layer_id: Mapped[str] = mapped_column(ForeignKey("layers.id"), nullable=False, unique=True)
    style: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    layer: Mapped["Layer"] = relationship(back_populates="style")
