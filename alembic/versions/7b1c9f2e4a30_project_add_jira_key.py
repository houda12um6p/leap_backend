"""project_add_jira_key

Revision ID: 7b1c9f2e4a30
Revises: 2f04f571a774
Create Date: 2026-05-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7b1c9f2e4a30'
down_revision = '2f04f571a774'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(projects)"))}
    if "jira_key" not in cols:
        op.add_column('projects', sa.Column('jira_key', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_column('jira_key')
