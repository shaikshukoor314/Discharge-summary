"""Replace image_base64 with image_minio_path in document_pages

Revision ID: 5e24bea0544c
Revises: 
Create Date: 2026-01-27 08:44:04.233779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e24bea0544c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old image_base64 column (which stores base64 data)
    op.drop_column('document_pages', 'image_base64')
    # Add the new image_minio_path column (which stores MinIO file paths)
    op.add_column('document_pages', sa.Column('image_minio_path', sa.String(255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new image_minio_path column
    op.drop_column('document_pages', 'image_minio_path')
    # Restore the old image_base64 column
    op.add_column('document_pages', sa.Column('image_base64', sa.Text(), nullable=True))
