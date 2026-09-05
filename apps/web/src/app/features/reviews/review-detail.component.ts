import { DatePipe, PercentPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { ReviewFinding, ReviewRecord, ReviewTraceEvent } from '../../core/api.models';
import { ReviewApiService } from '../../core/review-api.service';

const PIPELINE_STAGES = new Set(['webhook', 'queue', 'worker', 'planning']);
const SPECIALIST_STAGES = new Set([
  'architecture',
  'correctness',
  'frontend',
  'security',
  'testing'
]);

interface AgentLane {
  lead: ReviewTraceEvent;
  subagents: ReviewTraceEvent[];
  findingCount: number;
}

@Component({
  selector: 'app-review-detail',
  imports: [DatePipe, PercentPipe, RouterLink],
  templateUrl: './review-detail.component.html',
  styleUrl: './review-detail.component.scss'
})
export class ReviewDetailComponent {
  private readonly api = inject(ReviewApiService);
  private readonly reviewId = inject(ActivatedRoute).snapshot.paramMap.get('id') ?? '';
  readonly review = signal<ReviewRecord | null>(null);
  readonly traces = signal<ReviewTraceEvent[]>([]);
  readonly findings = signal<ReviewFinding[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  /** System stages are displayed as the path into the parallel agent graph. */
  readonly pipeline = computed(() =>
    this.traces().filter(trace => PIPELINE_STAGES.has(trace.stage))
  );

  /**
   * Convert the flat trace stream into lead-agent lanes. A dotted stage such as
   * "security.authentication" is a child spawned by the "security" lead.
   */
  readonly agentLanes = computed<AgentLane[]>(() => {
    const traces = this.traces();
    const findings = this.findings();

    return traces
      .filter(trace => SPECIALIST_STAGES.has(trace.stage))
      .map(lead => ({
        lead,
        subagents: traces.filter(trace => trace.stage.startsWith(`${lead.stage}.`)),
        findingCount: findings.filter(finding => finding.source_agent === lead.stage).length
      }));
  });

  readonly publishStage = computed(() =>
    this.traces().find(trace => trace.stage === 'publish') ?? null
  );

  /** Combine persisted worker errors and failed trace nodes in one visible list. */
  readonly executionErrors = computed(() => {
    const persisted = this.review()?.errors ?? [];
    const failedTraces = this.traces()
      .filter(trace => trace.status === 'failed')
      .map(trace => `${trace.stage}: ${trace.detail}`);
    return [...new Set([...persisted, ...failedTraces])];
  });

  constructor() {
    forkJoin({
      review: this.api.getReview(this.reviewId),
      traces: this.api.getTraces(this.reviewId),
      findings: this.api.getFindings(this.reviewId)
    }).subscribe({
      next: result => { this.review.set(result.review); this.traces.set(result.traces); this.findings.set(result.findings); this.loading.set(false); },
      error: () => { this.error.set('This review could not be loaded.'); this.loading.set(false); }
    });
    this.api.streamReview(this.reviewId).pipe(takeUntilDestroyed()).subscribe({
      next: snapshot => {
        this.review.set(snapshot.review);
        this.traces.set(snapshot.traces);
        this.findings.set(snapshot.findings);
        this.loading.set(false);
        this.error.set('');
      },
      error: () => { this.error.set('Live review updates were interrupted.'); }
    });
  }
}
