"""Add chat_sessions table

Revision ID: add_chat_sessions
Revises: c4530d437c4d
Create Date: 2026-04-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_chat_sessions'
down_revision: Union[str, Sequence[str], None] = 'c4530d437c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create chat_messages table if not exists
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_chat_messages_session_id', 'session_id')
    )

    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
        sa.Index('ix_chat_sessions_session_id', 'session_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('chat_sessions')
    op.drop_table('chat_messages')
