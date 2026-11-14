"""checking new updates

Revision ID: 7a1dee228452
Revises: a7d1a230ae6e
Create Date: 2026-11-15 01:05:08.760495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1dee228452'
down_revision: Union[str, Sequence[str], None] = 'a7d1a230ae6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
