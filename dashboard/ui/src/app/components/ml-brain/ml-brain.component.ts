import { Component, OnInit, OnDestroy, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, forkJoin } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import {
  ApiService,
  MLPredictionData,
  MLAccuracyData,
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
          <span class="subtitle">LightGBM prediction engine &middot; per-pair models</span>
        </div>
        <div class="controls">
          <select class="pair-select" [(ngModel)]="selectedPair" (ngModelChange)="refresh()">
            <option value="">All Pairs</option>
            <option *ngFor="let p of availablePairs()" [value]="p">{{ p }}</option>
          </select>
        </div>
      </div>

      <!-- Accuracy + Model Cards Row -->
      <div class="summary-row">
        <!-- Accuracy Card -->
        <div class="summary-card">
          <span class="card-label">Prediction Accuracy</span>
          <div class="accuracy-value" [style.color]="accuracyColor()">
            {{ accuracy()?.accuracy ?? 0 | number:'1.1-1' }}%
          </div>
          <div class="accuracy-detail">
            {{ accuracy()?.correct ?? 0 }}/{{ accuracy()?.evaluated ?? 0 }} correct
            &middot; {{ accuracy()?.total ?? 0 }} total predictions
          </div>
          <div class="accuracy-bar-track">
            <div class="accuracy-bar-fill"
                 [style.width.%]="accuracy()?.accuracy ?? 0"
                 [style.background]="accuracyColor()"></div>
          </div>
        </div>

        <!-- Model Info Cards -->
        <div class="summary-card" *ngFor="let m of models()">
          <span class="card-label">{{ m.pair }} Model
            <span class="health-badge" [class]="'health-' + (m.model_health || 'unknown')">
              {{ m.model_health || 'unknown' }}
            </span>
          </span>
          <div class="model-stats">
            <div class="stat">
              <span class="stat-label">RMSE</span>
              <span class="stat-value">{{ m.validation_rmse | number:'1.3-3' }}</span>
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
            &middot; retrain in {{ m.next_retrain_hours | number:'1.0-0' }}h
          </div>
        </div>
      </div>

      <!-- Latest Prediction Detail -->
      <div class="prediction-detail" *ngIf="latestPrediction() as pred">
        <div class="detail-header">
          <span class="detail-title">Latest Prediction</span>
          <span class="detail-pair">{{ pred.pair }}</span>
          <span class="detail-time">{{ pred.timestamp | date:'MMM d, HH:mm' }}</span>
        </div>

        <div class="direction-row">
          <div class="direction-badge" [class]="'dir-' + pred.direction">
            {{ pred.direction === 'up' ? '^' : pred.direction === 'down' ? 'v' : '-' }}
            {{ pred.direction | uppercase }}
          </div>
          <div class="confidence-gauge">
            <div class="gauge-label">Confidence</div>
            <div class="gauge-value">{{ pred.confidence * 100 | number:'1.1-1' }}%</div>
            <div class="gauge-track">
              <div class="gauge-fill" [style.width.%]="pred.confidence * 100"
                   [style.background]="confidenceColor(pred.confidence)"></div>
            </div>
          </div>
          <div class="action-badge" [class]="actionClass(pred.recommended_action)">
            {{ pred.recommended_action }}
            <span class="size-pct">{{ pred.recommended_size_pct * 100 | number:'1.0-0' }}%</span>
          </div>
        </div>

        <!-- Feature Contributions -->
        <div class="factors-row">
          <div class="factors-col" *ngIf="pred.top_bullish.length">
            <span class="factors-label bullish-label">Bullish Factors</span>
            <div class="factor-item" *ngFor="let f of pred.top_bullish">
              <span class="factor-arrow bullish">^</span> {{ f }}
            </div>
          </div>
          <div class="factors-col" *ngIf="pred.top_bearish.length">
            <span class="factors-label bearish-label">Bearish Factors</span>
            <div class="factor-item" *ngFor="let f of pred.top_bearish">
              <span class="factor-arrow bearish">v</span> {{ f }}
            </div>
          </div>
        </div>

        <!-- Feature Importance Bar Chart -->
        <div class="importance-section" *ngIf="featureImportance().length">
          <span class="section-title">Feature Importance (Top Model)</span>
          <div class="importance-bar" *ngFor="let feat of featureImportance()">
            <span class="feat-name">{{ feat.name }}</span>
            <div class="feat-bar-track">
              <div class="feat-bar-fill" [style.width.%]="feat.pct"></div>
            </div>
            <span class="feat-value">{{ feat.value | number:'1.0-0' }}</span>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div class="empty-state" *ngIf="!latestPrediction() && !loading()">
        <div class="empty-icon">brain</div>
        <div class="empty-text">No ML predictions yet</div>
        <div class="empty-hint">Run the simulator with --ml flag to generate predictions</div>
      </div>

      <!-- Prediction History -->
      <div class="history-section" *ngIf="predictions().length > 1">
        <span class="section-title">Recent Predictions</span>
        <table class="pred-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Pair</th>
              <th>Dir</th>
              <th>Conf</th>
              <th>Action</th>
              <th>Outcome</th>
              <th>Price Chg</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let p of predictions().slice(0, 20)">
              <td>{{ p.timestamp | date:'MMM d HH:mm' }}</td>
              <td>{{ p.pair }}</td>
              <td [style.color]="dirColor(p.direction)">{{ p.direction }}</td>
              <td>{{ p.confidence * 100 | number:'1.1-1' }}%</td>
              <td>{{ p.recommended_action }}</td>
              <td [style.color]="outcomeColor(p)">
                {{ p.actual_outcome ?? 'pending' }}
              </td>
              <td>
                {{ p.actual_price_change !== null
                   ? (p.actual_price_change * 100 | number:'1.2-2') + '%'
                   : '-' }}
              </td>
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
    .accuracy-value { font-size: 2rem; font-weight: 800; line-height: 1.1; margin-bottom: 4px; }
    .accuracy-detail { font-size: 0.78rem; color: #6b7280; margin-bottom: 10px; }
    .accuracy-bar-track { height: 6px; background: #1a1d29; border-radius: 3px; overflow: hidden; }
    .accuracy-bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s; }

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
    .health-degraded { background: #450a0a; color: #f87171; }
    .health-unknown { background: #1e293b; color: #94a3b8; }

    /* Prediction Detail */
    .prediction-detail {
      background: #242736; border: 1px solid #2d3148; border-radius: 14px;
      padding: 22px; margin-bottom: 18px;
    }
    .detail-header {
      display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
    }
    .detail-title { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.07em; color: #6b7280; }
    .detail-pair { font-weight: 700; color: #a78bfa; }
    .detail-time { font-size: 0.78rem; color: #4b5563; margin-left: auto; }

    .direction-row {
      display: flex; align-items: center; gap: 20px; margin-bottom: 18px; flex-wrap: wrap;
    }
    .direction-badge {
      font-size: 1.2rem; font-weight: 800; padding: 8px 20px; border-radius: 10px;
      text-transform: uppercase; letter-spacing: 0.05em;
    }
    .dir-up { background: #14532d; color: #4ade80; border: 1px solid #166534; }
    .dir-down { background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
    .dir-neutral { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }

    .confidence-gauge { flex: 1; min-width: 200px; }
    .gauge-label { font-size: 0.72rem; color: #6b7280; text-transform: uppercase; }
    .gauge-value { font-size: 1.6rem; font-weight: 800; }
    .gauge-track { height: 8px; background: #1a1d29; border-radius: 4px; overflow: hidden; margin-top: 4px; }
    .gauge-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }

    .action-badge {
      padding: 8px 16px; border-radius: 10px; font-weight: 700; font-size: 0.88rem;
    }
    .action-buy-full { background: #14532d; color: #4ade80; }
    .action-buy-half { background: #1a3a2a; color: #86efac; }
    .action-skip { background: #1e293b; color: #94a3b8; }
    .action-sell { background: #450a0a; color: #f87171; }
    .size-pct { margin-left: 6px; font-size: 0.78rem; opacity: 0.7; }

    /* Factors */
    .factors-row { display: flex; gap: 20px; margin-bottom: 18px; flex-wrap: wrap; }
    .factors-col { flex: 1; min-width: 250px; }
    .factors-label {
      font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; display: block; margin-bottom: 8px;
    }
    .bullish-label { color: #4ade80; }
    .bearish-label { color: #f87171; }
    .factor-item { font-size: 0.82rem; color: #9ca3af; padding: 4px 0; }
    .factor-arrow { font-weight: 700; margin-right: 6px; }
    .factor-arrow.bullish { color: #4ade80; }
    .factor-arrow.bearish { color: #f87171; }

    /* Feature Importance */
    .importance-section {
      padding-top: 16px; border-top: 1px solid #2d3148;
    }
    .section-title {
      font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; color: #6b7280; display: block; margin-bottom: 12px;
    }
    .importance-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
    .feat-name { font-size: 0.75rem; color: #9ca3af; width: 110px; text-align: right; }
    .feat-bar-track { flex: 1; height: 8px; background: #1a1d29; border-radius: 4px; overflow: hidden; }
    .feat-bar-fill { height: 100%; background: linear-gradient(90deg, #4f46e5, #7c83ff); border-radius: 4px; }
    .feat-value { font-size: 0.72rem; color: #6b7280; width: 40px; }

    /* Empty State */
    .empty-state {
      text-align: center; padding: 60px 20px;
      background: #242736; border: 1px solid #2d3148; border-radius: 14px;
    }
    .empty-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3; }
    .empty-text { font-size: 1.1rem; font-weight: 600; color: #6b7280; margin-bottom: 6px; }
    .empty-hint { font-size: 0.82rem; color: #4b5563; }

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
  `],
})
export class MlBrainComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private sub: Subscription | null = null;

  selectedPair = '';
  availablePairs = signal<string[]>([]);
  predictions = signal<MLPredictionData[]>([]);
  accuracy = signal<MLAccuracyData | null>(null);
  models = signal<MLModelInfo[]>([]);
  loading = signal(false);

  latestPrediction = computed(() => {
    const preds = this.predictions();
    return preds.length > 0 ? preds[0] : null;
  });

  featureImportance = computed(() => {
    const ms = this.models();
    if (!ms.length) return [];
    // Use first model's importance (or selected pair's model)
    const target = this.selectedPair
      ? ms.find(m => m.pair === this.selectedPair) ?? ms[0]
      : ms[0];
    const imp = target.feature_importance;
    if (!imp) return [];
    const entries = Object.entries(imp).sort((a, b) => b[1] - a[1]);
    const maxVal = entries[0]?.[1] ?? 1;
    return entries.map(([name, value]) => ({
      name,
      value,
      pct: maxVal > 0 ? (value / maxVal) * 100 : 0,
    }));
  });

  accuracyColor = computed(() => {
    const acc = this.accuracy()?.accuracy ?? 0;
    if (acc >= 60) return '#4ade80';
    if (acc >= 50) return '#fbbf24';
    return '#f87171';
  });

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

  confidenceColor(conf: number): string {
    if (conf >= 0.70) return '#4ade80';
    if (conf >= 0.55) return '#fbbf24';
    return '#94a3b8';
  }

  dirColor(dir: string): string {
    if (dir === 'up') return '#4ade80';
    if (dir === 'down') return '#f87171';
    return '#94a3b8';
  }

  actionClass(action: string): string {
    if (action.includes('sell')) return 'action-badge action-sell';
    if (action.includes('full')) return 'action-badge action-buy-full';
    if (action.includes('half')) return 'action-badge action-buy-half';
    return 'action-badge action-skip';
  }

  outcomeColor(p: MLPredictionData): string {
    if (!p.actual_outcome) return '#6b7280';
    if (p.actual_outcome === p.direction) return '#4ade80';
    return '#f87171';
  }

  private startPolling() {
    this.sub = interval(60_000).pipe(
      startWith(0),
      switchMap(() => {
        this.loading.set(true);
        const pair = this.selectedPair || undefined;
        return forkJoin({
          predictions: this.api.fetchMLPredictions(pair, 50),
          accuracy: this.api.fetchMLAccuracy(pair),
          models: this.api.fetchMLModelInfo(),
        });
      }),
    ).subscribe({
      next: (data) => {
        this.predictions.set(data.predictions);
        this.accuracy.set(data.accuracy);
        this.models.set(data.models);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
