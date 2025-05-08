"""initial schema

Revision ID: c218a10c528c
Revises: 
Create Date: 2025-04-23 10:26:05.131464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c218a10c528c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ensure schema exists
    op.execute("CREATE SCHEMA IF NOT EXISTS greencore")

    op.create_table(
        'users',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('email', sa.String(length=100), nullable=False, unique=True),
        sa.Column('global_role', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='greencore'
    )

    op.create_table(
        'user_passwords',
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.users.id'), nullable=False, primary_key=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        schema='greencore'
    )

    op.create_table(
        'sessions',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.users.id'), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='greencore'
    )

    op.create_table(
        'data_stores',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('storage_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='greencore'
    )

    op.create_table(
        'orgs',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='greencore'
    )

    op.create_table(
        'org_members',
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.users.id'), nullable=False),
        sa.Column('org_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.orgs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('user_id', 'org_id', name='uq_org_members_user_org'),
        schema='greencore'
    )

    op.create_table(
        'org_data_store_access',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('org_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.orgs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('data_store_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.data_stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('allowed_path', sa.String(length=255), nullable=False),
        sa.Column('permissions', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='greencore'
    )

    op.create_table(
        'datasets',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('org_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.orgs.id'), nullable=False),
        sa.Column('data_store_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.data_stores.id'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('name_normalized', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('spec', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('org_id', 'name_normalized', name='uq_datasets_org_name_norm'),
        schema='greencore'
    )

    op.create_table(
        'uploads',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.users.id'), nullable=False),
        sa.Column('dataset_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('greencore.datasets.id'), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('validated_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('processed_at', sa.TIMESTAMP(), nullable=True),
        schema='greencore'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('uploads', schema='greencore')
    op.drop_table('datasets', schema='greencore')
    op.drop_table('org_data_store_access', schema='greencore')
    op.drop_table('org_members', schema='greencore')
    op.drop_table('orgs', schema='greencore')
    op.drop_table('data_stores', schema='greencore')
    op.drop_table('sessions', schema='greencore')
    op.drop_table('users', schema='greencore')

    # remove schema
    op.execute("DROP SCHEMA IF EXISTS greencore CASCADE")
