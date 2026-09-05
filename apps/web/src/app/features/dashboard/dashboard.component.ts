import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { ReviewRecord, ReviewSnapshot, ReviewTraceEvent } from '../../core/api.models';
import { ReviewApiService } from '../../core/review-api.service';

const LEAD_AGENTS = new Set(['architecture', 'correctness', 'frontend', 'security', 'testing']);

interface AgentView {
  name: string;
  status: ReviewTraceEvent['status'];
  detail: string;
  subagents: ReviewTraceEvent[];
}

interface UiNotification {
  id: string;
  title: string;
  detail: string;
  createdAt: Date;
  unread: boolean;
}

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent {
  private readonly api = inject(ReviewApiService);
  private readonly destroyRef = inject(DestroyRef);
  private activeStream?: Subscription;
  private streamedReviewId = '';
  private readonly knownStatuses = new Map<string, ReviewRecord['status']>();

  readonly reviews = signal<ReviewRecord[]>([]);
  readonly activeSnapshot = signal<ReviewSnapshot | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly notifications = signal<UiNotification[]>([]);
  readonly notificationsOpen = signal(false);
  readonly toast = signal<UiNotification | null>(null);

  readonly activeCount = computed(() => this.reviews().filter(item => ['queued', 'running'].includes(item.status)).length);
  readonly findingCount = computed(() => this.reviews().reduce((sum, item) => sum + item.finding_count, 0));
  readonly completedCount = computed(() => this.reviews().filter(item => item.status === 'completed').length);
  readonly unreadCount = computed(() => this.notifications().filter(item => item.unread).length);
  readonly currentReview = computed(() => this.activeSnapshot()?.review ?? this.reviews()[0] ?? null);
  readonly currentTraces = computed(() => this.activeSnapshot()?.traces ?? []);
  readonly currentFindings = computed(() => this.activeSnapshot()?.findings ?? []);
  readonly activeTrace = computed(() => [...this.currentTraces()].reverse().find(trace => trace.status === 'running') ?? null);
  readonly progress = computed(() => {
    const review = this.currentReview();
    if (!review) return 0;
    if (['completed', 'failed', 'canceled'].includes(review.status)) return 100;
    const traces = this.currentTraces();
    if (!traces.length) return review.status === 'queued' ? 8 : 18;
    const done = traces.filter(trace => ['completed', 'skipped', 'failed'].includes(trace.status)).length;
    return Math.min(94, Math.max(18, Math.round((done / traces.length) * 100)));
  });
  readonly agents = computed<AgentView[]>(() => {
    const traces = this.currentTraces();
    return traces.filter(trace => LEAD_AGENTS.has(trace.stage)).map(trace => ({
      name: trace.stage,
      status: trace.status,
      detail: trace.detail,
      subagents: traces.filter(candidate => candidate.stage.startsWith(`${trace.stage}.`))
    }));
  });

  constructor() {
    this.destroyRef.onDestroy(() => this.activeStream?.unsubscribe());
    this.api.listReviews().pipe(takeUntilDestroyed()).subscribe({
      next: reviews => this.acceptReviews(reviews, false),
      error: () => { this.error.set('The review API is unavailable.'); this.loading.set(false); }
    });
    this.api.streamReviews().pipe(takeUntilDestroyed()).subscribe(reviews => this.acceptReviews(reviews, true));
  }

  toggleNotifications(): void {
    const open = !this.notificationsOpen();
    this.notificationsOpen.set(open);
    if (open) this.notifications.update(items => items.map(item => ({ ...item, unread: false })));
  }

  dismissToast(): void { this.toast.set(null); }

  private acceptReviews(reviews: ReviewRecord[], announceTransitions: boolean): void {
    const ordered = [...reviews].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    if (announceTransitions) this.captureTransitions(ordered);
    ordered.forEach(review => this.knownStatuses.set(review.id, review.status));
    this.reviews.set(ordered);
    this.loading.set(false);
    this.error.set('');
    const selected = ordered.find(review => ['queued', 'running'].includes(review.status)) ?? ordered[0];
    if (selected) this.followReview(selected.id);
  }

  /** Follow the detailed stream so agent nodes update during execution, not only at completion. */
  private followReview(reviewId: string): void {
    if (reviewId === this.streamedReviewId) return;
    this.activeStream?.unsubscribe();
    this.streamedReviewId = reviewId;
    this.activeSnapshot.set(null);
    this.activeStream = this.api.streamReview(reviewId).subscribe({
      next: snapshot => this.activeSnapshot.set(snapshot),
      error: () => this.error.set('Live agent updates were interrupted. Reconnecting…')
    });
  }

  private captureTransitions(reviews: ReviewRecord[]): void {
    for (const review of reviews) {
      const previous = this.knownStatuses.get(review.id);
      if (!previous || previous === review.status || !['completed', 'failed'].includes(review.status)) continue;
      const message: UiNotification = {
        id: `${review.id}-${review.status}-${review.updated_at}`,
        title: review.status === 'completed' ? 'Review complete' : 'Review needs attention',
        detail: `${review.repository} #${review.pull_request_number} · ${review.finding_count} findings`,
        createdAt: new Date(review.updated_at),
        unread: true
      };
      this.notifications.update(items => [message, ...items].slice(0, 12));
      this.toast.set(message);
      window.setTimeout(() => { if (this.toast()?.id === message.id) this.toast.set(null); }, 6000);
    }
  }
}
