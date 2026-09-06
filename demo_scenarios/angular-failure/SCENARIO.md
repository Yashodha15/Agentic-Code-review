# Angular subscription failure demo

This component starts an infinite RxJS interval when it is created but never
unsubscribes when it is destroyed. Repeated navigation creates leaked timers
and unnecessary change detection work.

Expected reviewers: frontend lead, RxJS lifecycle subagent, change detection
subagent, testing lead, and regression tests subagent.
