import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';

const API = '/api';

export interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeData {
  id: number;
  timestamp: string;
  pair: string;
  side: string;
  price: number;
  amount: number;
  cost_usd: number;
  fee: number;
  strategy: string;
  reason: string;
}

export interface EquityData {
  time: string;
  equity: number;
  balance_usd: number;
  positions_value: number;
}

export interface PairInfo {
  pair: string;
  price: number;
  last_candle: string | null;
  trade_count: number;
  regime: string;
}

export interface StatusData {
  equity: number;
  balance_usd: number;
  positions_value: number;
  pnl: number;
  pnl_pct: number;
  starting_balance: number;
  total_trades: number;
  last_trade_time: string | null;
  pairs: PairInfo[];
}

export interface IndicatorData {
  time: string;
  adx: number | null;
  rsi: number | null;
  bb_upper: number | null;
  bb_lower: number | null;
  bb_mid: number | null;
  ema50: number | null;
  ema200: number | null;
  obv: number | null;
  volume: number;
  volume_avg: number | null;
  atr: number | null;
}

export interface GridLevelData {
  pair: string;
  lower: number;
  upper: number;
  num_grids: number;
  levels: { price: number; type: string; index: number }[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly status = signal<StatusData | null>(null);
  readonly refreshCountdown = signal(60);

  private _intervalId: any;

  constructor(private http: HttpClient) {}

  startPolling(intervalSeconds = 60) {
    this.refreshAll();
    let countdown = intervalSeconds;
    this._intervalId = setInterval(() => {
      countdown--;
      this.refreshCountdown.set(countdown);
      if (countdown <= 0) {
        this.refreshAll();
        countdown = intervalSeconds;
      }
    }, 1000);
  }

  stopPolling() {
    if (this._intervalId) clearInterval(this._intervalId);
  }

  refreshAll() {
    this.fetchStatus();
    this.refreshCountdown.set(60);
  }

  fetchCandles(pair: string, hours = 72) {
    return this.http.get<CandleData[]>(`${API}/candles`, { params: { pair, hours: hours.toString() } });
  }

  fetchTrades(pair?: string, limit = 50) {
    const params: any = { limit: limit.toString() };
    if (pair) params.pair = pair;
    return this.http.get<TradeData[]>(`${API}/trades`, { params });
  }

  fetchEquity(hours = 72) {
    return this.http.get<EquityData[]>(`${API}/equity`, { params: { hours: hours.toString() } });
  }

  fetchStatus() {
    this.http.get<StatusData>(`${API}/status`).subscribe({
      next: (data) => this.status.set(data),
      error: () => {},
    });
  }

  fetchIndicators(pair: string, hours = 72) {
    return this.http.get<IndicatorData[]>(`${API}/indicators`, { params: { pair, hours: hours.toString() } });
  }

  fetchGridLevels(pair: string) {
    return this.http.get<GridLevelData>(`${API}/grid-levels`, { params: { pair } });
  }
}
