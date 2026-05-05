import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./components/command-center/command-center.component').then(
        (m) => m.CommandCenterComponent
      ),
  },
  {
    path: 'login',
    loadComponent: () =>
      import('./components/login/login.component').then(
        (m) => m.LoginComponent
      ),
  },
  {
    path: 'setup',
    loadComponent: () =>
      import('./components/setup/setup.component').then(
        (m) => m.SetupComponent
      ),
  },
  {
    path: 'momentum-strategy',
    loadComponent: () =>
      import('./components/momentum-strategy/momentum-strategy.component').then(
        (m) => m.MomentumStrategyComponent
      ),
  },
  { path: 'pair/:symbol', redirectTo: '', pathMatch: 'full' },
  { path: 'ml-brain', redirectTo: '', pathMatch: 'full' },
  { path: 'pair-scanner', redirectTo: '', pathMatch: 'full' },
  { path: 'simulator', redirectTo: '', pathMatch: 'full' },
  { path: 'regime', redirectTo: '', pathMatch: 'full' },
  { path: 'self-check', redirectTo: '', pathMatch: 'full' },
];
