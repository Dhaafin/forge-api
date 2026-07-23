"""add sequence order to workout sets

Revision ID: 9e1c45f6a987
Revises: ba90ce55f545
Create Date: 2026-07-23 14:08:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e1c45f6a987'
down_revision: Union[str, Sequence[str], None] = 'ba90ce55f545'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add sequence_order column as nullable first
    op.add_column('workout_sets', sa.Column('sequence_order', sa.Integer(), nullable=True))
    
    # 2. Populate sequence_order for existing records
    # Group sets by session_id, order by exercise_id and set_number, and assign 0-based index
    op.execute(
        """
        WITH ordered_sets AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY session_id 
                ORDER BY exercise_id, set_number, id
            ) - 1 as calc_order
            FROM workout_sets
        )
        UPDATE workout_sets
        SET sequence_order = ordered_sets.calc_order
        FROM ordered_sets
        WHERE workout_sets.id = ordered_sets.id
        """
    )
    
    # 3. Alter column to NOT NULL
    op.alter_column('workout_sets', 'sequence_order', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('workout_sets', 'sequence_order')
