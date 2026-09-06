# Demo 05 - Angular lifecycle and template safety

Expected review focus: frontend, correctness, and testing. Angular subagents should
show RxJS lifecycle, template safety, change detection, and accessibility.

The component keeps a subscription for its lifetime without teardown and renders
URL-derived content through `innerHTML`. It demonstrates framework-aware delegation.
