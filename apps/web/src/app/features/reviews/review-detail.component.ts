import { DatePipe, PercentPipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { ReviewFinding, ReviewRecord, ReviewTraceEvent } from '../../core/api.models';
import { ReviewApiService } from '../../core/review-api.service';

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

  constructor() {
    forkJoin({
      review: this.api.getReview(this.reviewId),
      traces: this.api.getTraces(this.reviewId),
      findings: this.api.getFindings(this.reviewId)
    }).subscribe({
      next: result => { this.review.set(result.review); this.traces.set(result.traces); this.findings.set(result.findings); this.loading.set(false); },
      error: () => { this.error.set('This review could not be loaded.'); this.loading.set(false); }
    });
  }
}
