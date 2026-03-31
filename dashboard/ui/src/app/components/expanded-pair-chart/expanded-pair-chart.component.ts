import {
  Component, inject, input, signal, computed, effect, OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ApiService,
  CandleData, TradeData, IndicatorData, PositionData,
} from '../../services/api.service';
import { PriceChartComponent } from '../price-chart/price-chart.component';
import { IndicatorPanelComponent } from '../indicator-panel/indicator-panel.component';

@Component({
  selector: 'app-expanded-pair-chart',
  standalone: true,
  imports: [CommonModule, PriceChartComponent, IndicatorPanelComponent],
  template: `
    <div class="expanded-chart">
      <div class="header">
        <span class="header-pair">{{ pair() }}</span>
        <span class="header-meta">· 4h Candles · 7 Days</span>
        <span class="loading-badge" *ngIf="loading()">Loading…</span>
      </div>

      <app-price-chart
        [candles]="candles()"
        [trades]="trades()"
        [indicators]="indicators()"
        [gridLevels]="gridLevels()"
        [rangeLower]="rangeLower()"
        [rangeUpper]="rangeUpper()"
        [positions]="positions()"
      />

      <app-indicator-panel [indicators]="indicators()" />
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; overflow: hidden; }

    .expanded-chart {
      background: #0f1117;
      border-top: 1px solid #2d3148;
      animation: slideDown 0.3s ease forwards;
    }

    @keyframes slideDown {
      from { max-height: 0; opacity: 0; }
      to   { max-height: 1200px; opacity: 1; }
    }

    .header {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 10px 16px;
      border-bottom: 1px solid #2d3148;
      background: #1a1d2e;
    }

    .header-pair {
      font-size: 14px;
      font-weight: 700;
      color: #e2e8f0;
      font-family: 'Inter', system-ui, sans-serif;
    }

    .header-meta {
      font-size: 12px;
      color: #6b7280;
      font-family: 'Inter', system-ui, sans-serif;
    }

    .loading-badge {
      font-size: 11px;
      color: #60a5fa;
      background: rgba(96,165,250,0.1);
      padding: 2px 8px;
      border-radius: 4px;
      margin-left: auto;
      font-family: 'Inter', system-ui, sans-serif;
    }
  `],
})
export class ExpandedPairChartComponent implements OnDestroy {
  private readonly api = inject(ApiService);

  readonly pair = input.required<string>();

  readonly candles    = signal<CandleData[]>([]);
  readonly trades     = signal<TradeData[]>([]);
  readonly indicators = signal<IndicatorData[]>([]);
  readonly gridLevels = signal<{ price: number; type: string }[]>([]);
  readonly rangeLower = signal<number>(0);
  readonly rangeUpper = signal<number>(0);
  readonly positions  = signal<PositionData[]>([]);
  readonly loading    = signal(true);

  private _pendingRequests = 0;

  constructor() {
    effect(() => {
      const p = this.pair();
      if (p) this.fetchAll(p);
    });
  }

  ngOnDestroy(): void {}

  private fetchAll(pair: string): void {
    this.loading.set(true);
    this._pendingRequests = 5;

    const done = () => {
      this._pendingRequests--;
      if (this._pendingRequests <= 0) this.loading.set(false);
    };

    this.api.fetchCandles(pair, 168).subscribe({
      next: (d) => { this.candles.set(d); done(); },
      error: () => done(),
    });

    this.api.fetchTrades(pair, 100).subscribe({
      next: (d) => { this.trades.set(d); done(); },
      error: () => done(),
    });

    this.api.fetchIndicators(pair, 168).subscribe({
      next: (d) => { this.indicators.set(d); done(); },
      error: () => done(),
    });

    this.api.fetchGridLevels(pair).subscribe({
      next: (d) => {
        this.gridLevels.set(d.levels ?? []);
        this.rangeLower.set(d.lower);
        this.rangeUpper.set(d.upper);
        done();
      },
      error: () => done(),
    });

    this.api.fetchPositions().subscribe({
      next: (all) => {
        this.positions.set(all.filter(p => p.pair === pair));
        done();
      },
      error: () => done(),
    });
  }
}
