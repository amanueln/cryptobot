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
import { ApiService, EquityData, TradeData, PositionData } from '../../services/api.service';
import { TradeLogComponent } from '../trade-log/trade-log.component';
import { PositionCardsComponent } from '../position-cards/position-cards.component';
import { Subscription, forkJoin } from 'rxjs';

Chart.register(...registerables);

const STARTING_BALANCE = 3000;

const PAIR_COLORS: string[] = [
  '#22c55e', '#00e5ff', '#ff8c00', '#a78bfa', '#f59e0b',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

@Component({
  selector: 'app-equity-curve',
  standalone: true,
  imports: [CommonModule, TradeLogComponent, PositionCardsComponent],
  template: `
    <div class="equity-curve-container">

      <!-- Summary stats -->
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">Current Equity</span>
          <span class="stat-value equity">{{ formatCurrency(currentEquity()) }}</span>
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
      <div class="chart-wrapper">
        <canvas #equityCanvas></canvas>
      </div>

      <!-- Chart legend -->
      <div class="pair-legend">
        <span class="legend-item total">
          <span class="legend-dot"></span>Net Equity
        </span>
        <span class="legend-item cash">
          <span class="legend-dot cash-dot"></span>Cash Balance
        </span>
        @for (pair of pairNames; track pair) {
          <span class="legend-item" [style.color]="pairColor(pair)">
            <span class="legend-dot" [style.background]="pairColor(pair)"></span>
            {{ pair }}
          </span>
        }
        <span class="legend-item dd">
          <span class="legend-dot dd-dot"></span>
          Drawdown
        </span>
      </div>

      <!-- Trade summary bar -->
      <div class="trade-summary">
        <div class="summary-item">
          <span class="summary-label">Realized P&amp;L</span>
          <span class="summary-value"
                [class.positive]="totalRealizedPnl() >= 0"
                [class.negative]="totalRealizedPnl() < 0">
            {{ totalRealizedPnl() >= 0 ? '+' : '' }}{{ formatCurrency(totalRealizedPnl()) }}
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Total Fees</span>
          <span class="summary-value fees">{{ formatCurrency(totalFees()) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Trade Count</span>
          <span class="summary-value">{{ allTrades().length }}</span>
        </div>
      </div>

      <!-- Position summary cards -->
      <app-position-cards [positions]="positions()" />

      <!-- Trade log table -->
      <app-trade-log [trades]="allTrades()" />

      <!-- Positions panel -->
      @if (positions().length > 0) {
        <div class="positions-panel">
          <div class="positions-header">
            <h3>Open Positions</h3>
          </div>
          <table class="positions-table">
            <thead>
              <tr>
                <th class="text-left">Pair</th>
                <th class="text-right">Quantity</th>
                <th class="text-right">Entry Price</th>
                <th class="text-right">Breakeven</th>
                <th class="text-right">Current Price</th>
                <th class="text-right">Market Value</th>
                <th class="text-right">Unrealized P&amp;L</th>
                <th class="text-right">Hold Duration</th>
              </tr>
            </thead>
            <tbody>
              @for (pos of positions(); track pos.pair) {
                <tr [style.background]="pos.unrealized_pnl >= 0 ? 'rgba(34, 197, 94, 0.08)' : 'rgba(239, 68, 68, 0.08)'">
                  <td class="text-left font-medium text-white">{{ pos.pair }}</td>
                  <td class="text-right font-mono">{{ formatQty(pos.quantity, pos.pair) }}</td>
                  <td class="text-right font-mono">{{ formatPosPrice(pos.entry_price) }}</td>
                  <td class="text-right font-mono">{{ pos.breakeven_price ? formatPosPrice(pos.breakeven_price) : '—' }}</td>
                  <td class="text-right font-mono">{{ formatPosPrice(pos.current_price) }}</td>
                  <td class="text-right font-mono">{{ formatCurrency(pos.market_value) }}</td>
                  <td class="text-right font-mono"
                      [class.positive]="pos.unrealized_pnl >= 0"
                      [class.negative]="pos.unrealized_pnl < 0">
                    {{ pos.unrealized_pnl >= 0 ? '+' : '' }}{{ formatCurrency(pos.unrealized_pnl) }}
                    <span class="pnl-sub">({{ pos.unrealized_pnl_pct >= 0 ? '+' : '' }}{{ pos.unrealized_pnl_pct.toFixed(1) }}%)</span>
                  </td>
                  <td class="text-right font-mono text-gray-400">{{ formatHoldSince(pos.hold_since) }}</td>
                </tr>
              }
            </tbody>
            <tfoot>
              <tr class="total-row">
                <td class="text-left" colspan="6">Total Unrealized</td>
                <td class="text-right font-mono"
                    [class.positive]="totalUnrealizedPnl() >= 0"
                    [class.negative]="totalUnrealizedPnl() < 0">
                  {{ totalUnrealizedPnl() >= 0 ? '+' : '' }}{{ formatCurrency(totalUnrealizedPnl()) }}
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      }

    </div>
  `,
  styles: [`
    .equity-curve-container {
      background: transparent;
      color: #e0e0e0;
      font-family: 'Inter', 'Roboto', sans-serif;
    }

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

    .stat-value.equity { color: #ffffff; }
    .stat-value.positive, .positive { color: #4cffb0; }
    .stat-value.negative, .negative { color: #ff4c6a; }

    .pnl-pct {
      font-size: 13px;
      font-weight: 400;
      opacity: 0.8;
      margin-left: 4px;
    }

    .chart-wrapper {
      position: relative;
      width: 100%;
      height: 420px;
      margin-bottom: 8px;
    }

    .chart-wrapper canvas {
      display: block;
      width: 100% !important;
      height: 100% !important;
    }

    .pair-legend {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      font-size: 12px;
      color: #8b8fa3;
      margin-bottom: 16px;
    }

    .legend-item { display: flex; align-items: center; gap: 6px; }
    .legend-item.total { color: #ffffff; }
    .legend-item.cash { color: #8b8fa3; }
    .legend-item.dd { color: rgba(255, 76, 106, 0.6); }

    .legend-dot {
      width: 10px; height: 10px;
      border-radius: 50%;
      background: #ffffff;
      flex-shrink: 0;
    }

    .cash-dot {
      background: #8b8fa3;
      border: 2px dashed #8b8fa3;
      background: transparent;
    }

    .dd-dot { background: rgba(255, 76, 106, 0.4); }

    .trade-summary {
      display: flex;
      gap: 24px;
      padding: 12px 16px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid #2d3148;
      border-bottom: none;
      border-radius: 8px 8px 0 0;
    }

    .summary-item { display: flex; align-items: center; gap: 8px; }

    .summary-label {
      font-size: 11px;
      color: #8b8fa3;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .summary-value {
      font-size: 14px;
      font-weight: 600;
      color: #ffffff;
    }

    .summary-value.positive { color: #4cffb0; }
    .summary-value.negative { color: #ff4c6a; }
    .summary-value.fees { color: #f0c040; }

    /* Positions panel */
    .positions-panel {
      margin-top: 16px;
      border: 1px solid #2d3148;
      border-radius: 8px;
      overflow: hidden;
      background: #1a1d29;
    }

    .positions-header {
      padding: 10px 16px;
      border-bottom: 1px solid #2d3148;
    }

    .positions-header h3 {
      font-size: 12px;
      font-weight: 600;
      color: #e1e4ed;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin: 0;
    }

    .positions-table {
      width: 100%;
      font-size: 12px;
      border-collapse: collapse;
    }

    .positions-table th {
      padding: 8px 16px;
      font-size: 10px;
      font-weight: 600;
      color: #6b7094;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-bottom: 1px solid #2d3148;
    }

    .positions-table td {
      padding: 10px 16px;
      color: #c4c8db;
      border-bottom: 1px solid #232640;
    }

    .positions-table .font-mono { font-family: 'JetBrains Mono', monospace; font-size: 11px; }
    .positions-table .font-medium { font-weight: 600; }
    .positions-table .text-white { color: #e1e4ed; }

    .positions-table .total-row td {
      font-weight: 700;
      color: #e1e4ed;
      border-bottom: none;
      border-top: 1px solid #2d3148;
    }

    .pnl-sub {
      font-size: 10px;
      opacity: 0.7;
      margin-left: 4px;
    }
  `],
})
export class EquityCurveComponent implements OnInit, AfterViewInit, OnDestroy {

  @ViewChild('equityCanvas') private equityCanvasRef!: ElementRef<HTMLCanvasElement>;

  private readonly api = inject(ApiService);
  private sub?: Subscription;
  private equityChart?: Chart;

  private equityPoints: EquityData[] = [];

  currentEquity    = signal<number>(0);
  pnl              = signal<number>(0);
  pnlPct           = signal<number>(0);
  totalTrades      = signal<number>(0);
  maxDrawdown      = signal<number>(0);
  allTrades        = signal<TradeData[]>([]);
  totalRealizedPnl = signal<number>(0);
  totalFees        = signal<number>(0);
  positions        = signal<PositionData[]>([]);

  pairNames: string[] = [];

  // ------------------------------------------------------------------ lifecycle

  ngOnInit(): void {
    const status = this.api.status?.();
    if (status) {
      this.totalTrades.set(status.total_trades ?? 0);
      this.pairNames = (status.pairs ?? []).map(p => p.pair.replace('-USD', ''));
    }
    // Also fetch dynamically
    this.api.fetchPairs().subscribe(pairs => {
      this.pairNames = pairs.map(p => p.replace('-USD', ''));
    });
  }

  ngAfterViewInit(): void {
    this.loadData();
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.equityChart?.destroy();
  }

  // ------------------------------------------------------------------ data

  private loadData(): void {
    this.sub = forkJoin({
      equity: this.api.fetchEquity(72),
      trades: this.api.fetchTrades(undefined, 200),
      positions: this.api.fetchPositions(),
    }).subscribe({
      next: ({ equity, trades, positions }) => {
        this.equityPoints = equity.sort((a, b) =>
          String(a.time).localeCompare(String(b.time))
        );
        const sorted = [...trades].sort((a, b) =>
          String(b.timestamp).localeCompare(String(a.timestamp))
        );
        this.allTrades.set(sorted);
        this.positions.set(positions);
        this.computeStats();
        this.computeTradeStats(sorted);
        this.buildChart();
      },
      error: (err) => console.error('[EquityCurve] fetch failed', err),
    });
  }

  private computeStats(): void {
    if (!this.equityPoints.length) return;

    const last  = this.equityPoints[this.equityPoints.length - 1].equity;

    this.currentEquity.set(last);
    this.pnl.set(last - STARTING_BALANCE);
    this.pnlPct.set(((last - STARTING_BALANCE) / STARTING_BALANCE) * 100);

    let peak = -Infinity;
    let maxDD = 0;
    for (const pt of this.equityPoints) {
      if (pt.equity > peak) peak = pt.equity;
      const dd = peak > 0 ? ((peak - pt.equity) / peak) * 100 : 0;
      if (dd > maxDD) maxDD = dd;
    }
    this.maxDrawdown.set(maxDD);

    const status = this.api.status?.();
    if (status) this.totalTrades.set(status.total_trades ?? 0);
  }

  private computeTradeStats(trades: TradeData[]): void {
    let pnl = 0;
    let fees = 0;
    for (const t of trades) {
      if (t.net_profit != null) pnl += t.net_profit;
      if (t.fee != null) fees += t.fee;
    }
    this.totalRealizedPnl.set(pnl);
    this.totalFees.set(fees);
  }

  // ------------------------------------------------------------------ chart helpers

  private get labels(): string[] {
    return this.equityPoints.map(pt =>
      new Date(pt.time).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
    );
  }

  private get equityValues(): number[] {
    return this.equityPoints.map(pt => pt.equity);
  }

  private get cashValues(): number[] {
    return this.equityPoints.map(pt => pt.balance_usd ?? pt.equity * 0.6);
  }

  private simulatePairEquity(pair: string): number[] {
    const n = Math.max(this.pairNames.length, 1);
    const w = 1 / n;
    return this.equityPoints.map(pt => {
      const base = pt.balance_usd ?? pt.equity * 0.6;
      const pos  = pt.positions_value ?? pt.equity - base;
      return base * w + pos * w;
    });
  }

  private drawdownSeries(): number[] {
    let peak = -Infinity;
    return this.equityPoints.map(pt => {
      if (pt.equity > peak) peak = pt.equity;
      return peak > 0 ? -((peak - pt.equity) / peak) * 100 : 0;
    });
  }

  private buildTradeMarkers(): { idx: number; y: number; color: string }[] {
    const trades = this.allTrades();
    if (!trades.length || !this.equityPoints.length) return [];

    const eqTimes = this.equityPoints.map(pt => new Date(pt.time).getTime());
    const markers: { idx: number; y: number; color: string }[] = [];

    for (const t of trades) {
      const tt = new Date(t.timestamp).getTime();
      let best = 0;
      let bestD = Infinity;
      for (let i = 0; i < eqTimes.length; i++) {
        const d = Math.abs(eqTimes[i] - tt);
        if (d < bestD) { bestD = d; best = i; }
      }

      let color: string;
      if (t.side === 'sell' || t.side === 'SELL') {
        color = (t.net_profit != null && t.net_profit >= 0) ? '#22c55e' : '#ef5350';
      } else {
        color = 'rgba(34, 197, 94, 0.6)';
      }

      markers.push({ idx: best, y: this.equityPoints[best].equity, color });
    }

    return markers;
  }

  // ------------------------------------------------------------------ build chart

  private buildChart(): void {
    this.equityChart?.destroy();

    const ctx = this.equityCanvasRef.nativeElement.getContext('2d');
    if (!ctx) return;

    const labels  = this.labels;
    const equity  = this.equityValues;
    const cash    = this.cashValues;
    const dd      = this.drawdownSeries();
    const markers = this.buildTradeMarkers();

    const allVals = [...equity, ...cash, STARTING_BALANCE];
    const yMin    = Math.min(...allVals) * 0.99;
    const yMax    = Math.max(...allVals) * 1.01;

    const mData:   (number | null)[] = equity.map(() => null);
    const mColors: string[]          = equity.map(() => 'transparent');
    const mRadii:  number[]          = equity.map(() => 0);
    for (const m of markers) {
      if (m.idx >= 0 && m.idx < equity.length) {
        mData[m.idx]   = m.y;
        mColors[m.idx] = m.color;
        mRadii[m.idx]  = 5;
      }
    }

    const pairDatasets = this.pairNames.map((pair, i) => ({
      label:           pair,
      data:            this.simulatePairEquity(pair),
      borderColor:     PAIR_COLORS[i % PAIR_COLORS.length],
      backgroundColor: 'transparent',
      borderWidth:     2,
      pointRadius:     0,
      tension:         0.3,
      yAxisID:         'y' as const,
      order:           3,
    }));

    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels,
        datasets: [
          // Drawdown overlay
          {
            label:           'Drawdown',
            data:            dd,
            borderColor:     'rgba(255, 76, 106, 0.25)',
            backgroundColor: 'rgba(255, 76, 106, 0.06)',
            borderWidth:     1,
            pointRadius:     0,
            tension:         0.3,
            fill:            'origin' as any,
            yAxisID:         'y2',
            order:           6,
          },
          // Starting balance reference
          {
            label:           'Starting Balance',
            data:            equity.map(() => STARTING_BALANCE),
            borderColor:     'rgba(139,143,163,0.4)',
            backgroundColor: 'transparent',
            borderWidth:     1,
            borderDash:      [6, 4],
            pointRadius:     0,
            tension:         0,
            yAxisID:         'y',
            order:           5,
          },
          // Cash balance (dashed gray)
          {
            label:           'Cash Balance',
            data:            cash,
            borderColor:     'rgba(139, 143, 163, 0.6)',
            backgroundColor: 'transparent',
            borderWidth:     1.5,
            borderDash:      [4, 3],
            pointRadius:     0,
            tension:         0.3,
            yAxisID:         'y',
            order:           4,
          },
          // Per-pair equity lines
          ...pairDatasets,
          // Net equity (solid green)
          {
            label:           'Net Equity',
            data:            equity,
            borderColor:     '#4ade80',
            backgroundColor: 'transparent',
            borderWidth:     2.5,
            pointRadius:     0,
            tension:         0.3,
            yAxisID:         'y',
            fill:            {
              target: { value: STARTING_BALANCE },
              above:  'rgba(34, 197, 94, 0.12)',
              below:  'rgba(239, 68, 68, 0.12)',
            } as any,
            order:           1,
          },
          // Trade markers
          {
            label:             'Trades',
            data:              mData,
            borderColor:       'transparent',
            backgroundColor:   mColors,
            pointBackgroundColor: mColors as any,
            borderWidth:       0,
            pointRadius:       mRadii,
            pointHoverRadius:  mRadii.map(r => r > 0 ? 7 : 0) as any,
            showLine:          false,
            yAxisID:           'y',
            order:             0,
          },
        ],
      },
      options: {
        responsive:          true,
        maintainAspectRatio: false,
        animation:           { duration: 400 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(20,22,40,0.92)',
            borderColor:     '#2d3148',
            borderWidth:     1,
            titleColor:      '#8b8fa3',
            bodyColor:       '#e0e0e0',
            padding:         10,
            filter: (item) => {
              const l = item.dataset.label;
              return l !== 'Trades' && l !== 'Starting Balance';
            },
            callbacks: {
              label: (item) => {
                if (item.dataset.label === 'Drawdown') {
                  return ` Drawdown: ${(item.parsed.y ?? 0).toFixed(2)}%`;
                }
                return ` ${item.dataset.label}: ${this.formatCurrency(item.parsed.y ?? 0)}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: '#8b8fa3', font: { size: 10 }, maxTicksLimit: 10, maxRotation: 0 },
            grid:  { color: '#2d3148', lineWidth: 1 },
            border: { color: '#2d3148' },
          },
          y: {
            position: 'left',
            min: yMin,
            max: yMax,
            ticks: {
              color: '#8b8fa3',
              font: { size: 10 },
              callback: (v) => this.formatCurrency(Number(v)),
            },
            grid:  { color: '#2d3148', lineWidth: 1 },
            border: { color: '#2d3148' },
          },
          y2: {
            position: 'right',
            max: 0,
            min: dd.length ? Math.min(...dd) * 3 : -10,
            display: false,
            grid: { display: false },
          },
        },
      },
    };

    this.equityChart = new Chart(ctx, config);
  }

  // ------------------------------------------------------------------ utils

  totalMarketValue(): number {
    return this.positions().reduce((sum, p) => sum + p.market_value, 0);
  }

  totalUnrealizedPnl(): number {
    return this.positions().reduce((sum, p) => sum + p.unrealized_pnl, 0);
  }

  pairColor(pair: string): string {
    const idx = this.pairNames.indexOf(pair);
    return idx >= 0 && idx < PAIR_COLORS.length ? PAIR_COLORS[idx] : '#8b8fa3';
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

  formatPosPrice(price: number): string {
    if (price == null || price === 0) return '—';
    if (price >= 1) return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 8 });
  }

  formatQty(qty: number, pair: string): string {
    if (qty == null) return '—';
    if (pair.includes('PEPE') || pair.includes('DOGE')) {
      return qty.toLocaleString('en-US', { maximumFractionDigits: 2 });
    }
    return qty.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
  }

  formatHoldSince(holdSince: string | null): string {
    if (!holdSince) return '—';
    try {
      const then = new Date(holdSince).getTime();
      const now = Date.now();
      const diffSeconds = Math.floor((now - then) / 1000);
      if (diffSeconds < 0) return '—';

      const days = Math.floor(diffSeconds / 86400);
      const hours = Math.floor((diffSeconds % 86400) / 3600);
      const minutes = Math.floor((diffSeconds % 3600) / 60);

      if (days > 0) {
        return `Holding for ${days}d ${hours}h`;
      }
      return `Holding for ${hours}h ${minutes}m`;
    } catch {
      return '—';
    }
  }
}
