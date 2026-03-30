import { Component, signal, OnInit, OnDestroy, AfterViewInit, ElementRef, ViewChild, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

interface SafetyOrder {
  index: number;
  price: number;
  amount: number;
  filled: boolean;
  fillPoint: number | null; // price-line index when filled
}

interface SimParams {
  balance: number;
  riskPct: number;
  volumeScale: number;
  maxSO: number;
  stepScale: number;
}

@Component({
  selector: 'app-dca-simulator',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="dca-simulator">
      <div class="sim-header">
        <h2>DCA Safety Orders Simulator</h2>
        <p class="subtitle">Visualise how safety orders protect your average entry</p>
      </div>

      <div class="controls-grid">
        <div class="control-group">
          <label>
            <span class="label-text">Balance</span>
            <span class="label-value">\${{ params().balance | number:'1.0-0' }}</span>
          </label>
          <input
            type="range"
            min="500"
            max="10000"
            step="100"
            [(ngModel)]="balanceModel"
            (ngModelChange)="onParamChange()"
            class="slider"
          />
          <div class="range-hints"><span>$500</span><span>$10,000</span></div>
        </div>

        <div class="control-group">
          <label>
            <span class="label-text">Risk per Deal</span>
            <span class="label-value">{{ (params().riskPct * 100) | number:'1.0-0' }}%</span>
          </label>
          <input
            type="range"
            min="10"
            max="50"
            step="1"
            [(ngModel)]="riskPctModel"
            (ngModelChange)="onParamChange()"
            class="slider"
          />
          <div class="range-hints"><span>10%</span><span>50%</span></div>
        </div>

        <div class="control-group">
          <label>
            <span class="label-text">Volume Scale</span>
            <span class="label-value">{{ params().volumeScale | number:'1.1-1' }}x</span>
          </label>
          <input
            type="range"
            min="10"
            max="30"
            step="1"
            [(ngModel)]="volumeScaleModel"
            (ngModelChange)="onParamChange()"
            class="slider"
          />
          <div class="range-hints"><span>1.0x</span><span>3.0x</span></div>
        </div>

        <div class="control-group">
          <label>
            <span class="label-text">Max Safety Orders</span>
            <span class="label-value">{{ params().maxSO }}</span>
          </label>
          <input
            type="range"
            min="1"
            max="8"
            step="1"
            [(ngModel)]="maxSOModel"
            (ngModelChange)="onParamChange()"
            class="slider"
          />
          <div class="range-hints"><span>1</span><span>8</span></div>
        </div>

        <div class="control-group">
          <label>
            <span class="label-text">Step Scale</span>
            <span class="label-value">{{ params().stepScale | number:'1.1-1' }}x</span>
          </label>
          <input
            type="range"
            min="10"
            max="30"
            step="1"
            [(ngModel)]="stepScaleModel"
            (ngModelChange)="onParamChange()"
            class="slider"
          />
          <div class="range-hints"><span>1.0x</span><span>3.0x</span></div>
        </div>
      </div>

      <div class="stats-row">
        <div class="stat">
          <span class="stat-label">Base Order</span>
          <span class="stat-value">\${{ baseOrder() | number:'1.2-2' }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Total Deployed</span>
          <span class="stat-value">\${{ totalDeployed() | number:'1.2-2' }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Avg Entry</span>
          <span class="stat-value">\${{ avgEntry() | number:'1.2-2' }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Take Profit</span>
          <span class="stat-value green">\${{ takeProfit() | number:'1.2-2' }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Orders Filled</span>
          <span class="stat-value">{{ filledCount() }} / {{ params().maxSO + 1 }}</span>
        </div>
      </div>

      <div class="chart-container">
        <canvas #chartCanvas></canvas>
      </div>

      <div class="playback-controls">
        <button class="btn-play" (click)="togglePlay()" [class.active]="isPlaying()">
          {{ isPlaying() ? '⏸ Pause' : '▶ Auto-Play' }}
        </button>
        <button class="btn-reset" (click)="resetSimulation()">↺ Reset</button>
        <div class="playback-info" *ngIf="animFrame() > 0">
          Price Point: {{ animFrame() }} / {{ pricePoints.length }}
        </div>
      </div>

      <div class="orders-table">
        <div class="orders-header">
          <span>Order</span>
          <span>Type</span>
          <span>Price</span>
          <span>Amount</span>
          <span>Value</span>
          <span>Status</span>
        </div>
        <div
          class="order-row"
          *ngFor="let o of allOrders()"
          [class.filled]="o.filled"
          [class.pending]="!o.filled"
        >
          <span class="order-num">#{{ o.index === 0 ? 'Base' : 'SO' + o.index }}</span>
          <span class="order-type">{{ o.index === 0 ? 'Base' : 'Safety' }}</span>
          <span class="order-price">\${{ o.price | number:'1.2-2' }}</span>
          <span class="order-amount">{{ o.amount | number:'1.4-4' }}</span>
          <span class="order-value">\${{ (o.price * o.amount) | number:'1.2-2' }}</span>
          <span class="order-status" [class.status-filled]="o.filled" [class.status-pending]="!o.filled">
            {{ o.filled ? 'Filled' : 'Pending' }}
          </span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      font-family: 'Inter', 'Segoe UI', sans-serif;
    }

    .dca-simulator {
      background: #0f1117;
      color: #e2e8f0;
      border-radius: 16px;
      padding: 24px;
      max-width: 900px;
      margin: 0 auto;
      border: 1px solid #1e2433;
    }

    .sim-header {
      margin-bottom: 24px;
    }

    .sim-header h2 {
      margin: 0 0 4px 0;
      font-size: 1.4rem;
      font-weight: 700;
      color: #f1f5f9;
      letter-spacing: -0.02em;
    }

    .subtitle {
      margin: 0;
      font-size: 0.85rem;
      color: #64748b;
    }

    .controls-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px;
      margin-bottom: 20px;
    }

    .control-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .control-group label {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.78rem;
    }

    .label-text {
      color: #94a3b8;
      font-weight: 500;
    }

    .label-value {
      color: #60a5fa;
      font-weight: 700;
      font-size: 0.82rem;
    }

    .slider {
      -webkit-appearance: none;
      appearance: none;
      width: 100%;
      height: 4px;
      border-radius: 2px;
      background: #1e2d3d;
      outline: none;
      cursor: pointer;
    }

    .slider::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: #3b82f6;
      cursor: pointer;
      transition: background 0.2s, transform 0.1s;
    }

    .slider::-webkit-slider-thumb:hover {
      background: #60a5fa;
      transform: scale(1.2);
    }

    .slider::-moz-range-thumb {
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: #3b82f6;
      cursor: pointer;
      border: none;
    }

    .range-hints {
      display: flex;
      justify-content: space-between;
      font-size: 0.68rem;
      color: #475569;
    }

    .stats-row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
      padding: 14px 16px;
      background: #141821;
      border-radius: 10px;
      border: 1px solid #1e2433;
    }

    .stat {
      display: flex;
      flex-direction: column;
      gap: 2px;
      flex: 1;
      min-width: 100px;
    }

    .stat-label {
      font-size: 0.72rem;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .stat-value {
      font-size: 0.95rem;
      font-weight: 700;
      color: #e2e8f0;
    }

    .stat-value.green {
      color: #22c55e;
    }

    .chart-container {
      position: relative;
      background: #0b0e14;
      border-radius: 12px;
      padding: 16px;
      border: 1px solid #1e2433;
      margin-bottom: 16px;
      height: 320px;
    }

    .chart-container canvas {
      width: 100% !important;
      height: 100% !important;
    }

    .playback-controls {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
    }

    .btn-play {
      padding: 8px 20px;
      background: #1d4ed8;
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }

    .btn-play:hover {
      background: #2563eb;
    }

    .btn-play.active {
      background: #7c3aed;
    }

    .btn-play.active:hover {
      background: #8b5cf6;
    }

    .btn-reset {
      padding: 8px 16px;
      background: #1e2433;
      color: #94a3b8;
      border: 1px solid #2d3748;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s, color 0.2s;
    }

    .btn-reset:hover {
      background: #263044;
      color: #e2e8f0;
    }

    .playback-info {
      font-size: 0.8rem;
      color: #64748b;
    }

    .orders-table {
      background: #0b0e14;
      border-radius: 12px;
      border: 1px solid #1e2433;
      overflow: hidden;
    }

    .orders-header {
      display: grid;
      grid-template-columns: 70px 70px 1fr 1fr 1fr 80px;
      padding: 10px 16px;
      background: #141821;
      font-size: 0.72rem;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-bottom: 1px solid #1e2433;
    }

    .order-row {
      display: grid;
      grid-template-columns: 70px 70px 1fr 1fr 1fr 80px;
      padding: 10px 16px;
      font-size: 0.82rem;
      border-bottom: 1px solid #0f1117;
      transition: background 0.15s;
      align-items: center;
    }

    .order-row:last-child {
      border-bottom: none;
    }

    .order-row:hover {
      background: #141821;
    }

    .order-row.filled {
      opacity: 1;
    }

    .order-row.pending {
      opacity: 0.55;
    }

    .order-num {
      font-weight: 700;
      color: #93c5fd;
    }

    .order-type {
      color: #94a3b8;
    }

    .order-price {
      color: #e2e8f0;
      font-weight: 600;
    }

    .order-amount {
      color: #94a3b8;
    }

    .order-value {
      color: #cbd5e1;
    }

    .order-status {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 20px;
      text-align: center;
      width: fit-content;
    }

    .status-filled {
      background: rgba(34, 197, 94, 0.15);
      color: #22c55e;
    }

    .status-pending {
      background: rgba(100, 116, 139, 0.15);
      color: #64748b;
    }
  `]
})
export class DcaSimulatorComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('chartCanvas') chartCanvas!: ElementRef<HTMLCanvasElement>;

  // Slider models (scaled integers for range inputs)
  balanceModel = 3000;
  riskPctModel = 35;      // 10–50 → divide by 100
  volumeScaleModel = 15;  // 10–30 → divide by 10
  maxSOModel = 5;
  stepScaleModel = 15;    // 10–30 → divide by 10

  params = signal<SimParams>({
    balance: 3000,
    riskPct: 0.35,
    volumeScale: 1.5,
    maxSO: 5,
    stepScale: 1.5
  });

  // Derived signals
  baseOrder = signal(0);
  totalDeployed = signal(0);
  avgEntry = signal(0);
  takeProfit = signal(0);
  filledCount = signal(0);
  allOrders = signal<SafetyOrder[]>([]);
  isPlaying = signal(false);
  animFrame = signal(0);

  // Full price-line (100 points)
  pricePoints: number[] = [];

  // Safety order definitions (re-computed on param change)
  private safetyOrders: SafetyOrder[] = [];

  // Chart instance
  private chart: Chart | null = null;

  // Animation state
  private animTimer: ReturnType<typeof setInterval> | null = null;
  private currentFrame = 0;

  // Track per-frame average / TP for annotation updates
  private frameAvgEntry: number[] = [];
  private frameTakeProfit: number[] = [];

  constructor(private ngZone: NgZone) {}

  ngOnInit(): void {
    this.computeSimulation();
  }

  ngAfterViewInit(): void {
    this.buildChart();
  }

  ngOnDestroy(): void {
    this.stopAnimation();
    this.chart?.destroy();
  }

  // -----------------------------------------------------------------------
  // Param change
  // -----------------------------------------------------------------------

  onParamChange(): void {
    this.params.set({
      balance: this.balanceModel,
      riskPct: this.riskPctModel / 100,
      volumeScale: this.volumeScaleModel / 10,
      maxSO: this.maxSOModel,
      stepScale: this.stepScaleModel / 10
    });
    this.resetSimulation();
  }

  // -----------------------------------------------------------------------
  // Simulation logic
  // -----------------------------------------------------------------------

  private computeSimulation(): void {
    const p = this.params();
    const START_PRICE = 100;

    // 1. Base order size
    let volumeSum = 0;
    for (let i = 1; i <= p.maxSO; i++) {
      volumeSum += Math.pow(p.volumeScale, i);
    }
    const base = (p.balance * p.riskPct) / (1 + volumeSum);

    // 2. Safety order price levels & amounts
    const orders: SafetyOrder[] = [];

    // Base order (index 0) at START_PRICE
    const baseAmount = base / START_PRICE;
    orders.push({
      index: 0,
      price: START_PRICE,
      amount: baseAmount,
      filled: false,
      fillPoint: 0  // always filled at start
    });

    // Safety orders
    const BASE_STEP = 1.5; // % drop for first SO
    let cumStep = 0;
    for (let i = 1; i <= p.maxSO; i++) {
      cumStep += BASE_STEP * Math.pow(p.stepScale, i - 1);
      const soPrice = START_PRICE * (1 - cumStep / 100);
      const soSpend = base * Math.pow(p.volumeScale, i);
      const soAmount = soSpend / soPrice;
      orders.push({
        index: i,
        price: soPrice,
        amount: soAmount,
        filled: false,
        fillPoint: null
      });
    }

    this.safetyOrders = orders;

    // 3. Generate price line (100 points)
    // Drop ~15% over ~70 points then bounce back ~10%
    this.pricePoints = this.generatePriceLine(START_PRICE, 100);

    // 4. Pre-compute per-frame avg entry and TP for animation overlay
    this.precomputeFrameData();

    // 5. Emit initial (un-animated) stats with all SOs filled for static view
    this.computeStaticStats(orders, p);
    this.allOrders.set(orders.map(o => ({ ...o, filled: false })));
    this.filledCount.set(0);

    this.baseOrder.set(base);
  }

  private generatePriceLine(start: number, count: number): number[] {
    const points: number[] = [start];
    // Use a deterministic pseudo-random walk that drops ~15% then recovers
    const seed = (n: number) => {
      let x = Math.sin(n * 9301 + 49297) * 233280;
      return x - Math.floor(x);
    };

    for (let i = 1; i < count; i++) {
      const prev = points[i - 1];
      let drift: number;
      const progress = i / count;

      if (progress < 0.65) {
        // Downtrend phase: drift down ~0.25% per step + noise
        drift = -0.0025 + (seed(i) - 0.45) * 0.006;
      } else if (progress < 0.75) {
        // Consolidation / bottom
        drift = (seed(i) - 0.5) * 0.004;
      } else {
        // Recovery phase
        drift = 0.0015 + (seed(i) - 0.4) * 0.005;
      }

      points.push(Math.max(prev * (1 + drift), start * 0.5));
    }
    return points;
  }

  private precomputeFrameData(): void {
    const orders = this.safetyOrders;
    this.frameAvgEntry = [];
    this.frameTakeProfit = [];

    let filledCost = 0;
    let filledQty = 0;

    for (let frame = 0; frame < this.pricePoints.length; frame++) {
      const price = this.pricePoints[frame];

      for (const o of orders) {
        if (!o.filled && price <= o.price) {
          o.filled = true;
          o.fillPoint = frame;
          filledCost += o.price * o.amount;
          filledQty += o.amount;
        }
      }

      const avg = filledQty > 0 ? filledCost / filledQty : orders[0].price;
      this.frameAvgEntry.push(avg);
      this.frameTakeProfit.push(avg * 1.02);
    }

    // Reset filled flags
    for (const o of orders) {
      o.filled = false;
      o.fillPoint = null;
    }
  }

  private computeStaticStats(orders: SafetyOrder[], p: SimParams): void {
    // Compute as-if all filled
    let totalCost = 0;
    let totalQty = 0;
    for (const o of orders) {
      totalCost += o.price * o.amount;
      totalQty += o.amount;
    }
    const avg = totalQty > 0 ? totalCost / totalQty : 0;
    this.totalDeployed.set(totalCost);
    this.avgEntry.set(avg);
    this.takeProfit.set(avg * 1.02);
  }

  // -----------------------------------------------------------------------
  // Chart
  // -----------------------------------------------------------------------

  private buildChart(): void {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }

    const ctx = this.chartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    const labels = this.pricePoints.map((_, i) => i.toString());

    // Buy marker dataset (scatter)
    const buyMarkers = this.safetyOrders.map(o => ({
      x: o.fillPoint !== null ? o.fillPoint : this.findFillPoint(o.price),
      y: o.price
    }));

    const avgLineData = Array(this.pricePoints.length).fill(null);
    const tpLineData = Array(this.pricePoints.length).fill(null);
    // Static lines show final state
    const allFillMax = Math.max(...this.safetyOrders.map(o =>
      o.fillPoint !== null ? o.fillPoint : this.findFillPoint(o.price)
    ));
    for (let i = 0; i < this.pricePoints.length; i++) {
      if (i >= allFillMax) {
        avgLineData[i] = this.frameAvgEntry[i] ?? this.avgEntry();
        tpLineData[i] = this.frameTakeProfit[i] ?? this.takeProfit();
      }
    }

    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Price',
            data: this.pricePoints,
            borderColor: '#60a5fa',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
            order: 1
          },
          {
            label: 'Avg Entry',
            data: avgLineData,
            borderColor: '#f59e0b',
            borderWidth: 1.5,
            borderDash: [6, 3],
            pointRadius: 0,
            tension: 0,
            fill: false,
            order: 2
          },
          {
            label: 'Take Profit',
            data: tpLineData,
            borderColor: '#22c55e',
            borderWidth: 1.5,
            borderDash: [4, 4],
            pointRadius: 0,
            tension: 0,
            fill: false,
            order: 2
          },
          {
            label: 'Buy Orders',
            data: buyMarkers,
            type: 'scatter',
            backgroundColor: '#f97316',
            borderColor: '#fff',
            borderWidth: 1.5,
            pointRadius: 7,
            pointHoverRadius: 9,
            order: 0,
            parsing: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            labels: {
              color: '#94a3b8',
              font: { size: 11 },
              boxWidth: 14
            }
          },
          tooltip: {
            backgroundColor: '#1e2433',
            titleColor: '#e2e8f0',
            bodyColor: '#94a3b8',
            borderColor: '#2d3748',
            borderWidth: 1,
            callbacks: {
              label: (ctx) => {
                if (ctx.dataset.label === 'Buy Orders') {
                  const raw = ctx.raw as { x: number; y: number };
                  return ` Order @ $${raw.y.toFixed(2)}`;
                }
                return ` ${ctx.dataset.label}: $${(ctx.parsed.y as number).toFixed(2)}`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: '#1a2035' },
            ticks: {
              color: '#475569',
              maxTicksLimit: 10,
              font: { size: 10 }
            }
          },
          y: {
            grid: { color: '#1a2035' },
            ticks: {
              color: '#475569',
              font: { size: 10 },
              callback: (v) => `$${(v as number).toFixed(1)}`
            }
          }
        }
      }
    });
  }

  private findFillPoint(price: number): number {
    for (let i = 0; i < this.pricePoints.length; i++) {
      if (this.pricePoints[i] <= price) return i;
    }
    return this.pricePoints.length - 1;
  }

  // -----------------------------------------------------------------------
  // Animation
  // -----------------------------------------------------------------------

  togglePlay(): void {
    if (this.isPlaying()) {
      this.stopAnimation();
    } else {
      if (this.currentFrame >= this.pricePoints.length - 1) {
        this.currentFrame = 0;
        this.resetOrderFills();
      }
      this.startAnimation();
    }
  }

  private startAnimation(): void {
    this.isPlaying.set(true);
    this.ngZone.runOutsideAngular(() => {
      this.animTimer = setInterval(() => {
        this.ngZone.run(() => {
          this.stepFrame();
        });
      }, 60);
    });
  }

  private stopAnimation(): void {
    if (this.animTimer !== null) {
      clearInterval(this.animTimer);
      this.animTimer = null;
    }
    this.isPlaying.set(false);
  }

  private stepFrame(): void {
    if (this.currentFrame >= this.pricePoints.length) {
      this.stopAnimation();
      return;
    }

    const frame = this.currentFrame;
    const currentPrice = this.pricePoints[frame];

    // Check if any orders fill at this frame
    let anyNewFill = false;
    const orders = this.safetyOrders;
    for (const o of orders) {
      if (!o.filled && currentPrice <= o.price) {
        o.filled = true;
        o.fillPoint = frame;
        anyNewFill = true;
      }
    }

    if (anyNewFill || frame === 0) {
      this.allOrders.set(orders.map(o => ({ ...o })));
      const filled = orders.filter(o => o.filled);
      this.filledCount.set(filled.length);

      let cost = 0, qty = 0;
      for (const o of filled) { cost += o.price * o.amount; qty += o.amount; }
      const avg = qty > 0 ? cost / qty : orders[0].price;
      this.avgEntry.set(avg);
      this.takeProfit.set(avg * 1.02);
    }

    // Update chart: reveal price line up to current frame
    this.updateChartFrame(frame);

    this.currentFrame++;
    this.animFrame.set(this.currentFrame);

    if (this.currentFrame >= this.pricePoints.length) {
      this.stopAnimation();
    }
  }

  private updateChartFrame(frame: number): void {
    if (!this.chart) return;

    const priceDataset = this.chart.data.datasets[0] as { data: (number | null)[] };
    const avgDataset = this.chart.data.datasets[1] as { data: (number | null)[] };
    const tpDataset = this.chart.data.datasets[2] as { data: (number | null)[] };
    const buyDataset = this.chart.data.datasets[3] as { data: { x: number; y: number }[] };

    // Reveal price line up to frame
    priceDataset.data = this.pricePoints.map((v, i) => (i <= frame ? v : null));

    // Update avg and TP lines dynamically
    const avgLine: (number | null)[] = Array(this.pricePoints.length).fill(null);
    const tpLine: (number | null)[] = Array(this.pricePoints.length).fill(null);

    const filled = this.safetyOrders.filter(o => o.filled);
    if (filled.length > 0) {
      for (let i = 0; i <= frame; i++) {
        avgLine[i] = this.frameAvgEntry[i] ?? null;
        tpLine[i] = this.frameTakeProfit[i] ?? null;
      }
    }
    avgDataset.data = avgLine;
    tpDataset.data = tpLine;

    // Update buy markers to show only filled orders
    buyDataset.data = this.safetyOrders
      .filter(o => o.filled && o.fillPoint !== null && o.fillPoint <= frame)
      .map(o => ({ x: o.fillPoint as number, y: o.price }));

    this.chart.update('none');
  }

  resetSimulation(): void {
    this.stopAnimation();
    this.currentFrame = 0;
    this.animFrame.set(0);
    this.resetOrderFills();
    this.computeSimulation();
    // Rebuild chart with new params
    if (this.chartCanvas) {
      this.buildChart();
    }
  }

  private resetOrderFills(): void {
    for (const o of this.safetyOrders) {
      o.filled = false;
      o.fillPoint = null;
    }
    this.allOrders.set(this.safetyOrders.map(o => ({ ...o })));
    this.filledCount.set(0);
  }
}
