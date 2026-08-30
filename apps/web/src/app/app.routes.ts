import { Routes } from '@angular/router';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { ReviewDetailComponent } from './features/reviews/review-detail.component';
import { ReviewListComponent } from './features/reviews/review-list.component';
import { SettingsComponent } from './features/settings/settings.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent, title: 'Dashboard · Aegis Review' },
  { path: 'reviews', component: ReviewListComponent, title: 'Reviews · Aegis Review' },
  { path: 'reviews/:id', component: ReviewDetailComponent, title: 'Review · Aegis Review' },
  { path: 'settings', component: SettingsComponent, title: 'Settings · Aegis Review' },
  { path: '**', redirectTo: '' }
];
