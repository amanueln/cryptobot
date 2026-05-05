import {
  HttpClient,
  Injectable,
  setClassMetadata,
  signal,
  ɵɵdefineInjectable,
  ɵɵinject
} from "./chunk-VJUHBL36.js";

// src/app/services/api.service.ts
var API = "/api";
function asUtcDate(iso) {
  if (!iso)
    return null;
  const s = String(iso);
  if (/[zZ]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)) {
    const d2 = new Date(s);
    return isNaN(d2.getTime()) ? null : d2;
  }
  const d = /* @__PURE__ */ new Date(s + "Z");
  return isNaN(d.getTime()) ? null : d;
}
function fmt12Hour(iso, opts = {}) {
  const d = asUtcDate(iso);
  if (!d)
    return "--";
  const timeOpts = {
    hour: "numeric",
    minute: "2-digit",
    hour12: true
  };
  if (opts.seconds)
    timeOpts.second = "2-digit";
  const time = d.toLocaleTimeString([], timeOpts);
  if (!opts.date)
    return time;
  const dateStr = d.toLocaleDateString([], { month: "short", day: "numeric" });
  return `${dateStr} ${time}`;
}
var ApiService = class _ApiService {
  http;
  status = signal(null, ...ngDevMode ? [{ debugName: "status" }] : []);
  refreshCountdown = signal(60, ...ngDevMode ? [{ debugName: "refreshCountdown" }] : []);
  scanProgress = signal({
    scanning: false,
    total_pairs: 0,
    scanned: 0,
    elapsed_seconds: 0,
    estimated_remaining: 0
  }, ...ngDevMode ? [{ debugName: "scanProgress" }] : []);
  _intervalId;
  constructor(http) {
    this.http = http;
  }
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
    }, 1e3);
  }
  stopPolling() {
    if (this._intervalId)
      clearInterval(this._intervalId);
  }
  refreshAll() {
    this.fetchStatus();
    this.refreshMomentumStatus();
    this.refreshCountdown.set(60);
  }
  fetchCandles(pair, hours = 72) {
    return this.http.get(`${API}/candles`, { params: { pair, hours: hours.toString() } });
  }
  fetchLiveCandles(pair, tf = "1m", limit = 200) {
    return this.http.get(`${API}/candles/live`, {
      params: { pair, tf, limit: limit.toString() }
    });
  }
  fetchTrades(pair, limit = 50) {
    const params = { limit: limit.toString() };
    if (pair)
      params.pair = pair;
    return this.http.get(`${API}/trades`, { params });
  }
  fetchEquity(hours = 72) {
    return this.http.get(`${API}/equity`, { params: { hours: hours.toString() } });
  }
  fetchStatus() {
    this.http.get(`${API}/status`).subscribe({
      next: (data) => this.status.set(data),
      error: () => {
      }
    });
  }
  fetchIndicators(pair, hours = 72) {
    return this.http.get(`${API}/indicators`, { params: { pair, hours: hours.toString() } });
  }
  fetchGridLevels(pair) {
    return this.http.get(`${API}/grid-levels`, { params: { pair } });
  }
  fetchPositions() {
    return this.http.get(`${API}/positions`);
  }
  fetchPairs() {
    return this.http.get(`${API}/pairs`);
  }
  fetchMLPredictions(pair, limit = 50) {
    const params = { limit: limit.toString() };
    if (pair)
      params.pair = pair;
    return this.http.get(`${API}/ml/predictions`, { params });
  }
  fetchMLAccuracy(pair) {
    const params = {};
    if (pair)
      params.pair = pair;
    return this.http.get(`${API}/ml/accuracy`, { params });
  }
  fetchMLModelInfo() {
    return this.http.get(`${API}/ml/model-info`);
  }
  fetchSelfCheck() {
    return this.http.get(`${API}/self-check`);
  }
  fetchVolPredictions(pair, limit = 50) {
    const params = { limit: limit.toString() };
    if (pair)
      params.pair = pair;
    return this.http.get(`${API}/volatility/predictions`, { params });
  }
  fetchVolLatest() {
    return this.http.get(`${API}/volatility/latest`);
  }
  fetchPairScans(limit = 10) {
    return this.http.get(`${API}/pair-scans`, { params: { limit: limit.toString() } });
  }
  fetchLatestPairScan() {
    return this.http.get(`${API}/pair-scans/latest`);
  }
  fetchScanProgress() {
    return this.http.get(`${API}/pair-scans/progress`);
  }
  fetchOrderBookCheck(pairs) {
    const params = {};
    if (pairs?.length)
      params.pairs = pairs.join(",");
    return this.http.get(`${API}/orderbook-check`, { params });
  }
  fetchPnlAttribution() {
    return this.http.get(`${API}/pnl-attribution`);
  }
  fetchHealth() {
    return this.http.get(`${API}/health`);
  }
  triggerUpdate() {
    return this.http.post(`${API}/update`, {});
  }
  resetData() {
    return this.http.post(`${API}/reset-data`, {});
  }
  backupNow() {
    return this.http.post(`${API}/backup-now`, {});
  }
  resetMomentumData() {
    return this.http.post(`${API}/momentum/reset`, {});
  }
  manualSellMomentum(pair) {
    return this.http.post(`${API}/momentum/sell`, { pair });
  }
  skipMomentumCooldown() {
    return this.http.post(`${API}/momentum/skip-cooldown`, {});
  }
  fetchMomentumOrderbook() {
    return this.http.get(`${API}/momentum/orderbook`);
  }
  toggleWallAware(enabled) {
    return this.http.post(`${API}/momentum/wall-aware/toggle`, { enabled });
  }
  fetchEvents(limit = 50) {
    return this.http.get(`${API}/events`, { params: { limit: limit.toString() } });
  }
  fetchAdaptations(limit = 30) {
    return this.http.get(`${API}/adaptations`, { params: { limit: limit.toString() } });
  }
  // --- Momentum Rotation Engine ---
  momentumStatus = signal(null, ...ngDevMode ? [{ debugName: "momentumStatus" }] : []);
  fetchMomentumStatus() {
    return this.http.get(`${API}/momentum/status`);
  }
  fetchMomentumEquity(hours = 72) {
    return this.http.get(`${API}/momentum/equity`, { params: { hours: hours.toString() } });
  }
  fetchMomentumTrades(limit = 50) {
    return this.http.get(`${API}/momentum/trades`, { params: { limit: limit.toString() } });
  }
  fetchMomentumEvents(limit = 50) {
    return this.http.get(`${API}/momentum/events`, { params: { limit: limit.toString() } });
  }
  fetchMomentumProgress() {
    return this.http.get(`${API}/momentum/progress`);
  }
  fetchMomentumAccel() {
    return this.http.get(`${API}/momentum/accel`);
  }
  refreshMomentumStatus() {
    this.fetchMomentumStatus().subscribe({
      next: (data) => this.momentumStatus.set(data),
      error: () => {
      }
    });
  }
  momentumOrderbook = signal(null, ...ngDevMode ? [{ debugName: "momentumOrderbook" }] : []);
  refreshMomentumOrderbook() {
    this.fetchMomentumOrderbook().subscribe({
      next: (data) => this.momentumOrderbook.set(data),
      error: () => {
      }
    });
  }
  fetchVersion() {
    return this.http.get(`${API}/version`);
  }
  /** Poll scan progress every 2s while scanning, stop when done. */
  startScanProgressPolling(onComplete) {
    const poll = () => {
      this.fetchScanProgress().subscribe({
        next: (p) => {
          this.scanProgress.set(p);
          if (p.scanning) {
            setTimeout(poll, 2e3);
          } else if (onComplete) {
            onComplete();
          }
        },
        error: () => setTimeout(poll, 5e3)
      });
    };
    poll();
  }
  // ---------- Momentum Strategy ----------
  getStrategyProfiles() {
    return this.http.get(`${API}/momentum/strategy/profiles`);
  }
  getStrategyProfile(key) {
    return this.http.get(`${API}/momentum/strategy/profile/${encodeURIComponent(key)}`);
  }
  saveStrategyProfile(body) {
    return this.http.post(`${API}/momentum/strategy/profile/save`, body);
  }
  updateStrategyProfile(name, body) {
    return this.http.put(`${API}/momentum/strategy/profile/${encodeURIComponent(name)}`, body);
  }
  deleteStrategyProfile(name) {
    return this.http.delete(`${API}/momentum/strategy/profile/${encodeURIComponent(name)}`);
  }
  applyStrategy(body) {
    return this.http.post(`${API}/momentum/strategy/apply`, body);
  }
  getStrategyChangelog() {
    return this.http.get(`${API}/momentum/strategy/recommended/changelog`);
  }
  getActiveStrategy() {
    return this.http.get(`${API}/momentum/strategy/active`);
  }
  // --- Scanner Bot ---
  getScannerBotPositions() {
    return this.http.get(`${API}/scanner-bot/positions`);
  }
  getScannerBotTrades(limit = 50) {
    return this.http.get(`${API}/scanner-bot/trades?limit=${limit}`);
  }
  getScannerBotEquity(hours = 24) {
    return this.http.get(`${API}/scanner-bot/equity?hours=${hours}`);
  }
  getScannerBotStats() {
    return this.http.get(`${API}/scanner-bot/stats`);
  }
  scannerBotSellNow(positionId) {
    return this.http.post(`${API}/scanner-bot/positions/${positionId}/sell-now`, {});
  }
  getScannerBotAlertDecisions(limit = 50) {
    return this.http.get(`${API}/scanner-bot/alert-decisions?limit=${limit}`);
  }
  resetScannerBot() {
    return this.http.post(`${API}/scanner-bot/reset`, {});
  }
  // --- Early Momentum Scanner ---
  fetchEarlyScannerAlerts(limit = 50) {
    return this.http.get(`${API}/early-scanner/alerts`, { params: { limit: limit.toString() } });
  }
  fetchEarlyScannerStats() {
    return this.http.get(`${API}/early-scanner/stats`);
  }
  triggerEarlyScan() {
    return this.http.post(`${API}/early-scanner/scan`, {});
  }
  logout() {
    return this.http.post("/api/auth/logout", {});
  }
  static \u0275fac = function ApiService_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _ApiService)(\u0275\u0275inject(HttpClient));
  };
  static \u0275prov = /* @__PURE__ */ \u0275\u0275defineInjectable({ token: _ApiService, factory: _ApiService.\u0275fac, providedIn: "root" });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(ApiService, [{
    type: Injectable,
    args: [{ providedIn: "root" }]
  }], () => [{ type: HttpClient }], null);
})();

export {
  asUtcDate,
  fmt12Hour,
  ApiService
};
//# sourceMappingURL=chunk-W2ARAOE3.js.map
