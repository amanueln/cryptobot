import { Component, OnInit, OnDestroy, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, forkJoin } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import {
  ApiService,
  VolPredictionData,
  MLModelInfo,
} from '../../services/api.service';

@Component({
  selector: 'app-ml-brain',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="ml-container">
      <!-- Header -->
      <div class="header-row">
        <div class="title-group">
          <h2 class="title">AI Brain</h2>
          <span class="subtitle">GARCH-LightGBM volatility forecaster &middot; adaptive grid spacing</span>
        </div>
        <div class="controls">
          <select class="pair-select" [(ngModel)]="selectedPair" (ngModelChange)="refresh()">
            <option value="">All Pairs</option>
            <option *ngFor="let p of availablePairs()" [value]="p">{{ p }}</option>
          </select>
        </div>
      </div>

      <!-- Model Cards Row -->
      <div class="summary-row">
        <div class="summary-card" *ngFor="let m of volModels()">
          <span class="card-label">{{ m.pair }} Volatility Model
            <span class="health-badge" [class]="'health-' + (m.model_health || 'unknown')">
              {{ m.model_health || 'unknown' }}
            </span>
          </span>
          <div class="model-stats">
            <div class="stat">
              <span class="stat-label">RMSE</span>
              <span class="stat-value">{{ m.validation_rmse | number:'1.4-4' }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">R&sup2;</span>
              <span class="stat-value" [style.color]="r2Color(m.validation_r2)">
                {{ m.validation_r2 | number:'1.3-3' }}
              </span>
            </div>
            <div class="stat">
              <span class="stat-label">v{{ m.version }}</span>
              <span class="stat-value">{{ m.feature_count || 0 }} feat</span>
            </div>
          </div>
          <div class="model-trained">
            Trained: {{ m.trained_at | date:'short' }}
            &middot; {{ m.age_hours | number:'1.1-1' }}h ago
          </div>
        </div>
      </div>

      <!-- Volatility Predictions -->
      <div class="vol-cards" *ngIf="latestVol().length">
        <div class="vol-card" *ngFor="let v of latestVol()">
          <div class="vol-header">
            <span class="vol-pair">{{ v.pair }}</span>
            <span class="regime-badge" [class]="'regime-' + v.vol_regime">
              {{ v.vol_regime | uppercase }}
            </span>
            <span class="vol-time">{{ v.timestamp | date:'MMM d, HH:mm' }}</span>
          </div>

          <div class="vol-metrics">
            <div class="metric">
              <span class="metric-label">Predicted Vol (12h)</span>
              <span class="metric-value highlight">{{ v.predicted_vol_12h | number:'1.1-1' }}%</span>
            </div>
            <div class="metric">
              <span class="metric-label">Current Vol</span>
              <span class="metric-value">{{ v.current_vol_12h | number:'1.1-1' }}%</span>
            </div>
            <div class="metric">
              <span class="metric-label">30d Avg</span>
              <span class="metric-value">{{ v.vol_30d_avg | number:'1.1-1' }}%</span>
            </div>
            <div class="metric">
              <span class="metric-label">GARCH</span>
              <span class="metric-value">{{ v.garch_vol | number:'1.4-4' }}</span>
            </div>
          </div>

          <div class="spacing-row">
            <div class="spacing-info">
              <span class="spacing-label">Grid Spacing</span>
              <div class="spacing-bar-track">
                <div class="spacing-bar-fill"
                     [style.width.%]="spacingPct(v.spacing_multiplier)"
                     [style.background]="spacingColor(v.spacing_multiplier)"></div>
                <div class="spacing-marker" [style.left.%]="50"></div>
              </div>
              <div class="spacing-value">{{ v.spacing_multiplier | number:'1.2-2' }}x</div>
            </div>
            <div class="grids-info">
              <span class="grids-label">Grids</span>
              <span class="grids-value">{{ v.recommended_num_grids }}</span>
            </div>
            <div class="conf-info">
              <span class="conf-label">Confidence</span>
              <span class="conf-value" [style.color]="confColor(v.confidence)">
                {{ v.confidence * 100 | number:'1.0-0' }}%
              </span>
            </div>
          </div>

          <!-- Feature Importance for this pair -->
          <div class="importance-section" *ngIf="pairImportance(v.pair).length">
            <span class="section-title">Top Features</span>
            <div class="importance-bar" *ngFor="let feat of pairImportance(v.pair)">
              <span class="feat-name">{{ feat.name }}</span>
              <div class="feat-bar-track">
                <div class="feat-bar-fill" [style.width.%]="feat.pct"></div>
              </div>
              <span class="feat-value">{{ feat.value * 100 | number:'1.1-1' }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div class="empty-state" *ngIf="!latestVol().length && !loading()">
        <div class="empty-icon">chart</div>
        <div class="empty-text">No volatility predictions yet</div>
        <div class="empty-hint">
          The GARCH-LightGBM model trains on startup and predicts each polling cycle.
          Volatility forecasting is enabled when prediction_mode is set to "volatility" in ml_config.yaml.
        </div>
      </div>

      <!-- Prediction History -->
      <div class="history-section" *ngIf="volHistory().length > 1">
        <span class="section-title">Recent Volatility Predictions</span>
        <table class="pred-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Pair</th>
              <th>Pred Vol</th>
              <th>Cur Vol</th>
              <th>Regime</th>
              <th>Spacing</th>
              <th>Grids</th>
              <th>GARCH</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let p of volHistory().slice(0, 30)">
              <td>{{ p.timestamp | date:'MMM d HH:mm' }}</td>
              <td>{{ p.pair }}</td>
              <td class="highlight">{{ p.predicted_vol_12h | number:'1.1-1' }}%</td>
              <td>{{ p.current_vol_12h | number:'1.1-1' }}%</td>
              <td>
                <span class="regime-badge small" [class]="'regime-' + p.vol_regime">
                  {{ p.vol_regime }}
                </span>
              </td>
              <td [style.color]="spacingColor(p.spacing_multiplier)">
                {{ p.spacing_multiplier | number:'1.2-2' }}x
              </td>
              <td>{{ p.recommended_num_grids }}</td>
              <td>{{ p.garch_vol | number:'1.4-4' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; font-family: 'Inter', 'Segoe UI', sans-serif; color: #e2e8f0; }

    .ml-container { max-width: 1100px; margin: 0 auto; padding: 20px 0; }

    .header-row {
      display: flex; align-items: flex-end; justify-content: space-between;
      flex-wrap: wrap; gap: 12px; margin-bottom: 20px;
    }
    .title-group { display: flex; flex-direction: column; gap: 2px; }
    .title {
      margin: 0; font-size: 1.6rem; font-weight: 700;
      background: linear-gradient(90deg, #7c83ff, #a78bfa);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .subtitle { font-size: 0.8rem; color: #6b7280; }
    .controls { display: flex; align-items: center; gap: 12px; }
    .pair-select {
      background: #242736; border: 1px solid #2d3148; color: #e2e8f0;
      padding: 7px 12px; border-radius: 8px; font-size: 0.88rem; cursor: pointer; outline: none;
    }
    .pair-select:focus { border-color: #7c83ff; }

    /* Summary Row */
    .summary-row { display: flex; gap: 14px; margin-bottom: 18px; flex-wrap: wrap; }
    .summary-card {
      background: #242736; border: 1px solid #2d3148; border-radius: 12px;
      padding: 16px; flex: 1; min-width: 220px;
    }
    .card-label {
      font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; color: #6b7280; display: block; margin-bottom: 8px;
    }
    .model-stats { display: flex; gap: 16px; margin-bottom: 8px; }
    .stat { display: flex; flex-direction: column; gap: 2px; }
    .stat-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; }
    .stat-value { font-size: 1.1rem; font-weight: 700; color: #f1f5f9; }
    .model-trained { font-size: 0.72rem; color: #4b5563; }

    .health-badge {
      font-size: 0.65rem; padding: 2px 6px; border-radius: 4px;
      margin-left: 6px; text-transform: uppercase; font-weight: 700;
    }
    .health-healthy { background: #14532d; color: #4ade80; }
    .health-expired { background: #451a03; color: #fbbf24; }
    .health-unknown { background: #1e293b; color: #94a3b8; }

    /* Volatility Cards */
    .vol-cards { display: flex; flex-direction: column; gap: 14px; margin-bottom: 18px; }
    .vol-card {
      background: #242736; border: 1px solid #2d3148; border-radius: 14px; padding: 22px;
    }
    .vol-header {
      display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
    }
    .vol-pair { font-weight: 700; color: #a78bfa; font-size: 1.1rem; }
    .vol-time { font-size: 0.78rem; color: #4b5563; margin-left: auto; }

    .regime-badge {
      font-size: 0.72rem; padding: 3px 10px; border-radius: 6px;
      font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .regime-badge.small { font-size: 0.65rem; padding: 2px 6px; }
    .regime-low { background: #1a3a2a; color: #4ade80; }
    .regime-normal { background: #1e293b; color: #94a3b8; }
    .regime-high { background: #451a03; color: #fbbf24; }
    .regime-extreme { background: #450a0a; color: #f87171; }
    .regime-unknown { background: #1e293b; color: #6b7280; }

    .vol-metrics {
      display: flex; gap: 24px; margin-bottom: 18px; flex-wrap: wrap;
    }
    .metric { display: flex; flex-direction: column; gap: 2px; }
    .metric-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; }
    .metric-value { font-size: 1.3rem; font-weight: 700; color: #f1f5f9; }
    .metric-value.highlight { color: #a78bfa; }

    .spacing-row {
      display: flex; align-items: center; gap: 24px; flex-wrap: wrap;
      padding: 14px 0; border-top: 1px solid #2d3148; border-bottom: 1px solid #2d3148;
      margin-bottom: 16px;
    }
    .spacing-info { flex: 1; min-width: 200px; }
    .spacing-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; display: block; margin-bottom: 4px; }
    .spacing-bar-track {
      height: 10px; background: #1a1d29; border-radius: 5px; overflow: hidden;
      position: relative;
    }
    .spacing-bar-fill { height: 100%; border-radius: 5px; transition: width 0.5s; }
    .spacing-marker {
      position: absolute; top: -2px; width: 2px; height: 14px; background: #6b7280;
      transform: translateX(-50%);
    }
    .spacing-value { font-size: 1.2rem; font-weight: 800; margin-top: 4px; }

    .grids-info, .conf-info { text-align: center; }
    .grids-label, .conf-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; display: block; }
    .grids-value { font-size: 1.6rem; font-weight: 800; color: #f1f5f9; }
    .conf-value { font-size: 1.6rem; font-weight: 800; }

    /* Feature Importance */
    .importance-section { padding-top: 12px; }
    .section-title {
      font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; color: #6b7280; display: block; margin-bottom: 10px;
    }
    .importance-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
    .feat-name { font-size: 0.72rem; color: #9ca3af; width: 120px; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .feat-bar-track { flex: 1; height: 7px; background: #1a1d29; border-radius: 3px; overflow: hidden; }
    .feat-bar-fill { height: 100%; background: linear-gradient(90deg, #4f46e5, #7c83ff); border-radius: 3px; }
    .feat-value { font-size: 0.68rem; color: #6b7280; width: 44px; }

    /* Empty State */
    .empty-state {
      text-align: center; padding: 60px 20px;
      background: #242736; border: 1px solid #2d3148; border-radius: 14px;
    }
    .empty-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3; }
    .empty-text { font-size: 1.1rem; font-weight: 600; color: #6b7280; margin-bottom: 6px; }
    .empty-hint { font-size: 0.82rem; color: #4b5563; max-width: 450px; margin: 0 auto; }

    /* History Table */
    .history-section {
      background: #242736; border: 1px solid #2d3148; border-radius: 14px; padding: 18px;
    }
    .pred-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 10px; }
    .pred-table th {
      text-align: left; padding: 8px 10px; color: #6b7280; font-weight: 600;
      text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.05em;
      border-bottom: 1px solid #2d3148;
    }
    .pred-table td {
      padding: 8px 10px; border-bottom: 1px solid #1a1d29; color: #9ca3af;
    }
    .pred-table td.highlight { color: #a78bfa; font-weight: 600; }
  `],
})
export class MlBrainComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private sub: Subscription | null = null;

  selectedPair = '';
  availablePairs = signal<string[]>([]);
  volHistory = signal<VolPredictionData[]>([]);
  latestVol = signal<VolPredictionData[]>([]);
  volModels = signal<MLModelInfo[]>([]);
  loading = signal(false);

  ngOnInit() {
    this.api.fetchPairs().subscribe(pairs => this.availablePairs.set(pairs));
    this.startPolling();
  }

  ngOnDestroy() { this.sub?.unsubscribe(); }

  refresh() {
    this.sub?.unsubscribe();
    this.startPolling();
  }

  r2Color(r2: number): string {
    if (r2 >= 0.3) return '#4ade80';
    if (r2 >= 0.1) return '#fbbf24';
    return '#f87171';
  }

  confColor(conf: number): string {
    if (conf >= 0.4) return '#4ade80';
    if (conf >= 0.2) return '#fbbf24';
    return '#94a3b8';
  }

  spacingColor(mult: number): string {
    if (mult >= 1.5) return '#f87171';   // wide = high vol = red
    if (mult >= 1.1) return '#fbbf24';   // slightly wider
    if (mult <= 0.7) return '#4ade80';   // tight = low vol = green
    return '#94a3b8';                    // normal
  }

  spacingPct(mult: number): number {
    // Map 0.5-2.0 → 0-100%
    return Math.min(100, Math.max(0, ((mult - 0.5) / 1.5) * 100));
  }

  pairImportance(pair: string): { name: string; value: number; pct: number }[] {
    const vol = this.latestVol().find(v => v.pair === pair);
    if (!vol?.feature_importance) return [];
    const entries = Object.entries(vol.feature_importance)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
    const maxVal = entries[0]?.[1] ?? 1;
    return entries.map(([name, value]) => ({
      name,
      value,
      pct: maxVal > 0 ? (value / maxVal) * 100 : 0,
    }));
  }

  private startPolling() {
    this.sub = interval(60_000).pipe(
      startWith(0),
      switchMap(() => {
        this.loading.set(true);
        const pair = this.selectedPair || undefined;
        return forkJoin({
          volLatest: this.api.fetchVolLatest(),
          volHistory: this.api.fetchVolPredictions(pair, 50),
          models: this.api.fetchMLModelInfo(),
        });
      }),
    ).subscribe({
      next: (data) => {
        // Filter vol models (GARCH-LightGBM type)
        const vm = data.models.filter(m =>
          (m as any).model_type === 'GARCH-LightGBM' ||
          (m as any).vol_mean !== undefined
        );
        this.volModels.set(vm.length ? vm : data.models);
        this.latestVol.set(data.volLatest);
        this.volHistory.set(data.volHistory);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
