import {
  Component, input, output, computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { PairInfo, PositionData, VolPredictionData, GridLevelData } from '../../services/api.service';

interface RegimeCfg {
  label: string;
  bg: string;
  text: string;
}

const REGIME_MAP: Record<string, RegimeCfg> = {
  RANGING:        { label: 'RANGING',       bg: '#1e293b', text: '#94a3b8' },
  VOLATILE:       { label: 'VOLATILE',      bg: '#451a03', text: '#fbbf24' },
  TRENDING_UP:    { label: 'TRENDING UP',   bg: '#1e3a5f', text: '#60a5fa' },
  TRENDING_DOWN:  { label: 'TRENDING DOWN', bg: '#450a0a', text: '#f87171' },
  SQUEEZE:        { label: 'SQUEEZE',       bg: '#3b0764', text: '#c084fc' },
};

const DEFAULT_REGIME: RegimeCfg = { label: 'STARTING', bg: '#1e2130', text: '#94a3b8' };

@Component({
  selector: 'app-pair-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      class="card-root"
      [class.expanded]="isExpanded()"
      [class.dimmed]="isDimmed()"
      [style.border-color]="isExpanded() ? '#fbbf24' : '#2d3148'"
      (click)="cardClicked.emit(pair().pair)"
      role="button"
      [attr.aria-expanded]="isExpanded()"
    >
      <!-- Header: name + regime badge + price -->
      <div class="card-header">
        <div class="pair-name-row">
          <span class="pair-name">{{ shortPair() }}</span>
          <span
            class="regime-badge"
            [style.background]="regimeCfg().bg"
            [style.color]="regimeCfg().text"
          >{{ regimeCfg().label }}</span>
        </div>
        <span class="price-tag">{{ priceText() }}</span>
      </div>

      <!-- Summary sentence -->
      <div class="card-summary">{{ summaryText() }}</div>

      <!-- Key numbers row -->
      <div class="key-row">
        <div class="key-item">
          <span class="key-value" [class.positive]="pnlPositive()" [class.negative]="!pnlPositive()">
            {{ pnlText() }}
          </span>
          <span class="key-hint">P&amp;L</span>
        </div>
        <div class="key-item">
          <span class="key-value entry-price">{{ nextBuyText() }}</span>
          <span class="key-hint">next buy</span>
        </div>
        <div class="key-item">
          <span class="key-value">{{ gridFillText() }}</span>
          <span class="key-hint">filled</span>
        </div>
      </div>

      <!-- Grid fill progress bar -->
      <div class="grid-bar-track">
        <div
          class="grid-bar-fill"
          [style.width]="gridFillPct() + '%'"
          [style.background]="gridFillColor()"
        ></div>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; }

    .card-root {
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 10px;
      padding: 12px 14px 10px;
      cursor: pointer;
      transition: border-color 0.15s ease, opacity 0.15s ease, box-shadow 0.15s ease;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      overflow: hidden;
      user-select: none;
    }

    .card-root:hover {
      box-shadow: 0 0 0 1px #3d4168, 0 4px 12px rgba(0,0,0,0.3);
    }

    .card-root.expanded {
      box-shadow: 0 0 0 1px #fbbf24, 0 4px 20px rgba(251,191,36,0.15);
    }

    .card-root.dimmed { opacity: 0.7; }

    /* Header */
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }

    .pair-name-row {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .pair-name {
      font-size: 15px;
      font-weight: 700;
      color: #e2e8f0;
    }

    .regime-badge {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.07em;
      padding: 2px 7px;
      border-radius: 4px;
      text-transform: uppercase;
    }

    .price-tag {
      font-size: 13px;
      font-weight: 600;
      color: #e2e8f0;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
    }

    /* Summary */
    .card-summary {
      font-size: 11.5px;
      color: #94a3b8;
      line-height: 1.5;
      margin-bottom: 10px;
      min-height: 34px;
    }

    /* Key numbers */
    .key-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;
    }

    .key-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1px;
    }

    .key-value {
      font-size: 12px;
      font-weight: 600;
      color: #e2e8f0;
    }

    .key-value.positive { color: #4ade80; }
    .key-value.negative { color: #f87171; }
    .key-value.entry-price { color: #fbbf24; }

    .key-hint {
      font-size: 9px;
      color: #6b7280;
      text-transform: lowercase;
    }

    /* Progress bar */
    .grid-bar-track {
      height: 3px;
      background: #242840;
      border-radius: 2px;
      overflow: hidden;
    }

    .grid-bar-fill {
      height: 100%;
      border-radius: 2px;
      transition: width 0.4s ease;
    }
  `],
})
export class PairCardComponent {
  readonly pair       = input.required<PairInfo>();
  readonly isExpanded = input<boolean>(false);
  readonly isDimmed   = input<boolean>(false);
  readonly positions  = input<PositionData[]>([]);
  readonly volPrediction = input<VolPredictionData | null>(null);
  readonly gridHeld   = input<number>(0);
  readonly gridTotal  = input<number>(20);
  readonly gridLevels = input<GridLevelData | null>(null);

  readonly cardClicked = output<string>();

  readonly shortPair = computed(() => this.pair().pair.replace('-USD', ''));

  readonly regimeCfg = computed<RegimeCfg>(() => {
    const key = (this.pair().regime ?? '').toUpperCase().replace(/ /g, '_');
    return REGIME_MAP[key] ?? DEFAULT_REGIME;
  });

  readonly priceText = computed(() => {
    const p = this.pair().price;
    if (!p) return '';
    if (p >= 1000) return '$' + p.toLocaleString('en-US', { maximumFractionDigits: 2 });
    if (p >= 1)    return '$' + p.toFixed(4);
    return '$' + p.toFixed(6);
  });

  readonly pairPosition = computed(() =>
    this.positions().find(pos => pos.pair === this.pair().pair) ?? null
  );

  readonly pnlPositive = computed(() =>
    (this.pairPosition()?.unrealized_pnl ?? 0) >= 0
  );

  readonly pnlText = computed(() => {
    const pos = this.pairPosition();
    if (!pos) return '--';
    const sign = pos.unrealized_pnl >= 0 ? '+' : '';
    return sign + '$' + Math.abs(pos.unrealized_pnl).toFixed(2);
  });

  readonly gridFillPct = computed(() => {
    const total = this.gridTotal();
    if (!total) return 0;
    return Math.min(100, Math.round((this.gridHeld() / total) * 100));
  });

  readonly gridFillText = computed(() =>
    `${this.gridHeld()} / ${this.gridTotal()}`
  );

  readonly gridFillColor = computed(() => {
    const pct = this.gridFillPct();
    if (pct >= 80) return '#4ade80';
    if (pct >= 40) return '#60a5fa';
    return '#6b7280';
  });

  private formatPrice(p: number): string {
    if (p >= 1) return '$' + p.toFixed(2);
    return '$' + p.toPrecision(4);
  }

  readonly nextBuyText = computed(() => {
    const gl = this.gridLevels();
    if (!gl) return '--';
    const price = this.pair().price;
    const buyLevels = gl.levels.filter(l => l.type === 'buy').map(l => l.price).sort((a, b) => b - a);
    const next = buyLevels.find(p => p <= price) ?? buyLevels[buyLevels.length - 1];
    if (!next) return '--';
    return this.formatPrice(next);
  });

  readonly gridRangeText = computed(() => {
    const gl = this.gridLevels();
    if (!gl) return '--';
    return this.formatPrice(gl.lower) + ' - ' + this.formatPrice(gl.upper);
  });

  // Human-readable summary
  readonly summaryText = computed(() => {
    const p = this.pair();

    // Use server summary if available
    if (p.summary) return p.summary;

    // Client-side fallback
    const name = this.shortPair();
    const regime = (p.regime ?? '').toLowerCase().replace('_', ' ');
    const held = this.gridHeld();
    const total = this.gridTotal();
    const trades = p.trade_count;

    let regimeText = `${name} is active.`;
    if (regime === 'ranging') regimeText = `${name} is bouncing in a range -- good for grid trading.`;
    else if (regime === 'trending up') regimeText = `${name} is trending up.`;
    else if (regime === 'trending down') regimeText = `${name} is trending down. Being cautious.`;
    else if (regime === 'volatile') regimeText = `${name} is seeing big swings.`;
    else if (regime === 'squeeze') regimeText = `${name} is quiet. Waiting for a move.`;

    let gridText = '';
    if (held === 0 && trades === 0) {
      gridText = 'No fills yet -- waiting for the right price.';
    } else if (held === 0) {
      gridText = 'All sold. Ready for next dip.';
    } else {
      gridText = `${held} of ${total} levels filled.`;
    }

    const nxt = this.nextBuyText();
    const nextText = nxt && nxt !== '--' ? `Next buy at ${nxt}.` : '';

    return [regimeText, gridText, nextText].filter(Boolean).join(' ');
  });
}
