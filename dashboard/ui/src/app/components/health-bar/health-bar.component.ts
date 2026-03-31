import {
  Component, inject, signal, computed, OnInit, OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, SelfCheckData } from '../../services/api.service';

const DAILY_LIMIT = 30; // USD — configurable default

@Component({
  selector: 'app-health-bar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="hbar-root">

      <!-- Daily P&L vs limit -->
      <div class="hbar-item" [title]="'Daily P&L limit: -$' + dailyLimit">
        <span class="hbar-label">DAILY P&L</span>
        <span class="hbar-value" [style.color]="dailyPnlColor()">
          {{ dailyPnlText() }}
          <span class="hbar-limit">/ -{{ '$' + dailyLimit }}</span>
        </span>
      </div>

      <div class="hbar-divider"></div>

      <!-- Weekly P&L -->
      <div class="hbar-item">
        <span class="hbar-label">WEEKLY P&L</span>
        <span class="hbar-value" [class.positive]="weeklyPnlPositive()" [class.negative]="!weeklyPnlPositive()">
          {{ weeklyPnlText() }}
        </span>
      </div>

      <div class="hbar-divider"></div>

      <!-- Win/loss streak -->
      <div class="hbar-item">
        <span class="hbar-label">STREAK</span>
        <span class="hbar-value" [style.color]="streakColor()">
          {{ streakText() }}
        </span>
      </div>

      <div class="hbar-divider"></div>

      <!-- Vol accuracy -->
      <div class="hbar-item" [title]="'Avg vol prediction error (24h)'">
        <span class="hbar-label">VOL ACC</span>
        <span class="hbar-value" [style.color]="volAccColor()">
          {{ volAccText() }}
        </span>
      </div>

      <div class="hbar-divider"></div>

      <!-- Next refresh countdown -->
      <div class="hbar-item hbar-refresh" [class.urgent]="refreshCountdown() <= 10">
        <svg class="refresh-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
        <span class="hbar-label">REFRESH</span>
        <span class="hbar-value mono">{{ refreshCountdown() }}s</span>
      </div>

    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }

    .hbar-root {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 0;
      padding: 0 16px;
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 8px;
      min-height: 42px;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    .hbar-item {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
    }

    .hbar-divider {
      width: 1px;
      height: 24px;
      background: #2d3148;
      flex-shrink: 0;
    }

    .hbar-label {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.1em;
      color: #6b7280;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .hbar-value {
      font-size: 13px;
      font-weight: 600;
      color: #e2e8f0;
      white-space: nowrap;
    }

    .hbar-value.mono {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 12px;
    }

    .hbar-value.positive { color: #4ade80; }
    .hbar-value.negative { color: #f87171; }

    .hbar-limit {
      font-size: 10px;
      color: #6b7280;
      font-weight: 500;
      margin-left: 2px;
    }

    .hbar-refresh {
      margin-left: auto;
      color: #6b7280;
      transition: color 0.3s ease;
    }

    .hbar-refresh.urgent { color: #fbbf24; }
    .hbar-refresh.urgent .hbar-value { color: #fbbf24; }

    .refresh-icon {
      width: 12px;
      height: 12px;
      flex-shrink: 0;
    }
  `],
})
export class HealthBarComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);

  readonly dailyLimit = DAILY_LIMIT;
  readonly selfCheck  = signal<SelfCheckData | null>(null);
  readonly refreshCountdown = this.api.refreshCountdown;

  private readonly status = this.api.status;

  private _pollInterval: any;

  ngOnInit(): void {
    this.loadSelfCheck();
    this._pollInterval = setInterval(() => this.loadSelfCheck(), 60_000);
  }

  ngOnDestroy(): void {
    if (this._pollInterval) clearInterval(this._pollInterval);
  }

  private loadSelfCheck(): void {
    this.api.fetchSelfCheck().subscribe({
      next: (d) => this.selfCheck.set(d),
      error: () => {},
    });
  }

  readonly dailyPnl = computed(() => this.selfCheck()?.daily_pnl ?? null);

  readonly dailyPnlText = computed(() => {
    const v = this.dailyPnl();
    if (v === null) return '—';
    const sign = v >= 0 ? '+' : '';
    return sign + '$' + Math.abs(v).toFixed(2);
  });

  readonly dailyPnlColor = computed(() => {
    const v = this.dailyPnl();
    if (v === null) return '#6b7280';
    if (v <= -DAILY_LIMIT) return '#f87171';                   // breached
    if (v <= -(DAILY_LIMIT * 0.6)) return '#fbbf24';          // >60% of limit
    return '#4ade80';
  });

  readonly weeklyPnl = computed(() => this.selfCheck()?.weekly_pnl ?? null);

  readonly weeklyPnlPositive = computed(() => (this.weeklyPnl() ?? 0) >= 0);

  readonly weeklyPnlText = computed(() => {
    const v = this.weeklyPnl();
    if (v === null) return '—';
    const sign = v >= 0 ? '+' : '';
    return sign + '$' + Math.abs(v).toFixed(2);
  });

  readonly streakText = computed(() => {
    const sc = this.selfCheck();
    if (!sc?.streak) return '—';
    const { type, days } = sc.streak;
    if (type === 'win')  return `${days}W`;
    if (type === 'loss') return `${days}L`;
    return `${days} ${type}`;
  });

  readonly streakColor = computed(() => {
    const sc = this.selfCheck();
    if (!sc?.streak) return '#6b7280';
    return sc.streak.type === 'win' ? '#4ade80' : '#f87171';
  });

  readonly volAccText = computed(() => {
    const sc = this.selfCheck();
    const acc = sc?.vol_accuracy_24h;
    if (!acc || acc.count === 0) return '—';
    return acc.avg_error_pct.toFixed(1) + '%';
  });

  readonly volAccColor = computed(() => {
    const sc = this.selfCheck();
    const acc = sc?.vol_accuracy_24h;
    if (!acc || acc.count === 0) return '#6b7280';
    const err = acc.avg_error_pct;
    if (err <= 10) return '#4ade80';
    if (err <= 25) return '#fbbf24';
    return '#f87171';
  });
}
