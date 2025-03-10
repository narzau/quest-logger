"""add user integrations

Revision ID: 4c70d044072b
Revises: 
Create Date: 2025-03-08 00:12:50.819242

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c70d044072b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('achievements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(), nullable=True),
    sa.Column('exp_reward', sa.Integer(), nullable=True),
    sa.Column('is_repeatable', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_achievements_id'), 'achievements', ['id'], unique=False)
    op.create_index(op.f('ix_achievements_name'), 'achievements', ['name'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('level', sa.Integer(), nullable=True),
    sa.Column('experience', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('achievement_criteria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('achievement_id', sa.Integer(), nullable=True),
    sa.Column('criterion_type', sa.String(), nullable=False),
    sa.Column('target_value', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_achievement_criteria_id'), 'achievement_criteria', ['id'], unique=False)
    op.create_table('google_calendar_integration',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('oauth_state', sa.String(), nullable=True),
    sa.Column('selected_calendar_id', sa.String(), nullable=True),
    sa.Column('selected_calendar_name', sa.String(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('access_token', sa.String(), nullable=True),
    sa.Column('refresh_token', sa.String(), nullable=True),
    sa.Column('token_expiry', sa.DateTime(), nullable=True),
    sa.Column('scopes', sa.String(), nullable=True),
    sa.Column('connection_status', sa.String(), nullable=True),
    sa.Column('config', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_google_calendar_integration_id'), 'google_calendar_integration', ['id'], unique=False)
    op.create_table('quests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_completed', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('due_date', sa.DateTime(), nullable=True),
    sa.Column('rarity', sa.Enum('COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', name='questrarity'), nullable=True),
    sa.Column('quest_type', sa.Enum('DAILY', 'REGULAR', 'EPIC', 'BOSS', name='questtype'), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('exp_reward', sa.Integer(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('parent_quest_id', sa.Integer(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('tracked', sa.Boolean(), nullable=True),
    sa.Column('google_calendar_event_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['parent_quest_id'], ['quests.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quests_id'), 'quests', ['id'], unique=False)
    op.create_index(op.f('ix_quests_title'), 'quests', ['title'], unique=False)
    op.create_table('user_achievements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('achievement_id', sa.Integer(), nullable=True),
    sa.Column('unlocked_at', sa.DateTime(), nullable=True),
    sa.Column('times_earned', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_achievements_id'), 'user_achievements', ['id'], unique=False)
    op.create_table('user_achievement_progress',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('criterion_id', sa.Integer(), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['criterion_id'], ['achievement_criteria.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'criterion_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_achievement_progress')
    op.drop_index(op.f('ix_user_achievements_id'), table_name='user_achievements')
    op.drop_table('user_achievements')
    op.drop_index(op.f('ix_quests_title'), table_name='quests')
    op.drop_index(op.f('ix_quests_id'), table_name='quests')
    op.drop_table('quests')
    op.drop_index(op.f('ix_google_calendar_integration_id'), table_name='google_calendar_integration')
    op.drop_table('google_calendar_integration')
    op.drop_index(op.f('ix_achievement_criteria_id'), table_name='achievement_criteria')
    op.drop_table('achievement_criteria')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_achievements_name'), table_name='achievements')
    op.drop_index(op.f('ix_achievements_id'), table_name='achievements')
    op.drop_table('achievements')
    # ### end Alembic commands ###