import { HttpClient } from '@angular/common/http';
import { inject, Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';
import { ReviewFinding, ReviewPolicy, ReviewRecord, ReviewSnapshot, ReviewTraceEvent } from './api.models';

@Injectable({ providedIn: 'root' })
export class ReviewApiService {
  private readonly baseUrl = '/api/v1';
  private readonly zone = inject(NgZone);

  constructor(private readonly http: HttpClient) {}

  listReviews(): Observable<ReviewRecord[]> {
    return this.http.get<ReviewRecord[]>(`${this.baseUrl}/reviews`);
  }

  getReview(reviewId: string): Observable<ReviewRecord> {
    return this.http.get<ReviewRecord>(`${this.baseUrl}/reviews/${reviewId}`);
  }

  getTraces(reviewId: string): Observable<ReviewTraceEvent[]> {
    return this.http.get<ReviewTraceEvent[]>(`${this.baseUrl}/reviews/${reviewId}/traces`);
  }

  getFindings(reviewId: string): Observable<ReviewFinding[]> {
    return this.http.get<ReviewFinding[]>(`${this.baseUrl}/reviews/${reviewId}/findings`);
  }

  /** Receive list updates without requiring the user to refresh the page. */
  streamReviews(): Observable<ReviewRecord[]> {
    return this.sse<ReviewRecord[]>(`${this.baseUrl}/reviews/events`, 'reviews');
  }

  /** Receive the record, traces, and findings as the agent graph progresses. */
  streamReview(reviewId: string): Observable<ReviewSnapshot> {
    return this.sse<ReviewSnapshot>(`${this.baseUrl}/reviews/${reviewId}/events`, 'review');
  }

  getPolicy(): Observable<ReviewPolicy> {
    return this.http.get<ReviewPolicy>(`${this.baseUrl}/policy`);
  }

  updatePolicy(policy: ReviewPolicy): Observable<ReviewPolicy> {
    return this.http.put<ReviewPolicy>(`${this.baseUrl}/policy`, policy);
  }

  private sse<T>(url: string, eventName: string): Observable<T> {
    return new Observable<T>(subscriber => {
      const source = new EventSource(url);
      source.addEventListener(eventName, event => {
        try {
          const payload = JSON.parse((event as MessageEvent<string>).data) as T;
          // EventSource is a native browser API and is not consistently patched
          // by Zone.js. Re-enter Angular explicitly so signals repaint at once.
          this.zone.run(() => subscriber.next(payload));
        } catch (error) {
          this.zone.run(() => subscriber.error(error));
          source.close();
        }
      });
      // Native EventSource retries transient network failures automatically.
      return () => source.close();
    });
  }
}
