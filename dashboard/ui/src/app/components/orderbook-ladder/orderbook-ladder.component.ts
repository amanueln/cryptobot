import {
  Component, inject, input, computed, signal, OnInit, OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ApiService, MomentumOrderbookData, MomentumOrderbookLevel, MomentumHoldingData, asUtcDate,
} from '../../services/api.service';

interface Row {
  price: number;
  size: number;
  usd: number;
  age_ms: number;
  barPct: number;
  isWall: boolean;
  isAnchor: boolean;
  fresh: boolean;
}

@Component({
  selector: 'app-orderbook-ladder',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (!ob() || !ob()!.available) {
      <div class="l2-card empty">
        <div class="l2-head">
          <span class="l2-title">Order book</span>
          <span class="l2-status"><span class="l2-dot off"></span>
            <span>{{ ob()?.reason ?? 'waiting for holding…' }}</span>
          </span>
        </div>
        <div class="l2-empty">WebSocket book unavailable. It activates on buy and stops on sell.</div>
      </div>
    } @else {
      <div class="l2-card">
        <div class="l2-head">
          <span class="l2-title">Order book · {{ ob()!.pair }}</span>
          <span class="l2-status">
            <span class="l2-dot" [class.off]="ageSec() > 10"></span>
            <span>{{ ageSec() > 10 ? 'stale' : 'live' }}</span>
            <span class="l2-age">· {{ ageDisplay() }}</span>
          </span>
        </div>
        <div class="l2-body">
          @for (r of asks(); track r.price) {
            <div class="l2-row ask" [class.wall]="r.isWall" [class.fresh]="r.fresh">
              <span class="price">{{ formatPrice(r.price) }}</span>
              <span class="bar" [style.width.%]="r.barPct"></span>
              <span class="size">{{ formatUsd(r.usd) }}</span>
              <span class="age">{{ formatAge(r.age_ms) }}</span>
            </div>
          }
          <div class="l2-mid">
            <span class="l2-mid-label">Mid</span>
            <span class="l2-mid-val">{{ formatPrice(ob()!.mid ?? 0) }}</span>
            <span class="l2-mid-spread">{{ (ob()!.spread_bps ?? 0).toFixed(1) }}bps</span>
          </div>
          @for (r of bids(); track r.price) {
            <div class="l2-row bid"
                 [class.wall]="r.isWall"
                 [class.fresh]="r.fresh"
                 [class.stop-anchor]="r.isAnchor">
              <span class="age">{{ formatAge(r.age_ms) }}</span>
              <span class="size">{{ formatUsd(r.usd) }}</span>
              <span class="bar" [style.width.%]="r.barPct"></span>
              <span class="price">{{ formatPrice(r.price) }}</span>
            </div>
          }
        </div>
        <div class="l2-signals">
          <span class="l2-sig-lbl">Spread</span>
          <span class="l2-sig-val">{{ (ob()!.spread_bps ?? 0).toFixed(1) }} bps</span>
          <span class="l2-sig-lbl">Bid imbalance</span>
          <span class="l2-sig-val" [class]="imbClass()">{{ imbPct().toFixed(0) }}% buy</span>
          <span class="l2-sig-lbl">Bids price→stop</span>
          <span class="l2-sig-val" [class]="stopDepthClass()">{{ formatUsd(stopDepthUsd()) }}</span>
          <span class="l2-sig-lbl">Anchor wall</span>
          <span class="l2-sig-val" [class]="anchorClass()">
            @if (anchorUsd() > 0) {
              {{ formatUsd(anchorUsd()) }} &#64; {{ formatPrice(anchorPrice()) }}
            } @else { — }
          </span>
        </div>
        <div class="l2-read">
          <div class="l2-read-head">
            <span class="l2-read-title">What the book is saying</span>
            <span class="l2-verdict" [class]="verdict()">{{ verdictText() }}</span>
          </div>
          <ul class="l2-read-list">
            @for (l of readLines(); track l.html) {
              <li>
                <span class="ic" [class]="l.ic">{{ l.ic === 'ok' ? '●' : l.ic === 'warn' ? '▲' : '✕' }}</span>
                <span [innerHTML]="l.html"></span>
              </li>
            }
          </ul>
        </div>
      </div>
    }
  `,
  styles: [`
    :host { display: block; min-width: 0; }
    .l2-card {
      background: #121821; border: 1px solid #25304a;
      border-radius: 8px; overflow: hidden;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }
    .l2-card.empty .l2-empty {
      padding: 16px; font-size: 11px; color: #5a6679; line-height: 1.5;
    }
    .l2-head {
      display: flex; justify-content: space-between; align-items: center;
      padding: 8px 12px; border-bottom: 1px solid #25304a; background: #182030;
    }
    .l2-title {
      font-size: 10px; font-weight: 600; color: #8895ad;
      text-transform: uppercase; letter-spacing: .3px;
    }
    .l2-status { display: flex; align-items: center; gap: 5px; font-size: 10px; color: #8895ad; }
    .l2-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 6px #22c55e; }
    .l2-dot.off { background: #5a6679; box-shadow: none; }
    .l2-age { color: #5a6679; font-variant-numeric: tabular-nums; }

    .l2-body { padding: 6px 0; font-variant-numeric: tabular-nums; }
    .l2-row {
      display: grid; align-items: center; height: 17px; padding: 0 10px;
      font-size: 10.5px; position: relative;
    }
    .l2-row.ask { grid-template-columns: 62px 1fr 52px 22px; }
    .l2-row.bid { grid-template-columns: 22px 52px 1fr 62px; }
    .l2-row .price { font-weight: 500; }
    .l2-row.bid .price { color: #22c55e; }
    .l2-row.ask .price { color: #ef4444; }
    .l2-row .bar {
      height: 11px; border-radius: 2px; margin: 0 5px;
      opacity: .45; z-index: 0;
    }
    .l2-row.bid .bar { background: #22c55e; justify-self: end; }
    .l2-row.ask .bar { background: #ef4444; justify-self: start; }
    .l2-row .size { font-size: 10px; color: #8895ad; z-index: 2; position: relative; }
    .l2-row.bid .size { text-align: right; }
    .l2-row.ask .size { text-align: left; }
    .l2-row .age { font-size: 9px; color: #5a6679; z-index: 2; position: relative; }
    .l2-row.bid .age { text-align: left; }
    .l2-row.ask .age { text-align: right; }
    .l2-row.fresh .age { color: #22c55e; font-weight: 600; }
    .l2-row.wall .bar { opacity: .8; box-shadow: 0 0 6px currentColor; }
    .l2-row.wall .size {
      color: #fbbf24; font-weight: 600;
      text-shadow: 0 0 3px #0b0f17, 0 0 3px #0b0f17;
    }
    .l2-row.stop-anchor {
      background: linear-gradient(90deg, rgba(251,191,36,.22), transparent);
      border-left: 2px solid #fbbf24;
      padding-left: 8px;
    }
    .l2-row.stop-anchor .price { color: #fbbf24; font-weight: 700; }

    .l2-mid {
      display: flex; justify-content: space-between; align-items: center;
      padding: 5px 10px; margin: 3px 0;
      background: linear-gradient(90deg, rgba(59,130,246,0), rgba(59,130,246,.12) 50%, rgba(59,130,246,0));
      border-top: 1px dashed #25304a; border-bottom: 1px dashed #25304a;
      font-size: 11px; font-weight: 600;
    }
    .l2-mid-label { color: #8895ad; font-size: 9px; text-transform: uppercase; letter-spacing: .3px; }
    .l2-mid-val { font-variant-numeric: tabular-nums; color: #e6ecf5; }
    .l2-mid-spread { color: #5a6679; font-size: 10px; }

    .l2-signals {
      padding: 8px 12px; border-top: 1px solid #25304a; background: #182030;
      font-size: 10.5px; display: grid; grid-template-columns: 1fr auto; gap: 3px 8px;
    }
    .l2-sig-lbl { color: #8895ad; }
    .l2-sig-val {
      font-weight: 600; text-align: right; color: #e6ecf5;
      font-variant-numeric: tabular-nums;
    }
    .l2-sig-val.good { color: #22c55e; }
    .l2-sig-val.warn { color: #fbbf24; }
    .l2-sig-val.bad  { color: #ef4444; }

    .l2-read { border-top: 1px solid #25304a; padding: 8px 12px; background: #0f1520; }
    .l2-read-head {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 6px;
    }
    .l2-read-title {
      font-size: 9px; font-weight: 600; color: #8895ad;
      text-transform: uppercase; letter-spacing: .3px;
    }
    .l2-verdict {
      font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 3px;
      text-transform: uppercase; letter-spacing: .3px;
    }
    .l2-verdict.hold { background: rgba(34,197,94,.15); color: #22c55e; }
    .l2-verdict.watch { background: rgba(251,191,36,.15); color: #fbbf24; }
    .l2-verdict.risk { background: rgba(239,68,68,.18); color: #ef4444; }
    .l2-read-list {
      list-style: none; margin: 0; padding: 0;
      display: flex; flex-direction: column; gap: 4px;
    }
    .l2-read-list li {
      display: grid; grid-template-columns: 12px 1fr; gap: 6px;
      align-items: start; font-size: 10.5px; line-height: 1.35;
      color: #e6ecf5;
    }
    .l2-read-list .ic {
      text-align: center; font-weight: 700; font-size: 9px; margin-top: 1px;
    }
    .l2-read-list .ic.ok { color: #22c55e; }
    .l2-read-list .ic.warn { color: #fbbf24; }
    .l2-read-list .ic.bad { color: #ef4444; }
    .l2-read-list .hi { font-weight: 600; font-variant-numeric: tabular-nums; }
    .l2-read-list .dim { color: #5a6679; }
  `],
})
export class OrderbookLadderComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);

  readonly holding = input<MomentumHoldingData | null>(null);
  readonly wallAwareEnabled = input<boolean>(false);

  readonly ob = this.api.momentumOrderbook;

  private refreshHandle: ReturnType<typeof setInterval> | null = null;
  private ageHandle: ReturnType<typeof setInterval> | null = null;
  private tickSignal = signal(0);

  ngOnInit(): void {
    this.api.refreshMomentumOrderbook();
    this.refreshHandle = setInterval(() => this.api.refreshMomentumOrderbook(), 1500);
    this.ageHandle = setInterval(() => this.tickSignal.update(n => n + 1), 500);
  }

  ngOnDestroy(): void {
    if (this.refreshHandle) clearInterval(this.refreshHandle);
    if (this.ageHandle) clearInterval(this.ageHandle);
  }

  ageSec = computed(() => {
    this.tickSignal();
    const w = this.ob()?.written_at;
    if (!w) return 999;
    return (Date.now() - (asUtcDate(w)?.getTime() ?? Date.now())) / 1000;
  });

  ageDisplay = computed(() => {
    const s = this.ageSec();
    if (s < 1) return '0.0s';
    if (s < 60) return `${s.toFixed(1)}s`;
    return `${Math.round(s / 60)}m`;
  });

  private maxUsd = computed(() => {
    const o = this.ob();
    if (!o) return 1;
    const all = [...(o.bids ?? []), ...(o.asks ?? [])].map(l => l.usd);
    return Math.max(1, ...all);
  });

  private wallThreshUsd = computed(() => {
    const o = this.ob();
    if (!o) return Infinity;
    const all = [...(o.bids ?? []), ...(o.asks ?? [])].map(l => l.usd).sort((a, b) => a - b);
    if (all.length === 0) return Infinity;
    const median = all[Math.floor(all.length / 2)] ?? 0;
    return median * 3;
  });

  private anchorPriceRaw = computed(() => this.holding()?.active_anchor_price ?? 0);

  asks = computed<Row[]>(() => {
    const o = this.ob();
    if (!o) return [];
    const max = this.maxUsd();
    const wall = this.wallThreshUsd();
    const list = (o.asks ?? []).slice(0, 11);
    return list.map(l => this.toRow(l, max, wall, false)).reverse();
  });

  bids = computed<Row[]>(() => {
    const o = this.ob();
    if (!o) return [];
    const max = this.maxUsd();
    const wall = this.wallThreshUsd();
    const anchor = this.anchorPriceRaw();
    const list = (o.bids ?? []).slice(0, 11);
    return list.map(l => ({
      ...this.toRow(l, max, wall, false),
      isAnchor: this.wallAwareEnabled() && anchor > 0 && Math.abs(l.price - anchor) < 1e-9,
    }));
  });

  private toRow(l: MomentumOrderbookLevel, max: number, wallThresh: number, isAnchor: boolean): Row {
    return {
      price: l.price,
      size: l.size,
      usd: l.usd,
      age_ms: l.age_ms,
      barPct: Math.min(100, (l.usd / max) * 100),
      isWall: l.usd >= wallThresh,
      isAnchor,
      fresh: l.age_ms < 1500,
    };
  }

  imbPct = computed(() => {
    const o = this.ob();
    if (!o || o.mid == null) return 50;
    const mid = o.mid;
    const bidNear = (o.bids ?? [])
      .filter(b => (mid - b.price) / mid * 100 < 1)
      .reduce((a, b) => a + b.usd, 0);
    const askNear = (o.asks ?? [])
      .filter(a => (a.price - mid) / mid * 100 < 1)
      .reduce((a, b) => a + b.usd, 0);
    const total = bidNear + askNear;
    return total > 0 ? (bidNear / total) * 100 : 50;
  });

  imbClass = computed(() => {
    const i = this.imbPct();
    return i >= 58 ? 'good' : i <= 42 ? 'bad' : 'warn';
  });

  private equityUsd = computed(() => {
    const h = this.holding();
    if (!h) return 0;
    return h.shares * (h.current_price || 0);
  });

  private activeStop = computed(() => {
    const h = this.holding();
    if (!h) return 0;
    if (this.wallAwareEnabled() && (h.wall_aware_stop ?? 0) > 0) {
      return Math.max(h.wall_aware_stop ?? 0, h.price_only_stop ?? 0);
    }
    return h.price_only_stop ?? h.stop_price ?? 0;
  });

  stopDepthUsd = computed(() => {
    const o = this.ob();
    const mid = o?.mid ?? 0;
    const stop = this.activeStop();
    if (!o || stop <= 0) return 0;
    return (o.bids ?? [])
      .filter(b => b.price <= mid && b.price >= stop)
      .reduce((a, b) => a + b.usd, 0);
  });

  stopDepthClass = computed(() => {
    const d = this.stopDepthUsd();
    const e = this.equityUsd();
    if (e === 0) return '';
    return d > e * 5 ? 'good' : d > e ? 'warn' : 'bad';
  });

  anchorUsd = computed(() => this.holding()?.active_anchor_usd ?? 0);
  anchorPrice = computed(() => this.holding()?.active_anchor_price ?? 0);
  anchorClass = computed(() => this.anchorUsd() > 0 ? 'good' : '');

  readLines = computed<{ ic: 'ok' | 'warn' | 'bad'; html: string }[]>(() => {
    const lines: { ic: 'ok' | 'warn' | 'bad'; html: string }[] = [];
    const imb = this.imbPct();
    const sp = this.ob()?.spread_bps ?? 0;
    const dep = this.stopDepthUsd();
    const eq = this.equityUsd();
    const aUsd = this.anchorUsd();

    if (imb >= 60) lines.push({ ic: 'ok', html: `<span class="hi">Buyers in control</span> — ${imb.toFixed(0)}% bid near mid.` });
    else if (imb <= 40) lines.push({ ic: 'bad', html: `<span class="hi">Sellers heavy</span> — ${imb.toFixed(0)}% bid.` });
    else lines.push({ ic: 'warn', html: `<span class="hi">Balanced</span> — ${imb.toFixed(0)}% buy.` });

    if (aUsd > 0 && eq > 0) {
      if (aUsd > eq * 3) lines.push({ ic: 'ok', html: `<span class="hi">Strong support</span> — ${this.formatUsd(aUsd)} (${(aUsd / eq).toFixed(1)}× position).` });
      else lines.push({ ic: 'warn', html: `<span class="hi">Moderate wall</span> — ${this.formatUsd(aUsd)}.` });
    } else if (this.wallAwareEnabled()) {
      lines.push({ ic: 'warn', html: `<span class="hi">No qualifying wall</span> — using price-only trail.` });
    }

    if (eq > 0) {
      if (dep > eq * 5) lines.push({ ic: 'ok', html: `<span class="hi">Stop cushioned</span> — ${this.formatUsd(dep)} between price and stop.` });
      else if (dep > eq) lines.push({ ic: 'warn', html: `<span class="hi">Thin cushion</span> — ${this.formatUsd(dep)}.` });
      else lines.push({ ic: 'bad', html: `<span class="hi">Almost no cushion</span> above stop.` });
    }

    if (sp <= 5) lines.push({ ic: 'ok', html: `<span class="hi">Tight spread</span> (${sp.toFixed(1)} bps).` });
    else if (sp <= 20) lines.push({ ic: 'warn', html: `<span class="hi">Moderate spread</span> (${sp.toFixed(1)} bps).` });
    else lines.push({ ic: 'bad', html: `<span class="hi">Wide spread</span> (${sp.toFixed(1)} bps).` });
    return lines;
  });

  verdict = computed<'hold' | 'watch' | 'risk'>(() => {
    const lines = this.readLines();
    const score = lines.reduce((a, l) => a + (l.ic === 'ok' ? 1 : l.ic === 'bad' ? -1 : 0), 0);
    return score >= 2 ? 'hold' : score <= -2 ? 'risk' : 'watch';
  });

  verdictText = computed(() => {
    const v = this.verdict();
    return v === 'hold' ? 'Book supports holding' : v === 'risk' ? 'Risk rising' : 'Mixed — watch';
  });

  formatPrice(p: number): string {
    if (p >= 1) return '$' + p.toFixed(4);
    if (p >= 0.01) return '$' + p.toFixed(4);
    return '$' + p.toFixed(6);
  }

  formatUsd(u: number): string {
    if (u >= 1e6) return '$' + (u / 1e6).toFixed(1) + 'M';
    if (u >= 1000) return '$' + (u / 1000).toFixed(1) + 'k';
    return '$' + u.toFixed(0);
  }

  formatAge(ms: number): string {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
    return `${Math.round(ms / 60_000)}m`;
  }
}
