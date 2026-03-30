import { Component, OnInit, signal, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService, CandleData, TradeData, IndicatorData, GridLevelData } from '../../services/api.service';
import { PriceChartComponent } from './price-chart.component';
import { IndicatorPanelComponent } from '../indicator-panel/indicator-panel.component';
import { TradeLogComponent } from '../trade-log/trade-log.component';

@Component({
  selector: 'app-pair-view',
  standalone: true,
  imports: [PriceChartComponent, IndicatorPanelComponent, TradeLogComponent],
  template: `
    <div class="flex flex-col gap-4">
      <div class="flex items-baseline gap-3 pb-2" style="border-bottom: 1px solid #2d3148;">
        <h2 class="text-xl font-semibold" style="color: #e1e4ed;">{{ symbol() }}</h2>
        <span class="text-sm" style="color: #8b8fa3;">Live Chart &amp; Analytics</span>
      </div>

      <div style="border-radius: 8px; overflow: hidden; border: 1px solid #2d3148;">
        <app-price-chart
          [candles]="candles()"
          [trades]="trades()"
          [indicators]="indicators()"
          [gridLevels]="gridLevelPrices()"
        />
      </div>

      <div style="border-radius: 8px; overflow: hidden; border: 1px solid #2d3148; background: #0f1117;">
        <app-indicator-panel [indicators]="indicators()" />
      </div>

      <div style="border-radius: 8px; overflow: hidden; border: 1px solid #2d3148; background: #0f1117;">
        <app-trade-log [trades]="trades()" />
      </div>
    </div>
  `,
})
export class PairViewComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private api = inject(ApiService);

  symbol = signal('');
  candles = signal<CandleData[]>([]);
  trades = signal<TradeData[]>([]);
  indicators = signal<IndicatorData[]>([]);
  gridLevelPrices = signal<{ price: number; type: string }[]>([]);

  ngOnInit(): void {
    const sym = this.route.snapshot.paramMap.get('symbol') ?? '';
    this.symbol.set(sym);
    if (!sym) return;

    this.api.fetchCandles(sym, 168).subscribe({
      next: (data) => this.candles.set(data),
    });

    this.api.fetchTrades(sym, 100).subscribe({
      next: (data) => this.trades.set(data),
    });

    this.api.fetchIndicators(sym, 168).subscribe({
      next: (data) => this.indicators.set(data),
    });

    this.api.fetchGridLevels(sym).subscribe({
      next: (data: GridLevelData) => this.gridLevelPrices.set(data.levels),
    });
  }
}
