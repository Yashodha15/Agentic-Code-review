import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ReviewFinding, ReviewPolicy, ReviewRecord, ReviewTraceEvent } from './api.models';

@Injectable({ providedIn: 'root' })
export class ReviewApiService {
  private readonly baseUrl = '/api/v1';

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

  getPolicy(): Observable<ReviewPolicy> {
    return this.http.get<ReviewPolicy>(`${this.baseUrl}/policy`);
  }

  updatePolicy(policy: ReviewPolicy): Observable<ReviewPolicy> {
    return this.http.put<ReviewPolicy>(`${this.baseUrl}/policy`, policy);
  }
}
