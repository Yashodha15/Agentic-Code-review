# Demo 03 - TypeScript contracts

Expected review focus: correctness and testing with contract, boundary, and
regression reasoning.

The public contract does not state whether `expiresAt` is seconds or milliseconds.
Many APIs send epoch seconds, while `Date.now()` returns milliseconds. The PR is a
compact example of a type-correct implementation that can still be behaviorally wrong.
