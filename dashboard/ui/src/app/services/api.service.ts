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
  cost_basis: number | null;
  revenue: number | null;
  net_profit: number | null;
  cumulative_pnl: number | null;
  live_pnl: number | null;
  live_pnl_pct: number | null;
  hold_duration_seconds: number | null;
  entry_price: number | null;
  regime: string;
  adx: number;
  rsi: number;
  atr_multiplier: number;
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
  grid_held: number;
  grid_total: number;
  summary?: string;
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
  summary?: string;
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

export interface PositionData {
  pair: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  cost_basis: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  hold_since: string | null;
  breakeven_price: number | null;
}

export interface GridLevelData {
  pair: string;
  lower: number;
  upper: number;
  num_grids: number;
  levels: { price: number; type: string; index: number }[];
}

export interface MLPredictionData {
  id: number;
  timestamp: string;
  pair: string;
  direction: string;
  predicted_change_pct: number | null;
  confidence: number;
  do_predict: number | null;
  di_value: number | null;
  feature_values: Record<string, number>;
  feature_contributions: Record<string, number>;
  top_bullish: string[];
  top_bearish: string[];
  recommended_action: string;
  recommended_size_pct: number;
  actual_outcome: string | null;
  actual_price_change: number | null;
}

export interface MLAccuracyData {
  total: number;
  evaluated: number;
  correct: number;
  accuracy: number;
}

export interface MLModelInfo {
  pair: string;
  version: number;
  trained_at: string;
  candle_count: number;
  validation_rmse: number;
  validation_r2: number;
  feature_count: number;
  feature_importance: Record<string, number>;
  label_mean: number;
  label_std: number;
  model_health: string;
  age_hours: number;
  next_retrain_hours: number;
}

export interface VolPredictionData {
  id: number;
  timestamp: string;
  pair: string;
  predicted_vol_12h: number;
  current_vol_12h: number;
  vol_30d_avg: number;
  vol_regime: string;
  spacing_multiplier: number;
  recommended_num_grids: number;
  confidence: number;
  garch_vol: number;
  feature_importance: Record<string, number>;
}

export interface SelfCheckData {
  vol_accuracy_24h: { count: number; avg_error_pct: number; min_error_pct: number; max_error_pct: number };
  vol_accuracy_7d: { count: number; avg_error_pct: number; min_error_pct: number; max_error_pct: number };
  grid_performance: {
    vol_regime: string;
    avg_spacing_mult: number;
    cycles: number;
    total_pnl: number;
    avg_pnl: number;
    avg_spacing_pct: number;
  }[];
  streak: { type: string; days: number };
  events: { timestamp: string; event_type: string; details: string }[];
  trading_paused: { paused: boolean; reason: string; since: string };
  daily_pnl: number;
  weekly_pnl: number;
  summary?: string;
}

export interface PairScanData {
  id: number;
  timestamp: string;
  scan_type: string;
  total_pairs_scanned: number;
  results: PairScoreData[];
  selected_pairs: PairScoreData[];
  swapped_out: { pair: string; reason: string }[];
  swapped_in: { pair: string; reason: string }[];
}

export interface PairScoreData {
  pair: string;
  composite_score: number;
  volatility: number;
  range_bound: number;
  liquidity: number;
  fee_clearance: number;
  regime: string;
  regime_bonus: number;
  backtest_pnl: number;
  candle_count: number;
  price: number;
  volume_24h: number;
}

export interface OrderBookCheck {
  pair: string;
  best_bid: number;
  best_ask: number;
  mid: number;
  spread_pct: number;
  bid_depth_2pct: number;
  ask_depth_2pct: number;
  low_liquidity: boolean;
  flags: string[];
  error?: string;
}

export interface PnlAttribution {
  legacy: Record<string, PairPnlStats>;
  legacy_total_pnl: number;
  auto_selected: Record<string, PairPnlStats>;
  auto_total_pnl: number;
  auto_pairs: string[];
}

export interface PairPnlStats {
  pair: string;
  trades: number;
  buys: number;
  sells: number;
  total_cost: number;
  total_revenue: number;
  total_fees: number;
  realized_pnl: number;
  source: string;
}

export interface ScanProgressData {
  scanning: boolean;
  total_pairs: number;
  scanned: number;
  elapsed_seconds: number;
  estimated_remaining: number;
}

export interface HealthData {
  status: string;
  bot_running: boolean;
  uptime_seconds: number;
  last_trade: string | null;
  active_pairs: string[];
  total_trades: number;
  equity: number;
  pnl: number;
  last_update_check: string | null;
  update_status: string;
  model_status: Record<string, string>;
}

export interface UpdateResult {
  status: string;
  output: string;
  update_status?: string;
}

export interface EventData {
  id: number;
  timestamp: string;
  event_type: string;
  pair: string;
  title: string;
  detail: string;
}

export interface AdaptationData {
  id: number;
  timestamp: string;
  pair: string;
  loop_type: string;
  description: string;
  old_value: number | null;
  new_value: number | null;
}

export interface MomentumScannerData {
  last_scan_time: string | null;
  pairs_count: number;
  pairs: string[];
  top_by_volume: { pair: string; volume_24h: number; price: number }[];
}

export interface MomentumStatusData {
  enabled: boolean;
  status: string;
  equity: number;
  cash: number;
  positions_value: number;
  pnl: number;
  pnl_pct: number;
  starting_balance: number;
  trade_count: number;
  holdings: MomentumHoldingData[];
  scanner?: MomentumScannerData | null;
  regime_bullish?: boolean;
  regime_state?: string;
  exit_cooldown_remaining?: number;
  hours_in_position?: number;
  warmup_done?: boolean;
  was_cash?: boolean;
  next_rebal_hours?: number;
  btc_price?: number;
  btc_ma?: number;
  regime_hysteresis?: number;
  entry_rejections?: string[];
  error?: string;
}

export interface MomentumHoldingData {
  pair: string;
  shares: number;
  entry_price: number;
  current_price: number;
  value: number;
  pnl: number;
  pnl_pct: number;
  accel: number;
  entry_time: string;
  peak_price: number;
  stop_price: number;
  stop_distance_pct: number;
  max_hold_remaining_hours: number;
}

export interface MomentumTradeData {
  timestamp: string;
  pair: string;
  side: string;
  price: number;
  amount: number;
  cost_usd: number;
  fee: number;
  reason: string;
  net_pnl: number | null;
  entry_price: number | null;
  closed: boolean;
}

export interface MomentumEquityData {
  time: string;
  equity: number;
  cash: number;
  positions_value: number;
  status: string;
}

export interface MomentumEventData {
  timestamp: string;
  event_type: string;
  title: string;
  detail: string;
}

export interface EarlyScannerAlert {
  id: number;
  timestamp: string;
  pair: string;
  price: number;
  score: number;
  signals: string[];
  volume_24h: number;
  change_1h_pct: number;
  change_3h_pct: number;
  notified: boolean;
  outcome_1h_pct: number | null;
  outcome_4h_pct: number | null;
  outcome_12h_pct: number | null;
  outcome_24h_pct: number | null;
  outcome_peak_pct: number | null;
  outcome_peak_time: string | null;
  score_adj: number;
  effective_score: number;
}

export interface SignalComboStats {
  combo: string;
  combo_display: string;
  total: number;
  wins: number;
  win_rate: number;
  avg_peak_pct: number;
  score_adj: number;
}

export interface EarlyScannerStats {
  total_alerts: number;
  alerts_24h: number;
  evaluated: number;
  wins: number;
  win_rate: number;
  hit_rate: number;
  running: boolean;
  last_run: string | null;
  combo_stats: SignalComboStats[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly status = signal<StatusData | null>(null);
  readonly refreshCountdown = signal(60);
  readonly scanProgress = signal<ScanProgressData>({
    scanning: false, total_pairs: 0, scanned: 0,
    elapsed_seconds: 0, estimated_remaining: 0,
  });

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
    this.refreshMomentumStatus();
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

  fetchPositions() {
    return this.http.get<PositionData[]>(`${API}/positions`);
  }

  fetchPairs() {
    return this.http.get<string[]>(`${API}/pairs`);
  }

  fetchMLPredictions(pair?: string, limit = 50) {
    const params: any = { limit: limit.toString() };
    if (pair) params.pair = pair;
    return this.http.get<MLPredictionData[]>(`${API}/ml/predictions`, { params });
  }

  fetchMLAccuracy(pair?: string) {
    const params: any = {};
    if (pair) params.pair = pair;
    return this.http.get<MLAccuracyData>(`${API}/ml/accuracy`, { params });
  }

  fetchMLModelInfo() {
    return this.http.get<MLModelInfo[]>(`${API}/ml/model-info`);
  }

  fetchSelfCheck() {
    return this.http.get<SelfCheckData>(`${API}/self-check`);
  }

  fetchVolPredictions(pair?: string, limit = 50) {
    const params: any = { limit: limit.toString() };
    if (pair) params.pair = pair;
    return this.http.get<VolPredictionData[]>(`${API}/volatility/predictions`, { params });
  }

  fetchVolLatest() {
    return this.http.get<VolPredictionData[]>(`${API}/volatility/latest`);
  }

  fetchPairScans(limit = 10) {
    return this.http.get<PairScanData[]>(`${API}/pair-scans`, { params: { limit: limit.toString() } });
  }

  fetchLatestPairScan() {
    return this.http.get<PairScanData | null>(`${API}/pair-scans/latest`);
  }

  fetchScanProgress() {
    return this.http.get<ScanProgressData>(`${API}/pair-scans/progress`);
  }

  fetchOrderBookCheck(pairs?: string[]) {
    const params: any = {};
    if (pairs?.length) params.pairs = pairs.join(',');
    return this.http.get<OrderBookCheck[]>(`${API}/orderbook-check`, { params });
  }

  fetchPnlAttribution() {
    return this.http.get<PnlAttribution>(`${API}/pnl-attribution`);
  }

  fetchHealth() {
    return this.http.get<HealthData>(`${API}/health`);
  }

  triggerUpdate() {
    return this.http.post<UpdateResult>(`${API}/update`, {});
  }

  resetData() {
    return this.http.post<{ status: string; deleted: Record<string, number> }>(`${API}/reset-data`, {});
  }

  resetMomentumData() {
    return this.http.post<{ status: string; deleted: Record<string, number> }>(`${API}/momentum/reset`, {});
  }

  manualSellMomentum(pair: string) {
    return this.http.post<{ status: string }>(`${API}/momentum/sell`, { pair });
  }

  skipMomentumCooldown() {
    return this.http.post<{ status: string }>(`${API}/momentum/skip-cooldown`, {});
  }

  fetchEvents(limit = 50) {
    return this.http.get<EventData[]>(`${API}/events`, { params: { limit: limit.toString() } });
  }

  fetchAdaptations(limit = 30) {
    return this.http.get<AdaptationData[]>(`${API}/adaptations`, { params: { limit: limit.toString() } });
  }

  // --- Momentum Rotation Engine ---

  readonly momentumStatus = signal<MomentumStatusData | null>(null);

  fetchMomentumStatus() {
    return this.http.get<MomentumStatusData>(`${API}/momentum/status`);
  }

  fetchMomentumEquity(hours = 72) {
    return this.http.get<MomentumEquityData[]>(`${API}/momentum/equity`, { params: { hours: hours.toString() } });
  }

  fetchMomentumTrades(limit = 50) {
    return this.http.get<MomentumTradeData[]>(`${API}/momentum/trades`, { params: { limit: limit.toString() } });
  }

  fetchMomentumEvents(limit = 50) {
    return this.http.get<MomentumEventData[]>(`${API}/momentum/events`, { params: { limit: limit.toString() } });
  }

  fetchMomentumProgress() {
    return this.http.get<{ step: string; pair?: string; done?: number; total?: number; pct?: number; estimated_remaining?: number }>(`${API}/momentum/progress`);
  }

  fetchMomentumAccel() {
    return this.http.get<{ pair: string; accel: number; price: number }[]>(`${API}/momentum/accel`);
  }

  refreshMomentumStatus() {
    this.fetchMomentumStatus().subscribe({
      next: (data) => this.momentumStatus.set(data),
      error: () => {},
    });
  }

  /** Poll scan progress every 2s while scanning, stop when done. */
  startScanProgressPolling(onComplete?: () => void) {
    const poll = () => {
      this.fetchScanProgress().subscribe({
        next: (p) => {
          this.scanProgress.set(p);
          if (p.scanning) {
            setTimeout(poll, 2000);
          } else if (onComplete) {
            onComplete();
          }
        },
        error: () => setTimeout(poll, 5000),
      });
    };
    poll();
  }

  // --- Early Momentum Scanner ---

  fetchEarlyScannerAlerts(limit = 50) {
    return this.http.get<EarlyScannerAlert[]>(`${API}/early-scanner/alerts`, { params: { limit: limit.toString() } });
  }

  fetchEarlyScannerStats() {
    return this.http.get<EarlyScannerStats>(`${API}/early-scanner/stats`);
  }

  triggerEarlyScan() {
    return this.http.post<{ status: string }>(`${API}/early-scanner/scan`, {});
  }
}
