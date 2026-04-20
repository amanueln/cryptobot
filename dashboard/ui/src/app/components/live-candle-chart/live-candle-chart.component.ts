import {
  Component, input, effect, ElementRef, viewChild, OnDestroy,
} from '@angular/core';
import {
  createChart, IChartApi, ISeriesApi, Time,
  CandlestickSeries, CandlestickData,
} from 'lightweight-charts';
import { ApiService, LiveCandleBar } from '../../services/api.service';

@Component({
  selector: 'app-live-candle-chart',
  standalone: true,
  template: `
    <div class="live-chart-root">
      <div #chartContainer class="chart-container" [style.height.px]="height()"></div>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }
    .live-chart-root { width: 100%; background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; overflow: hidden; }
    .chart-container { width: 100%; }
  `],
})
export class LiveCandleChartComponent implements OnDestroy {
  pair = input.required<string>();
  entry = input<number>(0);
  trailStop = input<number>(0);
  height = input<number>(160);

  chartContainer = viewChild<ElementRef<HTMLDivElement>>('chartContainer');

  private chart: IChartApi | null = null;
  private candleSeries: ISeriesApi<'Candlestick'> | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private visHandler: (() => void) | null = null;
  private currentTf: '1m' | '5m' | '15m' | '1h' = '1m';
  private lastLiveBucketMs = 0;

  constructor(private api: ApiService) {
    effect(() => {
      const container = this.chartContainer();
      const p = this.pair();
      if (!container || !p) return;
      if (!this.chart) this.initChart(container.nativeElement);
      this.loadData(p, this.currentTf);
      this.startPolling();
    });
  }

  private initChart(container: HTMLDivElement): void {
    this.chart = createChart(container, {
      width: container.clientWidth,
      height: this.height(),
      layout: { background: { color: '#0f1117' }, textColor: '#8895ad' },
      grid: { vertLines: { color: '#1e2130' }, horzLines: { color: '#1e2130' } },
      rightPriceScale: { borderColor: '#1e2130' },
      timeScale: { borderColor: '#1e2130', timeVisible: true, secondsVisible: false },
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
    const series: CandlestickData<Time>[] = bars.map(b => ({
      time: (b.t / 1000) as Time, open: b.open, high: b.high, low: b.low, close: b.close,
    }));
    if (live) series.push({
      time: (live.t / 1000) as Time,
      open: live.open, high: live.high, low: live.low, close: live.close,
    });
    this.candleSeries.setData(series);
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
      },
      error: () => {},
    });
  }

  ngOnDestroy(): void {
    this.stopPolling();
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.candleSeries = null;
    if (this.chart) { this.chart.remove(); this.chart = null; }
  }
}
