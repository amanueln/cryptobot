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

  constructor(private api: ApiService) {
    effect(() => {
      const container = this.chartContainer();
      const p = this.pair();
      if (!container || !p) return;
      if (!this.chart) this.initChart(container.nativeElement);
      this.loadData(p, '1m');
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
    this.api.fetchLiveCandles(pair, tf, 200).subscribe({
      next: (resp) => this.applyBars(resp.bars, resp.live),
      error: () => {},
    });
  }

  private applyBars(bars: LiveCandleBar[], live: LiveCandleBar | null): void {
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

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    if (this.chart) { this.chart.remove(); this.chart = null; }
  }
}
