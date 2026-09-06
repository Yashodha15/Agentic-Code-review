# Demo 07 - Django authorization

Expected review focus: security, correctness, architecture, and testing. Security
subagents should cover authentication, authorization, and input validation.

The view returns a customer record by caller-controlled ID without authenticating the
request or checking ownership, and exposes internal notes. The `auth` path activates the
high-risk security plan; the model import also activates architecture review.
