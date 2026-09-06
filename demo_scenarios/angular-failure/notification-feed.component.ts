import { Component, OnInit } from '@angular/core';
import { interval } from 'rxjs';

@Component({
  selector: 'demo-notification-feed',
  standalone: true,
  template: `<p>{{ refreshCount }} refreshes</p>`,
})
export class NotificationFeedComponent implements OnInit {
  refreshCount = 0;

  ngOnInit(): void {
    interval(500).subscribe(() => {
      this.refreshCount += 1;
    });
  }
}
