import {
  Component, OnInit, inject, signal, computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ApiService, EarlyScannerAlert, EarlyScannerStats, SignalComboStats,
} from '../../services/api.service';

@Component({
  selector: 'app-early-scanner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="es-root">

      <!-- Header -->
      <div class="engine-tab">
        <span class="engine-dot" [class.active]="stats()?.running" [class.idle]="!stats()?.running"></span>
        <span class="engine-name">Early Momentum Scanner</span>
        <span class="engine-tag" [class.running]="stats()?.running" [class.idle]="!stats()?.running">
          {{ stats()?.running ? 'SCANNING' : 'IDLE' }}
        </span>
        <span class="last-run" *ngIf="stats()?.last_run">Last: {{ timeAgo(stats()!.last_run!) }}</span>
        <button class="scan-btn" (click)="triggerScan()" [disabled]="scanning()">
          {{ scanning() ? 'Scanning...' : 'Scan Now' }}
        </button>
      </div>

      <!-- Stats bar -->
      <div class="stats-bar">
        <div class="stat-item">
          <span class="stat-value">{{ stats()?.alerts_24h ?? 0 }}</span>
          <span class="stat-label">Alerts (24h)</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <span class="stat-value">{{ stats()?.total_alerts ?? 0 }}</span>
          <span class="stat-label">Total</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <span class="stat-value" [class.pos]="(stats()?.hit_rate ?? 0) >= 60" [class.warn]="(stats()?.hit_rate ?? 0) > 0 && (stats()?.hit_rate ?? 0) < 60">
            {{ stats()?.hit_rate ?? 0 }}%
          </span>
          <span class="stat-label">Hit Rate (3%+ peak)</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <span class="stat-value">{{ stats()?.evaluated ?? 0 }}</span>
          <span class="stat-label">Evaluated</span>
        </div>
      </div>

      <!-- Signal Performance (collapsible) -->
      @if (comboStats().length > 0) {
        <div class="combo-section">
          <div class="combo-header" (click)="comboExpanded.set(!comboExpanded())">
            <span class="section-header-text">Signal Performance</span>
            <span class="combo-toggle">{{ comboExpanded() ? '▼' : '▶' }}</span>
          </div>
          @if (comboExpanded()) {
            <div class="combo-table-wrap">
              <table class="combo-table">
                <thead>
                  <tr>
                    <th class="left">Combo</th>
                    <th>Alerts</th>
                    <th>Win%</th>
                    <th>Avg Peak</th>
                    <th>Score Adj</th>
                  </tr>
                </thead>
                <tbody>
                  @for (c of comboStats(); track c.combo) {
                    <tr>
                      <td class="left">{{ c.combo_display }}</td>
                      <td class="center">{{ c.total }}</td>
                      <td class="center" [class.pos]="c.win_rate >= 60" [class.warn]="c.win_rate >= 35 && c.win_rate < 60" [class.neg]="c.win_rate < 35">
                        {{ c.win_rate.toFixed(0) }}%
                      </td>
                      <td class="center" [class.pos]="c.avg_peak_pct >= 3" [class.warn]="c.avg_peak_pct > 0 && c.avg_peak_pct < 3">
                        +{{ c.avg_peak_pct.toFixed(1) }}%
                      </td>
                      <td class="center">
                        @if (c.score_adj > 0) {
                          <span class="adj-badge pos">+{{ c.score_adj }}</span>
                        } @else if (c.score_adj < 0) {
                          <span class="adj-badge neg">{{ c.score_adj }}</span>
                        } @else {
                          <span class="adj-none">0</span>
                        }
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
              <div class="combo-footer">Win = peaked 3%+ within 12h. Score adjustments after 10+ samples.</div>
            </div>
          }
        </div>
      }

      <!-- How it works -->
      <div class="info-box">
        <div class="info-title">How it works</div>
        <div class="info-text">
          Scans all Coinbase USD pairs every ~10 min for early momentum signals. Requires 2+ signals to fire:
          <strong>Volume spike</strong> (2.5x avg + price rising),
          <strong>72h breakout</strong> (new high + momentum),
          <strong>Reversal</strong> (flat-to-up),
          <strong>Strong move</strong> (5%+ in 3h).
          Alerts sent to Discord for manual trading. Signal combos auto-adjust scores based on win rates.
        </div>
      </div>

      <!-- Filter tabs + Alerts list -->
      <div class="alerts-section">
        <div class="alerts-header-row">
          <div class="section-header">Recent Alerts</div>
          <div class="filter-tabs">
            <button class="filter-tab" [class.active]="filterMode() === 'high'" (click)="filterMode.set('high')">
              High Confidence ({{ highConfCount() }})
            </button>
            <button class="filter-tab" [class.active]="filterMode() === 'all'" (click)="filterMode.set('all')">
              All ({{ alerts().length }})
            </button>
          </div>
        </div>

        @if (filteredAlerts().length === 0) {
          <div class="empty-state">
            No alerts yet. Hit "Scan Now" or wait for the scanner to detect early moves.
          </div>
        }

        @for (alert of filteredAlerts(); track alert.id) {
          <div class="alert-card" [class.high-score]="alert.effective_score >= 3">
            <div class="alert-header">
              <span class="alert-pair">{{ coinName(alert.pair) }}</span>
              <span class="alert-score">
                @for (i of scoreArray(alert.score); track i) {
                  <span class="score-dot filled"></span>
                }
                @for (i of scoreArray(4 - alert.score); track i) {
                  <span class="score-dot"></span>
                }
                @if (alert.score_adj > 0) {
                  <span class="score-adj-label pos">+{{ alert.score_adj }}</span>
                } @else if (alert.score_adj < 0) {
                  <span class="score-adj-label neg">{{ alert.score_adj }}</span>
                }
              </span>
              <span class="alert-price">\${{ formatPrice(alert.price) }}</span>
              <span class="alert-time">{{ timeAgo(alert.timestamp) }}</span>
            </div>

            <!-- Checkpoint timeline -->
            <div class="checkpoint-row">
              <span class="cp-badge" [class.pos]="(alert.outcome_1h_pct ?? 0) > 0" [class.neg]="(alert.outcome_1h_pct ?? 0) < 0" [class.pending]="alert.outcome_1h_pct === null">
                {{ alert.outcome_1h_pct !== null ? '1h ' + formatPct(alert.outcome_1h_pct) : '1h ...' }}
              </span>
              <span class="cp-arrow">&#8250;</span>
              <span class="cp-badge" [class.pos]="(alert.outcome_4h_pct ?? 0) > 0" [class.neg]="(alert.outcome_4h_pct ?? 0) < 0" [class.pending]="alert.outcome_4h_pct === null">
                {{ alert.outcome_4h_pct !== null ? '4h ' + formatPct(alert.outcome_4h_pct) : '4h ...' }}
              </span>
              <span class="cp-arrow">&#8250;</span>
              <span class="cp-badge peak" [class.pos]="(alert.outcome_peak_pct ?? 0) >= 3" [class.pending]="alert.outcome_peak_pct === null">
                {{ alert.outcome_peak_pct !== null ? 'Pk ' + formatPct(alert.outcome_peak_pct) : 'Pk ...' }}
              </span>
              <span class="cp-arrow">&#8250;</span>
              <span class="cp-badge" [class.pos]="(alert.outcome_12h_pct ?? 0) > 0" [class.neg]="(alert.outcome_12h_pct ?? 0) < 0" [class.pending]="alert.outcome_12h_pct === null">
                {{ alert.outcome_12h_pct !== null ? '12h ' + formatPct(alert.outcome_12h_pct) : '12h ...' }}
              </span>
              <span class="verdict-badge" [class.win]="isWin(alert)" [class.loss]="isLoss(alert)" [class.pending]="isPending(alert)">
                {{ getVerdict(alert) }}
              </span>
            </div>

            <div class="alert-details">
              <span class="vol-badge">Vol: \${{ formatVol(alert.volume_24h) }}</span>
            </div>
            <div class="alert-signals">
              @for (sig of alert.signals; track sig) {
                <span class="signal-tag">{{ formatSignal(sig) }}</span>
              }
              @if (alert.notified) {
                <span class="discord-badge">Discord sent</span>
              }
            </div>
          </div>
        }
      </div>

    </div>
  `,
  styles: [`
    .es-root {
      background: #0f1117;
      color: #e2e8f0;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      min-height: 100%;
    }

    /* Header */
    .engine-tab {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 20px;
      background: linear-gradient(90deg, rgba(56,189,248,0.08) 0%, transparent 100%);
      border-bottom: 1px solid rgba(56,189,248,0.3);
      flex-wrap: wrap;
    }
    .engine-dot {
      width: 8px; height: 8px; border-radius: 50%;
      animation: pulse 2s ease-in-out infinite;
    }
    .engine-dot.active { background: #4ade80; box-shadow: 0 0 6px rgba(74,222,128,0.4); }
    .engine-dot.idle { background: #38bdf8; box-shadow: 0 0 6px rgba(56,189,248,0.3); }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
    .engine-name {
      font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; color: #38bdf8;
    }
    .engine-tag {
      font-size: 9px; font-weight: 700; letter-spacing: 0.06em;
      padding: 2px 8px; border-radius: 4px; text-transform: uppercase;
    }
    .engine-tag.running { background: rgba(74,222,128,0.12); color: #4ade80; }
    .engine-tag.idle { background: rgba(56,189,248,0.1); color: #38bdf8; }
    .last-run {
      margin-left: auto; font-size: 10px; color: #6b7280;
      font-family: 'JetBrains Mono', monospace;
    }
    .scan-btn {
      padding: 4px 14px; font-size: 10px; font-weight: 700;
      background: rgba(56,189,248,0.1); color: #38bdf8;
      border: 1px solid rgba(56,189,248,0.3); border-radius: 4px;
      cursor: pointer; transition: all 0.15s; text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .scan-btn:hover:not(:disabled) { background: rgba(56,189,248,0.2); border-color: #38bdf8; }
    .scan-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Stats bar */
    .stats-bar {
      display: flex; align-items: center; justify-content: center;
      gap: 0; padding: 14px 16px;
      background: linear-gradient(180deg, #141621 0%, #0f1117 100%);
      border-bottom: 1px solid #2d3148; flex-wrap: wrap;
    }
    .stat-item { display: flex; flex-direction: column; align-items: center; padding: 0 20px; }
    .stat-value {
      font-size: 20px; font-weight: 700; color: #f1f5f9;
      font-family: 'JetBrains Mono', monospace;
    }
    .stat-value.pos { color: #4ade80; }
    .stat-value.warn { color: #fbbf24; }
    .stat-label { font-size: 10px; font-weight: 500; color: #6b7280; margin-top: 2px; }
    .stat-divider { width: 1px; height: 28px; background: #2d3148; }

    /* Combo performance section */
    .combo-section {
      margin: 12px 16px 0;
    }
    .combo-header {
      display: flex; align-items: center; gap: 6px; cursor: pointer; margin-bottom: 8px;
    }
    .section-header-text {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: #38bdf8;
    }
    .combo-toggle { font-size: 9px; color: #38bdf8; }
    .combo-table-wrap {
      background: rgba(30,33,48,0.5); border: 1px solid #2d3148; border-radius: 8px; overflow: hidden;
    }
    .combo-table {
      width: 100%; border-collapse: collapse; font-size: 10px;
      font-family: 'JetBrains Mono', monospace;
    }
    .combo-table th {
      padding: 7px 10px; color: #6b7280; font-weight: 600;
      border-bottom: 1px solid #2d3148; text-align: center;
    }
    .combo-table th.left { text-align: left; }
    .combo-table td { padding: 5px 10px; color: #e2e8f0; }
    .combo-table td.center { text-align: center; }
    .combo-table td.left { text-align: left; }
    .combo-table td.pos { color: #4ade80; font-weight: 700; }
    .combo-table td.warn { color: #fbbf24; font-weight: 700; }
    .combo-table td.neg { color: #f87171; font-weight: 700; }
    .combo-table tr + tr { border-top: 1px solid rgba(45,49,72,0.5); }
    .adj-badge {
      padding: 1px 6px; border-radius: 3px; font-weight: 700; font-size: 10px;
    }
    .adj-badge.pos { background: rgba(74,222,128,0.15); color: #4ade80; }
    .adj-badge.neg { background: rgba(248,113,113,0.15); color: #f87171; }
    .adj-none { color: #94a3b8; }
    .combo-footer {
      font-size: 8px; color: #4b5563; font-style: italic; padding: 4px 10px 6px;
    }

    /* Info box */
    .info-box {
      margin: 12px 16px; padding: 10px 14px; border-radius: 6px;
      background: rgba(56,189,248,0.05); border: 1px solid rgba(56,189,248,0.15);
    }
    .info-title { font-size: 10px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
    .info-text { font-size: 11px; color: #94a3b8; line-height: 1.5; }
    .info-text strong { color: #e2e8f0; }

    /* Alerts section */
    .alerts-section { padding: 12px 16px; }
    .alerts-header-row {
      display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap;
    }
    .section-header {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: #94a3b8;
    }
    .filter-tabs { display: flex; gap: 0; }
    .filter-tab {
      padding: 3px 10px; font-size: 9px; font-weight: 700;
      background: rgba(56,189,248,0.08); color: #64748b;
      border: 1px solid #2d3148; cursor: pointer; transition: all 0.15s;
    }
    .filter-tab:first-child { border-radius: 4px 0 0 4px; }
    .filter-tab:last-child { border-radius: 0 4px 4px 0; border-left: 0; }
    .filter-tab.active {
      background: rgba(74,222,128,0.15); color: #4ade80;
      border-color: rgba(74,222,128,0.3);
    }
    .empty-state {
      text-align: center; padding: 32px 16px; color: #6b7280;
      font-size: 12px; font-style: italic;
    }

    /* Alert card */
    .alert-card {
      background: rgba(30,33,48,0.7); border: 1px solid #2d3148;
      border-radius: 8px; padding: 12px 14px; margin-bottom: 8px;
      transition: border-color 0.15s;
    }
    .alert-card:hover { border-color: rgba(56,189,248,0.3); }
    .alert-card.high-score { border-color: rgba(74,222,128,0.3); }
    .alert-header {
      display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
      flex-wrap: wrap;
    }
    .alert-pair {
      font-size: 15px; font-weight: 700; color: #f1f5f9;
      font-family: 'JetBrains Mono', monospace;
    }
    .alert-score { display: flex; gap: 3px; align-items: center; }
    .score-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: #2d3148; border: 1px solid #4b5563;
    }
    .score-dot.filled { background: #38bdf8; border-color: #38bdf8; box-shadow: 0 0 4px rgba(56,189,248,0.4); }
    .score-adj-label {
      font-size: 7px; font-weight: 700; margin-left: 2px;
    }
    .score-adj-label.pos { color: #4ade80; }
    .score-adj-label.neg { color: #f87171; }
    .alert-price {
      font-size: 12px; color: #94a3b8;
      font-family: 'JetBrains Mono', monospace;
    }
    .alert-time {
      margin-left: auto; font-size: 10px; color: #6b7280;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Checkpoint timeline */
    .checkpoint-row {
      display: flex; gap: 3px; margin-bottom: 6px; align-items: center; flex-wrap: wrap;
    }
    .cp-badge {
      font-size: 9px; font-weight: 600; padding: 2px 5px; border-radius: 3px;
      font-family: 'JetBrains Mono', monospace;
      background: rgba(100,116,139,0.1); color: #94a3b8;
    }
    .cp-badge.pos { background: rgba(74,222,128,0.1); color: #4ade80; }
    .cp-badge.neg { background: rgba(248,113,113,0.1); color: #f87171; }
    .cp-badge.pending { color: #4b5563; font-style: italic; }
    .cp-badge.peak { font-weight: 700; }
    .cp-badge.peak.pos { background: rgba(74,222,128,0.2); border: 1px solid rgba(74,222,128,0.25); }
    .cp-arrow { font-size: 8px; color: #4b5563; }
    .verdict-badge {
      margin-left: auto; font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 4px;
    }
    .verdict-badge.win { background: rgba(74,222,128,0.2); color: #4ade80; }
    .verdict-badge.loss { background: rgba(248,113,113,0.15); color: #f87171; }
    .verdict-badge.pending { background: rgba(100,116,139,0.1); color: #6b7280; font-style: italic; }

    /* Details row */
    .alert-details { display: flex; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
    .vol-badge {
      font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
      background: rgba(167,139,250,0.1); color: #a78bfa;
    }

    /* Signals */
    .alert-signals { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
    .signal-tag {
      font-size: 9px; font-weight: 600; padding: 2px 7px; border-radius: 3px;
      background: rgba(56,189,248,0.08); color: #38bdf8;
      border: 1px solid rgba(56,189,248,0.15);
    }

    /* Discord badge */
    .discord-badge {
      font-size: 8px; font-weight: 700; padding: 1px 6px; border-radius: 3px;
      background: rgba(88,101,242,0.12); color: #7c85e8;
      text-transform: uppercase; letter-spacing: 0.05em;
    }

    /* Responsive */
    @media (max-width: 600px) {
      .stats-bar { gap: 4px; padding: 10px 8px; }
      .stat-item { padding: 0 12px; }
      .stat-value { font-size: 16px; }
      .alert-pair { font-size: 13px; }
    }
  `],
})
export class EarlyScannerComponent implements OnInit {
  private api = inject(ApiService);

  readonly alerts = signal<EarlyScannerAlert[]>([]);
  readonly stats = signal<EarlyScannerStats | null>(null);
  readonly scanning = signal(false);
  readonly filterMode = signal<'high' | 'all'>('high');
  readonly comboExpanded = signal(true);

  readonly comboStats = computed(() => this.stats()?.combo_stats ?? []);

  readonly highConfCount = computed(() =>
    this.alerts().filter(a => a.effective_score >= 3).length
  );

  readonly filteredAlerts = computed(() => {
    const all = this.alerts();
    if (this.filterMode() === 'high') {
      return all.filter(a => a.effective_score >= 3);
    }
    return all;
  });

  private _pollId: any;

  ngOnInit() {
    this.refresh();
    this._pollId = setInterval(() => this.refresh(), 30_000);
  }

  ngOnDestroy() {
    if (this._pollId) clearInterval(this._pollId);
  }

  refresh() {
    this.api.fetchEarlyScannerAlerts(50).subscribe({
      next: (data) => this.alerts.set(data),
      error: () => {},
    });
    this.api.fetchEarlyScannerStats().subscribe({
      next: (data) => this.stats.set(data),
      error: () => {},
    });
  }

  triggerScan() {
    this.scanning.set(true);
    this.api.triggerEarlyScan().subscribe({
      next: () => {
        const poll = setInterval(() => {
          this.api.fetchEarlyScannerStats().subscribe({
            next: (s) => {
              this.stats.set(s);
              if (!s.running) {
                this.scanning.set(false);
                clearInterval(poll);
                this.refresh();
              }
            },
          });
        }, 3000);
        setTimeout(() => { this.scanning.set(false); clearInterval(poll); }, 120_000);
      },
      error: () => this.scanning.set(false),
    });
  }

  coinName(pair: string): string {
    return pair.replace('-USD', '');
  }

  formatPrice(price: number): string {
    if (price >= 1000) return price.toFixed(2);
    if (price >= 1) return price.toFixed(4);
    return price.toFixed(6);
  }

  formatVol(vol: number): string {
    if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(1) + 'M';
    if (vol >= 1000) return (vol / 1000).toFixed(0) + 'K';
    return vol.toFixed(0);
  }

  formatPct(val: number): string {
    return (val > 0 ? '+' : '') + val.toFixed(1) + '%';
  }

  formatSignal(sig: string): string {
    const tag = sig.split(' ')[0];
    const labels: Record<string, string> = {
      'vol_spike': 'Volume Spike',
      '72h_breakout': '72h Breakout',
      'mom_reversal': 'Reversal',
      'strong_move': 'Strong Move',
      'accumulation': 'Accumulation',
      'bottom_bounce': 'Bottom Bounce',
      'squeeze': 'Squeeze',
    };
    return labels[tag] || tag;
  }

  timeAgo(ts: string): string {
    const diff = (Date.now() - new Date(ts).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  }

  scoreArray(n: number): number[] {
    return Array.from({ length: Math.max(0, n) }, (_, i) => i);
  }

  isWin(alert: EarlyScannerAlert): boolean {
    return alert.outcome_peak_pct !== null && alert.outcome_peak_pct >= 3;
  }

  isLoss(alert: EarlyScannerAlert): boolean {
    return alert.outcome_12h_pct !== null && alert.outcome_peak_pct !== null && alert.outcome_peak_pct < 3;
  }

  isPending(alert: EarlyScannerAlert): boolean {
    return alert.outcome_peak_pct === null;
  }

  getVerdict(alert: EarlyScannerAlert): string {
    if (this.isWin(alert)) return 'WIN';
    if (this.isLoss(alert)) return 'LOSS';
    return 'pending';
  }
}
