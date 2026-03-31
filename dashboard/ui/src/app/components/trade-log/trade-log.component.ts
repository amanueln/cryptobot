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

      <div style="max-height: 400px; overflow-y: auto;">
        <table class="w-full text-xs">
          <thead class="sticky top-0 z-10" style="background: #1a1d29;">
            <tr style="border-bottom: 1px solid #2d3148;">
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Time</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Pair</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Side</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Price</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Quantity</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Cost Basis</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Revenue</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Fees</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Net Profit</th>
              <th class="px-3 py-2 text-right font-medium text-gray-400 whitespace-nowrap">Cumulative</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Status</th>
              <th class="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap">Reason</th>
            </tr>
          </thead>
          <tbody>
            @if (trades().length === 0) {
              <tr>
                <td colspan="12" class="px-3 py-8 text-center text-gray-500">No trades to display</td>
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
                <!-- Time -->
                <td class="px-3 py-2 text-gray-300 whitespace-nowrap font-mono">
                  {{ formatTime(trade.timestamp) }}
                </td>
                <!-- Pair -->
                <td class="px-3 py-2 text-white font-medium whitespace-nowrap">
                  {{ shortPair(trade.pair) }}
                </td>
                <!-- Side -->
                <td class="px-3 py-2 whitespace-nowrap">
                  @if (isBuy(trade.side)) {
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
                <!-- Price -->
                <td class="px-3 py-2 text-right text-gray-200 whitespace-nowrap font-mono">
                  {{ formatPrice(trade.price) }}
                </td>
                <!-- Quantity -->
                <td class="px-3 py-2 text-right text-gray-200 whitespace-nowrap font-mono">
                  {{ formatAmount(trade.amount) }}
                </td>
                <!-- Cost Basis -->
                <td class="px-3 py-2 text-right text-gray-400 whitespace-nowrap font-mono">
                  {{ trade.cost_basis != null ? formatUsd(trade.cost_basis) : (isBuy(trade.side) ? formatUsd(trade.cost_usd) : 'N/A') }}
                </td>
                <!-- Revenue -->
                <td class="px-3 py-2 text-right text-gray-400 whitespace-nowrap font-mono">
                  {{ trade.revenue != null ? formatUsd(trade.revenue) : '—' }}
                </td>
                <!-- Fees -->
                <td class="px-3 py-2 text-right text-gray-500 whitespace-nowrap font-mono">
                  {{ formatUsd(trade.fee) }}
                </td>
                <!-- Net Profit -->
                <td class="px-3 py-2 text-right whitespace-nowrap font-mono font-semibold"
                    [style.color]="getNetProfitColor(trade)"
                    [title]="getSellTooltip(trade)">
                  {{ formatNetProfit(trade) }}
                </td>
                <!-- Cumulative -->
                <td class="px-3 py-2 text-right whitespace-nowrap font-mono"
                    [style.color]="getCumColor(trade)">
                  {{ trade.cumulative_pnl != null ? formatSigned(trade.cumulative_pnl) : '—' }}
                </td>
                <!-- Status -->
                <td class="px-3 py-2 whitespace-nowrap">
                  @if (!isBuy(trade.side)) {
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                          style="background: rgba(34, 197, 94, 0.1); color: #4ade80;">
                      {{ formatHoldStatus(trade) }}
                    </span>
                  } @else {
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                          style="background: rgba(250, 204, 21, 0.1); color: #fbbf24;">
                      Holding
                    </span>
                  }
                </td>
                <!-- Reason -->
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

  isBuy(side: string): boolean {
    return side === 'buy' || side === 'BUY';
  }

  shortPair(pair: string): string {
    return pair.replace('-USD', '');
  }

  onRowMouseEnter(event: MouseEvent, side: string): void {
    const row = event.currentTarget as HTMLElement;
    row.style.background = this.isBuy(side)
      ? 'rgba(34, 197, 94, 0.15)'
      : 'rgba(239, 68, 68, 0.15)';
  }

  onRowMouseLeave(event: MouseEvent, side: string, odd: boolean): void {
    const row = event.currentTarget as HTMLElement;
    row.style.background = this.getRowBackground(side, odd);
  }

  getRowBackground(side: string, odd: boolean): string {
    if (this.isBuy(side)) {
      return odd ? 'rgba(34, 197, 94, 0.06)' : 'rgba(34, 197, 94, 0.03)';
    }
    return odd ? 'rgba(239, 68, 68, 0.06)' : 'rgba(239, 68, 68, 0.03)';
  }

  formatTime(timestamp: string | number): string {
    return new Date(timestamp).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
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
    return amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 });
  }

  formatUsd(value: number | null): string {
    if (value == null) return '—';
    return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  formatSigned(value: number): string {
    const sign = value >= 0 ? '+' : '';
    return sign + '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  formatNetProfit(trade: TradeData): string {
    if (this.isBuy(trade.side)) {
      if (trade.live_pnl != null && trade.live_pnl_pct != null) {
        const sign = trade.live_pnl >= 0 ? '+' : '';
        const pctSign = trade.live_pnl_pct >= 0 ? '+' : '';
        return `Holding: ${sign}$${Math.abs(trade.live_pnl).toFixed(2)} (${pctSign}${trade.live_pnl_pct.toFixed(1)}%)`;
      }
      return 'Pending';
    }
    if (trade.cost_basis == null) return 'N/A';
    if (trade.net_profit == null) return '—';
    return this.formatSigned(trade.net_profit);
  }

  getNetProfitColor(trade: TradeData): string {
    if (this.isBuy(trade.side)) {
      if (trade.live_pnl != null) {
        return trade.live_pnl >= 0 ? '#4ade80' : '#f87171';
      }
      return '#6b7094';
    }
    if (trade.cost_basis == null) return '#6b7094';
    if (trade.net_profit == null) return '#9ca3af';
    if (trade.net_profit > 0) return '#4ade80';
    if (trade.net_profit < 0) return '#f87171';
    return '#9ca3af';
  }

  getCumColor(trade: TradeData): string {
    if (trade.cumulative_pnl == null) return '#6b7094';
    if (trade.cumulative_pnl > 0) return '#4ade80';
    if (trade.cumulative_pnl < 0) return '#f87171';
    return '#9ca3af';
  }

  getSellTooltip(trade: TradeData): string {
    if (this.isBuy(trade.side)) return '';
    if (trade.cost_basis == null) return 'No matching buy found — cost basis unknown';
    if (trade.entry_price == null || trade.net_profit == null) return '';

    const entryPrice = this.formatPrice(trade.entry_price);
    const sellPrice = this.formatPrice(trade.price);
    const perUnit = trade.amount > 0 ? (trade.net_profit / trade.amount) : 0;
    const perUnitSign = perUnit >= 0 ? '+' : '';
    const pctChange = trade.entry_price > 0 ? ((trade.price / trade.entry_price) - 1) * 100 : 0;
    const pctSign = pctChange >= 0 ? '+' : '';
    const profitSign = trade.net_profit >= 0 ? '+' : '';

    return `Bought at ${entryPrice} → Sold at ${sellPrice} = ${perUnitSign}$${Math.abs(perUnit).toFixed(4)}/unit (${pctSign}${pctChange.toFixed(1)}%) — Net profit: ${profitSign}$${Math.abs(trade.net_profit).toFixed(2)} after $${trade.fee.toFixed(2)} fees`;
  }

  formatHoldStatus(trade: TradeData): string {
    if (trade.hold_duration_seconds != null && trade.hold_duration_seconds > 0) {
      return 'Held ' + this.formatDurationShort(trade.hold_duration_seconds);
    }
    return 'Closed';
  }

  private formatDurationShort(seconds: number): string {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
      return `${days}d ${hours}h`;
    }
    return `${hours}h ${minutes}m`;
  }
}
