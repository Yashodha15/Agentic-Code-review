# React stale state failure demo

The effect reads accountId but declares no dependency. If the same component
is reused for a different account, it continues showing the first account.
The request also has no cancellation or stale-response protection.

Expected reviewers: frontend lead, hooks lifecycle subagent, rendering
subagent, testing lead, and edge case design subagent.
