# Breaking contract and migration failure demo

The database migration drops full_name immediately while the serializer still
reads it. The response contract also changes from name to display_name without
versioning or a compatibility period. Existing data has no backfill before the
new non-null column is required.

Expected reviewers: architecture lead, API contract subagent, data migration
subagent, dependency boundaries subagent, correctness lead, and testing lead.
