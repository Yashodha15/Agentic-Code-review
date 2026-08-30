import { Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ReviewPolicy } from '../../core/api.models';
import { ReviewApiService } from '../../core/review-api.service';

@Component({
  selector: 'app-settings',
  imports: [ReactiveFormsModule],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss'
})
export class SettingsComponent {
  private readonly api = inject(ReviewApiService);
  readonly saved = signal(false);
  readonly error = signal('');
  readonly policy = new FormGroup({
    minimumSeverity: new FormControl('medium', { nonNullable: true }),
    maximumComments: new FormControl(12, { nonNullable: true }),
    maximumCost: new FormControl(3, { nonNullable: true }),
    verifiedOnly: new FormControl(true, { nonNullable: true }),
    reproductionTests: new FormControl(true, { nonNullable: true })
  });

  constructor() {
    this.api.getPolicy().subscribe({
      next: policy => this.policy.patchValue({
        minimumSeverity: policy.minimum_severity,
        maximumComments: policy.limits.maximum_comments,
        maximumCost: policy.limits.maximum_cost_usd,
        verifiedOnly: policy.require_verified_findings,
        reproductionTests: policy.allow_reproduction_tests
      }),
      error: () => this.error.set('Unable to load the current policy.')
    });
  }

  save(): void {
    const values = this.policy.getRawValue();
    const request: ReviewPolicy = {
      minimum_severity: values.minimumSeverity as ReviewPolicy['minimum_severity'],
      require_verified_findings: values.verifiedOnly,
      block_on_critical_findings: true,
      allow_reproduction_tests: values.reproductionTests,
      ignored_paths: ['**/node_modules/**', '**/dist/**', '**/build/**'],
      limits: {
        maximum_specialist_agents: 6,
        maximum_subagents: 12,
        maximum_delegation_depth: 2,
        maximum_runtime_seconds: 900,
        maximum_comments: values.maximumComments,
        maximum_cost_usd: values.maximumCost
      }
    };
    this.saved.set(false);
    this.error.set('');
    this.api.updatePolicy(request).subscribe({
      next: () => this.saved.set(true),
      error: () => this.error.set('Policy could not be saved.')
    });
  }
}
