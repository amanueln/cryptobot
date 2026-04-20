import {
  Component, input, output, effect, ElementRef, viewChild, OnDestroy, signal,
} from '@angular/core';
import {
  createChart, IChartApi, ISeriesApi, IPriceLine, Time, LogicalRange,
  CandlestickSeries, CandlestickData,
} from 'lightweight-charts';
import { ApiService, LiveCandleBar } from '../../services/api.service';

@Component({
  selector: 'app-live-candle-chart',
  standalone: true,
  template: `
    <div class="live-chart-root">
      <div class="chart-top">
        <div class="tf-group">
          <button class="tf-btn" [class.active]="currentTf === '1m'"  (click)="setTf('1m')">1m</button>
          <button class="tf-btn" [class.active]="currentTf === '5m'"  (click)="setTf('5m')">5m</button>
          <button class="tf-btn" [class.active]="currentTf === '15m'" (click)="setTf('15m')">15m</button>
          <button class="tf-btn" [class.active]="currentTf === '1h'"  (click)="setTf('1h')">1h</button>
        </div>
        <span class="top-right">
          <button class="jump-live" [class.show]="pannedOff()" (click)="snapToLive()">● go live</button>
          <span class="live-pill">LIVE · 1Hz</span>
        </span>
      </div>
      <div #chartContainer class="chart-container" [style.height.px]="height()"></div>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }
    .live-chart-root { width: 100%; background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; overflow: hidden; }
    .chart-top { display: flex; justify-content: space-between; align-items: center; padding: 4px 6px; }
    .tf-group { display: flex; gap: 2px; }
    .tf-btn {
      background: transparent; color: #8895ad;
      border: 1px solid #2d3148; border-radius: 3px;
      padding: 2px 8px; font-size: 11px; cursor: pointer; font-family: inherit;
    }
    .tf-btn:hover { border-color: #3b82f6; color: #e6ecf5; }
    .tf-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
    .live-pill {
      background: rgba(34,197,94,.15); color: #22c55e;
      padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600;
      letter-spacing: .5px;
    }
    .live-pill::before {
      content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
      background: #22c55e; margin-right: 5px; animation: pulse 1s infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .3 } }
    .chart-container { width: 100%; }
    .top-right { display: inline-flex; align-items: center; gap: 6px; }
    .jump-live {
      display: none;
      background: #22c55e; color: #0b0f17;
      border: 1px solid #22c55e; border-radius: 10px;
      padding: 2px 8px; font-size: 10px; font-weight: 700; cursor: pointer;
      font-family: inherit; letter-spacing: .3px;
    }
    .jump-live.show { display: inline-block; }
    .jump-live:hover { background: #16a34a; border-color: #16a34a; }
  `],
})
export class LiveCandleChartComponent implements OnDestroy {
  pair = input.required<string>();
  entry = input<number>(0);
  trailStop = input<number>(0);
  height = input<number>(160);

  readonly openExpanded = output<void>();

  chartContainer = viewChild<ElementRef<HTMLDivElement>>('chartContainer');

  private dragStartX = 0;
  private dragStartY = 0;

  private chart: IChartApi | null = null;
  private candleSeries: ISeriesApi<'Candlestick'> | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private visHandler: (() => void) | null = null;
  public currentTf: '1m' | '5m' | '15m' | '1h' = '1m';
  private lastLiveBucketMs = 0;
  private entryLine: IPriceLine | null = null;
  private trailLine: IPriceLine | null = null;
  private nowLine: IPriceLine | null = null;
  private lastNowPrice = 0;
  readonly pannedOff = signal(false);
  private barCount = 0;

  constructor(private api: ApiService) {
    effect(() => {
      const container = this.chartContainer();
      const p = this.pair();
      if (!container || !p) return;
      if (!this.chart) this.initChart(container.nativeElement);
      this.loadData(p, this.currentTf);
      this.startPolling();
    });

    effect(() => {
      const e = this.entry();
      const t = this.trailStop();
      if (!this.candleSeries) return;
      if (this.entryLine) { this.candleSeries.removePriceLine(this.entryLine); this.entryLine = null; }
      if (this.trailLine) { this.candleSeries.removePriceLine(this.trailLine); this.trailLine = null; }
      if (e > 0) {
        this.entryLine = this.candleSeries.createPriceLine({
          price: e, color: '#3b82f6', lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: 'entry',
        });
      }
      if (t > 0) {
        this.trailLine = this.candleSeries.createPriceLine({
          price: t, color: '#ef4444', lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: 'trail',
        });
      }
    });
  }

  // lightweight-charts passes Time as UTCTimestamp (seconds) for our intraday data.
  // Render 12-hour AM/PM clock (no seconds — matches secondsVisible: false).
  private formatAxisTime(t: Time): string {
    const d = new Date((t as number) * 1000);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
  }

  private initChart(container: HTMLDivElement): void {
    this.chart = createChart(container, {
      width: container.clientWidth,
      height: this.height(),
      layout: { background: { color: '#0f1117' }, textColor: '#8895ad' },
      grid: { vertLines: { color: '#1e2130' }, horzLines: { color: '#1e2130' } },
      rightPriceScale: { borderColor: '#1e2130' },
      localization: { timeFormatter: (t: Time) => this.formatAxisTime(t) },
      timeScale: {
        borderColor: '#1e2130',
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (t: Time) => this.formatAxisTime(t),
      },
    });
    this.candleSeries = this.chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e', downColor: '#ef4444',
      borderUpColor: '#22c55e', borderDownColor: '#ef4444',
      wickUpColor: '#22c55e', wickDownColor: '#ef4444',
    });

    this.resizeObserver = new ResizeObserver(entries => {
      for (const e of entries) this.chart?.applyOptions({ width: e.contentRect.width });
    });
    this.resizeObserver.observe(container);

    this.chart.timeScale().subscribeVisibleLogicalRangeChange((range: LogicalRange | null) => {
      if (!range) { this.pannedOff.set(false); return; }
      const lastIdx = this.barCount - 1;
      this.pannedOff.set(range.to < lastIdx - 1);
    });
    container.addEventListener('dblclick', () => this.snapToLive());
    container.addEventListener('pointerdown', (e: PointerEvent) => {
      this.dragStartX = e.clientX;
      this.dragStartY = e.clientY;
    });
    container.addEventListener('pointerup', (e: PointerEvent) => {
      const dx = Math.abs(e.clientX - this.dragStartX);
      const dy = Math.abs(e.clientY - this.dragStartY);
      if (dx < 4 && dy < 4) this.openExpanded.emit();
    });
  }

  private loadData(pair: string, tf: '1m' | '5m' | '15m' | '1h'): void {
    this.lastLiveBucketMs = 0;
    this.api.fetchLiveCandles(pair, tf, 200).subscribe({
      next: (resp) => {
        this.setAllBars(resp.bars, resp.live);
        this.lastLiveBucketMs = resp.live?.t ?? 0;
      },
      error: () => {},
    });
  }

  private setAllBars(bars: LiveCandleBar[], live: LiveCandleBar | null): void {
    if (!this.candleSeries) return;
    this.barCount = bars.length + (live ? 1 : 0);
    const series: CandlestickData<Time>[] = bars.map(b => ({
      time: (b.t / 1000) as Time, open: b.open, high: b.high, low: b.low, close: b.close,
    }));
    if (live) series.push({
      time: (live.t / 1000) as Time,
      open: live.open, high: live.high, low: live.low, close: live.close,
    });
    this.candleSeries.setData(series);
    this.updateNowLine(bars, live);
  }

  private updateNowLine(bars: LiveCandleBar[], live: LiveCandleBar | null): void {
    if (!this.candleSeries) return;
    const nowPrice = live?.close ?? (bars.length ? bars[bars.length - 1].close : 0);
    if (!nowPrice || nowPrice === this.lastNowPrice) return;
    if (this.nowLine) this.candleSeries.removePriceLine(this.nowLine);
    this.nowLine = this.candleSeries.createPriceLine({
      price: nowPrice, color: '#fbbf24', lineWidth: 1, lineStyle: 2,
      axisLabelVisible: true, title: 'now',
    });
    this.lastNowPrice = nowPrice;
  }

  private startPolling(): void {
    this.stopPolling();
    this.pollTimer = setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      this.tick();
    }, 1000);
    this.visHandler = () => { if (document.visibilityState === 'visible') this.tick(); };
    document.addEventListener('visibilitychange', this.visHandler);
  }

  private stopPolling(): void {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
    if (this.visHandler) { document.removeEventListener('visibilitychange', this.visHandler); this.visHandler = null; }
  }

  private tick(): void {
    const p = this.pair();
    if (!p || !this.candleSeries) return;
    this.api.fetchLiveCandles(p, this.currentTf, 200).subscribe({
      next: (resp) => {
        const live = resp.live;
        const newestHistorical = resp.bars.length ? resp.bars[resp.bars.length - 1] : null;

        // If a new closed bar appeared (lastLiveBucketMs advanced), reload full window.
        if (live && this.lastLiveBucketMs && live.t !== this.lastLiveBucketMs) {
          this.setAllBars(resp.bars, live);
          this.barCount = resp.bars.length + (resp.live ? 1 : 0);
          this.lastLiveBucketMs = live.t;
          return;
        }
        // Otherwise just update the live-forming bar in place.
        if (live) {
          this.candleSeries?.update({
            time: (live.t / 1000) as Time,
            open: live.open, high: live.high, low: live.low, close: live.close,
          });
          if (!this.lastLiveBucketMs) this.lastLiveBucketMs = live.t;
        } else if (newestHistorical) {
          this.candleSeries?.update({
            time: (newestHistorical.t / 1000) as Time,
            open: newestHistorical.open, high: newestHistorical.high,
            low: newestHistorical.low, close: newestHistorical.close,
          });
        }
        this.updateNowLine(resp.bars, resp.live);
      },
      error: () => {},
    });
  }

  setTf(tf: '1m' | '5m' | '15m' | '1h'): void {
    if (tf === this.currentTf) return;
    this.currentTf = tf;
    this.lastLiveBucketMs = 0;
    const p = this.pair();
    if (p) this.loadData(p, tf);
  }

  snapToLive(): void {
    this.chart?.timeScale().scrollToRealTime();
    this.pannedOff.set(false);
  }

  ngOnDestroy(): void {
    this.stopPolling();
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.candleSeries = null;
    if (this.chart) { this.chart.remove(); this.chart = null; }
  }
}
