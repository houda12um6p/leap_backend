"""add_resolved_at_resolved_by_to_alerts

Revision ID: 2f04f571a774
Revises: 9de6f61f30fc
Create Date: 2026-05-13 18:28:36.223242

Adds resolved_at (DATETIME) and resolved_by (VARCHAR(255)) to the alerts
table so that POST /alerts/{id}/resolve works on fresh deployments.

Uses PRAGMA table_info to skip the ADD COLUMN if columns already exist,
making this migration safe to run against DBs that were patched manually.
"""
from alembic import op
import sqlalchemy as sa


revision = '2f04f571a774'
down_revision = '9de6f61f30fc'
branch_labels = None
depends_on = None


def _existing_columns(conn, table: str) -> set:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def upgrade() -> None:
    conn = op.get_bind()
    cols = _existing_columns(conn, 'alerts')
    if 'resolved_at' not in cols:
        op.add_column('alerts', sa.Column('resolved_at', sa.DateTime(), nullable=True))
    if 'resolved_by' not in cols:
        op.add_column('alerts', sa.Column('resolved_by', sa.String(255), nullable=True))


def downgrade() -> None:
    # SQLite does not support DROP COLUMN before version 3.35.
    # Use table-rebuild strategy for maximum compatibility.
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE alerts_downgrade (
            id          VARCHAR(36)  NOT NULL PRIMARY KEY,
            type        VARCHAR      NOT NULL,
            severity    VARCHAR(8)   NOT NULL,
            message     VARCHAR      NOT NULL,
            project_id  VARCHAR(36)  NOT NULL,
            is_resolved BOOLEAN,
            created_at  DATETIME     NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO alerts_downgrade
            (id, type, severity, message, project_id, is_resolved, created_at)
        SELECT id, type, severity, message, project_id, is_resolved, created_at
        FROM alerts
    """))
    conn.execute(sa.text("DROP TABLE alerts"))
    conn.execute(sa.text("ALTER TABLE alerts_downgrade RENAME TO alerts"))
