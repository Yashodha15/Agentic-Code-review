# Demo 08 - Data migration

Expected review focus: architecture, correctness, and testing with data-migration,
dependency-boundaries, boundary-case, error-handling, and regression subagents.

The migration adds a non-null column before backfilling, loads every user into memory,
derives display names from possibly malformed email values, and has no rollback strategy.
This demonstrates operational and data-integrity reasoning beyond syntax review.
