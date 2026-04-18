import { Component, input, effect, ElementRef, viewChild, OnDestroy } from '@angular/core';
import { Chart, registerables } from 'chart.js';
import { IndicatorData, asUtcDate } from '../../services/api.service';

Chart.register(...registerables);

@Component({
  selector: 'app-indicator-panel',
  standalone: true,
  imports: [],
  template: `
    <div class="indicator-panel">
      <div class="chart-wrapper">
        <span class="chart-label">ADX</span>
        <canvas #adxCanvas></canvas>
      </div>
      <div class="chart-wrapper">
        <span class="chart-label">RSI</span>
        <canvas #rsiCanvas></canvas>
      </div>
      <div class="chart-wrapper">
        <span class="chart-label">Volume</span>
        <canvas #volumeCanvas></canvas>
      </div>
      <div class="chart-wrapper">
        <span class="chart-label">OBV</span>
        <canvas #obvCanvas></canvas>
      </div>
    </div>
  `,
  styles: [`
    .indicator-panel {
      display: flex;
      flex-direction: column;
      gap: 4px;
      width: 100%;
      background: transparent;
    }
    .chart-wrapper {
      position: relative;
      height: 120px;
      width: 100%;
    }
    .chart-label {
      position: absolute;
      top: 4px;
      left: 8px;
      font-size: 11px;
      color: #8b8fa3;
      z-index: 1;
      pointer-events: none;
      font-family: sans-serif;
    }
    canvas {
      width: 100% !important;
      height: 120px !important;
    }
  `]
})
export class IndicatorPanelComponent implements OnDestroy {
  indicators = input<IndicatorData[]>([]);

  adxCanvas = viewChild<ElementRef<HTMLCanvasElement>>('adxCanvas');
  rsiCanvas = viewChild<ElementRef<HTMLCanvasElement>>('rsiCanvas');
  volumeCanvas = viewChild<ElementRef<HTMLCanvasElement>>('volumeCanvas');
  obvCanvas = viewChild<ElementRef<HTMLCanvasElement>>('obvCanvas');

  private adxChart: Chart | null = null;
  private rsiChart: Chart | null = null;
  private volumeChart: Chart | null = null;
  private obvChart: Chart | null = null;

  private readonly gridColor = '#2d3148';
  private readonly textColor = '#8b8fa3';

  private baseScaleConfig = {
    grid: {
      color: this.gridColor,
      drawBorder: false,
    },
    ticks: {
      color: this.textColor,
      font: { size: 10 },
      maxTicksLimit: 4,
    },
  };

  private baseChartOptions(yMin?: number, yMax?: number): any {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: {
        mode: 'index' as const,
        intersect: false,
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1d2e',
          titleColor: '#8b8fa3',
          bodyColor: '#e0e0e0',
          borderColor: '#2d3148',
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          ...this.baseScaleConfig,
          ticks: {
            ...this.baseScaleConfig.ticks,
            maxTicksLimit: 6,
            maxRotation: 0,
          },
        },
        y: {
          ...this.baseScaleConfig,
          ...(yMin !== undefined ? { min: yMin } : {}),
          ...(yMax !== undefined ? { max: yMax } : {}),
        },
      },
    };
  }

  constructor() {
    effect(() => {
      const data = this.indicators();
      if (data && data.length > 0) {
        this.drawCharts(data);
      }
    });
  }

  private drawCharts(data: IndicatorData[]): void {
    const labels = data.map(d => {
      const date = asUtcDate(d.time) ?? new Date(d.time);
      return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
    });

    this.drawAdxChart(data, labels);
    this.drawRsiChart(data, labels);
    this.drawVolumeChart(data, labels);
    this.drawObvChart(data, labels);
  }

  private drawAdxChart(data: IndicatorData[], labels: string[]): void {
    const canvas = this.adxCanvas()?.nativeElement;
    if (!canvas) return;

    if (this.adxChart) {
      this.adxChart.destroy();
      this.adxChart = null;
    }

    const adxValues = data.map(d => d.adx);
    const threshold20 = data.map(() => 20);
    const threshold25 = data.map(() => 25);

    this.adxChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'ADX',
            data: adxValues,
            borderColor: '#ffffff',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.1,
            fill: false,
          },
          {
            label: 'Level 20',
            data: threshold20,
            borderColor: '#f0c040',
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            tension: 0,
            fill: false,
          },
          {
            label: 'Level 25',
            data: threshold25,
            borderColor: '#e05050',
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            tension: 0,
            fill: false,
          },
        ],
      },
      options: this.baseChartOptions(0),
    });
  }

  private drawRsiChart(data: IndicatorData[], labels: string[]): void {
    const canvas = this.rsiCanvas()?.nativeElement;
    if (!canvas) return;

    if (this.rsiChart) {
      this.rsiChart.destroy();
      this.rsiChart = null;
    }

    const rsiValues = data.map(d => d.rsi);
    const overbought = data.map(() => 70);
    const oversold = data.map(() => 30);

    this.rsiChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Overbought',
            data: overbought,
            borderColor: 'transparent',
            borderWidth: 0,
            pointRadius: 0,
            fill: '+1',
            backgroundColor: 'rgba(224, 80, 80, 0.15)',
            tension: 0,
          },
          {
            label: 'RSI',
            data: rsiValues,
            borderColor: '#a855f7',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.1,
            fill: false,
          },
          {
            label: 'Oversold',
            data: oversold,
            borderColor: 'transparent',
            borderWidth: 0,
            pointRadius: 0,
            fill: false,
            backgroundColor: 'rgba(80, 160, 224, 0.15)',
            tension: 0,
          },
        ],
      },
      options: {
        ...this.baseChartOptions(0, 100),
        plugins: {
          ...this.baseChartOptions(0, 100).plugins,
          tooltip: {
            ...this.baseChartOptions(0, 100).plugins.tooltip,
            filter: (item: any) => item.dataset.label === 'RSI',
          },
        },
      },
    });
  }

  private drawVolumeChart(data: IndicatorData[], labels: string[]): void {
    const canvas = this.volumeCanvas()?.nativeElement;
    if (!canvas) return;

    if (this.volumeChart) {
      this.volumeChart.destroy();
      this.volumeChart = null;
    }

    const volumeValues = data.map(d => d.volume);
    const barColors = data.map(d =>
      d.volume > (d.volume_avg ?? 0) ? 'rgba(34, 197, 94, 0.75)' : 'rgba(239, 68, 68, 0.75)'
    );
    const barBorderColors = data.map(d =>
      d.volume > (d.volume_avg ?? 0) ? 'rgba(34, 197, 94, 1)' : 'rgba(239, 68, 68, 1)'
    );

    this.volumeChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Volume',
            data: volumeValues,
            backgroundColor: barColors,
            borderColor: barBorderColors,
            borderWidth: 1,
            borderRadius: 1,
          },
        ],
      },
      options: {
        ...this.baseChartOptions(0),
        scales: {
          ...this.baseChartOptions(0).scales,
          x: {
            ...this.baseChartOptions(0).scales.x,
            grid: { display: false },
          },
        },
      },
    });
  }

  private drawObvChart(data: IndicatorData[], labels: string[]): void {
    const canvas = this.obvCanvas()?.nativeElement;
    if (!canvas) return;

    if (this.obvChart) {
      this.obvChart.destroy();
      this.obvChart = null;
    }

    const obvValues = data.map(d => d.obv);

    this.obvChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'OBV',
            data: obvValues,
            borderColor: '#22d3ee',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.1,
            fill: false,
          },
        ],
      },
      options: this.baseChartOptions(),
    });
  }

  ngOnDestroy(): void {
    this.adxChart?.destroy();
    this.rsiChart?.destroy();
    this.volumeChart?.destroy();
    this.obvChart?.destroy();
  }
}
