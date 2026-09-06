import { Component, OnInit } from '@angular/core';
import { interval } from 'rxjs';

@Component({
  standalone: true,
  selector: 'demo-activity-panel',
  template: `<section [innerHTML]="message"></section><p>{{ ticks }}</p>`,
})
export class ActivityPanelComponent implements OnInit {
  message = location.hash.slice(1);
  ticks = 0;

  ngOnInit(): void {
    interval(1000).subscribe(() => this.ticks++);
  }
}

