# Demo 06 - FastAPI contract and validation

Expected review focus: architecture, correctness, and testing, including API-contract,
dependency-boundaries, input boundaries, and coverage subagents.

The request schema permits negative quantities, non-finite prices, and arbitrary values.
The endpoint also lacks a stable response model. The `schema` path deliberately activates
architecture planning in addition to normal production-code review.
