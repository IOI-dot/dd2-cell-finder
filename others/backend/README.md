# backend/ (planned)

The API service of the platform: authentication, RBAC, rate limiting, runs, artifacts and the
audit trail, on PostgreSQL plus a vector database. Nothing is built yet. The design is to be
agreed with the user first; see `docs/architecture.md`, "Open design questions", and `Backend.md`.
It may call the agent layer, never `src/dd2` internals.
