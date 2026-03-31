import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./components/command-center/command-center.component').then(
        (m) => m.CommandCenterComponent
      ),
  },
  { path: 'pair/:symbol', redirectTo: '', pathMatch: 'full' },
  { path: 'ml-brain', redirectTo: '', pathMatch: 'full' },
  { path: 'pair-scanner', redirectTo: '', pathMatch: 'full' },
  { path: 'simulator', redirectTo: '', pathMatch: 'full' },
  { path: 'regime', redirectTo: '', pathMatch: 'full' },
  { path: 'self-check', redirectTo: '', pathMatch: 'full' },
];
