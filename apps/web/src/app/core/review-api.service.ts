import { HttpClient } from '@angular/common/http';
import { Injectable, NgZone, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ReviewFinding, ReviewPolicy, ReviewRecord, ReviewSnapshot, ReviewTrace } from './models';
@Injectable({providedIn:'root'})
export class ReviewApiService{
  private readonly http=inject(HttpClient); private readonly zone=inject(NgZone); private readonly base='/api/v1';
  listReviews=()=>this.http.get<ReviewRecord[]>(`${this.base}/reviews`); getReview=(id:string)=>this.http.get<ReviewRecord>(`${this.base}/reviews/${id}`); getTraces=(id:string)=>this.http.get<ReviewTrace[]>(`${this.base}/reviews/${id}/traces`); getFindings=(id:string)=>this.http.get<ReviewFinding[]>(`${this.base}/reviews/${id}/findings`); getPolicy=()=>this.http.get<ReviewPolicy>(`${this.base}/policy`); updatePolicy=(policy:ReviewPolicy)=>this.http.put<ReviewPolicy>(`${this.base}/policy`,policy);
  streamReviews():Observable<ReviewRecord[]>{return this.sse(`${this.base}/reviews/events`,'reviews')} streamReview(id:string):Observable<ReviewSnapshot>{return this.sse(`${this.base}/reviews/${id}/events`,'review')}
  private sse<T>(url:string,eventName:string):Observable<T>{return new Observable(subscriber=>{const source=new EventSource(url);source.addEventListener(eventName,event=>this.zone.run(()=>{try{subscriber.next(JSON.parse((event as MessageEvent<string>).data) as T)}catch(error){subscriber.error(error);source.close()}}));return()=>source.close()})}
}
