# Database backend boundary

USIPHU persistence now opens database connections through `usiphu.database`.
The current `SQLiteBackend` preserves the existing local behavior and supports
explicit database paths for isolated tests. `usiphu.storage.connect` remains a
compatibility wrapper, so current learner and faculty repositories do not need
a behavior-changing rewrite in this step.

## Current status

- Supported backend: SQLite only.
- Default selector: `USIPHU_DATABASE_BACKEND=sqlite` (also the default when unset).
- Existing `USIPHU_DB_PATH` continues to select the SQLite file.
- Foreign-key enforcement and `sqlite3.Row` behavior are preserved.
- Unsupported backend values fail closed; they never silently fall back to a
  local database.

## Deliberate non-goals

This is the seam for a future PostgreSQL implementation, not that implementation.
The existing schema initialization and repository SQL still contain SQLite
features such as `PRAGMA`, `executescript`, `INSERT OR IGNORE`, positional
question-mark placeholders, and SQLite conflict semantics. A PostgreSQL adapter
must explicitly address those differences and add PostgreSQL integration tests
before it can be enabled.

The faculty review and shared assessment review modules currently import
`connect` from `usiphu.storage`; they therefore inherit this connection
boundary without changing their approval logic. Source Inbox and extraction
remain filesystem-backed and are not changed by this database-only step.
