# Successful architecture review demo

This example uses an expand-and-contract migration. It adds a nullable column,
backfills existing records, makes the new field required only after the
backfill, and keeps the old field during a compatibility window. The serializer
returns both names so existing clients continue working during rollout.

Expected reviewers: architecture lead with API contract, data migration, and
dependency boundaries subagents. The team should complete without a verified
architecture finding.
