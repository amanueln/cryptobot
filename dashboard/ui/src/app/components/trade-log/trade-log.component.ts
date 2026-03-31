import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TradeData } from '../../services/api.service';

@Component({
  selector: 'app-trade-log',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="tl-root">
      <div class="tl-header">
        <h3 class="tl-title">Trade Log</h3>
      </div>

      <div class="tl-scroll">
        <table class="tl-table">
          <thead>
            <tr>
              <th class="left">Time</th>
              <th class="left">Pair</th>
              <th class="right">Price</th>
              <th class="right">Amount</th>
              <th class="right">P&amp;L</th>
              <th class="left">Status</th>
              <th class="left hide-sm">Reason</th>
            </tr>
          </thead>
          <tbody>
            @if (trades().length === 0) {
              <tr><td colspan="7" class="empty-row">No trades to display</td></tr>
            }
            @for (trade of trades(); track trade.id; let odd = $odd) {
              <tr
                [class.buy-row]="isBuy(trade.side)"
                [class.sell-row]="!isBuy(trade.side)"
                [class.odd]="odd"
                (click)="onRowClick(trade)"
                [title]="getSellTooltip(trade)"
              >
                <td class="left mono time-cell">{{ formatTime(trade.timestamp) }}</td>
                <td class="left">
                  <span class="pair-name">{{ shortPair(trade.pair) }}</span>
                  <span class="side-tag" [class.buy]="isBuy(trade.side)" [class.sell]="!isBuy(trade.side)">
                    {{ isBuy(trade.side) ? 'BUY' : 'SELL' }}
                  </span>
                </td>
                <td class="right mono">{{ formatPrice(trade.price) }}</td>
                <td class="right mono">
                  <span class="amount-main">{{ formatUsd(isBuy(trade.side) ? trade.cost_usd : trade.revenue) }}</span>
                  <span class="amount-fee">fee {{ formatUsd(trade.fee) }}</span>
                </td>
                <td class="right mono" [style.color]="getNetProfitColor(trade)">
                  {{ formatNetProfit(trade) }}
                </td>
                <td class="left">
                  @if (!isBuy(trade.side)) {
                    <span class="status-badge closed">{{ formatHoldStatus(trade) }}</span>
                  } @else {
                    <span class="status-badge holding">Holding</span>
                  }
                </td>
                <td class="left hide-sm reason-cell">{{ trade.reason || '—' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }

    .tl-root {
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 10px;
      overflow: hidden;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    .tl-header {
      padding: 12px 16px 10px;
      border-bottom: 1px solid #2d3148;
    }

    .tl-title {
      margin: 0;
      font-size: 13px;
      font-weight: 700;
      color: #e2e8f0;
      letter-spacing: 0.03em;
    }

    .tl-scroll {
      max-height: 400px;
      overflow-y: auto;
      overflow-x: auto;
      scrollbar-width: thin;
      scrollbar-color: #2d3148 transparent;
    }

    .tl-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      min-width: 500px;
    }

    .tl-table th {
      padding: 8px 12px;
      font-size: 10px;
      font-weight: 700;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-bottom: 1px solid #2d3148;
      position: sticky;
      top: 0;
      background: #1a1d2e;
      z-index: 2;
      white-space: nowrap;
    }

    .tl-table td {
      padding: 8px 12px;
      border-bottom: 1px solid rgba(45,49,72,0.5);
      white-space: nowrap;
      color: #e2e8f0;
    }

    .left { text-align: left; }
    .right { text-align: right; }
    .mono { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 11px; }

    .time-cell { color: #9ca3af; font-size: 11px; }

    .pair-name { font-weight: 700; color: #e2e8f0; margin-right: 6px; }

    .side-tag {
      display: inline-block;
      font-size: 9px;
      font-weight: 800;
      padding: 1px 5px;
      border-radius: 3px;
      letter-spacing: 0.04em;
      vertical-align: middle;
    }
    .side-tag.buy { background: rgba(34,197,94,0.2); color: #4ade80; }
    .side-tag.sell { background: rgba(239,68,68,0.2); color: #f87171; }

    .amount-main { display: block; }
    .amount-fee { display: block; font-size: 10px; color: #6b7280; }

    .status-badge {
      font-size: 10px;
      font-weight: 600;
      padding: 2px 7px;
      border-radius: 4px;
    }
    .status-badge.holding { background: rgba(250,204,21,0.1); color: #fbbf24; }
    .status-badge.closed { background: rgba(34,197,94,0.1); color: #4ade80; }

    .reason-cell {
      color: #6b7280;
      max-width: 160px;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .empty-row {
      text-align: center;
      padding: 24px 12px;
      color: #6b7280;
      font-style: italic;
    }

    tr.buy-row { background: rgba(34,197,94,0.03); }
    tr.buy-row.odd { background: rgba(34,197,94,0.06); }
    tr.sell-row { background: rgba(239,68,68,0.03); }
    tr.sell-row.odd { background: rgba(239,68,68,0.06); }
    tr:hover { background: rgba(255,255,255,0.04) !important; }
    tr { cursor: pointer; transition: background 0.1s; }

    @media (max-width: 768px) {
      .hide-sm { display: none; }
    }
  `],
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

  formatTime(timestamp: string | number): string {
    return new Date(timestamp).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true,
    });
  }

  formatPrice(price: number): string {
    if (price == null) return '—';
    if (price >= 1) return '$' + price.toFixed(4);
    return '$' + price.toPrecision(4);
  }

  formatUsd(value: number | null | undefined): string {
    if (value == null) return '—';
    return '$' + Math.abs(value).toFixed(2);
  }

  formatNetProfit(trade: TradeData): string {
    if (this.isBuy(trade.side)) {
      if (trade.live_pnl != null && trade.live_pnl_pct != null) {
        const sign = trade.live_pnl >= 0 ? '+' : '-';
        return `${sign}$${Math.abs(trade.live_pnl).toFixed(2)} (${trade.live_pnl_pct >= 0 ? '+' : ''}${trade.live_pnl_pct.toFixed(1)}%)`;
      }
      return '—';
    }
    if (trade.net_profit == null) return '—';
    const sign = trade.net_profit >= 0 ? '+' : '-';
    return `${sign}$${Math.abs(trade.net_profit).toFixed(2)}`;
  }

  getNetProfitColor(trade: TradeData): string {
    if (this.isBuy(trade.side)) {
      if (trade.live_pnl != null) return trade.live_pnl >= 0 ? '#4ade80' : '#f87171';
      return '#6b7094';
    }
    if (trade.net_profit == null) return '#9ca3af';
    return trade.net_profit >= 0 ? '#4ade80' : '#f87171';
  }

  getSellTooltip(trade: TradeData): string {
    if (this.isBuy(trade.side)) return '';
    if (trade.entry_price == null || trade.net_profit == null) return '';
    const pctChange = trade.entry_price > 0 ? ((trade.price / trade.entry_price) - 1) * 100 : 0;
    return `Entry: $${trade.entry_price.toPrecision(4)} → Exit: $${trade.price.toPrecision(4)} (${pctChange >= 0 ? '+' : ''}${pctChange.toFixed(1)}%)`;
  }

  formatHoldStatus(trade: TradeData): string {
    if (trade.hold_duration_seconds != null && trade.hold_duration_seconds > 0) {
      const h = Math.floor(trade.hold_duration_seconds / 3600);
      const m = Math.floor((trade.hold_duration_seconds % 3600) / 60);
      return h > 0 ? `Held ${h}h ${m}m` : `Held ${m}m`;
    }
    return 'Closed';
  }
}
