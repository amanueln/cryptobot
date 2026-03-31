import { Component, input, effect, ElementRef, viewChild, OnDestroy } from '@angular/core';
import {
  createChart, IChartApi, ISeriesApi, Time, IPriceLine,
  CandlestickSeries, LineSeries,
  CandlestickData, LineData,
  createSeriesMarkers,
} from 'lightweight-charts';
import { CandleData, TradeData, IndicatorData, PositionData } from '../../services/api.service';

@Component({
  selector: 'app-price-chart',
  standalone: true,
  template: `
    <div class="chart-wrapper">
      <div #chartContainer class="chart-container"></div>
    </div>
  `,
  styles: [`
    .chart-wrapper {
      width: 100%;
      background: #0f1117;
      border-radius: 8px;
      overflow: hidden;
    }
    .chart-container {
      width: 100%;
      height: 450px;
    }
  `]
})
export class PriceChartComponent implements OnDestroy {
  candles = input<CandleData[]>([]);
  trades = input<TradeData[]>([]);
  indicators = input<IndicatorData[]>([]);
  gridLevels = input<{ price: number; type: string }[]>([]);
  rangeLower = input<number>(0);
  rangeUpper = input<number>(0);
  positions = input<PositionData[]>([]);

  chartContainer = viewChild<ElementRef<HTMLDivElement>>('chartContainer');

  private chart: IChartApi | null = null;
  private candleSeries: ISeriesApi<'Candlestick'> | null = null;
  private ema50Series: ISeriesApi<'Line'> | null = null;
  private ema200Series: ISeriesApi<'Line'> | null = null;
  private bbUpperSeries: ISeriesApi<'Line'> | null = null;
  private bbLowerSeries: ISeriesApi<'Line'> | null = null;
  private gridPriceLines: IPriceLine[] = [];
  private rangePriceLines: IPriceLine[] = [];
  private currentPriceLine: IPriceLine | null = null;
  private entryPriceLines: IPriceLine[] = [];
  private markersPlugin: any = null;
  private resizeObserver: ResizeObserver | null = null;

  constructor() {
    effect(() => {
      const container = this.chartContainer();
      if (!container) return;

      if (!this.chart) {
        this.initChart(container.nativeElement);
      }

      this.updateCandles();
      this.updateIndicators();
      this.updateTrades();
      this.updateGridLevels();
    });
  }

  private initChart(container: HTMLDivElement): void {
    this.chart = createChart(container, {
      width: container.clientWidth,
      height: 450,
      layout: {
        background: { color: '#0f1117' },
        textColor: '#8b8fa3',
      },
      grid: {
        vertLines: { color: '#1e2130' },
        horzLines: { color: '#1e2130' },
      },
      crosshair: {
        vertLine: { color: '#444860', width: 1, style: 1 },
        horzLine: { color: '#444860', width: 1, style: 1 },
      },
      rightPriceScale: {
        borderColor: '#1e2130',
      },
      timeScale: {
        borderColor: '#1e2130',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    this.candleSeries = this.chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    this.ema50Series = this.chart.addSeries(LineSeries, {
      color: '#f0c040',
      lineWidth: 1,
      title: 'EMA 50',
      priceLineVisible: false,
      lastValueVisible: false,
    });

    this.ema200Series = this.chart.addSeries(LineSeries, {
      color: '#00bcd4',
      lineWidth: 1,
      title: 'EMA 200',
      priceLineVisible: false,
      lastValueVisible: false,
    });

    this.bbUpperSeries = this.chart.addSeries(LineSeries, {
      color: 'rgba(100, 149, 237, 0.6)',
      lineWidth: 1,
      title: 'BB Upper',
      priceLineVisible: false,
      lastValueVisible: false,
      lineStyle: 2,
    });

    this.bbLowerSeries = this.chart.addSeries(LineSeries, {
      color: 'rgba(100, 149, 237, 0.6)',
      lineWidth: 1,
      title: 'BB Lower',
      priceLineVisible: false,
      lastValueVisible: false,
      lineStyle: 2,
    });

    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (this.chart) {
          this.chart.applyOptions({ width });
        }
      }
    });
    this.resizeObserver.observe(container);
  }

  private toTime(isoString: string): Time {
    return (isoString as unknown) as Time;
  }

  private updateCandles(): void {
    if (!this.candleSeries) return;
    const data = this.candles();
    if (!data.length) return;

    const chartData: CandlestickData<Time>[] = data.map(c => ({
      time: this.toTime(c.time),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    this.candleSeries.setData(chartData);
  }

  private updateIndicators(): void {
    const indicatorList = this.indicators();
    if (!indicatorList.length) return;

    const ema50Data: LineData<Time>[] = [];
    const ema200Data: LineData<Time>[] = [];
    const bbUpperData: LineData<Time>[] = [];
    const bbLowerData: LineData<Time>[] = [];

    for (const ind of indicatorList) {
      const time = this.toTime(ind.time);
      if (ind.ema50 != null) ema50Data.push({ time, value: ind.ema50 });
      if (ind.ema200 != null) ema200Data.push({ time, value: ind.ema200 });
      if (ind.bb_upper != null) bbUpperData.push({ time, value: ind.bb_upper });
      if (ind.bb_lower != null) bbLowerData.push({ time, value: ind.bb_lower });
    }

    if (this.ema50Series && ema50Data.length) this.ema50Series.setData(ema50Data);
    if (this.ema200Series && ema200Data.length) this.ema200Series.setData(ema200Data);
    if (this.bbUpperSeries && bbUpperData.length) this.bbUpperSeries.setData(bbUpperData);
    if (this.bbLowerSeries && bbLowerData.length) this.bbLowerSeries.setData(bbLowerData);
  }

  private updateTrades(): void {
    if (!this.candleSeries) return;
    const tradeList = this.trades();
    if (!tradeList.length) return;

    const markers = tradeList.map(trade => ({
      time: this.toTime(trade.timestamp),
      position: trade.side === 'buy' ? 'belowBar' as const : 'aboveBar' as const,
      color: trade.side === 'buy' ? '#26a69a' : '#ef5350',
      shape: trade.side === 'buy' ? 'arrowUp' as const : 'arrowDown' as const,
      text: `${trade.side === 'buy' ? 'B' : 'S'} $${trade.price.toFixed(4)}`,
      size: 1,
    }));

    markers.sort((a, b) => (a.time as string).localeCompare(b.time as string));
    if (!this.markersPlugin) {
      this.markersPlugin = createSeriesMarkers(this.candleSeries, markers);
    } else {
      this.markersPlugin.setMarkers(markers);
    }
  }

  private updateGridLevels(): void {
    if (!this.chart || !this.candleSeries) return;

    // Remove old grid price lines
    for (const pl of this.gridPriceLines) {
      this.candleSeries.removePriceLine(pl);
    }
    this.gridPriceLines = [];

    // Remove old range price lines
    for (const pl of this.rangePriceLines) {
      this.candleSeries.removePriceLine(pl);
    }
    this.rangePriceLines = [];

    // Remove old current price line
    if (this.currentPriceLine) {
      this.candleSeries.removePriceLine(this.currentPriceLine);
      this.currentPriceLine = null;
    }

    // Remove old entry price lines
    for (const pl of this.entryPriceLines) {
      this.candleSeries.removePriceLine(pl);
    }
    this.entryPriceLines = [];

    const levels = this.gridLevels();
    const candles = this.candles();

    // Current price line (bright white)
    if (candles.length) {
      const currentPrice = candles[candles.length - 1].close;
      this.currentPriceLine = this.candleSeries.createPriceLine({
        price: currentPrice,
        color: '#ffffff',
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: 'Current',
      });
    }

    // Grid level price lines — green for buy, red for sell
    if (levels.length) {
      for (const level of levels) {
        const pl = this.candleSeries.createPriceLine({
          price: level.price,
          color: level.type === 'buy' ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)',
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: false,
          title: '',
        });
        this.gridPriceLines.push(pl);
      }
    }

    // Range boundary price lines
    const lower = this.rangeLower();
    const upper = this.rangeUpper();
    if (lower > 0 && upper > 0) {
      this.rangePriceLines.push(
        this.candleSeries.createPriceLine({
          price: lower,
          color: 'rgba(139, 143, 163, 0.6)',
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: 'Range Low',
        }),
        this.candleSeries.createPriceLine({
          price: upper,
          color: 'rgba(139, 143, 163, 0.6)',
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: 'Range High',
        })
      );
    }

    // Entry price lines for open positions (amber)
    const positionList = this.positions();
    for (const pos of positionList) {
      if (pos.quantity > 0) {
        const label = `Entry ${pos.pair.replace('-USD', '')}`;
        const pl = this.candleSeries.createPriceLine({
          price: pos.entry_price,
          color: '#f59e0b',
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: label,
        });
        this.entryPriceLines.push(pl);
      }
    }
  }

  ngOnDestroy(): void {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }
    this.gridPriceLines = [];
    this.rangePriceLines = [];
    this.currentPriceLine = null;
    this.entryPriceLines = [];
    if (this.chart) {
      this.chart.remove();
      this.chart = null;
    }
  }
}
