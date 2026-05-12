import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, signal, computed } from '@angular/core';
import { ApiService } from '../../services/api.service';

interface DailyRow {
  date: string;
  donch_n_kept: number;
  donch_pnl_usd: number;
  real_n: number;
  real_pnl_usd: number;
  delta_usd: number;
  real_in_cash_all_day: number;
  cum_donch_usd: number;
  cum_real_usd: number;
  cum_delta_usd: number;
}

@Component({
  selector: 'app-donchian-shadow',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="donch-tile">
      <div class="header">
        <h3>Donchian Shadow Mode</h3>
        <span class="status-pill" [ngClass]="statusClass()">{{ statusLabel() }}</span>
      </div>

      <ng-container *ngIf="strip() as s; else loadingTpl">
        <div class="message" [ngClass]="statusClass()">{{ s.message }}</div>

        <div class="today-strip" *ngIf="s.days > 0">
          <div class="strip-row">
            <span class="label">Today ({{ s.today_date }}):</span>
            <span class="donch">
              Donch {{ s.today_donch_n }} trade<span *ngIf="s.today_donch_n !== 1">s</span>,
              <strong [class.pos]="s.today_donch_pnl > 0" [class.neg]="s.today_donch_pnl < 0">
                {{ s.today_donch_pnl | currency:'USD':'symbol':'1.2-2' }}
              </strong>
            </span>
            <span class="vs">vs</span>
            <span class="real" [class.cash]="s.today_real_in_cash">
              Real {{ s.today_real_n }} trade<span *ngIf="s.today_real_n !== 1">s</span>,
              <strong [class.pos]="s.today_real_pnl > 0" [class.neg]="s.today_real_pnl < 0">
                {{ s.today_real_pnl | currency:'USD':'symbol':'1.2-2' }}
              </strong>
              <span *ngIf="s.today_real_in_cash" class="cash-flag" title="Real bot held no positions today — not a fair comparison">🟡 in cash</span>
            </span>
          </div>
          <div class="strip-row cumulative">
            <span class="label">Cumulative ({{ s.days }} day<span *ngIf="s.days !== 1">s</span>):</span>
            <span class="donch">
              Donch <strong [class.pos]="s.cum_donch_pnl > 0" [class.neg]="s.cum_donch_pnl < 0">
                {{ s.cum_donch_pnl | currency:'USD':'symbol':'1.2-2' }}
              </strong>
              ({{ s.cum_donch_trades }} trades)
            </span>
            <span class="vs">vs</span>
            <span class="real">
              Real <strong [class.pos]="s.cum_real_pnl > 0" [class.neg]="s.cum_real_pnl < 0">
                {{ s.cum_real_pnl | currency:'USD':'symbol':'1.2-2' }}
              </strong>
            </span>
            <span class="delta">
              Δ <strong [class.pos]="s.cum_delta > 0" [class.neg]="s.cum_delta < 0">
                {{ s.cum_delta | currency:'USD':'symbol':'1.2-2' }}
              </strong>
            </span>
          </div>
          <div class="strip-row meta" *ngIf="s.fair_days > 0">
            Winning days: {{ s.winning_days }}/{{ s.fair_days }}
            (need {{ s.consistency_threshold }} for early-ship eligibility)
          </div>
        </div>

        <div class="chart" *ngIf="daily().length > 0">
          <div class="chart-header">Cumulative P&L by day</div>
          <svg class="cum-chart" [attr.viewBox]="chartViewBox()">
            <line *ngFor="let l of gridLines()" [attr.x1]="l.x1" [attr.y1]="l.y1"
                  [attr.x2]="l.x2" [attr.y2]="l.y2" stroke="#333" stroke-dasharray="2,2" />
            <polyline [attr.points]="donchPath()" fill="none" stroke="#4ade80" stroke-width="2" />
            <polyline [attr.points]="realPath()" fill="none" stroke="#f87171" stroke-width="2" />
            <text x="5" [attr.y]="chartLegendY1()" fill="#4ade80" font-size="10">— Donchian</text>
            <text x="5" [attr.y]="chartLegendY2()" fill="#f87171" font-size="10">— Real bot</text>
          </svg>
        </div>

        <table class="daily-table" *ngIf="daily().length > 0">
          <thead>
            <tr>
              <th>Date</th>
              <th class="num">Donch n</th>
              <th class="num">Donch $</th>
              <th class="num">Real n</th>
              <th class="num">Real $</th>
              <th class="num">Δ</th>
              <th>Flag</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let r of daily()">
              <td>{{ r.date }}</td>
              <td class="num">{{ r.donch_n_kept }}</td>
              <td class="num" [class.pos]="r.donch_pnl_usd > 0" [class.neg]="r.donch_pnl_usd < 0">
                {{ r.donch_pnl_usd | currency:'USD':'symbol':'1.2-2' }}
              </td>
              <td class="num">{{ r.real_n }}</td>
              <td class="num" [class.pos]="r.real_pnl_usd > 0" [class.neg]="r.real_pnl_usd < 0">
                {{ r.real_pnl_usd | currency:'USD':'symbol':'1.2-2' }}
              </td>
              <td class="num" [class.pos]="r.delta_usd > 0" [class.neg]="r.delta_usd < 0">
                {{ r.delta_usd | currency:'USD':'symbol':'1.2-2' }}
              </td>
              <td>
                <span *ngIf="r.real_in_cash_all_day" class="cash-flag"
                      title="Real bot in cash all day — comparison not fair">🟡</span>
              </td>
            </tr>
          </tbody>
        </table>
      </ng-container>

      <ng-template #loadingTpl><div class="loading">Loading…</div></ng-template>
    </div>
  `,
  styles: [`
    .donch-tile {
      background: #1a1a1a; border: 1px solid #333; border-radius: 8px;
      padding: 16px; color: #eee; font-family: system-ui, sans-serif;
    }
    .header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 12px;
    }
    h3 { margin: 0; font-size: 16px; font-weight: 600; }
    .status-pill {
      padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.5px;
    }
    .status-pill.gathering { background: #facc15; color: #1a1a1a; }
    .status-pill.eligible { background: #4ade80; color: #1a1a1a; }
    .status-pill.decision { background: #60a5fa; color: #1a1a1a; }
    .status-pill.nodata { background: #6b7280; color: #fff; }
    .message {
      font-size: 13px; padding: 8px 12px; border-radius: 4px;
      background: #2a2a2a; margin-bottom: 12px;
    }
    .message.eligible { background: #14532d; color: #bbf7d0; }
    .message.decision { background: #1e3a8a; color: #bfdbfe; }
    .today-strip { font-size: 13px; line-height: 1.8; }
    .strip-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    .strip-row .label { color: #888; font-weight: 600; min-width: 110px; }
    .strip-row .vs { color: #666; }
    .strip-row .delta { color: #aaa; }
    .strip-row.cumulative { padding-top: 4px; border-top: 1px solid #2a2a2a; margin-top: 6px; }
    .strip-row.meta { font-size: 11px; color: #888; padding-top: 4px; }
    .pos { color: #4ade80; }
    .neg { color: #f87171; }
    .cash { opacity: 0.6; }
    .cash-flag { font-size: 10px; color: #facc15; margin-left: 4px; }
    .chart { margin-top: 14px; }
    .chart-header { font-size: 11px; color: #888; margin-bottom: 4px; }
    .cum-chart { width: 100%; height: 120px; background: #0e0e0e; border-radius: 4px; }
    .daily-table {
      width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px;
    }
    .daily-table th, .daily-table td {
      padding: 4px 8px; border-bottom: 1px solid #2a2a2a; text-align: left;
    }
    .daily-table th { color: #888; font-weight: 600; }
    .daily-table td.num, .daily-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
    .loading { color: #666; font-size: 13px; padding: 12px; }
  `]
})
export class DonchianShadowComponent implements OnInit, OnDestroy {
  strip = signal<any | null>(null);
  daily = signal<DailyRow[]>([]);
  private pollId: any = null;

  statusLabel = computed(() => {
    const s = this.strip();
    if (!s) return '…';
    if (s.status === 'early_ship_eligible') return 'Eligible';
    if (s.status === 'decision_time') return 'Decide';
    if (s.status === 'no_data' || s.status === 'no_table') return 'Pending';
    return 'Gathering';
  });

  statusClass = computed(() => {
    const s = this.strip();
    if (!s) return 'nodata';
    if (s.status === 'early_ship_eligible') return 'eligible';
    if (s.status === 'decision_time') return 'decision';
    if (s.status === 'no_data' || s.status === 'no_table') return 'nodata';
    return 'gathering';
  });

  // Chart geometry (cumulative line chart, SVG viewBox 0 0 500 120)
  chartViewBox = computed(() => '0 0 500 120');
  chartLegendY1 = computed(() => 14);
  chartLegendY2 = computed(() => 28);
  gridLines = computed(() => {
    return [40, 60, 80, 100].map(y => ({ x1: 0, y1: y, x2: 500, y2: y }));
  });

  donchPath = computed(() => this.buildPath(d => d.cum_donch_usd));
  realPath = computed(() => this.buildPath(d => d.cum_real_usd));

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.refresh();
    this.pollId = setInterval(() => this.refresh(), 5 * 60 * 1000); // every 5 min
  }
  ngOnDestroy() { if (this.pollId) clearInterval(this.pollId); }

  refresh() {
    this.api.getDonchianTodayStrip().subscribe({
      next: data => this.strip.set(data),
      error: () => this.strip.set({status: 'no_data', message: 'API error', days: 0}),
    });
    this.api.getDonchianDailyCompare().subscribe({
      next: rows => this.daily.set(rows || []),
    });
  }

  private buildPath(getter: (d: DailyRow) => number): string {
    const rows = this.daily();
    if (!rows.length) return '';
    const W = 500;
    const H = 120;
    const padTop = 10;
    const padBot = 10;
    const padLeft = 20;
    const padRight = 10;
    const usableW = W - padLeft - padRight;
    const usableH = H - padTop - padBot;
    const all = rows.flatMap(r => [r.cum_donch_usd || 0, r.cum_real_usd || 0]);
    const minY = Math.min(0, ...all);
    const maxY = Math.max(0, ...all);
    const rangeY = maxY - minY || 1;
    const n = rows.length;
    return rows.map((r, i) => {
      const x = padLeft + (n === 1 ? usableW / 2 : (i / (n - 1)) * usableW);
      const y = padTop + ((maxY - getter(r)) / rangeY) * usableH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }
}
