# Database migrations

WUTT now uses Alembic for additive schema changes. The first revision expands
the existing `profiles` table and preserves all existing rows.

Before migrating an existing SQLite database:

1. Stop application writes.
2. Make a recoverable copy of `backend/wutt.db`.
3. Install `backend/requirements.txt`.
4. From `backend/`, run `alembic upgrade head`.
5. Start the API and verify profile read/update behavior.

The migration reads `DATABASE_URL` through the existing application settings,
so the same command works with PostgreSQL when that URL is configured.

Do not use `alembic downgrade` on production data without a separate backup.
The downgrade removes the newly added profile columns and their values.

This initial revision expects WUTT's existing base tables to exist. For a brand
new database, initialize the current base schema first, then run or stamp this
revision. Before production PostgreSQL deployment, replace that bootstrap step
with a complete baseline migration so deployments never depend on
`Base.metadata.create_all()`.
