import {
  Component, OnInit, inject, signal, computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ApiService, EarlyScannerAlert, EarlyScannerStats,
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
          <span class="stat-label">Total Alerts</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <span class="stat-value" [class.pos]="(stats()?.win_rate ?? 0) >= 60" [class.warn]="(stats()?.win_rate ?? 0) > 0 && (stats()?.win_rate ?? 0) < 60">
            {{ stats()?.win_rate ?? 0 }}%
          </span>
          <span class="stat-label">Win Rate (12h)</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <span class="stat-value">{{ stats()?.evaluated ?? 0 }}</span>
          <span class="stat-label">Evaluated</span>
        </div>
      </div>

      <!-- How it works -->
      <div class="info-box">
        <div class="info-title">How it works</div>
        <div class="info-text">
          Scans all Coinbase USD pairs every ~10 min for early momentum signals. Requires 2+ signals to fire:
          <strong>Volume spike</strong> (2.5x avg + price rising),
          <strong>72h breakout</strong> (new high + momentum),
          <strong>Reversal</strong> (flat-to-up),
          <strong>Strong move</strong> (5%+ in 3h).
          Alerts sent to Discord for manual trading.
        </div>
      </div>

      <!-- Alerts list -->
      <div class="alerts-section">
        <div class="section-header">Recent Alerts</div>

        @if (alerts().length === 0) {
          <div class="empty-state">
            No alerts yet. Hit "Scan Now" or wait for the scanner to detect early moves.
          </div>
        }

        @for (alert of alerts(); track alert.id) {
          <div class="alert-card" [class.high-score]="alert.score >= 3">
            <div class="alert-header">
              <span class="alert-pair">{{ coinName(alert.pair) }}</span>
              <span class="alert-score">
                @for (i of scoreArray(alert.score); track i) {
                  <span class="score-dot filled"></span>
                }
                @for (i of scoreArray(4 - alert.score); track i) {
                  <span class="score-dot"></span>
                }
              </span>
              <span class="alert-price">\${{ formatPrice(alert.price) }}</span>
              <span class="alert-time">{{ timeAgo(alert.timestamp) }}</span>
            </div>
            <div class="alert-changes">
              <span class="change-badge" [class.pos]="alert.change_1h_pct > 0" [class.neg]="alert.change_1h_pct < 0">
                1h: {{ alert.change_1h_pct > 0 ? '+' : '' }}{{ alert.change_1h_pct.toFixed(1) }}%
              </span>
              <span class="change-badge" [class.pos]="alert.change_3h_pct > 0" [class.neg]="alert.change_3h_pct < 0">
                3h: {{ alert.change_3h_pct > 0 ? '+' : '' }}{{ alert.change_3h_pct.toFixed(1) }}%
              </span>
              <span class="vol-badge">Vol: \${{ formatVol(alert.volume_24h) }}</span>
              @if (alert.outcome_12h_pct !== null) {
                <span class="outcome-badge" [class.pos]="alert.outcome_12h_pct! > 0" [class.neg]="alert.outcome_12h_pct! <= 0">
                  12h: {{ alert.outcome_12h_pct! > 0 ? '+' : '' }}{{ alert.outcome_12h_pct!.toFixed(1) }}%
                </span>
              }
            </div>
            <div class="alert-signals">
              @for (sig of alert.signals; track sig) {
                <span class="signal-tag">{{ formatSignal(sig) }}</span>
              }
            </div>
            @if (alert.notified) {
              <span class="discord-badge">Discord sent</span>
            }
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
    .section-header {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: #94a3b8; margin-bottom: 10px;
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
    .alert-score { display: flex; gap: 3px; }
    .score-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: #2d3148; border: 1px solid #4b5563;
    }
    .score-dot.filled { background: #38bdf8; border-color: #38bdf8; box-shadow: 0 0 4px rgba(56,189,248,0.4); }
    .alert-price {
      font-size: 12px; color: #94a3b8;
      font-family: 'JetBrains Mono', monospace;
    }
    .alert-time {
      margin-left: auto; font-size: 10px; color: #6b7280;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Changes */
    .alert-changes { display: flex; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
    .change-badge, .vol-badge, .outcome-badge {
      font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
    }
    .change-badge { background: rgba(100,116,139,0.1); color: #94a3b8; }
    .change-badge.pos { background: rgba(74,222,128,0.1); color: #4ade80; }
    .change-badge.neg { background: rgba(248,113,113,0.1); color: #f87171; }
    .vol-badge { background: rgba(167,139,250,0.1); color: #a78bfa; }
    .outcome-badge { font-weight: 700; }
    .outcome-badge.pos { background: rgba(74,222,128,0.15); color: #4ade80; }
    .outcome-badge.neg { background: rgba(248,113,113,0.15); color: #f87171; }

    /* Signals */
    .alert-signals { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 4px; }
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

  private _pollId: any;

  ngOnInit() {
    this.refresh();
    this._pollId = setInterval(() => this.refresh(), 30_000); // refresh every 30s
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
        // Poll until done
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
        // Safety timeout
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

  formatSignal(sig: string): string {
    // Clean up the raw signal string for display
    const tag = sig.split(' ')[0];
    const detail = sig.includes('(') ? sig.slice(sig.indexOf('(')) : '';
    const labels: Record<string, string> = {
      'vol_spike': 'Volume Spike',
      '72h_breakout': '72h Breakout',
      'mom_reversal': 'Reversal',
      'strong_move': 'Strong Move',
    };
    return (labels[tag] || tag) + (detail ? ' ' + detail : '');
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
}
