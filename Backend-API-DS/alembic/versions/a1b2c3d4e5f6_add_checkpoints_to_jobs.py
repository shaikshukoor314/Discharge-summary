"""Add checkpoints to jobs table

Revision ID: a1b2c3d4e5f6
Revises: 5e24bea0544c
Create Date: 2026-02-03 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5e24bea0544c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add checkpoints column to jobs table."""
    # Add checkpoints column
    op.add_column('jobs', sa.Column('checkpoints', JSONB, nullable=True))
    
    # Set default for existing rows
    op.execute("""
        UPDATE jobs 
        SET checkpoints = '{"ocrCheckpoint": "pending", "dischargeMedicationsCheckpoint": "pending", "dischargeSummaryCheckpoint": "pending"}'::jsonb
        WHERE checkpoints IS NULL
    """)


def downgrade() -> None:
    """Remove checkpoints column from jobs table."""
    op.drop_column('jobs', 'checkpoints')
