"""Add achievement criteria and progress tracking

Revision ID: e9f8e08bacfc
Revises: 7d031a728d0b
Create Date: 2025-03-01 07:41:39.542708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9f8e08bacfc'
down_revision: Union[str, None] = '7d031a728d0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('achievement_criteria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('achievement_id', sa.Integer(), nullable=True),
    sa.Column('criterion_type', sa.String(), nullable=False),
    sa.Column('target_value', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_achievement_criteria_id'), 'achievement_criteria', ['id'], unique=False)
    op.create_table('user_achievement_progress',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('criterion_id', sa.Integer(), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['criterion_id'], ['achievement_criteria.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'criterion_id')
    )
    op.add_column('achievements', sa.Column('is_repeatable', sa.Boolean(), nullable=True))
    op.add_column('user_achievements', sa.Column('times_earned', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user_achievements', 'times_earned')
    op.drop_column('achievements', 'is_repeatable')
    op.drop_table('user_achievement_progress')
    op.drop_index(op.f('ix_achievement_criteria_id'), table_name='achievement_criteria')
    op.drop_table('achievement_criteria')
    # ### end Alembic commands ###