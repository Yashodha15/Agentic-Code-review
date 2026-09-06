import { Component, input } from '@angular/core';

@Component({
  selector: 'ui-empty-state',
  standalone: true,
  template: `
    <div class="empty-state" role="status">
      <div class="signal" aria-hidden="true">
        <i></i><i></i><span></span>
      </div>
      <span>{{ eyebrow() }}</span>
      <h3>{{ title() }}</h3>
      <p>{{ message() }}</p>
    </div>
  `,
  styleUrl: './empty-state.component.scss',
})
export class EmptyStateComponent {
  readonly eyebrow = input('Ready when you are');
  readonly title = input.required<string>();
  readonly message = input.required<string>();
}
