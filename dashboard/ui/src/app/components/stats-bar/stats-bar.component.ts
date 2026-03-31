import { Component, inject, computed, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, PositionData, ScanProgressData, PnlAttribution, HealthData } from '../../services/api.service';

const REGIME_CONFIG: Record<string, { label: string; bg: string; text: string; ring: string }> = {
  RANGING:       { label: 'RANGING',        bg: '#14532d', text: '#4ade80', ring: '#16a34a' },
  TRENDING_UP:   { label: 'TRENDING UP',    bg: '#1e3a5f', text: '#60a5fa', ring: '#2563eb' },
  TRENDING_DOWN: { label: 'TRENDING DOWN',  bg: '#450a0a', text: '#f87171', ring: '#dc2626' },
  VOLATILE:      { label: 'VOLATILE',       bg: '#451a03', text: '#fbbf24', ring: '#d97706' },
  SQUEEZE:       { label: 'SQUEEZE',        bg: '#3b0764', text: '#c084fc', ring: '#9333ea' },
};

const DEFAULT_REGIME = { label: 'UNKNOWN', bg: '#1e2130', text: '#94a3b8', ring: '#475569' };

@Component({
  selector: 'app-stats-bar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="stats-bar-root" role="banner" aria-label="Dashboard stats bar">

      <!-- Left cluster: financial summary -->
      <div class="stat-cluster">

        <div class="stat-block">
          <span class="stat-label">EQUITY</span>
          <span class="stat-value">
            {{ status() ? ('$' + formatNumber(status()!.equity)) : '—' }}
          </span>
        </div>

        <div class="stat-divider"></div>

        <div class="stat-block pnl-block" [title]="'Net = realized gains from completed trades minus unrealized losses on open positions'">
          <span class="stat-label">NET P&amp;L
            <span class="info-icon" title="Net = realized gains from completed trades minus unrealized losses on open positions">i</span>
          </span>
          <ng-container *ngIf="status(); else dash1">
            <span class="stat-value" [class.positive]="status()!.pnl >= 0" [class.negative]="status()!.pnl < 0">
              {{ (status()!.pnl >= 0 ? '+' : '') + '$' + formatNumber(status()!.pnl) }}
            </span>
            <span class="stat-sub" [class.positive]="status()!.pnl_pct >= 0" [class.negative]="status()!.pnl_pct < 0">
              ({{ (status()!.pnl_pct >= 0 ? '+' : '') + status()!.pnl_pct.toFixed(2) + '%' }})
            </span>
          </ng-container>
          <ng-template #dash1><span class="stat-value">—</span></ng-template>
          <span class="stat-breakdown" *ngIf="positions().length > 0">
            Realized: {{ formatRealized() }} | Unrealized: {{ formatUnrealized() }}
          </span>
          <span class="stat-breakdown" *ngIf="pnlAttrib() as a">
            Legacy: <span [class.positive]="a.legacy_total_pnl >= 0" [class.negative]="a.legacy_total_pnl < 0">{{ formatSignedDollar(a.legacy_total_pnl) }}</span>
            | Auto: <span [class.positive]="a.auto_total_pnl >= 0" [class.negative]="a.auto_total_pnl < 0">{{ formatSignedDollar(a.auto_total_pnl) }}</span>
          </span>
        </div>

        <div class="stat-divider"></div>

        <div class="stat-block">
          <span class="stat-label">PAIRS</span>
          <span class="stat-value accent">
            {{ status() ? activePairsCount() : '—' }}
          </span>
        </div>

        <div class="stat-divider"></div>

        <div class="stat-block">
          <span class="stat-label">TRADES</span>
          <span class="stat-value">
            {{ status() ? status()!.total_trades : '—' }}
          </span>
        </div>

      </div>

      <!-- Centre: per-pair regime badges -->
      <div class="regime-cluster" aria-label="Per-pair market regimes">
        <ng-container *ngIf="status() && status()!.pairs.length; else noPairs">
          <div
            *ngFor="let pair of status()!.pairs"
            class="regime-badge"
            [style.background-color]="regimeConfig(pair.regime).bg"
            [style.color]="regimeConfig(pair.regime).text"
            [style.box-shadow]="'0 0 0 1px ' + regimeConfig(pair.regime).ring"
            [title]="pair.pair + ' — ' + pair.regime + ' @ $' + formatPrice(pair.price)"
          >
            <span class="badge-pair">{{ shortPair(pair.pair) }}</span>
            <span class="badge-regime">{{ regimeConfig(pair.regime).label }}</span>
          </div>
        </ng-container>
        <ng-template #noPairs>
          <span class="no-data">No pairs active</span>
        </ng-template>
      </div>

      <!-- Right cluster: time & refresh -->
      <div class="stat-cluster right-cluster">

        <div class="scan-indicator" *ngIf="scanProgress().scanning" title="Pair scan in progress">
          <span class="scan-spinner"></span>
          <span class="scan-text">Scanning {{ scanProgress().scanned }}/{{ scanProgress().total_pairs }}</span>
        </div>

        <div class="stat-divider" *ngIf="scanProgress().scanning"></div>

        <div class="stat-block" *ngIf="status()">
          <span class="stat-label">LAST TRADE</span>
          <span class="stat-value mono">{{ formatLastTrade(status()!.last_trade_time) }}</span>
        </div>

        <div class="stat-divider" *ngIf="status()"></div>

        <div class="update-wrapper">
          <button
            class="update-btn"
            [class.checking]="updateChecking()"
            [disabled]="updateChecking()"
            (click)="checkForUpdates()"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span>{{ updateChecking() ? 'Checking...' : 'Update' }}</span>
          </button>
          <span
            *ngIf="updateResultVisible()"
            class="update-result"
            [class.success]="updateSuccess()"
            [class.error]="!updateSuccess()"
          >{{ updateStatus() }}</span>
        </div>

        <div class="stat-divider"></div>

        <div class="refresh-block" [class.urgent]="refreshCountdown() <= 10">
          <svg class="refresh-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          <span class="refresh-countdown">{{ refreshCountdown() }}s</span>
        </div>

      </div>

    </div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
    }

    .stats-bar-root {
      display: flex;
      align-items: center;
      gap: 0;
      width: 100%;
      min-height: 52px;
      padding: 0 16px;
      background: #1a1d29;
      border-bottom: 1px solid #2a2d3e;
      box-shadow: 0 1px 8px rgba(0,0,0,0.4);
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      overflow: hidden;
    }

    /* ── Stat clusters ── */

    .stat-cluster {
      display: flex;
      align-items: center;
      gap: 0;
      flex-shrink: 0;
    }

    .right-cluster {
      margin-left: auto;
    }

    .stat-block {
      display: flex;
      align-items: baseline;
      gap: 6px;
      padding: 0 14px;
    }

    .stat-divider {
      width: 1px;
      height: 28px;
      background: #2a2d3e;
      flex-shrink: 0;
    }

    .stat-label {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.1em;
      color: #4b5280;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .stat-value {
      font-size: 14px;
      font-weight: 600;
      color: #e1e4ed;
      white-space: nowrap;
    }

    .stat-value.mono {
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      font-size: 12px;
    }

    .stat-value.accent {
      color: #818cf8;
    }

    .stat-sub {
      font-size: 11px;
      font-weight: 500;
      margin-left: -2px;
    }

    .pnl-block {
      flex-direction: column;
      gap: 2px;
    }

    .stat-breakdown {
      font-size: 9px;
      color: #6b7094;
      font-weight: 500;
      white-space: nowrap;
    }

    .info-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #2d3148;
      color: #6b7094;
      font-size: 8px;
      font-weight: 700;
      font-style: italic;
      margin-left: 3px;
      cursor: help;
      vertical-align: middle;
    }

    .stat-value.positive,
    .stat-sub.positive {
      color: #4ade80;
    }

    .stat-value.negative,
    .stat-sub.negative {
      color: #f87171;
    }

    /* ── Regime badges ── */

    .regime-cluster {
      display: flex;
      align-items: center;
      gap: 6px;
      flex: 1;
      justify-content: center;
      padding: 0 12px;
      overflow-x: auto;
      scrollbar-width: none;
    }

    .regime-cluster::-webkit-scrollbar {
      display: none;
    }

    .regime-badge {
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 3px 9px 3px 7px;
      border-radius: 20px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.04em;
      white-space: nowrap;
      cursor: default;
      transition: filter 0.15s ease;
      flex-shrink: 0;
    }

    .regime-badge:hover {
      filter: brightness(1.15);
    }

    .badge-pair {
      font-size: 10px;
      font-weight: 800;
      opacity: 0.85;
    }

    .badge-regime {
      font-size: 9px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .no-data {
      font-size: 11px;
      color: #4b5280;
      font-style: italic;
    }

    /* ── Refresh indicator ── */

    .refresh-block {
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 0 14px;
      color: #4b5280;
      transition: color 0.3s ease;
    }

    .refresh-block.urgent {
      color: #fbbf24;
    }

    .refresh-icon {
      width: 13px;
      height: 13px;
      flex-shrink: 0;
    }

    .refresh-countdown {
      font-size: 11px;
      font-weight: 600;
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      min-width: 28px;
    }

    /* ── Scan indicator ── */

    .scan-indicator {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 0 14px;
    }

    .scan-spinner {
      display: inline-block;
      width: 12px;
      height: 12px;
      border: 2px solid #3b3f5c;
      border-top-color: #a78bfa;
      border-radius: 50%;
      animation: statspin 0.8s linear infinite;
    }

    @keyframes statspin { to { transform: rotate(360deg); } }

    .scan-text {
      font-size: 11px;
      font-weight: 600;
      color: #a78bfa;
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      white-space: nowrap;
    }

    /* ── Update button ── */

    .update-btn {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      border: 1px solid #3b3f5c;
      border-radius: 6px;
      background: #1e2130;
      color: #94a3b8;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
    }

    .update-btn:hover:not(:disabled) {
      background: #2d3148;
      color: #e1e4ed;
      border-color: #818cf8;
    }

    .update-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .update-btn.checking {
      color: #a78bfa;
      border-color: #a78bfa;
    }

    .update-wrapper {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .update-result {
      font-size: 10px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 4px;
      white-space: nowrap;
      animation: fadeIn 0.2s ease;
    }

    .update-result.success {
      color: #4ade80;
      background: rgba(74, 222, 128, 0.1);
    }

    .update-result.error {
      color: #f87171;
      background: rgba(248, 113, 113, 0.1);
    }

    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  `],
})
export class StatsBarComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly status = this.api.status;
  readonly refreshCountdown = this.api.refreshCountdown;
  readonly scanProgress = this.api.scanProgress;
  readonly positions = signal<PositionData[]>([]);
  readonly pnlAttrib = signal<PnlAttribution | null>(null);
  readonly updateChecking = signal(false);
  readonly updateStatus = signal('');
  readonly updateResultVisible = signal(false);
  readonly updateSuccess = signal(true);
  private _updateTimeout: any;

  readonly activePairsCount = computed(() => {
    const s = this.status();
    return s ? s.pairs.length : 0;
  });

  ngOnInit(): void {
    this.api.fetchPositions().subscribe({
      next: (data) => this.positions.set(data),
      error: () => {},
    });
    this.api.fetchPnlAttribution().subscribe({
      next: (data) => this.pnlAttrib.set(data),
      error: () => {},
    });
    // Start polling scan progress (shared signal updates stats bar reactively)
    this.api.startScanProgressPolling();
  }

  checkForUpdates(): void {
    this.updateChecking.set(true);
    this.updateResultVisible.set(false);
    clearTimeout(this._updateTimeout);
    this.api.triggerUpdate().subscribe({
      next: (res) => {
        this.updateChecking.set(false);
        this.updateStatus.set(res.update_status ?? res.output ?? 'Done');
        this.updateSuccess.set(res.status === 'ok');
        this.updateResultVisible.set(true);
        this._updateTimeout = setTimeout(() => this.updateResultVisible.set(false), 8000);
      },
      error: () => {
        this.updateChecking.set(false);
        this.updateStatus.set('Update failed');
        this.updateSuccess.set(false);
        this.updateResultVisible.set(true);
        this._updateTimeout = setTimeout(() => this.updateResultVisible.set(false), 8000);
      },
    });
  }

  regimeConfig(regime: string) {
    const key = (regime ?? '').toUpperCase().replace(/ /g, '_');
    return REGIME_CONFIG[key] ?? DEFAULT_REGIME;
  }

  shortPair(pair: string): string {
    return pair.replace('-USD', '');
  }

  formatNumber(value: number): string {
    const abs = Math.abs(value);
    if (abs >= 1_000_000) return (value / 1_000_000).toFixed(2) + 'M';
    if (abs >= 1_000)     return (value / 1_000).toFixed(2) + 'K';
    return value.toFixed(2);
  }

  formatPrice(price: number): string {
    if (price >= 1000) return price.toLocaleString('en-US', { maximumFractionDigits: 2 });
    if (price >= 1)    return price.toFixed(4);
    return price.toFixed(6);
  }

  formatRealized(): string {
    const s = this.status();
    if (!s) return '—';
    const unrealized = this.positions().reduce((sum, p) => sum + p.unrealized_pnl, 0);
    const realized = s.pnl - unrealized;
    const sign = realized >= 0 ? '+' : '';
    return sign + '$' + Math.abs(realized).toFixed(2);
  }

  formatUnrealized(): string {
    const unrealized = this.positions().reduce((sum, p) => sum + p.unrealized_pnl, 0);
    const sign = unrealized >= 0 ? '+' : '';
    return sign + '$' + Math.abs(unrealized).toFixed(2);
  }

  formatSignedDollar(value: number): string {
    const sign = value >= 0 ? '+' : '';
    return sign + '$' + Math.abs(value).toFixed(2);
  }

  formatLastTrade(ts: string | null): string {
    if (!ts) return 'None';
    try {
      const date = new Date(ts);
      const now  = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMin = Math.floor(diffMs / 60_000);
      if (diffMin < 1)   return 'Just now';
      if (diffMin < 60)  return `${diffMin}m ago`;
      const diffH = Math.floor(diffMin / 60);
      if (diffH < 24)    return `${diffH}h ago`;
      return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
    } catch {
      return ts;
    }
  }
}
