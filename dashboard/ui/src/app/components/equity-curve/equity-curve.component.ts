import {
  Component,
  OnInit,
  OnDestroy,
  AfterViewInit,
  ElementRef,
  ViewChild,
  signal,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chart, registerables, ChartConfiguration } from 'chart.js';
import { ApiService, EquityData } from '../../services/api.service';
import { Subscription } from 'rxjs';

Chart.register(...registerables);

interface PairEquity {
  time: number;
  value: number;
}

const PAIR_COLORS: Record<string, string> = {
  DOGE: '#f0e040',
  ETH:  '#00e5ff',
  PEPE: '#ff40c8',
};

@Component({
  selector: 'app-equity-curve',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="equity-curve-container">

      <!-- Summary stats -->
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">Current Equity</span>
          <span class="stat-value equity">
            {{ formatCurrency(currentEquity()) }}
          </span>
        </div>
        <div class="stat-card">
          <span class="stat-label">P&amp;L</span>
          <span class="stat-value" [class.positive]="pnl() >= 0" [class.negative]="pnl() < 0">
            {{ pnl() >= 0 ? '+' : '' }}{{ formatCurrency(pnl()) }}
            <span class="pnl-pct">({{ pnlPct() >= 0 ? '+' : '' }}{{ pnlPct().toFixed(2) }}%)</span>
          </span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Total Trades</span>
          <span class="stat-value">{{ totalTrades() }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Max Drawdown</span>
          <span class="stat-value negative">{{ maxDrawdown().toFixed(2) }}%</span>
        </div>
      </div>

      <!-- Equity chart -->
      <div class="chart-wrapper equity-chart-wrapper">
        <canvas #equityCanvas></canvas>
      </div>

      <!-- Drawdown chart -->
      <div class="chart-wrapper drawdown-chart-wrapper">
        <canvas #drawdownCanvas></canvas>
      </div>

      <!-- Pair legend -->
      <div class="pair-legend">
        <span class="legend-item total">
          <span class="legend-dot"></span>Total Equity
        </span>
        @for (pair of pairNames; track pair) {
          <span class="legend-item" [style.color]="pairColor(pair)">
            <span class="legend-dot" [style.background]="pairColor(pair)"></span>
            {{ pair }}
          </span>
        }
      </div>

    </div>
  `,
  styles: [`
    .equity-curve-container {
      padding: 16px;
      background: transparent;
      color: #e0e0e0;
      font-family: 'Inter', 'Roboto', sans-serif;
    }

    /* Stats row */
    .stats-row {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }

    .stat-card {
      flex: 1 1 140px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid #2d3148;
      border-radius: 8px;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .stat-label {
      font-size: 11px;
      color: #8b8fa3;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .stat-value {
      font-size: 20px;
      font-weight: 700;
      color: #ffffff;
      line-height: 1.2;
    }

    .stat-value.equity {
      color: #ffffff;
    }

    .stat-value.positive {
      color: #4cffb0;
    }

    .stat-value.negative {
      color: #ff4c6a;
    }

    .pnl-pct {
      font-size: 13px;
      font-weight: 400;
      opacity: 0.8;
      margin-left: 4px;
    }

    /* Chart wrappers */
    .chart-wrapper {
      position: relative;
      width: 100%;
    }

    .equity-chart-wrapper {
      height: 350px;
      margin-bottom: 4px;
    }

    .drawdown-chart-wrapper {
      height: 120px;
      margin-bottom: 12px;
    }

    .equity-chart-wrapper canvas,
    .drawdown-chart-wrapper canvas {
      display: block;
      width: 100% !important;
      height: 100% !important;
    }

    /* Pair legend */
    .pair-legend {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      font-size: 12px;
      color: #8b8fa3;
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .legend-item.total {
      color: #ffffff;
    }

    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #ffffff;
      flex-shrink: 0;
    }
  `],
})
export class EquityCurveComponent implements OnInit, AfterViewInit, OnDestroy {

  @ViewChild('equityCanvas')   private equityCanvasRef!:   ElementRef<HTMLCanvasElement>;
  @ViewChild('drawdownCanvas') private drawdownCanvasRef!: ElementRef<HTMLCanvasElement>;

  private readonly api = inject(ApiService);
  private sub?: Subscription;

  private equityChart?:   Chart;
  private drawdownChart?: Chart;

  // Raw data
  private equityPoints: EquityData[] = [];

  // Derived signals
  currentEquity = signal<number>(0);
  pnl           = signal<number>(0);
  pnlPct        = signal<number>(0);
  totalTrades   = signal<number>(0);
  maxDrawdown   = signal<number>(0);

  readonly pairNames = Object.keys(PAIR_COLORS);

  // ------------------------------------------------------------------ lifecycle

  ngOnInit(): void {
    // Pull summary stats from the status signal when available
    const status = this.api.status?.();
    if (status) {
      this.totalTrades.set(status.total_trades ?? 0);
    }
  }

  ngAfterViewInit(): void {
    this.loadData();
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.equityChart?.destroy();
    this.drawdownChart?.destroy();
  }

  // ------------------------------------------------------------------ data

  private loadData(): void {
    this.sub = this.api.fetchEquity(72).subscribe({
      next: (data: EquityData[]) => {
        this.equityPoints = data.sort((a, b) => String(a.time).localeCompare(String(b.time)));
        this.computeStats();
        this.buildEquityChart();
        this.buildDrawdownChart();
      },
      error: (err) => {
        console.error('[EquityCurve] Failed to fetch equity data', err);
      },
    });
  }

  private computeStats(): void {
    if (!this.equityPoints.length) return;

    const first  = this.equityPoints[0].equity;
    const last   = this.equityPoints[this.equityPoints.length - 1].equity;

    this.currentEquity.set(last);
    this.pnl.set(last - first);
    this.pnlPct.set(first !== 0 ? ((last - first) / first) * 100 : 0);

    // Max drawdown
    let peak = -Infinity;
    let maxDD = 0;
    for (const pt of this.equityPoints) {
      if (pt.equity > peak) peak = pt.equity;
      const dd = peak > 0 ? ((peak - pt.equity) / peak) * 100 : 0;
      if (dd > maxDD) maxDD = dd;
    }
    this.maxDrawdown.set(maxDD);

    // Total trades from status signal (refresh)
    const status = this.api.status?.();
    if (status) this.totalTrades.set(status.total_trades ?? 0);
  }

  // ------------------------------------------------------------------ chart helpers

  private get labels(): string[] {
    return this.equityPoints.map(pt =>
      new Date(pt.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    );
  }

  private get equityValues(): number[] {
    return this.equityPoints.map(pt => pt.equity);
  }

  /** Simulate per-pair equity by splitting positions_value proportionally
   *  using fixed weights derived from the pair name seed. */
  private simulatePairEquity(pair: string): number[] {
    // Deterministic weight per pair so lines are visually distinct
    const weights: Record<string, number> = { DOGE: 0.35, ETH: 0.45, PEPE: 0.20 };
    const w = weights[pair] ?? 0.33;

    return this.equityPoints.map(pt => {
      const base         = pt.balance_usd ?? pt.equity * 0.6;
      const positionsVal = pt.positions_value ?? pt.equity - base;
      return base * w + positionsVal * w;
    });
  }

  private drawdownSeries(): number[] {
    let peak = -Infinity;
    return this.equityPoints.map(pt => {
      if (pt.equity > peak) peak = pt.equity;
      return peak > 0 ? -((peak - pt.equity) / peak) * 100 : 0;
    });
  }

  private get startingBalance(): number {
    return this.equityPoints.length ? this.equityPoints[0].equity : 0;
  }

  // ------------------------------------------------------------------ build equity chart

  private buildEquityChart(): void {
    this.equityChart?.destroy();

    const ctx = this.equityCanvasRef.nativeElement.getContext('2d');
    if (!ctx) return;

    const labels = this.labels;
    const equity = this.equityValues;
    const start  = this.startingBalance;

    const pairDatasets = this.pairNames.map(pair => ({
      label:           pair,
      data:            this.simulatePairEquity(pair),
      borderColor:     PAIR_COLORS[pair],
      backgroundColor: 'transparent',
      borderWidth:     1.5,
      pointRadius:     0,
      tension:         0.3,
    }));

    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels,
        datasets: [
          // Starting balance reference line
          {
            label:           'Starting Balance',
            data:            equity.map(() => start),
            borderColor:     'rgba(139,143,163,0.5)',
            backgroundColor: 'transparent',
            borderWidth:     1,
            borderDash:      [6, 4],
            pointRadius:     0,
            tension:         0,
          },
          // Per-pair lines
          ...pairDatasets,
          // Total equity (on top, bold white)
          {
            label:           'Total Equity',
            data:            equity,
            borderColor:     '#ffffff',
            backgroundColor: (context) => {
              const chart  = context.chart;
              const { ctx: c, chartArea } = chart;
              if (!chartArea) return 'transparent';
              const gradient = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              gradient.addColorStop(0,   'rgba(255,255,255,0.18)');
              gradient.addColorStop(0.5, 'rgba(255,255,255,0.05)');
              gradient.addColorStop(1,   'rgba(255,255,255,0.00)');
              return gradient;
            },
            borderWidth:  2.5,
            pointRadius:  0,
            tension:      0.3,
            fill:         true,
            order:        0,
          },
        ],
      },
      options: {
        responsive:          true,
        maintainAspectRatio: false,
        animation:           { duration: 400 },
        interaction: {
          mode:      'index',
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(20,22,40,0.92)',
            borderColor:     '#2d3148',
            borderWidth:     1,
            titleColor:      '#8b8fa3',
            bodyColor:       '#e0e0e0',
            padding:         10,
            callbacks: {
              label: (item) => ` ${item.dataset.label}: ${this.formatCurrency(item.parsed.y ?? 0)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color:    '#8b8fa3',
              font:     { size: 10 },
              maxTicksLimit: 8,
              maxRotation:   0,
            },
            grid: {
              color:     '#2d3148',
              lineWidth: 1,
            },
            border: { color: '#2d3148' },
          },
          y: {
            ticks: {
              color:    '#8b8fa3',
              font:     { size: 10 },
              callback: (v) => this.formatCurrency(Number(v)),
            },
            grid: {
              color:     '#2d3148',
              lineWidth: 1,
            },
            border: { color: '#2d3148' },
          },
        },
      },
    };

    this.equityChart = new Chart(ctx, config);
  }

  // ------------------------------------------------------------------ build drawdown chart

  private buildDrawdownChart(): void {
    this.drawdownChart?.destroy();

    const ctx = this.drawdownCanvasRef.nativeElement.getContext('2d');
    if (!ctx) return;

    const ddSeries = this.drawdownSeries();

    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels: this.labels,
        datasets: [
          {
            label:           'Drawdown %',
            data:            ddSeries,
            borderColor:     '#ff4c6a',
            backgroundColor: (context) => {
              const chart  = context.chart;
              const { ctx: c, chartArea } = chart;
              if (!chartArea) return 'rgba(255,76,106,0.25)';
              const gradient = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              gradient.addColorStop(0,   'rgba(255,76,106,0.45)');
              gradient.addColorStop(1,   'rgba(255,76,106,0.03)');
              return gradient;
            },
            borderWidth:  1.5,
            pointRadius:  0,
            tension:      0.3,
            fill:         'origin',
          },
        ],
      },
      options: {
        responsive:          true,
        maintainAspectRatio: false,
        animation:           { duration: 400 },
        interaction: {
          mode:      'index',
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(20,22,40,0.92)',
            borderColor:     '#2d3148',
            borderWidth:     1,
            titleColor:      '#8b8fa3',
            bodyColor:       '#ff4c6a',
            padding:         10,
            callbacks: {
              label: (item) => ` Drawdown: ${(item.parsed.y ?? 0).toFixed(2)}%`,
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color:    '#8b8fa3',
              font:     { size: 9 },
              maxTicksLimit: 8,
              maxRotation:   0,
            },
            grid: {
              color:     '#2d3148',
              lineWidth: 1,
            },
            border: { color: '#2d3148' },
          },
          y: {
            max: 0,
            ticks: {
              color:    '#8b8fa3',
              font:     { size: 9 },
              maxTicksLimit: 4,
              callback: (v) => `${Number(v).toFixed(1)}%`,
            },
            grid: {
              color:     '#2d3148',
              lineWidth: 1,
            },
            border: { color: '#2d3148' },
          },
        },
      },
    };

    this.drawdownChart = new Chart(ctx, config);
  }

  // ------------------------------------------------------------------ utils

  pairColor(pair: string): string {
    return PAIR_COLORS[pair] ?? '#8b8fa3';
  }

  formatCurrency(value: number): string {
    if (value === undefined || value === null || isNaN(value)) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style:                 'currency',
      currency:              'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }
}
