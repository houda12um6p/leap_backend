"""jira_task_add_summary_and_project_id

Revision ID: 4a7129fdfa42
Revises: 2c36ad3b644d
Create Date: 2026-04-30 10:52:27.682010

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a7129fdfa42'
down_revision = '2c36ad3b644d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER TABLE reliably; use table-copy strategy.
    # The DB may already have summary/project_id from a partial earlier run,
    # so we detect what exists and build the SELECT accordingly.
    conn = op.get_bind()

    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(jira_tasks)"))}

    # Rebuild table with the correct final schema
    conn.execute(sa.text("""
        CREATE TABLE jira_tasks_new (
            id          VARCHAR(36) NOT NULL PRIMARY KEY,
            jira_key    VARCHAR     NOT NULL UNIQUE,
            summary     VARCHAR     NOT NULL,
            status      VARCHAR     NOT NULL,
            story_points INTEGER    DEFAULT 0,
            project_id  VARCHAR(36),
            created_at  DATETIME    NOT NULL,
            updated_at  DATETIME    NOT NULL
        )
    """))

    # Copy rows; use whichever column holds the text (summary if renamed, else title)
    summary_src = "summary" if "summary" in cols else "title"
    project_id_src = "project_id" if "project_id" in cols else "NULL"

    conn.execute(sa.text(f"""
        INSERT INTO jira_tasks_new
            (id, jira_key, summary, status, story_points, project_id, created_at, updated_at)
        SELECT
            id, jira_key, COALESCE({summary_src}, ''), status, story_points,
            {project_id_src}, created_at, updated_at
        FROM jira_tasks
    """))

    conn.execute(sa.text("DROP TABLE jira_tasks"))
    conn.execute(sa.text("ALTER TABLE jira_tasks_new RENAME TO jira_tasks"))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE jira_tasks_old (
            id          VARCHAR(36) NOT NULL PRIMARY KEY,
            jira_key    VARCHAR     NOT NULL UNIQUE,
            title       VARCHAR     NOT NULL,
            status      VARCHAR     NOT NULL,
            story_points INTEGER    DEFAULT 0,
            created_at  DATETIME    NOT NULL,
            updated_at  DATETIME    NOT NULL
        )
    """))

    conn.execute(sa.text("""
        INSERT INTO jira_tasks_old
            (id, jira_key, title, status, story_points, created_at, updated_at)
        SELECT
            id, jira_key, COALESCE(summary, ''), status, story_points, created_at, updated_at
        FROM jira_tasks
    """))

    conn.execute(sa.text("DROP TABLE jira_tasks"))
    conn.execute(sa.text("ALTER TABLE jira_tasks_old RENAME TO jira_tasks"))
