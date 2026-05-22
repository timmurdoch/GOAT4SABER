"""Initial schema — all application tables.

Revision ID: 0001
Revises:
Create Date: 2026-05-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("api_key", sa.String(64), unique=True, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_api_key", "users", ["api_key"])

    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("owner_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_members",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(20), server_default="viewer"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "layers",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("geom_type", sa.String(30), nullable=True),
        sa.Column("srid", sa.Integer, server_default="4326"),
        sa.Column("source_type", sa.String(20), server_default="upload"),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("table_name", sa.String(255), nullable=True),
        sa.Column("feature_count", sa.Integer, nullable=True),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("visible", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "layer_styles",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("layer_id", UUID(as_uuid=False), sa.ForeignKey("layers.id"), nullable=False, unique=True),
        sa.Column("style", JSONB, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "analysis_jobs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("config", JSONB, server_default="{}"),
        sa.Column("result_layer_id", UUID(as_uuid=False), sa.ForeignKey("layers.id"), nullable=True),
        sa.Column("result_data", JSONB, nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_jobs_project", "analysis_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_table("analysis_jobs")
    op.drop_table("layer_styles")
    op.drop_table("layers")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
