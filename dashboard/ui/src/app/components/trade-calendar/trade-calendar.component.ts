import { Component, input, output, signal, computed, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MomentumTradeData, asUtcDate, fmt12Hour } from '../../services/api.service';

interface RoundTrip {
  pair: string;
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pct: number;
}

interface DayData {
  trades: RoundTrip[];
  pnl: number;
  count: number;
  winrate: number | null;
}

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

@Component({
  selector: 'app-trade-calendar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="overlay" [class.open]="open()" (click)="onOverlayClick($event)">
      <div class="modal" (click)="$event.stopPropagation()">
        <div class="modal-head">
          <div class="modal-title">Trade Calendar</div>
          <div class="modal-nav">
            <button class="nav-btn" (click)="shiftMonth(-1)">&lsaquo;</button>
            <div class="month-label" (click)="togglePicker($event)">
              <span>{{ monthLabel() }}</span>
              <span class="caret">&#9662;</span>
              @if (pickerOpen()) {
                <div class="picker" (click)="$event.stopPropagation()">
                  <div class="picker-year">
                    <button class="year-arrow" (click)="shiftYear(-1)">&lsaquo;</button>
                    <div class="year-label">{{ pickerYear() }}</div>
                    <button class="year-arrow" (click)="shiftYear(1)">&rsaquo;</button>
                  </div>
                  <div class="picker-months">
                    @for (m of monthsShort; track m.i) {
                      <button class="pick-m"
                        [class.current]="pickerYear() === currentMonth().y && m.i === currentMonth().m"
                        [class.has-data]="monthHasData(pickerYear(), m.i)"
                        [class.loss]="monthNetPnl(pickerYear(), m.i) < 0"
                        (click)="pickMonth(m.i)">{{ m.label }}</button>
                    }
                  </div>
                </div>
              }
            </div>
            <button class="nav-btn" (click)="shiftMonth(1)">&rsaquo;</button>
            <button class="close-x" (click)="emitClose()">&times;</button>
          </div>
        </div>

        <div class="summary">
          <div class="summary-cell">
            <div class="sm-label">Month P&amp;L</div>
            <div class="sm-value" [class.win]="summary().total >= 0" [class.loss]="summary().total < 0">
              {{ fmtMoney(summary().total) }}
            </div>
            <div class="sm-sub">{{ summary().activeDays }} active {{ summary().activeDays === 1 ? 'day' : 'days' }}</div>
          </div>
          <div class="summary-cell">
            <div class="sm-label">Best Day</div>
            <div class="sm-value win">{{ summary().best ? fmtMoney(summary().best!.pnl) : '—' }}</div>
            <div class="sm-sub">{{ summary().best ? (dayLabel(summary().best!.key) + ' · ' + summary().best!.topPair) : '—' }}</div>
          </div>
          <div class="summary-cell">
            <div class="sm-label">Worst Day</div>
            <div class="sm-value" [class.loss]="summary().worst && summary().worst!.pnl < 0">
              {{ summary().worst ? fmtMoney(summary().worst!.pnl) : '—' }}
            </div>
            <div class="sm-sub">{{ summary().worst ? (dayLabel(summary().worst!.key) + ' · ' + summary().worst!.topPair) : '—' }}</div>
          </div>
          <div class="summary-cell">
            <div class="sm-label">Win Rate</div>
            <div class="sm-value">{{ summary().winRate }}%</div>
            <div class="sm-sub">{{ summary().wins }}W / {{ summary().losses }}L · {{ summary().tradeCount }} trades</div>
          </div>
        </div>

        <div class="cal-wrap">
          <div class="cal-dow">
            <div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div>
            <div>Thu</div><div>Fri</div><div>Sat</div>
          </div>
          <div class="cal-grid">
            @for (c of gridCells(); track c.key || c.idx) {
              @if (c.empty) {
                <div class="cal-cell empty"></div>
              } @else {
                <div class="cal-cell"
                  [class.win]="c.dayData && c.dayData.pnl > 0"
                  [class.loss]="c.dayData && c.dayData.pnl < 0"
                  [class.strong]="c.dayData && Math.abs(c.dayData.pnl) >= 150"
                  [class.today]="c.isToday"
                  [class.selected]="c.key === selectedKey()"
                  (click)="selectDay(c.key!)">
                  <div class="cell-top">
                    <span class="cell-day">{{ c.day }}</span>
                    @if (c.dayData && c.dayData.count > 0) {
                      <span class="cell-count">{{ c.dayData.count }}</span>
                    }
                  </div>
                  <div class="cell-pnl" [class.win]="c.dayData && c.dayData.pnl > 0" [class.loss]="c.dayData && c.dayData.pnl < 0" [class.flat]="!c.dayData || c.dayData.count === 0">
                    {{ c.dayData && c.dayData.count > 0 ? fmtMoney(c.dayData.pnl) : '—' }}
                  </div>
                  <div class="cell-winrate">
                    @if (c.dayData && c.dayData.count > 0) {
                      {{ c.dayData.count }} {{ c.dayData.count === 1 ? 'trade' : 'trades' }} · {{ c.dayData.winrate }}%
                    }
                  </div>
                </div>
              }
            }
          </div>
        </div>

        @if (selectedDay(); as day) {
          <div class="detail">
            <div class="detail-head">
              <div class="detail-title">{{ detailTitle() }}</div>
              <div class="detail-total" [class.win]="day.pnl >= 0" [class.loss]="day.pnl < 0">
                {{ fmtMoney(day.pnl) }}
              </div>
            </div>
            <div class="trade-head">
              <span>Held</span><span>Pair</span><span>Entry → Exit</span>
              <span class="r">%</span><span class="r">P&amp;L</span>
            </div>
            @for (t of day.trades; track t.exitTime) {
              <div class="trade-row">
                <span class="tr-time">{{ fmtTime(t.entryTime) }} → {{ fmtTime(t.exitTime) }}</span>
                <span class="tr-pair">{{ t.pair.replace('-USD', '') }}</span>
                <span class="tr-prices">{{ fmtPrice(t.entryPrice) }}<span class="arrow">→</span>{{ fmtPrice(t.exitPrice) }}</span>
                <span class="tr-pct" [class.win]="t.pct >= 0" [class.loss]="t.pct < 0">{{ fmtPct(t.pct) }}</span>
                <span class="tr-pnl" [class.win]="t.pnl >= 0" [class.loss]="t.pnl < 0">{{ fmtMoney(t.pnl) }}</span>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    :host{--panel:#121821;--panel-2:#182030;--border:#25304a;
          --text:#e6ecf5;--muted:#8895ad;--dim:#5a6679;
          --win:#16a34a;--win-bg:rgba(22,163,74,0.14);
          --loss:#dc2626;--loss-bg:rgba(220,38,38,0.14);
          --accent:#3b82f6;}
    .overlay{position:fixed;inset:0;background:rgba(0,0,0,.65);
             display:none;align-items:flex-start;justify-content:center;
             z-index:100;padding:40px 20px;overflow-y:auto}
    .overlay.open{display:flex}
    .modal{background:var(--panel);border:1px solid var(--border);
           border-radius:12px;width:100%;max-width:880px;
           box-shadow:0 20px 60px rgba(0,0,0,.5);overflow:visible;color:var(--text);
           font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:13px}
    .modal-head{display:flex;align-items:center;justify-content:space-between;
                padding:18px 22px;border-bottom:1px solid var(--border)}
    .modal-title{font-size:16px;font-weight:600}
    .modal-nav{display:flex;align-items:center;gap:10px}
    .nav-btn{background:var(--panel-2);border:1px solid var(--border);
             color:var(--text);width:28px;height:28px;border-radius:6px;
             cursor:pointer;display:flex;align-items:center;justify-content:center;
             font-size:14px}
    .nav-btn:hover{background:#1f2937}
    .month-label{font-size:14px;font-weight:500;min-width:130px;text-align:center;
                 cursor:pointer;padding:4px 10px;border-radius:6px;
                 transition:background .15s ease;position:relative;user-select:none}
    .month-label:hover{background:var(--panel-2)}
    .month-label .caret{margin-left:6px;color:var(--muted);font-size:10px}

    .picker{position:absolute;top:calc(100% + 6px);left:50%;transform:translateX(-50%);
            background:var(--panel);border:1px solid var(--border);border-radius:10px;
            padding:10px;width:240px;z-index:10;
            box-shadow:0 12px 40px rgba(0,0,0,.6)}
    .picker-year{display:flex;align-items:center;justify-content:space-between;
                 padding:4px 6px;margin-bottom:8px}
    .year-label{font-size:13px;font-weight:600;letter-spacing:.3px}
    .year-arrow{background:var(--panel-2);border:1px solid var(--border);
                color:var(--text);width:24px;height:24px;border-radius:5px;
                cursor:pointer;font-size:12px}
    .year-arrow:hover{background:#1f2937}
    .picker-months{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}
    .pick-m{background:var(--panel-2);border:1px solid var(--border);
            color:var(--text);padding:8px 4px;border-radius:6px;cursor:pointer;
            font-size:12px;transition:all .12s ease}
    .pick-m:hover{background:#1f2937;border-color:#3b4b6b}
    .pick-m.current{background:rgba(59,130,246,.18);border-color:var(--accent);color:#93c5fd}
    .pick-m.has-data::after{content:'';display:block;width:4px;height:4px;
                           background:var(--win);border-radius:50%;margin:3px auto 0}
    .pick-m.has-data.loss::after{background:var(--loss)}

    .close-x{background:transparent;border:0;color:var(--muted);
             font-size:20px;cursor:pointer;padding:4px 8px;line-height:1}
    .close-x:hover{color:var(--text)}

    .summary{display:grid;grid-template-columns:repeat(4,1fr);
             padding:14px 22px;border-bottom:1px solid var(--border);
             background:var(--panel-2)}
    .summary-cell{display:flex;flex-direction:column;gap:3px}
    .summary-cell + .summary-cell{border-left:1px solid var(--border);padding-left:16px}
    .sm-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
    .sm-value{font-size:16px;font-weight:600;font-variant-numeric:tabular-nums}
    .sm-value.win{color:var(--win)} .sm-value.loss{color:var(--loss)}
    .sm-sub{font-size:11px;color:var(--dim)}

    .cal-wrap{padding:18px 22px 22px}
    .cal-dow{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;
             margin-bottom:6px;font-size:10px;color:var(--muted);
             text-transform:uppercase;letter-spacing:.8px;text-align:center}
    .cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
    .cal-cell{aspect-ratio:1/0.85;background:var(--panel-2);
              border:1px solid var(--border);border-radius:8px;padding:6px 8px;
              display:flex;flex-direction:column;justify-content:space-between;
              cursor:pointer;transition:transform .1s ease,border-color .15s ease;
              position:relative}
    .cal-cell:hover{border-color:#3b4b6b;transform:translateY(-1px)}
    .cal-cell.empty{background:transparent;border:1px dashed #1e2736;cursor:default}
    .cal-cell.empty:hover{transform:none;border-color:#1e2736}
    .cal-cell.win{background:var(--win-bg);border-color:rgba(22,163,74,.35)}
    .cal-cell.win.strong{background:rgba(22,163,74,.28)}
    .cal-cell.loss{background:var(--loss-bg);border-color:rgba(220,38,38,.35)}
    .cal-cell.loss.strong{background:rgba(220,38,38,.28)}
    .cal-cell.today{outline:2px solid var(--accent);outline-offset:-2px}
    .cal-cell.selected{outline:2px solid #fbbf24;outline-offset:-2px}
    .cell-top{display:flex;justify-content:space-between;align-items:baseline}
    .cell-day{font-size:11px;color:var(--muted);font-weight:500}
    .cell-count{font-size:10px;color:var(--dim)}
    .cell-pnl{font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
    .cell-pnl.win{color:var(--win)} .cell-pnl.loss{color:var(--loss)}
    .cell-pnl.flat{color:var(--dim)}
    .cell-winrate{font-size:10px;color:var(--muted)}

    .detail{border-top:1px solid var(--border);padding:16px 22px 20px;
            background:var(--panel-2)}
    .detail-head{display:flex;justify-content:space-between;align-items:center;
                 margin-bottom:10px}
    .detail-title{font-size:14px;font-weight:600}
    .detail-total{font-size:14px;font-weight:600;font-variant-numeric:tabular-nums}
    .detail-total.win{color:var(--win)} .detail-total.loss{color:var(--loss)}

    .trade-head{display:grid;grid-template-columns:130px 90px 1fr 70px 90px;
                gap:10px;padding:6px 0 4px;border-bottom:1px solid var(--border);
                font-size:10px;color:var(--muted);text-transform:uppercase;
                letter-spacing:.6px}
    .trade-head .r{text-align:right}
    .trade-row{display:grid;grid-template-columns:130px 90px 1fr 70px 90px;
               gap:10px;padding:9px 0;border-top:1px solid rgba(255,255,255,.03);
               font-size:12px;align-items:center}
    .tr-time{color:var(--muted);font-variant-numeric:tabular-nums;font-size:11px}
    .tr-pair{font-weight:600}
    .tr-prices{color:var(--muted);font-variant-numeric:tabular-nums}
    .tr-prices .arrow{color:var(--dim);margin:0 4px}
    .tr-pct{text-align:right;font-variant-numeric:tabular-nums;font-weight:500;font-size:11px}
    .tr-pct.win{color:var(--win)} .tr-pct.loss{color:var(--loss)}
    .tr-pnl{text-align:right;font-weight:600;font-variant-numeric:tabular-nums}
    .tr-pnl.win{color:var(--win)} .tr-pnl.loss{color:var(--loss)}

    @media (max-width: 720px){
      .overlay{padding:12px 8px;align-items:flex-start}
      .modal{border-radius:10px;font-size:12px}
      .modal-head{padding:12px 14px;flex-wrap:wrap;gap:8px}
      .modal-title{font-size:15px}
      .modal-nav{gap:6px}
      .month-label{min-width:auto;font-size:13px;padding:4px 8px}
      .nav-btn{width:32px;height:32px}
      .close-x{padding:4px 6px;font-size:22px}
      .picker{width:210px}

      .summary{grid-template-columns:repeat(2,1fr);padding:10px 12px;gap:10px 12px}
      .summary-cell + .summary-cell{border-left:0;padding-left:0}
      .summary-cell:nth-child(even){border-left:1px solid var(--border);padding-left:12px}
      .sm-value{font-size:14px}
      .sm-label,.sm-sub{font-size:10px}

      .cal-wrap{padding:12px 10px 14px}
      .cal-dow{gap:3px;font-size:9px;letter-spacing:.4px}
      .cal-grid{gap:3px}
      .cal-cell{aspect-ratio:1/1;padding:3px 4px;border-radius:6px}
      .cell-day{font-size:10px}
      .cell-count{font-size:9px}
      .cell-pnl{font-size:10px;line-height:1.1}
      .cell-winrate{display:none}

      .detail{padding:12px 12px 16px}
      .detail-title{font-size:13px}
      .detail-total{font-size:13px}

      /* Trade rows: stack into two lines per trade */
      .trade-head{display:none}
      .trade-row{display:grid;
                 grid-template-columns:1fr auto;
                 grid-template-areas:"pair pnl" "prices pct" "time time";
                 gap:2px 8px;padding:10px 0;
                 border-top:1px solid rgba(255,255,255,.06)}
      .tr-pair{grid-area:pair;font-size:13px}
      .tr-pnl{grid-area:pnl;font-size:13px}
      .tr-prices{grid-area:prices;font-size:11px}
      .tr-pct{grid-area:pct;font-size:11px;text-align:right}
      .tr-time{grid-area:time;font-size:10px;color:var(--dim)}
    }

    @media (max-width: 380px){
      .cell-day{font-size:9px}
      .cell-pnl{font-size:9px}
      .cal-cell{padding:2px 3px}
      .sm-value{font-size:13px}
    }
  `]
})
export class TradeCalendarComponent implements OnChanges {
  trades = input<MomentumTradeData[]>([]);
  open = input<boolean>(false);
  close = output<void>();

  monthsShort = MONTHS.map((m, i) => ({ i, label: m.slice(0, 3) }));
  Math = Math;

  currentMonth = signal<{y: number; m: number}>(this.initMonth());
  pickerOpen = signal(false);
  pickerYear = signal(new Date().getFullYear());
  selectedKey = signal<string | null>(null);

  private initMonth() {
    const now = new Date();
    return { y: now.getFullYear(), m: now.getMonth() };
  }

  // Aggregate trades into round-trips grouped by day (local-date ISO).
  dayIndex = computed<Record<string, DayData>>(() => {
    const sorted = [...this.trades()].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    const pending = new Map<string, MomentumTradeData[]>();
    const byDay: Record<string, DayData> = {};
    for (const t of sorted) {
      if (t.side === 'buy') {
        if (!pending.has(t.pair)) pending.set(t.pair, []);
        pending.get(t.pair)!.push(t);
      } else if (t.side === 'sell') {
        const buys = pending.get(t.pair);
        if (!buys || !buys.length) continue;
        const buy = buys.shift()!;
        const pnl = t.net_pnl ?? 0;
        const entry = buy.price;
        const exit = t.price;
        const trip: RoundTrip = {
          pair: t.pair,
          entryTime: buy.timestamp,
          exitTime: t.timestamp,
          entryPrice: entry,
          exitPrice: exit,
          pnl,
          pct: entry > 0 ? ((exit - entry) / entry) * 100 : 0,
        };
        // Bucket by LOCAL date so day cells align with user's wall clock, not UTC.
        const sellDate = asUtcDate(t.timestamp);
        const key = sellDate
          ? `${sellDate.getFullYear()}-${String(sellDate.getMonth() + 1).padStart(2, '0')}-${String(sellDate.getDate()).padStart(2, '0')}`
          : t.timestamp.slice(0, 10);
        if (!byDay[key]) byDay[key] = { trades: [], pnl: 0, count: 0, winrate: null };
        byDay[key].trades.push(trip);
      }
    }
    for (const k in byDay) {
      const d = byDay[k];
      d.count = d.trades.length;
      d.pnl = d.trades.reduce((s, x) => s + x.pnl, 0);
      d.winrate = d.count ? Math.round(100 * d.trades.filter(x => x.pnl > 0).length / d.count) : null;
    }
    return byDay;
  });

  monthLabel = computed(() => `${MONTHS[this.currentMonth().m]} ${this.currentMonth().y}`);

  gridCells = computed(() => {
    const { y, m } = this.currentMonth();
    const first = new Date(y, m, 1).getDay();
    const days = new Date(y, m + 1, 0).getDate();
    const idx = this.dayIndex();
    const now = new Date();
    const cells: Array<{
      idx: number; empty: boolean; day?: number; key?: string;
      dayData?: DayData; isToday?: boolean;
    }> = [];
    for (let i = 0; i < first; i++) cells.push({ idx: i, empty: true });
    for (let d = 1; d <= days; d++) {
      const key = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      cells.push({
        idx: first + d,
        empty: false,
        day: d,
        key,
        dayData: idx[key],
        isToday: y === now.getFullYear() && m === now.getMonth() && d === now.getDate(),
      });
    }
    return cells;
  });

  selectedDay = computed<DayData | null>(() => {
    const k = this.selectedKey();
    if (!k) return null;
    const d = this.dayIndex()[k];
    return d && d.count > 0 ? d : null;
  });

  detailTitle = computed(() => {
    const k = this.selectedKey();
    const d = this.selectedDay();
    if (!k || !d) return '';
    const [, mm, dd] = k.split('-');
    return `${MONTHS[+mm - 1]} ${+dd} · ${d.count} ${d.count === 1 ? 'trade' : 'trades'}`;
  });

  summary = computed(() => {
    const { y, m } = this.currentMonth();
    const prefix = `${y}-${String(m + 1).padStart(2, '0')}-`;
    const idx = this.dayIndex();
    const activeKeys = Object.keys(idx).filter(k => k.startsWith(prefix) && idx[k].count > 0);
    const allTrips = activeKeys.flatMap(k => idx[k].trades);
    const total = allTrips.reduce((s, t) => s + t.pnl, 0);
    const wins = allTrips.filter(t => t.pnl > 0).length;
    const losses = allTrips.filter(t => t.pnl < 0).length;
    const pickPair = (k: string) =>
      idx[k].trades.slice().sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))[0]?.pair.replace('-USD', '') || '';
    let best: { key: string; pnl: number; topPair: string } | null = null;
    let worst: { key: string; pnl: number; topPair: string } | null = null;
    for (const k of activeKeys) {
      const p = idx[k].pnl;
      if (!best || p > best.pnl) best = { key: k, pnl: p, topPair: pickPair(k) };
      if (!worst || p < worst.pnl) worst = { key: k, pnl: p, topPair: pickPair(k) };
    }
    return {
      total,
      activeDays: activeKeys.length,
      wins, losses,
      tradeCount: allTrips.length,
      winRate: (wins + losses) ? Math.round(100 * wins / (wins + losses)) : 0,
      best, worst,
    };
  });

  ngOnChanges(changes: SimpleChanges) {
    if (changes['open'] && this.open()) {
      // reset to current month on open
      this.currentMonth.set(this.initMonth());
      this.selectedKey.set(null);
      this.pickerOpen.set(false);
    }
  }

  shiftMonth(d: number) {
    const cur = this.currentMonth();
    let m = cur.m + d, y = cur.y;
    if (m < 0) { m = 11; y--; }
    if (m > 11) { m = 0; y++; }
    this.currentMonth.set({ y, m });
    this.selectedKey.set(null);
    this.pickerOpen.set(false);
  }

  togglePicker(ev: MouseEvent) {
    ev.stopPropagation();
    const nowOpen = !this.pickerOpen();
    if (nowOpen) this.pickerYear.set(this.currentMonth().y);
    this.pickerOpen.set(nowOpen);
  }

  shiftYear(d: number) { this.pickerYear.update(y => y + d); }

  pickMonth(m: number) {
    this.currentMonth.set({ y: this.pickerYear(), m });
    this.pickerOpen.set(false);
    this.selectedKey.set(null);
  }

  monthHasData(y: number, m: number): boolean {
    const prefix = `${y}-${String(m + 1).padStart(2, '0')}-`;
    const idx = this.dayIndex();
    return Object.keys(idx).some(k => k.startsWith(prefix) && idx[k].count > 0);
  }

  monthNetPnl(y: number, m: number): number {
    const prefix = `${y}-${String(m + 1).padStart(2, '0')}-`;
    const idx = this.dayIndex();
    return Object.keys(idx).filter(k => k.startsWith(prefix)).reduce((s, k) => s + idx[k].pnl, 0);
  }

  selectDay(key: string) {
    const d = this.dayIndex()[key];
    if (!d || d.count === 0) { this.selectedKey.set(null); return; }
    this.selectedKey.set(key);
  }

  onOverlayClick(ev: MouseEvent) {
    if ((ev.target as HTMLElement).classList.contains('overlay')) this.emitClose();
  }

  emitClose() {
    this.pickerOpen.set(false);
    this.close.emit();
  }

  dayLabel(k: string): string {
    const [, mm, dd] = k.split('-');
    return `${MONTHS[+mm - 1].slice(0, 3)} ${+dd}`;
  }

  fmtMoney(v: number): string {
    if (Math.abs(v) < 0.005) return '$0';
    const s = v > 0 ? '+' : '\u2212';
    return `${s}$${Math.abs(v).toFixed(2)}`;
  }

  fmtPct(v: number): string {
    const s = v >= 0 ? '+' : '\u2212';
    return `${s}${Math.abs(v).toFixed(2)}%`;
  }

  fmtPrice(v: number): string {
    if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    if (v >= 1) return `$${v.toFixed(4)}`;
    return `$${v.toFixed(6)}`;
  }

  fmtTime(ts: string): string {
    return fmt12Hour(ts);
  }
}
