import {
  Component, OnInit, AfterViewInit, inject, signal, computed, ViewChild, ElementRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chart, registerables, ChartConfiguration } from 'chart.js';
import {
  ApiService, PositionData, TradeData, VolPredictionData,
  PairScanData, GridLevelData, EquityData,
} from '../../services/api.service';
import { StatusBannerComponent } from '../status-banner/status-banner.component';
import { ActivityLogComponent } from '../activity-log/activity-log.component';
import { PairCardComponent } from '../pair-card/pair-card.component';
import { ExpandedPairChartComponent } from '../expanded-pair-chart/expanded-pair-chart.component';
import { HealthBarComponent } from '../health-bar/health-bar.component';
import { TradeLogComponent } from '../trade-log/trade-log.component';
import { DcaSimulatorComponent } from '../dca-simulator/dca-simulator.component';
import { RegimeVisualizerComponent } from '../regime-visualizer/regime-visualizer.component';
import { SelfCheckComponent } from '../self-check/self-check.component';
import { PairScannerComponent } from '../pair-scanner/pair-scanner.component';
import { AdaptationsComponent } from '../adaptations/adaptations.component';
import { MomentumPanelComponent } from '../momentum-panel/momentum-panel.component';
import { EarlyScannerComponent } from '../early-scanner/early-scanner.component';
import { forkJoin } from 'rxjs';

Chart.register(...registerables);

const STARTING_BALANCE = 3000;

@Component({
  selector: 'app-command-center',
  standalone: true,
  imports: [
    CommonModule, StatusBannerComponent, ActivityLogComponent,
    PairCardComponent, ExpandedPairChartComponent, HealthBarComponent,
    TradeLogComponent, DcaSimulatorComponent, RegimeVisualizerComponent,
    SelfCheckComponent, PairScannerComponent, AdaptationsComponent,
    MomentumPanelComponent, EarlyScannerComponent,
  ],
  template: `
    <div class="cc-root">

      <!-- ENGINE SWITCHER TABS -->
      @if (momentumEnabled()) {
        <div class="engine-switcher">
          <button class="engine-switch-btn" [class.active]="activeEngine() === 'momentum'" (click)="activeEngine.set('momentum')">
            <span class="engine-dot-tab" [class.active]="true"></span>
            Momentum
          </button>
          <button class="engine-switch-btn" [class.active]="activeEngine() === 'grid'" (click)="activeEngine.set('grid')">
            <span class="engine-dot-tab" [class.active]="true"></span>
            Grid Trading
            <span class="engine-switch-count">{{ activePairsText() }}</span>
          </button>
          <button class="engine-switch-btn scanner-tab" [class.active]="activeEngine() === 'scanner'" (click)="activeEngine.set('scanner')">
            <span class="engine-dot-tab scanner-dot" [class.active]="true"></span>
            Scanner
          </button>
          <button class="logout-btn" (click)="logout()">Logout</button>
        </div>
      }

      <!-- MOMENTUM PANEL (shown when selected or no dual mode) -->
      @if (momentumEnabled() && activeEngine() === 'momentum') {
        <app-momentum-panel />
      }

      <!-- EARLY SCANNER PANEL -->
      @if (activeEngine() === 'scanner') {
        <app-early-scanner />
      }

      <!-- GRID PANEL -->
      <div class="grid-panel" [class.hidden]="momentumEnabled() && activeEngine() !== 'grid'">

      <!-- 0. Hero Numbers — the answer to "how much money do I have?" -->
      <div class="hero-bar">
        <div class="hero-item">
          <span class="hero-value">{{ formatCurrency(heroEquity()) }}</span>
          <span class="hero-label">Total</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-value cash">{{ formatCurrency(heroCash()) }}</span>
          <span class="hero-label">Cash</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-value positions">{{ formatCurrency(heroPositions()) }}</span>
          <span class="hero-label">In positions</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-value" [class.pos]="heroPnl() >= 0" [class.neg]="heroPnl() < 0">
            {{ heroPnl() >= 0 ? '+' : '' }}{{ formatCurrency(heroPnl()) }}
          </span>
          <span class="hero-label">P&amp;L ({{ heroPnlPct() }})</span>
        </div>
      </div>

      <!-- 1. Status Banner -->
      <app-status-banner
        (toolSelected)="openTool($event)"
        (updateClicked)="triggerUpdate()"
        (resetClicked)="resetData()"
      />

      <!-- 2. Equity + Activity Log row -->
      <div class="equity-activity-row">
        <div class="equity-col">
          <div class="section-header">Portfolio Equity (72h)</div>
          <div class="equity-chart-slot">
            <canvas #equityCanvas></canvas>
          </div>
          <div class="equity-substats">
            <span>
              <span class="sub-label">Realized </span>
              <span [class.pos]="realizedPnl() >= 0" [class.neg]="realizedPnl() < 0">
                {{ realizedPnl() >= 0 ? '+' : '' }}{{ formatCurrency(realizedPnl()) }}
              </span>
            </span>
            <span>
              <span class="sub-label">Unrealized </span>
              <span [class.pos]="unrealizedPnl() >= 0" [class.neg]="unrealizedPnl() < 0">
                {{ unrealizedPnl() >= 0 ? '+' : '' }}{{ formatCurrency(unrealizedPnl()) }}
              </span>
            </span>
            <span>
              <span class="sub-label">Fees </span>
              <span class="fees">{{ formatCurrency(totalFees()) }}</span>
            </span>
            <span>
              <span class="sub-label">Max DD </span>
              <span class="neg">{{ maxDrawdown().toFixed(2) }}%</span>
            </span>
          </div>
        </div>
        <div class="activity-col">
          <app-activity-log />
          <app-adaptations />
        </div>
      </div>

      <!-- 3. Pair Cards section -->
      <div class="pair-section">
        <div class="section-header">Active Pairs <span class="section-sub">(click to expand chart)</span></div>
        <div class="pair-cards-row">
          @for (p of pairs(); track p.pair) {
            <app-pair-card
              [pair]="p"
              [isExpanded]="expandedPair() === p.pair"
              [isDimmed]="expandedPair() !== null && expandedPair() !== p.pair"
              [positions]="positions()"
              [volPrediction]="volForPair(p.pair)"
              [gridHeld]="p.grid_held"
              [gridTotal]="p.grid_total"
              [gridLevels]="gridLevels().get(p.pair) ?? null"
              (cardClicked)="toggleExpandedPair($event)"
            />
          }
        </div>

        @if (expandedPair()) {
          <app-expanded-pair-chart [pair]="expandedPair()!" />
        }

        <!-- Why these pairs? -->
        <div class="why-pairs">
          <button class="why-toggle" (click)="whyOpen.set(!whyOpen())">
            {{ whyOpen() ? '▾' : '▸' }} Why these pairs?
          </button>
          @if (whyOpen() && latestScan()) {
            <div class="why-content">
              @for (entry of latestScan()!.selected_pairs; track entry.pair) {
                <div class="why-entry">
                  <strong>{{ entry.pair }}</strong>
                  &mdash; Score: {{ entry.composite_score.toFixed(2) }},
                  Vol: {{ (entry.volatility * 100).toFixed(1) }}%,
                  Range: {{ (entry.range_bound * 100).toFixed(0) }}%,
                  Regime: {{ entry.regime }}
                </div>
              }
              @if (!latestScan()!.selected_pairs.length) {
                <div class="why-entry">No scan data available yet.</div>
              }
            </div>
          }
        </div>
      </div>

      <!-- 4. Health Bar -->
      <app-health-bar />

      <!-- 5. Positions & Trades -->
      <div class="positions-section">
        <div class="section-header">Open Positions &amp; Recent Trades</div>
        <app-trade-log [trades]="allTrades()" />
      </div>

      <!-- 6. Tools section -->
      @if (activeTool()) {
        <div class="tool-section">
          <div class="tool-header">
            <span>{{ toolLabel(activeTool()!) }}</span>
            <button class="tool-close" (click)="activeTool.set(null)">✕ Close</button>
          </div>
          @if (activeTool() === 'scanner') {
            <app-pair-scanner />
          }
          @if (activeTool() === 'simulator') {
            <app-dca-simulator />
          }
          @if (activeTool() === 'regime') {
            <app-regime-visualizer />
          }
          @if (activeTool() === 'self-check') {
            <app-self-check />
          }
        </div>
      }

      </div><!-- /grid-panel -->
    </div>
  `,
  styles: [`
    .cc-root {
      background: #0f1117; color: #e2e8f0; min-height: 100vh;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    .grid-panel.hidden { display: none; }

    /* Engine switcher tabs */
    .engine-switcher {
      display: flex; position: sticky; top: 0; z-index: 50;
      background: #141621; border-bottom: 2px solid #2d3148;
    }
    .engine-switch-btn {
      flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px;
      padding: 12px 16px; border: none; background: transparent;
      color: #6b7280; font-size: 13px; font-weight: 600; cursor: pointer;
      text-transform: uppercase; letter-spacing: 0.06em;
      border-bottom: 3px solid transparent; transition: all 0.2s;
    }
    .engine-switch-btn:hover { color: #e2e8f0; background: rgba(255,255,255,0.03); }
    .engine-switch-btn.active {
      color: #e2e8f0; border-bottom-color: #60a5fa;
      background: linear-gradient(180deg, rgba(96,165,250,0.08) 0%, transparent 100%);
    }
    .engine-switch-count {
      font-size: 10px; color: #6b7280; font-weight: 400;
      font-family: 'JetBrains Mono', monospace;
    }
    .engine-dot-tab {
      width: 8px; height: 8px; border-radius: 50%;
      animation: tabpulse 2s ease-in-out infinite;
    }
    .engine-dot-tab.active { background: #4ade80; box-shadow: 0 0 6px rgba(74,222,128,0.4); }
    .scanner-tab .engine-dot-tab.active, .scanner-dot.active { background: #38bdf8; box-shadow: 0 0 6px rgba(56,189,248,0.4); }
    .scanner-tab.active { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }
    @keyframes tabpulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
    .logout-btn {
      margin-left: auto;
      font-size: 9px; font-weight: 600; padding: 4px 10px;
      background: rgba(248,113,113,0.08); color: #6b7280;
      border: 1px solid rgba(248,113,113,0.15); border-radius: 4px;
      cursor: pointer; text-transform: uppercase; letter-spacing: 0.05em;
      transition: all 0.15s; align-self: center; margin-right: 12px;
    }
    .logout-btn:hover {
      color: #f87171; background: rgba(248,113,113,0.15);
      border-color: rgba(248,113,113,0.3);
    }
    .hero-bar {
      display: flex; align-items: center; justify-content: center;
      gap: 0; padding: 20px 24px;
      background: linear-gradient(180deg, #141621 0%, #0f1117 100%);
      border-bottom: 1px solid #2d3148;
      flex-wrap: wrap;
    }
    .hero-item {
      display: flex; flex-direction: column; align-items: center;
      padding: 0 28px;
    }
    .hero-value {
      font-size: 28px; font-weight: 700; color: #f1f5f9;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      letter-spacing: -0.02em; line-height: 1.2;
    }
    .hero-value.cash { color: #94a3b8; }
    .hero-value.positions { color: #60a5fa; }
    .hero-value.pos { color: #4ade80; }
    .hero-value.neg { color: #f87171; }
    .hero-label {
      font-size: 11px; font-weight: 500; color: #6b7280;
      margin-top: 2px; letter-spacing: 0.03em;
    }
    .hero-divider {
      width: 1px; height: 36px; background: #2d3148; flex-shrink: 0;
    }
    @media (max-width: 640px) {
      .hero-bar { gap: 8px; padding: 16px 12px; }
      .hero-item { padding: 4px 12px; }
      .hero-value { font-size: 20px; }
      .hero-divider { display: none; }
    }
    .section-header {
      font-size: 13px; font-weight: 600; color: #e2e8f0;
      margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.06em;
    }
    .section-sub {
      font-size: 11px; font-weight: 400; color: #6b7280;
      text-transform: none; letter-spacing: 0;
    }
    .equity-activity-row {
      display: flex; gap: 0; border-bottom: 1px solid #2d3148; flex-wrap: wrap;
    }
    .equity-col {
      flex: 3; padding: 16px 20px; border-right: 1px solid #2d3148; min-width: 300px;
    }
    .activity-col { flex: 2; min-width: 280px; }
    .equity-chart-slot {
      position: relative; height: 200px; border-radius: 8px; overflow: hidden;
    }
    .equity-chart-slot canvas { display: block; width: 100% !important; height: 100% !important; }
    .equity-substats {
      display: flex; gap: 20px; margin-top: 8px; font-size: 11px; flex-wrap: wrap;
    }
    .sub-label { color: #6b7280; }
    .pos { color: #4ade80; }
    .neg { color: #f87171; }
    .fees { color: #fbbf24; }
    .pair-section { padding: 16px 20px; border-bottom: 1px solid #2d3148; }
    .pair-cards-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
    .why-pairs { margin-top: 12px; }
    .why-toggle {
      background: transparent; border: none; color: #6b7280; font-size: 12px; cursor: pointer;
    }
    .why-toggle:hover { color: #e2e8f0; }
    .why-content {
      margin-top: 8px; padding: 12px 16px; background: #1a1d2e;
      border: 1px solid #2d3148; border-radius: 8px; font-size: 12px; color: #9ca3af;
    }
    .why-entry { margin-bottom: 6px; line-height: 1.6; }
    .why-entry strong { color: #e2e8f0; }
    .positions-section { padding: 16px 20px; }
    .tool-section { padding: 16px 20px; border-top: 1px solid #2d3148; }
    .tool-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 12px; font-size: 13px; font-weight: 600; color: #e2e8f0;
    }
    .tool-close {
      background: transparent; border: 1px solid #2d3148; color: #6b7280;
      padding: 4px 12px; border-radius: 6px; cursor: pointer; font-size: 11px;
    }
    .tool-close:hover { background: #2d3148; color: #e2e8f0; }
    @media (max-width: 768px) {
      .equity-activity-row { flex-direction: column; }
      .equity-col { border-right: none; border-bottom: 1px solid #2d3148; }
      .pair-cards-row { flex-direction: column; }
    }
  `],
})
export class CommandCenterComponent implements OnInit, AfterViewInit {
  private api = inject(ApiService);

  expandedPair = signal<string | null>(null);
  whyOpen = signal(false);
  activeTool = signal<string | null>(null);
  activeEngine = signal<'momentum' | 'grid' | 'scanner'>('momentum');

  // Dual engine: momentum rotation
  momentumEnabled = computed(() => {
    const ms = this.api.momentumStatus();
    return ms !== null && ms.enabled === true;
  });

  activePairsText = computed(() => {
    const s = this.api.status();
    const count = s?.pairs?.length ?? 0;
    return `${count} pair${count !== 1 ? 's' : ''} active`;
  });

  positions = signal<PositionData[]>([]);
  allTrades = signal<TradeData[]>([]);
  volPredictions = signal<VolPredictionData[]>([]);
  latestScan = signal<PairScanData | null>(null);
  gridLevels = signal<Map<string, GridLevelData>>(new Map());

  // Equity sub-stats
  realizedPnl = signal(0);
  unrealizedPnl = signal(0);
  totalFees = signal(0);
  maxDrawdown = signal(0);

  pairs = computed(() => this.api.status()?.pairs ?? []);

  // Hero numbers — derived from status signal
  heroEquity = computed(() => this.api.status()?.equity ?? 0);
  heroCash = computed(() => this.api.status()?.balance_usd ?? 0);
  heroPositions = computed(() => this.api.status()?.positions_value ?? 0);
  heroPnl = computed(() => this.api.status()?.pnl ?? 0);
  heroPnlPct = computed(() => {
    const pct = this.api.status()?.pnl_pct ?? 0;
    return (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
  });

  @ViewChild('equityCanvas') equityCanvasRef!: ElementRef<HTMLCanvasElement>;
  private equityChart?: Chart;

  // ------------------------------------------------------------------ lifecycle

  ngOnInit(): void {
    forkJoin({
      positions: this.api.fetchPositions(),
      trades: this.api.fetchTrades(undefined, 200),
      volLatest: this.api.fetchVolLatest(),
      latestScan: this.api.fetchLatestPairScan(),
    }).subscribe({
      next: ({ positions, trades, volLatest, latestScan }) => {
        this.positions.set(positions);

        const sorted = [...trades].sort((a, b) =>
          String(b.timestamp).localeCompare(String(a.timestamp))
        );
        this.allTrades.set(sorted);
        this.volPredictions.set(volLatest);
        this.latestScan.set(latestScan);

        // Compute unrealized from positions
        const unrealized = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
        this.unrealizedPnl.set(unrealized);

        // Compute realized / fees from trades
        let realized = 0;
        let fees = 0;
        for (const t of sorted) {
          if (t.net_profit != null) realized += t.net_profit;
          if (t.fee != null) fees += t.fee;
        }
        this.realizedPnl.set(realized);
        this.totalFees.set(fees);

        // Fetch grid levels for each pair
        const pairsNow = this.api.status()?.pairs ?? [];
        for (const p of pairsNow) {
          this.api.fetchGridLevels(p.pair).subscribe({
            next: (gl) => {
              const map = new Map(this.gridLevels());
              map.set(p.pair, gl);
              this.gridLevels.set(map);
            },
            error: () => {},
          });
        }
      },
      error: (err) => console.error('[CommandCenter] init fetch failed', err),
    });
  }

  ngAfterViewInit(): void {
    this.api.fetchEquity(72).subscribe({
      next: (equity) => {
        const sorted = [...equity].sort((a, b) =>
          String(a.time).localeCompare(String(b.time))
        );
        this.buildEquityChart(sorted);
        // Compute max drawdown
        let peak = -Infinity;
        let maxDD = 0;
        for (const pt of sorted) {
          if (pt.equity > peak) peak = pt.equity;
          const dd = peak > 0 ? ((peak - pt.equity) / peak) * 100 : 0;
          if (dd > maxDD) maxDD = dd;
        }
        this.maxDrawdown.set(maxDD);
      },
      error: (err) => console.error('[CommandCenter] equity fetch failed', err),
    });
  }

  // ------------------------------------------------------------------ helpers

  toggleExpandedPair(pair: string): void {
    this.expandedPair.set(this.expandedPair() === pair ? null : pair);
  }

  openTool(tool: string): void {
    this.activeTool.set(tool);
    // Scroll to tool section after DOM update
    setTimeout(() => {
      const el = document.querySelector('.tool-section');
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }

  triggerUpdate(): void {
    this.api.triggerUpdate().subscribe({
      next: () => console.log('[CommandCenter] update triggered'),
      error: (err) => console.error('[CommandCenter] update failed', err),
    });
  }

  logout(): void {
    this.api.logout().subscribe({
      next: () => window.location.href = '/login',
    });
  }

  resetData(): void {
    if (!confirm('Clear all trading data (trades, equity, events)? This cannot be undone.')) return;
    this.api.resetData().subscribe({
      next: () => {
        console.log('[CommandCenter] data reset');
        window.location.reload();
      },
      error: (err) => console.error('[CommandCenter] reset failed', err),
    });
  }

  volForPair(pair: string): VolPredictionData | null {
    return this.volPredictions().find(v => v.pair === pair) ?? null;
  }

  toolLabel(tool: string): string {
    const labels: Record<string, string> = {
      scanner: 'Pair Scanner',
      simulator: 'DCA Simulator',
      regime: 'Regime Visualizer',
      'self-check': 'Self-Check',
    };
    return labels[tool] ?? tool;
  }

  formatCurrency(value: number): string {
    if (value === undefined || value === null || isNaN(value)) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  // ------------------------------------------------------------------ chart

  private buildEquityChart(points: EquityData[]): void {
    this.equityChart?.destroy();

    if (!this.equityCanvasRef?.nativeElement) return;
    const ctx = this.equityCanvasRef.nativeElement.getContext('2d');
    if (!ctx) return;

    const labels = points.map(pt =>
      new Date(pt.time).toLocaleTimeString('en-US', {
        hour: 'numeric', minute: '2-digit', hour12: true,
      })
    );
    const equityValues = points.map(pt => pt.equity);

    if (!equityValues.length) return;

    const allVals = [...equityValues, STARTING_BALANCE];
    const yMin = Math.min(...allVals) * 0.99;
    const yMax = Math.max(...allVals) * 1.01;

    // Green gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(34, 197, 94, 0.25)');
    gradient.addColorStop(1, 'rgba(34, 197, 94, 0.02)');

    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels,
        datasets: [
          // Starting balance reference line (dashed)
          {
            label: 'Starting Balance',
            data: equityValues.map(() => STARTING_BALANCE),
            borderColor: 'rgba(139, 143, 163, 0.4)',
            backgroundColor: 'transparent',
            borderWidth: 1,
            borderDash: [6, 4],
            pointRadius: 0,
            tension: 0,
            yAxisID: 'y',
            order: 2,
          } as any,
          // Main equity line with green fill
          {
            label: 'Net Equity',
            data: equityValues,
            borderColor: '#4ade80',
            backgroundColor: gradient,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
            yAxisID: 'y',
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(20, 22, 40, 0.92)',
            borderColor: '#2d3148',
            borderWidth: 1,
            titleColor: '#8b8fa3',
            bodyColor: '#e0e0e0',
            padding: 8,
            filter: (item) => item.dataset.label !== 'Starting Balance',
            callbacks: {
              label: (item) => ` ${item.dataset.label}: ${this.formatCurrency(item.parsed.y ?? 0)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: '#8b8fa3', font: { size: 9 },
              maxTicksLimit: 8, maxRotation: 0,
            },
            grid: { color: '#2d3148', lineWidth: 1 },
            border: { color: '#2d3148' },
          },
          y: {
            position: 'left',
            min: yMin,
            max: yMax,
            ticks: {
              color: '#8b8fa3', font: { size: 9 },
              callback: (v) => this.formatCurrency(Number(v)),
            },
            grid: { color: '#2d3148', lineWidth: 1 },
            border: { color: '#2d3148' },
          },
        },
      },
    };

    this.equityChart = new Chart(ctx, config);
  }
}
