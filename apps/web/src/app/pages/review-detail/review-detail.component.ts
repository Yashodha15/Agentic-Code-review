import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { ReviewFinding, ReviewRecord, ReviewTrace } from '../../core/models';
import { ReviewApiService } from '../../core/review-api.service';
import { AgentCardComponent } from '../../review/agent-card/agent-card.component';
import { StatusPillComponent } from '../../ui/status-pill/status-pill.component';
import { SurfaceCardComponent } from '../../ui/surface-card/surface-card.component';

type InsightTab = 'findings' | 'timeline';

@Component({standalone:true,imports:[DatePipe,RouterLink,AgentCardComponent,StatusPillComponent,SurfaceCardComponent],templateUrl:'./review-detail.component.html',styleUrl:'./review-detail.component.scss'})
export class ReviewDetailComponent {
  private readonly api=inject(ReviewApiService); private readonly destroyRef=inject(DestroyRef);
  readonly review=signal<ReviewRecord|null>(null); readonly traces=signal<ReviewTrace[]>([]); readonly findings=signal<ReviewFinding[]>([]);
  readonly loading=signal(true); readonly error=signal(''); readonly activeTab=signal<InsightTab>('findings');
  readonly leads=computed(()=>this.traces().filter(t=>['architecture','correctness','frontend','security','testing'].includes(t.stage)));
  readonly pipeline=computed(()=>this.traces().filter(t=>['webhook','queue','worker','planning','publish'].includes(t.stage)));
  readonly subagentCount=computed(()=>this.traces().filter(t=>t.stage.includes('.')).length);
  constructor(){
    const id=inject(ActivatedRoute).snapshot.paramMap.get('id')!;
    forkJoin({review:this.api.getReview(id),traces:this.api.getTraces(id),findings:this.api.getFindings(id)}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({next:data=>{this.review.set(data.review);this.traces.set(data.traces);this.findings.set(data.findings);this.loading.set(false)},error:()=>{this.error.set('The review could not be loaded.');this.loading.set(false)}});
    this.api.streamReview(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(s=>{this.review.set(s.review);this.traces.set(s.traces);this.findings.set(s.findings)});
  }
  children(stage:string):ReviewTrace[]{return this.traces().filter(t=>t.stage.startsWith(stage+'.'))}
  setTab(tab:InsightTab):void{this.activeTab.set(tab)}
}
