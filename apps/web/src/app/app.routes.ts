import { Routes } from '@angular/router';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { ReviewDetailComponent } from './features/reviews/review-detail.component';
import { ReviewListComponent } from './features/reviews/review-list.component';
import { SettingsComponent } from './features/settings/settings.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent, title: 'Dashboard · Code Review' },
  { path: 'reviews', component: ReviewListComponent, title: 'Reviews · Code Review' },
  { path: 'reviews/:id', component: ReviewDetailComponent, title: 'Review · Code Review' },
  { path: 'settings', component: SettingsComponent, title: 'Settings · Code Review' },
  { path: '**', redirectTo: '' }
];
