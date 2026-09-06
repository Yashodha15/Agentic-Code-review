export type ReviewStatus = 'queued' | 'running' | 'completed' | 'failed' | 'canceled';
export type TraceStatus = ReviewStatus | 'skipped';
export type Tone = 'neutral' | 'success' | 'info' | 'warning' | 'danger';
export interface ReviewRecord { id:string; repository:string; pull_request_number:number; head_sha:string; status:ReviewStatus; created_at:string; updated_at:string; finding_count:number; completed_agents:string[]; errors:string[]; }
export interface ReviewTrace { sequence:number; review_id:string; stage:string; status:TraceStatus; detail:string; created_at:string; }
export interface ReviewFinding { title:string; category:string; severity:'low'|'medium'|'high'|'critical'; confidence:number; path:string; line:number; comment:string; evidence:string[]; suggested_fix:string|null; source_agent:string; status:'proposed'|'verified'|'rejected'; }
export interface ReviewSnapshot { review:ReviewRecord; traces:ReviewTrace[]; findings:ReviewFinding[]; }
export interface ReviewPolicy { minimum_severity:'low'|'medium'|'high'|'critical'; require_verified_findings:boolean; block_on_critical_findings:boolean; allow_reproduction_tests:boolean; ignored_paths:string[]; limits:{maximum_specialist_agents:number;maximum_subagents:number;maximum_delegation_depth:number;maximum_runtime_seconds:number;maximum_comments:number;maximum_cost_usd:number}; }
