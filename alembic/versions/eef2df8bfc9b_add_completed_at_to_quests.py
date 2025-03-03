"""Add completed_at to quests

Revision ID: eef2df8bfc9b
Revises: 551963ce9889
Create Date: 2025-03-03 05:19:23.980504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eef2df8bfc9b'
down_revision: Union[str, None] = '551963ce9889'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('quests', sa.Column('tracked', sa.Boolean(), nullable=True))
    # update current quests to be tracked
    op.execute("UPDATE quests SET tracked = TRUE")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('quests', 'tracked')
    # ### end Alembic commands ###