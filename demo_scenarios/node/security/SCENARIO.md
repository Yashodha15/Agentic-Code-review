# Demo 09 - Node.js token security

Expected review focus: high-risk security plus correctness and testing. The security
lane should delegate authentication, authorization, and input-validation investigations.

The example hard-codes a signing secret, creates non-expiring tokens, and decodes rather
than verifies incoming tokens. This branch should produce an obvious red security path
and is ideal for explaining fail-closed publication behavior.
