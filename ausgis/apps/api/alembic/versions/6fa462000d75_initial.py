"""initial

Revision ID: 6fa462000d75
Revises: 
Create Date: 2026-05-22 08:39:20.139495
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '6fa462000d75'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('api_key', sa.String(length=64), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_api_key'), 'users', ['api_key'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('projects',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=True),
    sa.Column('owner_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('layers',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('project_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('geom_type', sa.Enum('point', 'linestring', 'polygon', 'multipoint', 'multilinestring', 'multipolygon', 'raster', name='geomtype'), nullable=True),
    sa.Column('srid', sa.Integer(), nullable=False),
    sa.Column('source_type', sa.Enum('upload', 'wms', 'wfs', 'analysis', 'abs', name='sourcetype'), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=True),
    sa.Column('table_name', sa.String(length=255), nullable=True),
    sa.Column('feature_count', sa.Integer(), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('visible', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('project_members',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('project_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('user_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('role', sa.Enum('admin', 'editor', 'viewer', name='projectrole'), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('analysis_jobs',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('project_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('created_by', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('type', sa.Enum('isochrone', 'buffer', 'point_in_polygon', 'spatial_join', 'catchment', name='analysistype'), nullable=False),
    sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', name='jobstatus'), nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('result_layer_id', sa.UUID(as_uuid=False), nullable=True),
    sa.Column('celery_task_id', sa.String(length=255), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['result_layer_id'], ['layers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('layer_styles',
    sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('layer_id', sa.UUID(as_uuid=False), nullable=False),
    sa.Column('style', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['layer_id'], ['layers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('layer_id')
    )


def downgrade() -> None:
    op.drop_table('layer_styles')
    op.drop_table('analysis_jobs')
    op.drop_table('project_members')
    op.drop_table('layers')
    op.drop_table('projects')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_api_key'), table_name='users')
    op.drop_table('users')
