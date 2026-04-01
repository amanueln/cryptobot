import {
  Component, inject, signal, computed, OnInit, OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, SelfCheckData } from '../../services/api.service';

const DAILY_LIMIT = 30;

@Component({
  selector: 'app-health-bar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="hbar-root">
      <div class="hbar-text" [style.color]="sentimentColor()">
        {{ summaryText() }}
      </div>
      <div class="hbar-refresh" [class.urgent]="refreshCountdown() <= 10">
        <svg class="refresh-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
        <span class="refresh-label">{{ refreshCountdown() }}s</span>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }

    .hbar-root {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 16px;
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 8px;
      min-height: 42px;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    .hbar-text {
      flex: 1;
      font-size: 12.5px;
      font-weight: 500;
      line-height: 1.5;
      color: #94a3b8;
    }

    .hbar-refresh {
      display: flex;
      align-items: center;
      gap: 4px;
      color: #6b7280;
      flex-shrink: 0;
      transition: color 0.3s ease;
    }

    .hbar-refresh.urgent { color: #fbbf24; }

    .refresh-icon {
      width: 12px;
      height: 12px;
      flex-shrink: 0;
    }

    .refresh-label {
      font-size: 11px;
      font-weight: 600;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
    }
  `],
})
export class HealthBarComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);

  readonly dailyLimit = DAILY_LIMIT;
  readonly selfCheck  = signal<SelfCheckData | null>(null);
  readonly refreshCountdown = this.api.refreshCountdown;

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

  readonly summaryText = computed(() => {
    const sc = this.selfCheck();

    // Use server summary if available
    if (sc?.summary) return sc.summary;

    // Client-side fallback
    if (!sc) return 'Loading health data...';

    const parts: string[] = [];

    // Daily P&L
    const daily = sc.daily_pnl ?? 0;
    if (daily >= 0) {
      parts.push(`Good day so far \u2014 up $${daily.toFixed(2)}, well within the $${DAILY_LIMIT} daily limit.`);
    } else if (daily > -DAILY_LIMIT * 0.6) {
      parts.push(`Down $${Math.abs(daily).toFixed(2)} today, but within normal range.`);
    } else {
      parts.push(`Rough day \u2014 down $${Math.abs(daily).toFixed(2)}. Approaching the $${DAILY_LIMIT} safety limit.`);
    }

    // Streak
    const streak = sc.streak;
    if (streak && streak.days > 0) {
      if (streak.type === 'winning') {
        parts.push(`${streak.days}-day winning streak!`);
      } else if (streak.type === 'losing') {
        parts.push(`${streak.days}-day losing streak \u2014 the bot will adjust if it continues.`);
      }
    }

    // Next scan
    const vol = sc.vol_accuracy_24h;
    if (vol && vol.count === 0) {
      parts.push('Volatility model is still learning.');
    } else if (vol && vol.avg_error_pct <= 10) {
      parts.push('Volatility predictions are accurate.');
    } else if (vol && vol.avg_error_pct > 25) {
      parts.push('Volatility model is still calibrating \u2014 using simple tracking for now.');
    }

    return parts.join(' ') || 'Everything is running normally.';
  });

  readonly sentimentColor = computed(() => {
    const sc = this.selfCheck();
    if (!sc) return '#6b7280';
    const daily = sc.daily_pnl ?? 0;
    if (daily <= -DAILY_LIMIT) return '#f87171';
    if (daily <= -(DAILY_LIMIT * 0.6)) return '#fbbf24';
    if (daily > 0) return '#4ade80';
    return '#94a3b8';
  });
}
