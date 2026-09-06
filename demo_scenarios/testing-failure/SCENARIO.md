# Weak testing failure demo

The test checks only the return type. It would pass even if every discount
percentage were wrong. It also omits the zero-year case, the one-year boundary,
the five-year boundary, negative input, and money-rounding behavior.

Expected reviewers: correctness lead, boundary cases subagent, testing lead,
coverage gaps subagent, edge case design subagent, and regression tests subagent.
