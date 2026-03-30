import { Component, inject, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';

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

        <div class="stat-block">
          <span class="stat-label">P&amp;L</span>
          <ng-container *ngIf="status(); else dash1">
            <span class="stat-value" [class.positive]="status()!.pnl >= 0" [class.negative]="status()!.pnl < 0">
              {{ (status()!.pnl >= 0 ? '+' : '') + '$' + formatNumber(status()!.pnl) }}
            </span>
            <span class="stat-sub" [class.positive]="status()!.pnl_pct >= 0" [class.negative]="status()!.pnl_pct < 0">
              ({{ (status()!.pnl_pct >= 0 ? '+' : '') + status()!.pnl_pct.toFixed(2) + '%' }})
            </span>
          </ng-container>
          <ng-template #dash1><span class="stat-value">—</span></ng-template>
        </div>

        <div class="stat-divider"></div>

        <div class="stat-block">
          <span class="stat-label">POSITIONS</span>
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

        <div class="stat-block" *ngIf="status()">
          <span class="stat-label">LAST TRADE</span>
          <span class="stat-value mono">{{ formatLastTrade(status()!.last_trade_time) }}</span>
        </div>

        <div class="stat-divider" *ngIf="status()"></div>

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
  `],
})
export class StatsBarComponent {
  private readonly api = inject(ApiService);

  readonly status = this.api.status;
  readonly refreshCountdown = this.api.refreshCountdown;

  readonly activePairsCount = computed(() => {
    const s = this.status();
    return s ? s.pairs.length : 0;
  });

  regimeConfig(regime: string) {
    return REGIME_CONFIG[regime] ?? DEFAULT_REGIME;
  }

  shortPair(pair: string): string {
    // "BTC/USDT" -> "BTC", "ETH/USDT:USDT" -> "ETH"
    return pair.split('/')[0];
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
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      return ts;
    }
  }
}
