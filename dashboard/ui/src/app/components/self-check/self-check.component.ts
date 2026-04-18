import { Component, OnInit, OnDestroy, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import { ApiService, SelfCheckData, fmt12Hour } from '../../services/api.service';

@Component({
  selector: 'app-self-check',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="sc-container">
      <div class="header-row">
        <div class="title-group">
          <h2 class="title">Self-Check</h2>
          <span class="subtitle">Bot health monitoring &middot; accuracy &middot; safety rails</span>
        </div>
      </div>

      <!-- Trading Pause Banner -->
      <div class="pause-banner" *ngIf="isPaused()">
        <div class="pause-icon">!!</div>
        <div class="pause-text">{{ pauseReason() }}</div>
        <div class="pause-since">Since {{ fmt12Hour(pauseSince(), {date: true}) }}</div>
      </div>

      <!-- Top Cards Row -->
      <div class="cards-row">
        <div class="card">
          <span class="card-label">Daily P&amp;L</span>
          <div class="card-value" [style.color]="pnlColor(dailyPnl())">
            {{ dailyPnl() >= 0 ? '+$' : '-$' }}{{ absPnl(dailyPnl()) | number:'1.2-2' }}
          </div>
        </div>

        <div class="card">
          <span class="card-label">Streak</span>
          <div class="card-value" [style.color]="streakColor()">
            {{ streakDays() }} {{ streakType() }} days
          </div>
        </div>

        <div class="card">
          <span class="card-label">Vol Accuracy (24h)</span>
          <div class="card-value" [style.color]="accuracyColor(volErr24h())">
            {{ volErr24h() | number:'1.1-1' }}% avg error
          </div>
          <div class="card-sub">{{ volCount24h() }} checks</div>
        </div>

        <div class="card">
          <span class="card-label">Vol Accuracy (7d)</span>
          <div class="card-value" [style.color]="accuracyColor(volErr7d())">
            {{ volErr7d() | number:'1.1-1' }}% avg error
          </div>
          <div class="card-sub">{{ volCount7d() }} checks</div>
        </div>
      </div>

      <!-- Grid Performance by Spacing -->
      <div class="section" *ngIf="gridPerf().length">
        <span class="section-title">Grid Performance by Vol Regime</span>
        <table class="perf-table">
          <thead>
            <tr>
              <th>Regime</th>
              <th>Avg Spacing</th>
              <th>Spacing Mult</th>
              <th>Cycles</th>
              <th>Total P&amp;L</th>
              <th>Avg P&amp;L/Cycle</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let r of gridPerf()">
              <td>
                <span class="regime-badge" [class]="'regime-' + r.vol_regime">
                  {{ r.vol_regime }}
                </span>
              </td>
              <td>{{ r.avg_spacing_pct | number:'1.2-2' }}%</td>
              <td>{{ r.avg_spacing_mult | number:'1.2-2' }}x</td>
              <td>{{ r.cycles }}</td>
              <td [style.color]="pnlColor(r.total_pnl)">
                {{ r.total_pnl >= 0 ? '+' : '' }}{{ r.total_pnl | number:'1.2-2' }}
              </td>
              <td [style.color]="pnlColor(r.avg_pnl)">
                {{ r.avg_pnl >= 0 ? '+' : '' }}{{ r.avg_pnl | number:'1.4-4' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Auto-Adjustment Events -->
      <div class="section" *ngIf="events().length">
        <span class="section-title">Auto-Adjustments &amp; Events</span>
        <div class="event-list">
          <div class="event-item" *ngFor="let e of events()">
            <span class="event-badge" [class]="'event-' + eventCategory(e.event_type)">
              {{ e.event_type }}
            </span>
            <span class="event-details">{{ e.details }}</span>
            <span class="event-time">{{ fmt12Hour(e.timestamp, {date: true}) }}</span>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div class="empty-state" *ngIf="!gridPerf().length && !events().length && !loading()">
        <div class="empty-icon">check</div>
        <div class="empty-text">No self-check data yet</div>
        <div class="empty-hint">
          Data will appear after the bot runs for a few hours.
          Volatility accuracy checks run every 12 hours.
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; font-family: 'Inter', 'Segoe UI', sans-serif; color: #e2e8f0; }
    .sc-container { max-width: 1100px; margin: 0 auto; padding: 20px 0; }

    .header-row {
      display: flex; align-items: flex-end; justify-content: space-between;
      flex-wrap: wrap; gap: 12px; margin-bottom: 20px;
    }
    .title-group { display: flex; flex-direction: column; gap: 2px; }
    .title {
      margin: 0; font-size: 1.6rem; font-weight: 700;
      background: linear-gradient(90deg, #fbbf24, #f59e0b);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .subtitle { font-size: 0.8rem; color: #6b7280; }

    .pause-banner {
      background: #451a03; border: 1px solid #92400e; border-radius: 12px;
      padding: 16px 20px; margin-bottom: 18px; display: flex;
      align-items: center; gap: 14px;
    }
    .pause-icon { font-size: 1.4rem; font-weight: 800; color: #f87171; }
    .pause-text { font-size: 0.95rem; font-weight: 600; color: #fbbf24; flex: 1; }
    .pause-since { font-size: 0.78rem; color: #92400e; }

    .cards-row { display: flex; gap: 14px; margin-bottom: 18px; flex-wrap: wrap; }
    .card {
      background: #242736; border: 1px solid #2d3148; border-radius: 12px;
      padding: 16px; flex: 1; min-width: 180px;
    }
    .card-label {
      font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; color: #6b7280; display: block; margin-bottom: 6px;
    }
    .card-value { font-size: 1.5rem; font-weight: 800; }
    .card-sub { font-size: 0.72rem; color: #4b5563; margin-top: 4px; }

    .section {
      background: #242736; border: 1px solid #2d3148; border-radius: 14px;
      padding: 18px; margin-bottom: 18px;
    }
    .section-title {
      font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; color: #6b7280; display: block; margin-bottom: 12px;
    }

    .perf-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    .perf-table th {
      text-align: left; padding: 8px 10px; color: #6b7280; font-weight: 600;
      text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.05em;
      border-bottom: 1px solid #2d3148;
    }
    .perf-table td {
      padding: 8px 10px; border-bottom: 1px solid #1a1d29; color: #9ca3af;
    }

    .regime-badge {
      font-size: 0.65rem; padding: 2px 6px; border-radius: 4px;
      font-weight: 700; text-transform: uppercase;
    }
    .regime-low { background: #1a3a2a; color: #4ade80; }
    .regime-normal { background: #1e293b; color: #94a3b8; }
    .regime-high { background: #451a03; color: #fbbf24; }
    .regime-extreme { background: #450a0a; color: #f87171; }
    .regime-unknown { background: #1e293b; color: #6b7280; }

    .event-list { display: flex; flex-direction: column; gap: 8px; }
    .event-item {
      display: flex; align-items: center; gap: 10px; padding: 8px 0;
      border-bottom: 1px solid #1a1d29;
    }
    .event-badge {
      font-size: 0.65rem; padding: 3px 8px; border-radius: 4px;
      font-weight: 700; text-transform: uppercase; white-space: nowrap;
    }
    .event-retrain { background: #1e3a5f; color: #60a5fa; }
    .event-pause { background: #451a03; color: #fbbf24; }
    .event-other { background: #1e293b; color: #94a3b8; }
    .event-details { font-size: 0.82rem; color: #9ca3af; flex: 1; }
    .event-time { font-size: 0.72rem; color: #4b5563; white-space: nowrap; }

    .empty-state {
      text-align: center; padding: 60px 20px;
      background: #242736; border: 1px solid #2d3148; border-radius: 14px;
    }
    .empty-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3; }
    .empty-text { font-size: 1.1rem; font-weight: 600; color: #6b7280; margin-bottom: 6px; }
    .empty-hint { font-size: 0.82rem; color: #4b5563; max-width: 400px; margin: 0 auto; }
  `],
})
export class SelfCheckComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private sub: Subscription | null = null;

  protected fmt12Hour = fmt12Hour;

  data = signal<SelfCheckData | null>(null);
  loading = signal(false);

  // Computed accessors to avoid ?? in templates
  isPaused = computed(() => this.data()?.trading_paused?.paused || false);
  pauseReason = computed(() => this.data()?.trading_paused?.reason || '');
  pauseSince = computed(() => this.data()?.trading_paused?.since || '');
  dailyPnl = computed(() => this.data()?.daily_pnl || 0);
  streakDays = computed(() => this.data()?.streak?.days || 0);
  streakType = computed(() => this.data()?.streak?.type || 'none');
  volErr24h = computed(() => this.data()?.vol_accuracy_24h?.avg_error_pct || 0);
  volCount24h = computed(() => this.data()?.vol_accuracy_24h?.count || 0);
  volErr7d = computed(() => this.data()?.vol_accuracy_7d?.avg_error_pct || 0);
  volCount7d = computed(() => this.data()?.vol_accuracy_7d?.count || 0);
  gridPerf = computed(() => this.data()?.grid_performance || []);
  events = computed(() => this.data()?.events || []);

  ngOnInit() { this.startPolling(); }
  ngOnDestroy() { this.sub?.unsubscribe(); }

  absPnl(v: number): number { return Math.abs(v); }

  pnlColor(pnl: number): string {
    if (pnl > 0) return '#4ade80';
    if (pnl < 0) return '#f87171';
    return '#94a3b8';
  }

  streakColor(): string {
    const t = this.streakType();
    return t === 'winning' ? '#4ade80' : t === 'losing' ? '#f87171' : '#94a3b8';
  }

  accuracyColor(errorPct: number): string {
    if (errorPct <= 20) return '#4ade80';
    if (errorPct <= 50) return '#fbbf24';
    return '#f87171';
  }

  eventCategory(type: string): string {
    if (type.includes('retrain')) return 'retrain';
    if (type.includes('pause') || type.includes('loss')) return 'pause';
    return 'other';
  }

  private startPolling() {
    this.sub = interval(60_000).pipe(
      startWith(0),
      switchMap(() => {
        this.loading.set(true);
        return this.api.fetchSelfCheck();
      }),
    ).subscribe({
      next: (d) => {
        this.data.set(d);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
