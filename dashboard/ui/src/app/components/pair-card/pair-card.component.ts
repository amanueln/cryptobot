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
  TRENDING_UP:    { label: 'TRENDING ↑',    bg: '#1e3a5f', text: '#60a5fa' },
  TRENDING_DOWN:  { label: 'TRENDING ↓',    bg: '#450a0a', text: '#f87171' },
  SQUEEZE:        { label: 'SQUEEZE',       bg: '#3b0764', text: '#c084fc' },
};

const DEFAULT_REGIME: RegimeCfg = { label: 'UNKNOWN', bg: '#1e2130', text: '#94a3b8' };

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
      [attr.aria-label]="pair().pair + ' pair card'"
    >
      <!-- Header row -->
      <div class="card-header">
        <div class="pair-name-row">
          <span class="pair-name">{{ shortPair() }}</span>
          <span
            class="regime-badge"
            [style.background]="regimeCfg().bg"
            [style.color]="regimeCfg().text"
          >{{ regimeCfg().label }}</span>
        </div>
        <span class="collapse-hint" *ngIf="isExpanded()">Click to collapse ▲</span>
      </div>

      <!-- 2×3 stats grid -->
      <div class="stats-grid">
        <div class="stat-cell">
          <span class="sc-label">Price</span>
          <span class="sc-value">{{ priceText() }}</span>
        </div>
        <div class="stat-cell">
          <span class="sc-label">P&amp;L</span>
          <span class="sc-value" [class.positive]="pnlPositive()" [class.negative]="!pnlPositive()">
            {{ pnlText() }}
          </span>
        </div>
        <div class="stat-cell">
          <span class="sc-label">Grid fill</span>
          <span class="sc-value">{{ gridFillText() }}</span>
        </div>
        <div class="stat-cell">
          <span class="sc-label">Next buy</span>
          <span class="sc-value entry-price">{{ nextBuyText() }}</span>
        </div>
        <div class="stat-cell">
          <span class="sc-label">Trades</span>
          <span class="sc-value">{{ pair().trade_count }}</span>
        </div>
        <div class="stat-cell">
          <span class="sc-label">Range</span>
          <span class="sc-value range-value">{{ gridRangeText() }}</span>
        </div>
      </div>

      <!-- Grid fill progress bar -->
      <div class="grid-bar-track" [title]="gridFillText() + ' grid levels filled'">
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

    .card-root.dimmed {
      opacity: 0.7;
    }

    /* Header */
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
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
      letter-spacing: 0.02em;
    }

    .regime-badge {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.07em;
      padding: 2px 7px;
      border-radius: 4px;
      text-transform: uppercase;
    }

    .collapse-hint {
      font-size: 10px;
      color: #fbbf24;
      font-weight: 600;
    }

    /* Stats grid */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px 8px;
      margin-bottom: 10px;
    }

    .stat-cell {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .sc-label {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: #6b7280;
      text-transform: uppercase;
    }

    .sc-value {
      font-size: 12px;
      font-weight: 600;
      color: #e2e8f0;
      white-space: nowrap;
    }

    .sc-value.positive { color: #4ade80; }
    .sc-value.negative { color: #f87171; }
    .sc-value.entry-price { color: #fbbf24; }
    .sc-value.range-value { font-size: 10px; color: #9ca3af; }

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
  readonly gridTotal  = input<number>(10);
  readonly gridLevels = input<GridLevelData | null>(null);

  readonly cardClicked = output<string>();

  readonly shortPair = computed(() => this.pair().pair.replace('-USD', ''));

  readonly regimeCfg = computed<RegimeCfg>(() => {
    const key = (this.pair().regime ?? '').toUpperCase().replace(/ /g, '_');
    return REGIME_MAP[key] ?? DEFAULT_REGIME;
  });

  readonly priceText = computed(() => {
    const p = this.pair().price;
    if (!p) return '—';
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
    if (!pos) return '—';
    const sign = pos.unrealized_pnl >= 0 ? '+' : '';
    return sign + '$' + Math.abs(pos.unrealized_pnl).toFixed(2);
  });

  readonly gridFillPct = computed(() => {
    const total = this.gridTotal();
    if (!total) return 0;
    return Math.min(100, Math.round((this.gridHeld() / total) * 100));
  });

  readonly gridFillText = computed(() =>
    `${this.gridHeld()}/${this.gridTotal()}`
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
    if (!gl) return '—';
    const price = this.pair().price;
    // Find the highest buy level below current price (next trigger)
    const buyLevels = gl.levels.filter(l => l.type === 'buy').map(l => l.price).sort((a, b) => b - a);
    const next = buyLevels.find(p => p <= price) ?? buyLevels[buyLevels.length - 1];
    if (!next) return '—';
    return this.formatPrice(next);
  });

  readonly gridRangeText = computed(() => {
    const gl = this.gridLevels();
    if (!gl) return '—';
    return this.formatPrice(gl.lower) + '–' + this.formatPrice(gl.upper);
  });
}
