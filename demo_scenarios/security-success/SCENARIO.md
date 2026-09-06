# Successful security review demo

This route obtains identity through a verified dependency, checks the admin
role before continuing, constrains the identifier to an integer, validates the
resolved path, and avoids returning a private filesystem path.

Expected reviewers: security lead with authentication, authorization, and
input validation subagents. The team should complete without a verified
security finding.
