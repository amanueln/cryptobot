import { Component, OnInit, OnDestroy, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';
import { ApiService, IndicatorData, StatusData } from '../../services/api.service';

interface IndicatorCard {
  key: string;
  label: string;
  value: number | null;
  signal: string;
  signalColor: string;
  progressPct: number;
  progressColor: string;
  unit: string;
  description: string;
}

interface RegimeVerdict {
  regime: string;
  confidence: number;
  aggressionPct: number;
  description: string;
}

const PRESETS: Record<string, Partial<Record<string, number>>> = {
  'Trending Up': {
    adx: 38,
    bb_width: 5.2,
    volume_ratio: 1.8,
    rsi: 62,
    obv_slope: 1,
    ema_gap: 2.4,
  },
  Ranging: {
    adx: 14,
    bb_width: 3.8,
    volume_ratio: 0.9,
    rsi: 52,
    obv_slope: 0,
    ema_gap: 0.1,
  },
  Volatile: {
    adx: 29,
    bb_width: 12.5,
    volume_ratio: 2.6,
    rsi: 71,
    obv_slope: 1,
    ema_gap: 1.1,
  },
  Squeeze: {
    adx: 11,
    bb_width: 1.8,
    volume_ratio: 0.6,
    rsi: 48,
    obv_slope: 0,
    ema_gap: 0.05,
  },
  Crash: {
    adx: 44,
    bb_width: 18.0,
    volume_ratio: 3.4,
    rsi: 22,
    obv_slope: -1,
    ema_gap: -4.2,
  },
};

@Component({
  selector: 'app-regime-visualizer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="regime-container">
      <!-- Header -->
      <div class="header-row">
        <div class="title-group">
          <h2 class="title">Regime Visualizer</h2>
          <span class="subtitle">Market structure confidence scoring</span>
        </div>
        <div class="controls">
          <select class="pair-select" [(ngModel)]="selectedPair" (ngModelChange)="onPairChange()">
            <option *ngFor="let p of availablePairs" [value]="p">{{ p }}</option>
          </select>
          <span class="refresh-badge" [class.refreshing]="isRefreshing()">
            <span class="dot"></span>
            {{ isRefreshing() ? 'Fetching…' : 'Live · 60s' }}
          </span>
        </div>
      </div>

      <!-- Preset Buttons -->
      <div class="preset-row">
        <span class="preset-label">Educational Presets:</span>
        <button
          *ngFor="let preset of presetNames"
          class="preset-btn"
          [class.active]="activePreset() === preset"
          (click)="loadPreset(preset)"
        >{{ preset }}</button>
        <button
          class="preset-btn clear-btn"
          *ngIf="activePreset()"
          (click)="clearPreset()"
        >Clear ×</button>
      </div>

      <!-- Error Banner -->
      <div class="error-banner" *ngIf="errorMsg()">
        <span>⚠ {{ errorMsg() }}</span>
      </div>

      <!-- Indicator Cards Grid -->
      <div class="cards-grid">
        <div class="indicator-card" *ngFor="let card of indicatorCards()">
          <div class="card-header">
            <span class="card-label">{{ card.label }}</span>
            <span class="card-signal" [style.color]="card.signalColor">{{ card.signal }}</span>
          </div>
          <div class="card-value">
            {{ card.value !== null ? (card.value | number:'1.2-2') : '—' }}<span class="card-unit" *ngIf="card.unit">{{ card.unit }}</span>
          </div>
          <div class="progress-track">
            <div
              class="progress-bar"
              [style.width.%]="card.progressPct"
              [style.background]="card.progressColor"
            ></div>
          </div>
          <div class="card-description">{{ card.description }}</div>
        </div>
      </div>

      <!-- Regime Verdict Card -->
      <div class="verdict-card" *ngIf="verdict() as v">
        <div class="verdict-header">
          <div class="verdict-title-group">
            <span class="verdict-label">Market Regime</span>
            <span class="verdict-regime">{{ v.regime }}</span>
          </div>
          <div class="confidence-badge">
            <span class="confidence-value">{{ v.confidence | number:'1.0-0' }}%</span>
            <span class="confidence-label">confidence</span>
          </div>
        </div>

        <p class="verdict-desc">{{ v.description }}</p>

        <!-- Confidence Bar -->
        <div class="meter-section">
          <div class="meter-label-row">
            <span class="meter-label">Confidence</span>
            <span class="meter-value">{{ v.confidence | number:'1.0-0' }}%</span>
          </div>
          <div class="meter-track">
            <div
              class="meter-fill confidence-fill"
              [style.width.%]="v.confidence"
            ></div>
          </div>
        </div>

        <!-- Aggression Meter -->
        <div class="meter-section">
          <div class="meter-label-row">
            <span class="meter-label">Aggression Level</span>
            <span class="meter-value">{{ v.aggressionPct | number:'1.0-0' }}%</span>
          </div>
          <div class="meter-track">
            <div
              class="meter-fill aggression-fill"
              [style.width.%]="v.aggressionPct"
              [style.background]="aggressionGradient(v.aggressionPct)"
            ></div>
          </div>
          <div class="aggression-scale">
            <span>Conservative</span>
            <span>Aggressive</span>
          </div>
        </div>

        <!-- Signal Summary Pills -->
        <div class="signal-pills">
          <div class="pill" *ngFor="let card of indicatorCards()" [style.border-color]="card.signalColor">
            <span class="pill-key">{{ card.label }}</span>
            <span class="pill-sig" [style.color]="card.signalColor">{{ card.signal }}</span>
          </div>
        </div>
      </div>

      <div class="last-updated" *ngIf="lastUpdated()">
        Last updated: {{ lastUpdated() | date:'h:mm:ss a' }}
        <span *ngIf="activePreset()" class="preset-notice"> · Showing preset: <strong>{{ activePreset() }}</strong></span>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      font-family: 'Inter', 'Segoe UI', sans-serif;
      background: #1a1d29;
      min-height: 100vh;
      color: #e2e8f0;
    }

    .regime-container {
      max-width: 1100px;
      margin: 0 auto;
      padding: 28px 20px;
    }

    /* Header */
    .header-row {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
    }

    .title-group {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .title {
      margin: 0;
      font-size: 1.6rem;
      font-weight: 700;
      background: linear-gradient(90deg, #7c83ff, #a78bfa);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .subtitle {
      font-size: 0.8rem;
      color: #6b7280;
    }

    .controls {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .pair-select {
      background: #242736;
      border: 1px solid #2d3148;
      color: #e2e8f0;
      padding: 7px 12px;
      border-radius: 8px;
      font-size: 0.88rem;
      cursor: pointer;
      outline: none;
      transition: border-color 0.2s;
    }

    .pair-select:focus {
      border-color: #7c83ff;
    }

    .refresh-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.78rem;
      color: #6b7280;
      background: #242736;
      border: 1px solid #2d3148;
      padding: 6px 12px;
      border-radius: 20px;
    }

    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #22c55e;
    }

    .refresh-badge.refreshing .dot {
      background: #f59e0b;
      animation: pulse 0.8s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }

    /* Presets */
    .preset-row {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 18px;
    }

    .preset-label {
      font-size: 0.8rem;
      color: #6b7280;
      margin-right: 4px;
    }

    .preset-btn {
      background: #242736;
      border: 1px solid #2d3148;
      color: #94a3b8;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.82rem;
      cursor: pointer;
      transition: all 0.18s;
    }

    .preset-btn:hover {
      border-color: #7c83ff;
      color: #e2e8f0;
    }

    .preset-btn.active {
      background: #2d3148;
      border-color: #7c83ff;
      color: #a78bfa;
    }

    .clear-btn {
      border-color: #4b5563;
      color: #ef4444;
    }

    .clear-btn:hover {
      border-color: #ef4444;
      background: #2d1f24;
    }

    /* Error */
    .error-banner {
      background: #2d1f24;
      border: 1px solid #7f1d1d;
      color: #fca5a5;
      padding: 10px 16px;
      border-radius: 8px;
      font-size: 0.85rem;
      margin-bottom: 18px;
    }

    /* Cards Grid */
    .cards-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-bottom: 16px;
    }

    @media (max-width: 700px) {
      .cards-grid {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    .indicator-card {
      background: #242736;
      border: 1px solid #2d3148;
      border-radius: 12px;
      padding: 16px;
      transition: transform 0.15s, border-color 0.2s;
    }

    .indicator-card:hover {
      transform: translateY(-2px);
      border-color: #3d4468;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .card-label {
      font-size: 0.78rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #6b7280;
    }

    .card-signal {
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .card-value {
      font-size: 1.55rem;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 10px;
      line-height: 1.1;
    }

    .card-unit {
      font-size: 0.75rem;
      color: #6b7280;
      margin-left: 2px;
      font-weight: 400;
    }

    .progress-track {
      height: 5px;
      background: #1a1d29;
      border-radius: 3px;
      overflow: hidden;
      margin-bottom: 8px;
    }

    .progress-bar {
      height: 100%;
      border-radius: 3px;
      transition: width 0.6s ease;
    }

    .card-description {
      font-size: 0.74rem;
      color: #4b5563;
    }

    /* Verdict Card */
    .verdict-card {
      background: #242736;
      border: 1px solid #2d3148;
      border-radius: 14px;
      padding: 22px;
      margin-bottom: 14px;
    }

    .verdict-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10px;
    }

    .verdict-title-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .verdict-label {
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: #6b7280;
    }

    .verdict-regime {
      font-size: 1.45rem;
      font-weight: 800;
      color: #a78bfa;
      letter-spacing: 0.02em;
    }

    .confidence-badge {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 2px;
    }

    .confidence-value {
      font-size: 1.8rem;
      font-weight: 800;
      color: #7c83ff;
    }

    .confidence-label {
      font-size: 0.72rem;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .verdict-desc {
      font-size: 0.86rem;
      color: #9ca3af;
      margin: 0 0 18px 0;
      line-height: 1.5;
    }

    /* Meters */
    .meter-section {
      margin-bottom: 16px;
    }

    .meter-label-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
    }

    .meter-label {
      font-size: 0.78rem;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .meter-value {
      font-size: 0.8rem;
      font-weight: 600;
      color: #e2e8f0;
    }

    .meter-track {
      height: 10px;
      background: #1a1d29;
      border-radius: 6px;
      overflow: hidden;
    }

    .meter-fill {
      height: 100%;
      border-radius: 6px;
      transition: width 0.7s ease;
    }

    .confidence-fill {
      background: linear-gradient(90deg, #4f46e5, #7c83ff);
    }

    .aggression-scale {
      display: flex;
      justify-content: space-between;
      margin-top: 4px;
    }

    .aggression-scale span {
      font-size: 0.7rem;
      color: #4b5563;
    }

    /* Signal Pills */
    .signal-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px solid #2d3148;
    }

    .pill {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 2px;
      background: #1a1d29;
      border: 1px solid;
      border-radius: 8px;
      padding: 6px 12px;
      min-width: 70px;
    }

    .pill-key {
      font-size: 0.68rem;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .pill-sig {
      font-size: 0.74rem;
      font-weight: 700;
    }

    /* Footer */
    .last-updated {
      font-size: 0.74rem;
      color: #374151;
      text-align: right;
    }

    .preset-notice {
      color: #6b7280;
    }

    .preset-notice strong {
      color: #a78bfa;
    }
  `],
})
export class RegimeVisualizerComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);

  availablePairs = ['ETH-USD', 'BTC-USD', 'SOL-USD', 'BNB-USD'];
  selectedPair = 'ETH-USD';
  presetNames = Object.keys(PRESETS);

  activePreset = signal<string>('');
  isRefreshing = signal(false);
  errorMsg = signal('');
  lastUpdated = signal<Date | null>(null);

  private rawValues = signal<Record<string, number>>({});

  private subscription: Subscription | null = null;

  indicatorCards = computed<IndicatorCard[]>(() => {
    const v = this.rawValues();
    return this.buildCards(v);
  });

  verdict = computed<RegimeVerdict>(() => {
    return this.buildVerdict(this.indicatorCards());
  });

  ngOnInit(): void {
    this.startPolling();
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  onPairChange(): void {
    this.activePreset.set('');
    this.errorMsg.set('');
    this.restartPolling();
  }

  loadPreset(name: string): void {
    this.activePreset.set(name);
    const preset = PRESETS[name];
    this.rawValues.set({ ...preset } as Record<string, number>);
    this.lastUpdated.set(new Date());
  }

  clearPreset(): void {
    this.activePreset.set('');
    this.rawValues.set({});
    this.restartPolling();
  }

  aggressionGradient(pct: number): string {
    // 0% = green, 50% = yellow, 100% = red
    const r = Math.round(Math.min(255, (pct / 50) * 255));
    const g = Math.round(Math.min(255, ((100 - pct) / 50) * 255));
    return `rgb(${r}, ${g}, 40)`;
  }

  private startPolling(): void {
    this.subscription = interval(60_000)
      .pipe(
        startWith(0),
        switchMap(() => {
          if (this.activePreset()) {
            return [];
          }
          this.isRefreshing.set(true);
          return this.api.fetchIndicators(this.selectedPair, 4);
        }),
      )
      .subscribe({
        next: (data: IndicatorData[]) => {
          this.isRefreshing.set(false);
          if (!data || data.length === 0) {
            this.errorMsg.set('No indicator data returned.');
            return;
          }
          const last = data[data.length - 1];
          this.rawValues.set(this.extractValues(last));
          this.errorMsg.set('');
          this.lastUpdated.set(new Date());
        },
        error: (err: unknown) => {
          this.isRefreshing.set(false);
          this.errorMsg.set('Failed to load indicators. Retrying in 60s.');
          console.error('[RegimeVisualizer] fetch error:', err);
        },
      });
  }

  private restartPolling(): void {
    this.subscription?.unsubscribe();
    this.startPolling();
  }

  private extractValues(d: IndicatorData): Record<string, number> {
    const bbUpper = d.bb_upper ?? 0;
    const bbLower = d.bb_lower ?? 0;
    const bbMid = d.bb_mid ?? 1;
    const bbWidth = bbMid > 0 ? ((bbUpper - bbLower) / bbMid) * 100 : 0;
    const volRatio = (d.volume_avg && d.volume_avg > 0) ? d.volume / d.volume_avg : 1;
    const emaGap = (d.ema50 != null && d.ema200 != null && d.ema200 > 0)
      ? ((d.ema50 - d.ema200) / d.ema200) * 100 : 0;

    return {
      adx: d.adx ?? 0,
      bb_width: bbWidth,
      volume_ratio: volRatio,
      rsi: d.rsi ?? 50,
      obv_slope: d.obv ?? 0,
      ema_gap: emaGap,
    };
  }

  private buildCards(v: Record<string, number>): IndicatorCard[] {
    const adx = v['adx'] ?? null;
    const bbWidth = v['bb_width'] ?? null;
    const volRatio = v['volume_ratio'] ?? null;
    const rsi = v['rsi'] ?? null;
    const obvSlope = v['obv_slope'] ?? null;
    const emaGap = v['ema_gap'] ?? null;

    return [
      this.adxCard(adx),
      this.bbWidthCard(bbWidth),
      this.volRatioCard(volRatio),
      this.rsiCard(rsi),
      this.obvCard(obvSlope),
      this.emaGapCard(emaGap),
    ];
  }

  private adxCard(value: number | null): IndicatorCard {
    let sig = 'No Data';
    let sigColor = '#6b7280';
    let pct = 0;
    let progColor = '#6b7280';
    let desc = 'Average Directional Index — measures trend strength.';

    if (value !== null) {
      pct = Math.min(100, (value / 60) * 100);
      if (value > 25) {
        sig = 'Strong Trend';
        sigColor = '#22c55e';
        progColor = '#22c55e';
        desc = 'ADX > 25: A directional trend is actively in play.';
      } else if (value >= 20) {
        sig = 'Weak Trend';
        sigColor = '#eab308';
        progColor = '#eab308';
        desc = 'ADX 20–25: Trend forming but not yet confirmed.';
      } else {
        sig = 'No Trend';
        sigColor = '#ef4444';
        progColor = '#ef4444';
        desc = 'ADX < 20: Market is non-directional / ranging.';
      }
    }

    return { key: 'adx', label: 'ADX', value, signal: sig, signalColor: sigColor, progressPct: pct, progressColor: progColor, unit: '', description: desc };
  }

  private bbWidthCard(value: number | null): IndicatorCard {
    let sig = 'No Data';
    let sigColor = '#6b7280';
    let pct = 0;
    let progColor = '#6b7280';
    let desc = 'Bollinger Band Width — measures volatility expansion/contraction.';

    if (value !== null) {
      pct = Math.min(100, (value / 20) * 100);
      if (value > 8) {
        sig = 'Wide / Volatile';
        sigColor = '#f59e0b';
        progColor = '#f59e0b';
        desc = 'BB Width > 8: Bands are wide — high volatility environment.';
      } else if (value < 3) {
        sig = 'Squeeze';
        sigColor = '#a855f7';
        progColor = '#a855f7';
        desc = 'BB Width < 3: Bands are squeezing — breakout potential building.';
      } else {
        sig = 'Normal';
        sigColor = '#22c55e';
        progColor = '#22c55e';
        desc = 'BB Width 3–8: Normal volatility range.';
      }
    }

    return { key: 'bb_width', label: 'BB Width', value, signal: sig, signalColor: sigColor, progressPct: pct, progressColor: progColor, unit: '%', description: desc };
  }

  private volRatioCard(value: number | null): IndicatorCard {
    let sig = 'No Data';
    let sigColor = '#6b7280';
    let pct = 0;
    let progColor = '#6b7280';
    let desc = 'Volume vs. 20-period average — detects unusual volume.';

    if (value !== null) {
      pct = Math.min(100, (value / 4) * 100);
      if (value > 1.5) {
        sig = 'Spike';
        sigColor = '#f59e0b';
        progColor = '#f59e0b';
        desc = 'Volume > 1.5×: Elevated activity — potential breakout or reversal.';
      } else {
        sig = 'Normal';
        sigColor = '#22c55e';
        progColor = '#22c55e';
        desc = 'Volume near average: No unusual activity.';
      }
    }

    return { key: 'volume_ratio', label: 'Vol Ratio', value, signal: sig, signalColor: sigColor, progressPct: pct, progressColor: progColor, unit: '×', description: desc };
  }

  private rsiCard(value: number | null): IndicatorCard {
    let sig = 'No Data';
    let sigColor = '#6b7280';
    let pct = value ?? 0;
    let progColor = '#6b7280';
    let desc = 'Relative Strength Index — momentum oscillator (0–100).';

    if (value !== null) {
      if (value > 70) {
        sig = 'Overbought';
        sigColor = '#ef4444';
        progColor = '#ef4444';
        desc = 'RSI > 70: Asset may be overextended to the upside.';
      } else if (value < 30) {
        sig = 'Oversold';
        sigColor = '#3b82f6';
        progColor = '#3b82f6';
        desc = 'RSI < 30: Asset may be overextended to the downside.';
      } else {
        sig = 'Neutral';
        sigColor = '#22c55e';
        progColor = '#22c55e';
        desc = 'RSI 30–70: Momentum is balanced.';
      }
    }

    return { key: 'rsi', label: 'RSI', value, signal: sig, signalColor: sigColor, progressPct: pct, progressColor: progColor, unit: '', description: desc };
  }

  private obvCard(value: number | null): IndicatorCard {
    let sig = 'No Data';
    let sigColor = '#6b7280';
    let pct = 50;
    let progColor = '#6b7280';
    let desc = 'On-Balance Volume trend slope — tracks buying/selling pressure.';
    let displayValue: number | null = value;

    if (value !== null) {
      if (value > 0) {
        sig = 'Accumulation';
        sigColor = '#22c55e';
        progColor = '#22c55e';
        pct = 75;
        desc = 'OBV rising: Smart money accumulating — bullish pressure.';
      } else if (value < 0) {
        sig = 'Distribution';
        sigColor = '#ef4444';
        progColor = '#ef4444';
        pct = 25;
        desc = 'OBV falling: Selling pressure dominant — bearish divergence.';
      } else {
        sig = 'Flat';
        sigColor = '#eab308';
        progColor = '#eab308';
        pct = 50;
        desc = 'OBV flat: No clear volume-backed direction.';
      }
      displayValue = value;
    }

    return { key: 'obv_slope', label: 'OBV Trend', value: displayValue, signal: sig, signalColor: sigColor, progressPct: pct, progressColor: progColor, unit: '', description: desc };
  }

  private emaGapCard(value: number | null): IndicatorCard {
    let sig = 'No Data';
    let sigColor = '#6b7280';
    let pct = 50;
    let progColor = '#6b7280';
    let desc = 'EMA 50 vs EMA 200 gap (%) — identifies macro trend bias.';

    if (value !== null) {
      const absPct = Math.abs(value);
      pct = Math.min(100, 50 + (value / 10) * 50);
      if (value > 0) {
        sig = 'Bullish';
        sigColor = '#22c55e';
        progColor = '#22c55e';
        desc = `EMA50 > EMA200 by ${absPct.toFixed(2)}%: Golden cross region — uptrend.`;
      } else {
        sig = 'Bearish';
        sigColor = '#ef4444';
        progColor = '#ef4444';
        desc = `EMA50 < EMA200 by ${absPct.toFixed(2)}%: Death cross region — downtrend.`;
      }
    }

    return { key: 'ema_gap', label: 'EMA Gap', value, signal: sig, signalColor: sigColor, progressPct: Math.max(0, Math.min(100, pct)), progressColor: progColor, unit: '%', description: desc };
  }

  private buildVerdict(cards: IndicatorCard[]): RegimeVerdict {
    const byKey = Object.fromEntries(cards.map(c => [c.key, c]));
    const v = this.rawValues();

    const adx = v['adx'] ?? 0;
    const bbWidth = v['bb_width'] ?? 5;
    const rsi = v['rsi'] ?? 50;
    const obvSlope = v['obv_slope'] ?? 0;
    const emaGap = v['ema_gap'] ?? 0;
    const volRatio = v['volume_ratio'] ?? 1;

    const hasTrend = adx > 25;
    const weakTrend = adx >= 20 && adx <= 25;
    const isBullish = emaGap > 0;
    const isSqueeze = bbWidth < 3;
    const isVolatile = bbWidth > 8;
    const isVolSpike = volRatio > 1.5;
    const isRsiBear = rsi < 30;
    const isRsiBull = rsi > 65;

    let regime = 'UNCERTAIN';
    let confidence = 40;
    let aggressionPct = 50;
    let description = 'Mixed signals — market structure is ambiguous.';

    // Score each scenario
    let trendUpScore = 0;
    let trendDownScore = 0;
    let rangingScore = 0;
    let volatileScore = 0;
    let squeezeScore = 0;

    if (hasTrend) { trendUpScore += 2; trendDownScore += 2; }
    if (weakTrend) { rangingScore += 1; }
    if (!hasTrend && !weakTrend) { rangingScore += 2; squeezeScore += 1; }

    if (isBullish) { trendUpScore += 2; }
    if (!isBullish) { trendDownScore += 2; }

    if (obvSlope > 0) { trendUpScore += 1; }
    if (obvSlope < 0) { trendDownScore += 1; }

    if (isRsiBull) { trendUpScore += 1; volatileScore += 1; }
    if (isRsiBear) { trendDownScore += 2; volatileScore += 1; }

    if (isVolatile) { volatileScore += 3; trendUpScore -= 1; rangingScore -= 1; }
    if (isSqueeze) { squeezeScore += 3; rangingScore += 1; }

    if (isVolSpike && isVolatile) { volatileScore += 2; }
    if (isVolSpike && hasTrend) { trendUpScore += 1; trendDownScore += 1; }

    const scores: [string, number][] = [
      ['TRENDING UP', trendUpScore],
      ['TRENDING DOWN', trendDownScore],
      ['RANGING', rangingScore],
      ['VOLATILE', volatileScore],
      ['SQUEEZE', squeezeScore],
    ];

    scores.sort((a, b) => b[1] - a[1]);
    const winner = scores[0];
    const total = scores.reduce((s, x) => s + Math.max(0, x[1]), 0) || 1;
    regime = winner[0];
    confidence = Math.min(95, Math.max(35, Math.round((winner[1] / total) * 100)));

    const aggressionMap: Record<string, number> = {
      'RANGING': 80,
      'TRENDING UP': 60,
      'VOLATILE': 30,
      'SQUEEZE': 40,
      'TRENDING DOWN': 20,
      'UNCERTAIN': 50,
    };
    aggressionPct = aggressionMap[regime] ?? 50;

    const descMap: Record<string, string> = {
      'TRENDING UP': 'Momentum and structure favour continued upside. Trend-following strategies are preferred.',
      'TRENDING DOWN': 'Bearish structure with downside pressure. Defensive positioning recommended.',
      'RANGING': 'Price is consolidating without clear direction. Mean-reversion setups are viable.',
      'VOLATILE': 'High volatility with wide swings. Exercise caution — position sizing matters most.',
      'SQUEEZE': 'Volatility compression detected. A breakout (either direction) may be imminent.',
      'UNCERTAIN': 'Conflicting signals across indicators. Wait for confirmation before acting.',
    };
    description = descMap[regime] ?? description;

    return { regime, confidence, aggressionPct, description };
  }
}
