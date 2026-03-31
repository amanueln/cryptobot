import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./components/equity-curve/equity-curve.component').then(m => m.EquityCurveComponent) },
  { path: 'pair/:symbol', loadComponent: () => import('./components/price-chart/pair-view.component').then(m => m.PairViewComponent) },
  { path: 'ml-brain', loadComponent: () => import('./components/ml-brain/ml-brain.component').then(m => m.MlBrainComponent) },
  { path: 'pair-scanner', loadComponent: () => import('./components/pair-scanner/pair-scanner.component').then(m => m.PairScannerComponent) },
  { path: 'simulator', loadComponent: () => import('./components/dca-simulator/dca-simulator.component').then(m => m.DcaSimulatorComponent) },
  { path: 'regime', loadComponent: () => import('./components/regime-visualizer/regime-visualizer.component').then(m => m.RegimeVisualizerComponent) },
];
