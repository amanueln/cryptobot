import { Component, OnInit, OnDestroy, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import { ApiService, PairScanData, PairScoreData, ScanProgressData, OrderBookCheck } from '../../services/api.service';

@Component({
  selector: 'app-pair-scanner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="scanner-container">
      <!-- Header -->
      <div class="header-row">
        <div class="title-group">
          <h2 class="title">Pair Scanner</h2>
          <span class="subtitle">Automatic pair discovery &middot; Coinbase USD markets</span>
        </div>
        <div class="scan-meta" *ngIf="latestScan() as scan">
          <span class="meta-badge">{{ scan.scan_type | uppercase }}</span>
          <span class="meta-time">{{ scan.timestamp | date:'MMM d, HH:mm' }}</span>
          <span class="meta-count">{{ scan.total_pairs_scanned }} pairs scanned</span>
        </div>
      </div>

      <!-- Scan Progress Bar -->
      <div class="progress-section" *ngIf="scanProgress().scanning">
        <div class="progress-header">
          <span class="progress-label">
            <span class="spinner"></span>
            Scanning Coinbase...
            {{ scanProgress().scanned }} / {{ scanProgress().total_pairs }} pairs
            ({{ scanPct() }}%)
          </span>
          <span class="progress-eta" *ngIf="scanProgress().estimated_remaining > 0">
            ~{{ scanProgress().estimated_remaining | number:'1.0-0' }}s remaining
          </span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" [style.width.%]="scanPct()"></div>
        </div>
      </div>

      <!-- Toast Notification -->
      <div class="toast-notification" *ngIf="toastMessage()" (click)="dismissToast()">
        {{ toastMessage() }}
      </div>

      <!-- Selected Pairs Cards -->
      <div class="selected-section" *ngIf="selectedPairs().length">
        <span class="section-title">Active Pairs</span>
        <div class="selected-row">
          <div class="selected-card" *ngFor="let p of selectedPairs()">
            <div class="sel-header">
              <span class="sel-pair">{{ p.pair }}</span>
              <span class="sel-score">{{ p.composite_score | number:'1.1-1' }}</span>
            </div>
            <div class="sel-stats">
              <div class="sel-stat">
                <span class="sl">Vol</span>
                <span class="sv">{{ p.volatility | number:'1.1-1' }}%</span>
              </div>
              <div class="sel-stat">
                <span class="sl">Range</span>
                <span class="sv">{{ p.range_bound | number:'1.0-0' }}%</span>
              </div>
              <div class="sel-stat">
                <span class="sl">Fee Clr</span>
                <span class="sv">{{ p.fee_clearance | number:'1.1-1' }}x</span>
              </div>
              <div class="sel-stat">
                <span class="sl">Liq</span>
                <span class="sv">{{ p.liquidity | number:'1.1-1' }}</span>
              </div>
            </div>
            <div class="sel-footer">
              <span class="regime-badge" [class]="'regime-' + p.regime">{{ p.regime }}</span>
              <span class="bt-pnl" [class.positive]="p.backtest_pnl >= 0" [class.negative]="p.backtest_pnl < 0">
                {{ formatPnl(p.backtest_pnl) }}
              </span>
            </div>
            <!-- Liquidity Risk Warning -->
            <div class="liq-warning" *ngIf="getLiqCheck(p.pair) as liq">
              <ng-container *ngIf="liq.low_liquidity">
                <div class="liq-badge danger">
                  <span class="liq-icon">!</span> LOW LIQUIDITY RISK
                </div>
                <div class="liq-details">
                  <span>Spread: {{ liq.spread_pct | number:'1.2-2' }}%</span>
                  <span>Bid depth: {{ formatDollar(liq.bid_depth_2pct) }}</span>
                  <span>Ask depth: {{ formatDollar(liq.ask_depth_2pct) }}</span>
                </div>
                <div class="liq-flags">
                  <span class="liq-flag" *ngFor="let f of liq.flags">{{ f }}</span>
                </div>
              </ng-container>
              <ng-container *ngIf="!liq.low_liquidity">
                <div class="liq-badge ok">
                  Liquidity OK &mdash; spread {{ liq.spread_pct | number:'1.2-2' }}%, depth {{ formatDollar(liq.bid_depth_2pct + liq.ask_depth_2pct) }}
                </div>
              </ng-container>
            </div>
          </div>
        </div>
      </div>

      <!-- Swap Events -->
      <div class="swaps-section" *ngIf="hasSwaps()">
        <span class="section-title">Recent Swaps</span>
        <div class="swap-event" *ngFor="let s of latestScan()!.swapped_out">
          <span class="swap-arrow out">OUT</span>
          <span class="swap-pair">{{ s.pair }}</span>
          <span class="swap-reason">{{ s.reason }}</span>
        </div>
        <div class="swap-event" *ngFor="let s of latestScan()!.swapped_in">
          <span class="swap-arrow in">IN</span>
          <span class="swap-pair">{{ s.pair }}</span>
          <span class="swap-reason">{{ s.reason }}</span>
        </div>
      </div>

      <!-- Ranked Table -->
      <div class="ranked-section" *ngIf="rankedPairs().length">
        <span class="section-title">All Scored Pairs ({{ rankedPairs().length }})</span>
        <table class="ranked-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Pair</th>
              <th>Score</th>
              <th>Vol%</th>
              <th>Range%</th>
              <th>Liq</th>
              <th>Fee Clr</th>
              <th>Regime</th>
              <th>BT P&L</th>
              <th>Price</th>
              <th>Vol 24h</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let p of rankedPairs(); let i = index"
                [class.active-row]="isSelected(p.pair)">
              <td>{{ i + 1 }}</td>
              <td class="pair-cell">{{ p.pair }}</td>
              <td class="score-cell">{{ p.composite_score | number:'1.1-1' }}</td>
              <td>{{ p.volatility | number:'1.1-1' }}%</td>
              <td>{{ p.range_bound | number:'1.0-0' }}%</td>
              <td>{{ p.liquidity | number:'1.1-1' }}</td>
              <td>{{ p.fee_clearance | number:'1.1-1' }}x</td>
              <td><span class="regime-badge small" [class]="'regime-' + p.regime">{{ p.regime }}</span></td>
              <td [class.positive]="p.backtest_pnl >= 0" [class.negative]="p.backtest_pnl < 0">
                {{ formatPnl(p.backtest_pnl) }}
              </td>
              <td>{{ p.price < 1 ? (p.price | number:'1.6-6') : (p.price | number:'1.2-2') }}</td>
              <td>{{ formatVolume(p.volume_24h) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty State -->
      <div class="empty-state" *ngIf="!latestScan() && !loading()">
        <div class="empty-text">No scan data yet</div>
        <div class="empty-hint">Run the simulator or use --scan flag to discover pairs</div>
      </div>

      <!-- Scan History -->
      <div class="history-section" *ngIf="scanHistory().length > 1">
        <span class="section-title">Scan History</span>
        <div class="history-row" *ngFor="let scan of scanHistory()">
          <span class="hist-type" [class]="'type-' + scan.scan_type">{{ scan.scan_type }}</span>
          <span class="hist-time">{{ scan.timestamp | date:'MMM d HH:mm' }}</span>
          <span class="hist-count">{{ scan.total_pairs_scanned }} scanned</span>
          <span class="hist-selected">
            {{ scan.selected_pairs.length }} selected:
            {{ scan.selected_pairs.slice(0, 5) | json }}
          </span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; font-family: 'Inter', 'Segoe UI', sans-serif; color: #e2e8f0; }

    .scanner-container { max-width: 1200px; margin: 0 auto; padding: 20px 0; }

    .header-row {
      display: flex; align-items: flex-end; justify-content: space-between;
      flex-wrap: wrap; gap: 12px; margin-bottom: 20px;
    }
    .title-group { display: flex; flex-direction: column; gap: 2px; }
    .title {
      margin: 0; font-size: 1.6rem; font-weight: 700;
      background: linear-gradient(90deg, #7c83ff, #a78bfa);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .subtitle { font-size: 0.8rem; color: #6b7280; }

    .scan-meta { display: flex; align-items: center; gap: 10px; }
    .meta-badge {
      background: #2d3148; color: #a78bfa; padding: 4px 10px; border-radius: 12px;
      font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em;
    }
    .meta-time { font-size: 0.78rem; color: #6b7280; }
    .meta-count { font-size: 0.78rem; color: #4b5563; }

    .section-title {
      font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; color: #6b7280; display: block; margin-bottom: 12px;
    }

    /* Selected Pairs */
    .selected-section { margin-bottom: 18px; }
    .selected-row { display: flex; gap: 14px; flex-wrap: wrap; }
    .selected-card {
      background: #242736; border: 1px solid #2d3148; border-radius: 12px;
      padding: 16px; flex: 1; min-width: 250px;
    }
    .sel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .sel-pair { font-size: 1.1rem; font-weight: 800; color: #a78bfa; }
    .sel-score {
      font-size: 1.3rem; font-weight: 800;
      background: linear-gradient(90deg, #7c83ff, #a78bfa);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .sel-stats { display: flex; gap: 14px; margin-bottom: 10px; }
    .sel-stat { display: flex; flex-direction: column; gap: 1px; }
    .sl { font-size: 0.68rem; color: #6b7280; text-transform: uppercase; }
    .sv { font-size: 0.9rem; font-weight: 600; color: #e2e8f0; }
    .sel-footer { display: flex; justify-content: space-between; align-items: center; }
    .bt-pnl { font-weight: 700; font-size: 0.88rem; }
    .positive { color: #4ade80; }
    .negative { color: #f87171; }

    /* Regime Badges */
    .regime-badge {
      padding: 3px 10px; border-radius: 10px; font-size: 0.72rem;
      font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .regime-badge.small { padding: 2px 8px; font-size: 0.68rem; }
    .regime-ranging { background: #1e3a5f; color: #60a5fa; }
    .regime-volatile { background: #3b1f0a; color: #fb923c; }
    .regime-squeeze { background: #2e1065; color: #c084fc; }
    .regime-trending_up { background: #14532d; color: #4ade80; }
    .regime-trending_down { background: #450a0a; color: #f87171; }
    .regime-unknown { background: #1e293b; color: #94a3b8; }

    /* Swaps */
    .swaps-section { margin-bottom: 18px; }
    .swap-event {
      display: flex; align-items: center; gap: 10px; padding: 8px 12px;
      background: #242736; border: 1px solid #2d3148; border-radius: 8px; margin-bottom: 6px;
    }
    .swap-arrow {
      padding: 2px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 800;
    }
    .swap-arrow.out { background: #450a0a; color: #f87171; }
    .swap-arrow.in { background: #14532d; color: #4ade80; }
    .swap-pair { font-weight: 700; color: #e2e8f0; }
    .swap-reason { font-size: 0.78rem; color: #6b7280; }

    /* Ranked Table */
    .ranked-section {
      background: #242736; border: 1px solid #2d3148; border-radius: 14px; padding: 18px;
      margin-bottom: 18px;
    }
    .ranked-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    .ranked-table th {
      text-align: left; padding: 8px 8px; color: #6b7280; font-weight: 600;
      text-transform: uppercase; font-size: 0.68rem; letter-spacing: 0.05em;
      border-bottom: 1px solid #2d3148;
    }
    .ranked-table td { padding: 7px 8px; border-bottom: 1px solid #1a1d29; color: #9ca3af; }
    .ranked-table .active-row { background: #1a2332; }
    .ranked-table .active-row td { color: #e2e8f0; }
    .pair-cell { font-weight: 700; color: #e2e8f0; }
    .score-cell { font-weight: 700; color: #a78bfa; }

    /* Empty State */
    .empty-state {
      text-align: center; padding: 60px 20px;
      background: #242736; border: 1px solid #2d3148; border-radius: 14px;
    }
    .empty-text { font-size: 1.1rem; font-weight: 600; color: #6b7280; margin-bottom: 6px; }
    .empty-hint { font-size: 0.82rem; color: #4b5563; }

    /* History */
    .history-section {
      background: #242736; border: 1px solid #2d3148; border-radius: 14px; padding: 18px;
    }
    .history-row {
      display: flex; align-items: center; gap: 12px; padding: 6px 0;
      border-bottom: 1px solid #1a1d29; font-size: 0.8rem;
    }
    .hist-type {
      padding: 2px 8px; border-radius: 6px; font-size: 0.7rem; font-weight: 700;
      text-transform: uppercase;
    }
    .type-full { background: #1e3a5f; color: #60a5fa; }
    .type-quick { background: #2e1065; color: #c084fc; }
    .hist-time { color: #6b7280; }
    .hist-count { color: #4b5563; }
    .hist-selected { color: #6b7280; font-size: 0.75rem; overflow: hidden; text-overflow: ellipsis; }

    /* Progress Bar */
    .progress-section {
      background: #242736; border: 1px solid #2d3148; border-radius: 12px;
      padding: 14px 18px; margin-bottom: 18px;
    }
    .progress-header {
      display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
    }
    .progress-label {
      font-size: 0.82rem; font-weight: 600; color: #a78bfa;
      display: flex; align-items: center; gap: 8px;
    }
    .progress-eta { font-size: 0.78rem; color: #6b7280; }
    .progress-track {
      width: 100%; height: 6px; background: #1a1d29; border-radius: 3px; overflow: hidden;
    }
    .progress-fill {
      height: 100%; border-radius: 3px;
      background: linear-gradient(90deg, #7c83ff, #a78bfa);
      transition: width 0.5s ease;
    }

    /* Spinner */
    .spinner {
      display: inline-block; width: 14px; height: 14px;
      border: 2px solid #3b3f5c; border-top-color: #a78bfa;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Toast */
    .toast-notification {
      position: fixed; bottom: 24px; right: 24px; z-index: 1000;
      background: #242736; border: 1px solid #a78bfa; border-radius: 12px;
      padding: 14px 20px; color: #e2e8f0; font-size: 0.85rem; font-weight: 500;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
      cursor: pointer; max-width: 500px;
      animation: slideUp 0.3s ease;
    }
    @keyframes slideUp {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }

    /* Liquidity Risk */
    .liq-warning { margin-top: 10px; padding-top: 10px; border-top: 1px solid #2d3148; }
    .liq-badge {
      font-size: 0.72rem; font-weight: 700; padding: 4px 10px; border-radius: 8px;
      display: inline-flex; align-items: center; gap: 5px;
    }
    .liq-badge.danger { background: #450a0a; color: #f87171; }
    .liq-badge.ok { background: #14532d; color: #4ade80; font-weight: 500; font-size: 0.7rem; }
    .liq-icon { font-size: 0.82rem; font-weight: 900; }
    .liq-details {
      display: flex; gap: 12px; margin-top: 6px;
      font-size: 0.72rem; color: #9ca3af;
    }
    .liq-flags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
    .liq-flag {
      font-size: 0.68rem; color: #fbbf24; background: #451a03;
      padding: 2px 8px; border-radius: 6px;
    }
  `],
})
export class PairScannerComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private sub: Subscription | null = null;
  private progressSub: any = null;

  loading = signal(false);
  scanHistory = signal<PairScanData[]>([]);
  scanProgress = this.api.scanProgress;
  toastMessage = signal<string | null>(null);
  liqChecks = signal<OrderBookCheck[]>([]);
  private toastTimer: any = null;

  latestScan = computed(() => {
    const scans = this.scanHistory();
    return scans.length > 0 ? scans[0] : null;
  });

  selectedPairs = computed(() => {
    const scan = this.latestScan();
    return scan?.selected_pairs ?? [];
  });

  rankedPairs = computed(() => {
    const scan = this.latestScan();
    return scan?.results ?? [];
  });

  hasSwaps = computed(() => {
    const scan = this.latestScan();
    if (!scan) return false;
    return scan.swapped_out.length > 0 || scan.swapped_in.length > 0;
  });

  scanPct = computed(() => {
    const p = this.scanProgress();
    return p.total_pairs > 0 ? Math.round((p.scanned / p.total_pairs) * 100) : 0;
  });

  private selectedSet = computed(() => {
    return new Set(this.selectedPairs().map(p => p.pair));
  });

  ngOnInit() {
    this.startPolling();
    this.startProgressPolling();
    this.fetchLiquidity();
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    if (this.toastTimer) clearTimeout(this.toastTimer);
  }

  dismissToast() {
    this.toastMessage.set(null);
    if (this.toastTimer) { clearTimeout(this.toastTimer); this.toastTimer = null; }
  }

  private showToast(msg: string, durationMs = 8000) {
    this.toastMessage.set(msg);
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => this.toastMessage.set(null), durationMs);
  }

  getLiqCheck(pair: string): OrderBookCheck | null {
    return this.liqChecks().find(c => c.pair === pair) ?? null;
  }

  private fetchLiquidity() {
    this.api.fetchOrderBookCheck().subscribe({
      next: (data) => this.liqChecks.set(data),
      error: () => {},
    });
  }

  isSelected(pair: string): boolean {
    return this.selectedSet().has(pair);
  }

  formatPnl(pnl: number): string {
    const sign = pnl >= 0 ? '+' : '';
    return `${sign}$${Math.abs(pnl).toFixed(2)}`;
  }

  formatDollar(val: number): string {
    if (val >= 1_000_000) return '$' + (val / 1_000_000).toFixed(1) + 'M';
    if (val >= 1_000) return '$' + (val / 1_000).toFixed(1) + 'K';
    return '$' + val.toFixed(0);
  }

  formatVolume(vol: number): string {
    if (vol >= 1_000_000) return '$' + (vol / 1_000_000).toFixed(1) + 'M';
    if (vol >= 1_000) return '$' + (vol / 1_000).toFixed(0) + 'K';
    return '$' + vol.toFixed(0);
  }

  private startPolling() {
    this.sub = interval(120_000).pipe(
      startWith(0),
      switchMap(() => {
        this.loading.set(true);
        return this.api.fetchPairScans(10);
      }),
    ).subscribe({
      next: (data) => {
        this.scanHistory.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private startProgressPolling() {
    this.api.startScanProgressPolling(() => {
      // Scan just completed — auto-refresh data + liquidity
      this.fetchLiquidity();
      this.api.fetchPairScans(10).subscribe({
        next: (data) => {
          this.scanHistory.set(data);
          // Build toast message
          const scan = data[0];
          if (scan) {
            const top3 = scan.selected_pairs
              .slice(0, 3)
              .map(p => `${p.pair.replace('-USD', '')} (${p.composite_score.toFixed(0)})`)
              .join(', ');
            this.showToast(
              `Scan complete: ${scan.total_pairs_scanned} pairs scored. Top 3: ${top3}`
            );
          }
        },
      });
      // Restart progress polling for the next scan
      setTimeout(() => this.startProgressPolling(), 10_000);
    });
  }
}
