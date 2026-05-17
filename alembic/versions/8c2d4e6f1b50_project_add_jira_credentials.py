"""project_add_jira_credentials

Revision ID: 8c2d4e6f1b50
Revises: 7b1c9f2e4a30
Create Date: 2026-05-16 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8c2d4e6f1b50'
down_revision = '7b1c9f2e4a30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(projects)"))}
    if "jira_base_url" not in cols:
        op.add_column('projects', sa.Column('jira_base_url', sa.String(), nullable=True))
    if "jira_email" not in cols:
        op.add_column('projects', sa.Column('jira_email', sa.String(), nullable=True))
    if "jira_api_token_encrypted" not in cols:
        op.add_column('projects', sa.Column('jira_api_token_encrypted', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_column('jira_api_token_encrypted')
        batch_op.drop_column('jira_email')
        batch_op.drop_column('jira_base_url')
