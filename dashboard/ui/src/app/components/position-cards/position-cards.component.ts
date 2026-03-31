import { Component, input, computed } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { PositionData } from '../../services/api.service';

@Component({
  selector: 'app-position-cards',
  standalone: true,
  imports: [DecimalPipe],
  template: `
    <div class="cards-container">
      @for (pos of enrichedPositions(); track pos.pair) {
        <div class="pos-card" [style.border-left-color]="pos.isUp ? '#22c55e' : '#ef4444'">
          <div class="pos-header">
            <span class="pos-pair">{{ pos.ticker }}</span>
            <span class="pos-qty">{{ pos.quantity | number:'1.4-4' }} units</span>
          </div>
          <div class="pos-details">
            <span>Bought at <strong>{{ pos.entry_price | number:'1.4-6' }}</strong></span>
            <span class="sep">&rarr;</span>
            <span>target <strong>{{ pos.sellTarget | number:'1.4-6' }}</strong></span>
          </div>
          <div class="pos-current">
            Current <strong>{{ pos.current_price | number:'1.4-6' }}</strong>
            &mdash;
            <span [style.color]="pos.isUp ? '#22c55e' : '#ef4444'">
              needs {{ pos.pctToSell > 0 ? '+' : '' }}{{ pos.pctToSell | number:'1.1-1' }}% to sell
            </span>
          </div>
          <div class="pos-pnl" [style.color]="pos.unrealized_pnl >= 0 ? '#22c55e' : '#ef4444'">
            PnL: {{ pos.unrealized_pnl >= 0 ? '+' : '' }}{{ pos.unrealized_pnl | number:'1.2-2' }} USD
            ({{ pos.unrealized_pnl_pct >= 0 ? '+' : '' }}{{ pos.unrealized_pnl_pct | number:'1.2-2' }}%)
          </div>
        </div>
      } @empty {
        <div class="no-positions">No open positions</div>
      }
    </div>
  `,
  styles: [`
    .cards-container {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      padding: 8px 0;
    }
    .pos-card {
      background: #161926;
      border: 1px solid #2d3148;
      border-left: 3px solid #22c55e;
      border-radius: 6px;
      padding: 10px 14px;
      min-width: 280px;
      flex: 1 1 280px;
      max-width: 420px;
    }
    .pos-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .pos-pair {
      font-weight: 600;
      font-size: 14px;
      color: #e1e4ed;
    }
    .pos-qty {
      font-size: 12px;
      color: #8b8fa3;
    }
    .pos-details {
      font-size: 12px;
      color: #a0a4b8;
      margin-bottom: 4px;
    }
    .pos-details strong {
      color: #e1e4ed;
    }
    .sep {
      margin: 0 4px;
      color: #555;
    }
    .pos-current {
      font-size: 12px;
      color: #a0a4b8;
      margin-bottom: 4px;
    }
    .pos-current strong {
      color: #e1e4ed;
    }
    .pos-pnl {
      font-size: 12px;
      font-weight: 500;
      margin-top: 4px;
    }
    .no-positions {
      color: #555;
      font-size: 13px;
      padding: 8px 0;
    }
  `],
})
export class PositionCardsComponent {
  positions = input<PositionData[]>([]);

  enrichedPositions = computed(() => {
    return this.positions()
      .filter(p => p.quantity > 0)
      .map(pos => {
        const sellTarget = pos.entry_price * 1.05;
        const pctToSell = ((sellTarget - pos.current_price) / pos.current_price) * 100;
        const ticker = pos.pair.replace('-USD', '');
        const isUp = pos.current_price >= pos.entry_price;
        return { ...pos, sellTarget, pctToSell, ticker, isUp };
      });
  });
}
