import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { ReviewRecord } from '../../core/api.models';
import { ReviewApiService } from '../../core/review-api.service';

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent {
  private readonly api = inject(ReviewApiService);
  readonly reviews = signal<ReviewRecord[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly activeCount = computed(() => this.reviews().filter(review => ['queued', 'running'].includes(review.status)).length);
  readonly findingCount = computed(() => this.reviews().reduce((total, review) => total + review.finding_count, 0));
  readonly failureCount = computed(() => this.reviews().filter(review => review.status === 'failed').length);

  constructor() {
    this.api.listReviews().pipe(takeUntilDestroyed()).subscribe({
      next: reviews => { this.reviews.set(reviews); this.loading.set(false); },
      error: () => { this.error.set('The review API is unavailable.'); this.loading.set(false); }
    });
  }
}
