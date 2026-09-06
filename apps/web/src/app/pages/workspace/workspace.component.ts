import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { ReviewTrace } from '../../core/models';
import { ReviewApiService } from '../../core/review-api.service';
import { ReviewStore } from '../../core/review-store.service';
import { ReviewRowComponent } from '../../review/review-row/review-row.component';
import { StatusPillComponent } from '../../ui/status-pill/status-pill.component';
import { SurfaceCardComponent } from '../../ui/surface-card/surface-card.component';

@Component({standalone:true,imports:[RouterLink,ReviewRowComponent,StatusPillComponent,SurfaceCardComponent],template:`
<header class="hero"><div><span>Autonomous review workspace</span><h1>Code review, in motion.</h1><p>Watch every agent reason, delegate, verify, and publish in real time.</p></div></header>
<section class="metrics"><div><span>Total runs</span><strong>{{store.reviews().length}}</strong></div><div><span>In progress</span><strong>{{store.activeCount()}}</strong></div><div><span>Findings</span><strong>{{store.totalFindings()}}</strong></div><div><span>Completed</span><strong>{{store.completedCount()}}</strong></div></section>
<div class="grid"><ui-surface-card eyebrow="Workspace history" title="Review runs"><a actions routerLink="/reviews">View all →</a>@for(review of store.reviews().slice(0,6);track review.id;let first=$first){<review-row [review]="review" [latest]="first"/>}</ui-surface-card>
<aside><div class="latest-live"><ui-surface-card eyebrow="Live execution" [title]="latestTitle()">@if(latest();as review){<div class="live-head"><span>Pull request #{{review.pull_request_number}}</span><div class="live-badges"><em>Latest</em><ui-status-pill [status]="review.status">{{review.status}}</ui-status-pill></div></div><ol class="timeline">@for(trace of rootTraces();track trace.sequence){<li [class]="trace.status"><i></i><div><strong>{{trace.stage}}</strong><small>{{trace.detail}}</small></div><time>{{trace.created_at.slice(11,16)}}</time>@if(children(trace.stage).length){<ul>@for(child of children(trace.stage);track child.sequence){<li><i [class]="child.status"></i><div><strong>{{child.stage.split('.')[1]}}</strong><small>Subagent · {{child.status}}</small></div></li>}</ul>}</li>}</ol><a class="report" [routerLink]="['/reviews',review.id]">Open execution graph →</a>}@else{<p class="empty">Open a pull request to start the graph.</p>}</ui-surface-card></div></aside></div>
`,styleUrl:'./workspace.component.scss'})
export class WorkspaceComponent{
  readonly store=inject(ReviewStore); private readonly api=inject(ReviewApiService); private readonly destroyRef=inject(DestroyRef);
  readonly latest=computed(()=>this.store.reviews()[0]??null); readonly latestTitle=computed(()=>this.latest()?.repository??'Waiting for a review'); readonly traces=signal<ReviewTrace[]>([]); private live?:Subscription;
  readonly rootTraces=computed(()=>this.traces().filter(t=>!t.stage.includes('.')));
  constructor(){effect(cleanup=>{const review=this.latest();this.live?.unsubscribe();this.traces.set([]);if(!review)return;this.api.getTraces(review.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(t=>this.traces.set(t));this.live=this.api.streamReview(review.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(s=>this.traces.set(s.traces));cleanup(()=>this.live?.unsubscribe())})}
  children(stage:string){return this.traces().filter(t=>t.stage.startsWith(stage+'.'))}
}
