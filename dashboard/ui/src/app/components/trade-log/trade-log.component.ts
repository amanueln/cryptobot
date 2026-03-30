import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TradeData } from '../../services/api.service';

@Component({
  selector: 'app-trade-log',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="rounded-lg overflow-hidden" style="background: #1a1d29; border: 1px solid #2d3148;">
      <div class="px-4 py-3" style="border-bottom: 1px solid #2d3148;">
        <h3 class="text-sm font-semibold text-gray-300 uppercase tracking-wider">Trade Log</h3>
      </div>

      <div style="max-height: 300px; overflow-y: auto;">
        <table class="w-full text-xs">
          <thead class="sticky top-0 z-10" style="background: #1a1d29;">
            <tr style="border-bottom: 1px solid #2d3148;">
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Time</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Pair</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Side</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Price</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Quantity</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Fees</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">P&amp;L</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Strategy</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Reason</th>
            </tr>
          </thead>
          <tbody>
            @if (trades().length === 0) {
              <tr>
                <td colspan="9" class="px-3 py-8 text-center text-gray-500">No trades to display</td>
              </tr>
            }
            @for (trade of trades(); track trade.id; let odd = $odd) {
              <tr
                class="cursor-pointer transition-colors duration-100"
                [style.background]="getRowBackground(trade.side, odd)"
                (click)="onRowClick(trade)"
                (mouseenter)="onRowMouseEnter($event, trade.side)"
                (mouseleave)="onRowMouseLeave($event, trade.side, odd)"
                style="border-bottom: 1px solid #2d3148;"
              >
                <td class="px-3 py-2 text-gray-300 whitespace-nowrap font-mono">
                  {{ formatTime(trade.timestamp) }}
                </td>
                <td class="px-3 py-2 text-white font-medium whitespace-nowrap">
                  {{ trade.pair }}
                </td>
                <td class="px-3 py-2 whitespace-nowrap">
                  @if (trade.side === 'buy' || trade.side === 'BUY') {
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold"
                          style="background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4);">
                      BUY
                    </span>
                  } @else {
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold"
                          style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);">
                      SELL
                    </span>
                  }
                </td>
                <td class="px-3 py-2 text-right text-gray-200 whitespace-nowrap font-mono">
                  {{ formatPrice(trade.price) }}
                </td>
                <td class="px-3 py-2 text-right text-gray-200 whitespace-nowrap font-mono">
                  {{ formatAmount(trade.amount) }}
                </td>
                <td class="px-3 py-2 text-right text-gray-400 whitespace-nowrap font-mono">
                  {{ formatFee(trade.fee) }}
                </td>
                <td class="px-3 py-2 text-right whitespace-nowrap font-mono"
                    [style.color]="getPnlColor(trade)">
                  {{ formatPnl(trade) }}
                </td>
                <td class="px-3 py-2 text-gray-300 whitespace-nowrap">
                  {{ trade.strategy || '—' }}
                </td>
                <td class="px-3 py-2 text-gray-400 max-w-32 truncate" [title]="trade.reason || ''">
                  {{ trade.reason || '—' }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </div>
  `,
})
export class TradeLogComponent {
  trades = input.required<TradeData[]>();
  tradeClicked = output<string>();

  onRowClick(trade: TradeData): void {
    this.tradeClicked.emit(trade.timestamp);
  }

  onRowMouseEnter(event: MouseEvent, side: string): void {
    const row = event.currentTarget as HTMLElement;
    const isBuy = side === 'buy' || side === 'BUY';
    row.style.background = isBuy
      ? 'rgba(34, 197, 94, 0.15)'
      : 'rgba(239, 68, 68, 0.15)';
  }

  onRowMouseLeave(event: MouseEvent, side: string, odd: boolean): void {
    const row = event.currentTarget as HTMLElement;
    row.style.background = this.getRowBackground(side, odd);
  }

  getRowBackground(side: string, odd: boolean): string {
    const isBuy = side === 'buy' || side === 'BUY';
    const base = odd ? '#242736' : '#1a1d29';
    if (isBuy) {
      return odd
        ? 'rgba(34, 197, 94, 0.06)'
        : 'rgba(34, 197, 94, 0.03)';
    } else {
      return odd
        ? 'rgba(239, 68, 68, 0.06)'
        : 'rgba(239, 68, 68, 0.03)';
    }
  }

  formatTime(timestamp: string | number): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  }

  formatPrice(price: number): string {
    if (price == null) return '—';
    if (price >= 1000) {
      return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
  }

  formatAmount(amount: number): string {
    if (amount == null) return '—';
    return amount.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 8 });
  }

  formatFee(fee: number): string {
    if (fee == null) return '—';
    return '$' + fee.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  }

  formatPnl(trade: TradeData): string {
    const pnl = this.computePnl(trade);
    if (pnl == null) return '—';
    const sign = pnl >= 0 ? '+' : '';
    return sign + '$' + pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  getPnlColor(trade: TradeData): string {
    const pnl = this.computePnl(trade);
    if (pnl == null) return '#9ca3af';
    if (pnl > 0) return '#4ade80';
    if (pnl < 0) return '#f87171';
    return '#9ca3af';
  }

  private computePnl(trade: TradeData): number | null {
    // cost_usd can serve as realized P&L if provided by the backend;
    // for buy trades it will typically be null or negative (outflow).
    // Expose it as-is when available, otherwise return null.
    if (trade.cost_usd != null && (trade.side === 'sell' || trade.side === 'SELL')) {
      return trade.cost_usd;
    }
    return null;
  }
}
