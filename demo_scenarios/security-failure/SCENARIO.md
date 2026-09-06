# Authorization failure demo

The route trusts a caller-controlled header as proof of administrator access.
It also continues after a failed check and returns a private download path.

Expected reviewers: security lead, authentication subagent, authorization
subagent, input validation subagent, and correctness error handling subagent.
