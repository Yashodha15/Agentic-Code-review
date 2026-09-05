import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { ReviewRecord } from '../../core/api.models';
import { ReviewApiService } from '../../core/review-api.service';

@Component({
  selector: 'app-review-list',
  imports: [DatePipe, RouterLink],
  templateUrl: './review-list.component.html'
})
export class ReviewListComponent {
  private readonly api = inject(ReviewApiService);
  readonly reviews = signal<ReviewRecord[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  constructor() {
    this.api.listReviews().pipe(takeUntilDestroyed()).subscribe({
      next: reviews => { this.reviews.set(reviews); this.loading.set(false); },
      error: () => { this.error.set('Unable to load reviews.'); this.loading.set(false); }
    });
    this.api.streamReviews().pipe(takeUntilDestroyed()).subscribe(reviews => {
      this.reviews.set(reviews);
      this.loading.set(false);
      this.error.set('');
    });
  }
}
