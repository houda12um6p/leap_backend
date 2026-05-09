"""add_compte_rendus

Revision ID: 9de6f61f30fc
Revises: 4a7129fdfa42
Create Date: 2026-05-09 21:22:44.223478

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9de6f61f30fc'
down_revision = '4a7129fdfa42'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'compte_rendus',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('language', sa.String(5), default='fr'),
        sa.Column('decisions', sa.Text(), default='[]'),
        sa.Column('actions', sa.Text(), default='[]'),
        sa.Column('blocages', sa.Text(), default='[]'),
        sa.Column('resume', sa.Text(), default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('compte_rendus')
