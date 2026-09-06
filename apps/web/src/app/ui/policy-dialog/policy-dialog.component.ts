import { Component, effect, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ReviewPolicy } from '../../core/models';
import { ReviewApiService } from '../../core/review-api.service';

@Component({selector:'ui-policy-dialog',standalone:true,imports:[FormsModule],template:`
@if(open()){
<div class="backdrop" (click)="close.emit()"><section class="dialog" role="dialog" aria-modal="true" aria-labelledby="policy-title" (click)="$event.stopPropagation()">
  <header><div><span>Guardrails</span><h2 id="policy-title">Review policy</h2></div><button type="button" aria-label="Close policy" (click)="close.emit()">×</button></header>
  @if(loading()){<p class="state">Loading policy…</p>}@else if(draft();as policy){<form (ngSubmit)="save()">
    <label>Minimum published severity<select name="severity" [(ngModel)]="policy.minimum_severity"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
    <label>Maximum inline comments<input name="comments" type="number" min="0" [(ngModel)]="policy.limits.maximum_comments"></label>
    <label>Maximum cost per review (USD)<input name="cost" type="number" min="0" step="0.5" [(ngModel)]="policy.limits.maximum_cost_usd"></label>
    <label class="check"><input name="verified" type="checkbox" [(ngModel)]="policy.require_verified_findings"> Publish only deterministically verified findings</label>
    <label class="check"><input name="tests" type="checkbox" [(ngModel)]="policy.allow_reproduction_tests"> Allow sandboxed reproduction tests</label>
    @if(message()){<p class="message">{{message()}}</p>}
    <footer><button type="button" (click)="close.emit()">Cancel</button><button class="primary" type="submit" [disabled]="saving()">{{saving()?'Applying…':'Apply policy'}}</button></footer>
  </form>}
</section></div>}
`,styleUrl:'./policy-dialog.component.scss'})
export class PolicyDialogComponent{
  private readonly api=inject(ReviewApiService); readonly open=input(false); readonly close=output<void>(); readonly draft=signal<ReviewPolicy|null>(null); readonly loading=signal(false); readonly saving=signal(false); readonly message=signal('');
  constructor(){effect(()=>{if(this.open()&&!this.draft()){this.loading.set(true);this.api.getPolicy().subscribe({next:p=>{this.draft.set(structuredClone(p));this.loading.set(false)},error:()=>{this.message.set('Policy could not be loaded.');this.loading.set(false)}})}})}
  save(){const policy=this.draft();if(!policy)return;this.saving.set(true);this.message.set('');this.api.updatePolicy(policy).subscribe({next:p=>{this.draft.set(structuredClone(p));this.saving.set(false);this.message.set('Policy applied.')},error:()=>{this.saving.set(false);this.message.set('Policy could not be saved.')}})}
}
