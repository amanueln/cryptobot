import {
  Component, OnInit, AfterViewInit, inject, signal, ViewChild, ElementRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chart, registerables, ChartConfiguration } from 'chart.js';
import zoomPlugin from 'chartjs-plugin-zoom';
import {
  ApiService, MomentumStatusData, MomentumTradeData,
  MomentumEquityData, MomentumEventData,
} from '../../services/api.service';
import { forkJoin } from 'rxjs';

Chart.register(...registerables, zoomPlugin);

@Component({
  selector: 'app-momentum-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="mp-root">

      <!-- Engine label tab -->
      <div class="engine-tab">
        <span class="engine-dot" [class.active]="isHolding()" [class.idle]="!isHolding() && isRunning()" [class.inactive]="!isRunning()"></span>
        <span class="engine-name">Momentum Rotation</span>
        <span class="engine-tag" [class.holding]="isHolding()" [class.idle]="!isHolding() && isRunning()" [class.inactive]="!isRunning()">
          {{ engineTagText() }}
        </span>
        <span class="engine-alloc">{{ formatCurrency(status()?.starting_balance ?? 0) }} allocated</span>
        <a class="export-btn" href="/api/download-db" download="candles.db" title="Download database">Export DB</a>
        <button class="reset-btn" (click)="resetData()" title="Reset momentum data">Reset Data</button>
      </div>

      <!-- Hero numbers -->
      <div class="hero-bar">
        <div class="hero-item">
          <span class="hero-label">Total</span>
          <span class="hero-value">{{ formatCurrency(status()?.equity ?? 0) }}</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-label">Cash</span>
          <span class="hero-value cash-val">{{ formatCurrency(status()?.cash ?? 0) }}</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-label">Positions</span>
          <span class="hero-value positions-val">{{ formatCurrency(status()?.positions_value ?? 0) }}</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-label">P&L ({{ pnlPctStr() }})</span>
          <span class="hero-value" [class.pos]="(status()?.pnl ?? 0) >= 0" [class.neg]="(status()?.pnl ?? 0) < 0">
            {{ (status()?.pnl ?? 0) >= 0 ? '+' : '' }}{{ formatCurrency(status()?.pnl ?? 0) }}
          </span>
          <span class="hero-pnl-fees">
            <span class="pnl-detail fee-detail">Fees: -{{ formatCurrency(totalFeesPaid()) }}</span>
            <span class="pnl-detail" [class.pos]="priceChange() >= 0" [class.neg]="priceChange() < 0">
              Price: {{ priceChange() >= 0 ? '+' : '' }}{{ formatCurrency(priceChange()) }}
            </span>
          </span>
        </div>
      </div>

      <!-- Status banner -->
      <div class="status-banner">
        <span class="status-dot" [class.running]="status()?.enabled"></span>
        <span class="status-text">{{ statusSummary() }}</span>
        <span class="regime-info">
          <span class="regime-badge" [class.bullish]="status()?.regime_bullish" [class.bearish]="!status()?.regime_bullish">
            {{ status()?.regime_bullish ? 'BULL' : 'BEAR' }}
          </span>
          @if ((status()?.exit_cooldown_remaining ?? 0) > 0) {
            <span class="cooldown-badge">Cooldown {{ cooldownDisplay() }}</span>
            <button class="skip-cooldown-btn" (click)="skipCooldown()" [disabled]="skippingCooldown()" title="Skip cooldown and allow immediate re-entry">{{ skippingCooldown() ? 'Skipping...' : 'Skip' }}</button>
          }
          @if ((status()?.hours_in_position ?? 0) > 0) {
            <span class="hold-time">In position {{ status()!.hours_in_position }}h</span>
          }
        </span>
        <span class="poll-timer">next check in {{ pollCountdown() }}s</span>
      </div>

      <!-- Warmup progress bar -->
      @if (warmupProgress().step === 'warmup' || warmupProgress().step === 'scanning') {
        <div class="warmup-progress">
          <div class="wp-header">
            <span class="wp-step">{{ warmupProgress().step === 'scanning' ? 'Scanning coins...' : 'Loading price history...' }}</span>
            <span class="wp-detail">
              {{ warmupProgress().pair ?? '' }}
              {{ warmupProgress().done ?? 0 }}/{{ warmupProgress().total ?? 0 }}
            </span>
            @if (warmupProgress().estimated_remaining) {
              <span class="wp-eta">~{{ formatEta(warmupProgress().estimated_remaining!) }} left</span>
            }
          </div>
          <div class="wp-bar-track">
            <div class="wp-bar-fill" [style.width.%]="warmupProgress().pct ?? 0"></div>
          </div>
        </div>
      }

      <!-- Equity chart + Activity log -->
      <div class="equity-activity-row">
        <div class="equity-col">
          <div class="chart-header">
            <span class="section-header" style="margin-bottom:0">Portfolio Equity</span>
            <div class="chart-range-btns">
              @for (r of chartRanges; track r.hours) {
                <button class="range-btn" [class.active]="chartHours() === r.hours" (click)="setChartRange(r.hours)">{{ r.label }}</button>
              }
            </div>
            <button class="range-btn reset-zoom-btn" (click)="resetChartZoom()" title="Reset zoom">↺</button>
          </div>
          <div class="chart-slot">
            <canvas #momEquityCanvas></canvas>
          </div>
          <div class="equity-substats">
            <span><span class="sub-label">Trades </span>{{ status()?.trade_count ?? 0 }}</span>
            <span class="sub-label zoom-hint">Scroll to zoom · Drag to pan</span>
          </div>
        </div>
        <div class="activity-col">
          <div class="section-header activity-toggle" (click)="activityOpen.set(!activityOpen())">
            What's Happening
            <span class="toggle-count">{{ events().length }}</span>
            <span class="toggle-arrow" [class.open]="activityOpen()">▾</span>
          </div>
          @if (activityOpen()) {
            <div class="event-list">
              @for (evt of events(); track evt.timestamp) {
                <div class="log-entry">
                  <span class="log-time">{{ shortTime(evt.timestamp) }}</span>
                  <span class="log-dot" [class.buy]="evt.event_type === 'momentum_buy'"
                        [class.sell]="evt.event_type === 'momentum_sell'"
                        [class.info]="evt.event_type !== 'momentum_buy' && evt.event_type !== 'momentum_sell'"></span>
                  <span class="log-msg">{{ evt.title }}</span>
                </div>
              }
              @if (events().length === 0) {
                <div class="no-data">No events yet</div>
              }
            </div>
          }
        </div>
      </div>

      <!-- Acceleration Scanner -->
      <div class="accel-section">
        <div class="section-header">
          ACCELERATION SCANNER
          @if (status()?.scanner) {
            <span class="scanner-meta">{{ status()!.scanner!.pairs_count }} scanned &middot; top {{ topAccelScores().length }} accelerating</span>
          }
        </div>
        <div class="accel-cards">
          @for (s of topAccelScores(); track s.pair) {
            <div class="accel-card" [class.qualifying-card]="s.accel > 0.20" [class.quality-blocked]="s.accel > 0.20 && s.quality && !s.quality.pass">
              <div class="ac-top">
                <span class="ac-coin">{{ s.pair.replace('-USD', '') }}</span>
                @if (s.accel > 0.20 && s.quality) {
                  <span class="ac-badge" [class.qual]="s.quality.pass" [class.blocked]="!s.quality.pass">
                    {{ s.quality.pass ? 'READY' : 'BLOCKED' }}
                  </span>
                } @else {
                  <span class="ac-badge" [class.qual]="s.accel > 0.20" [class.below]="s.accel <= 0.20">
                    {{ s.accel > 0.20 ? 'READY' : 'BELOW 20%' }}
                  </span>
                }
                <span class="ac-price">{{ formatPrice(s.price) }}</span>
              </div>
              <div class="ac-desc">
                @if (s.accel > 0.20 && s.quality && !s.quality.pass) {
                  Entry blocked by quality gate — poor short-term action.
                } @else if (s.accel > 0.20) {
                  Uptrend accelerating — qualifies for entry.
                } @else {
                  Momentum building but below the 20% re-entry threshold.
                }
              </div>
              @if (s.quality && s.accel > 0.20) {
                <div class="ac-gates">
                  <span class="ac-gate" [class.pass]="s.quality.green" [class.fail]="!s.quality.green"
                        [title]="s.quality.greenCount + '/6 green candles'">
                    {{ s.quality.green ? '\u2713' : '\u2717' }} {{ s.quality.greenCount }}/6 green
                  </span>
                  <span class="ac-gate" [class.pass]="s.quality.body" [class.fail]="!s.quality.body"
                        [title]="'Body ratio: ' + s.quality.bodyRatio">
                    {{ s.quality.body ? '\u2713' : '\u2717' }} body {{ s.quality.bodyRatio }}
                  </span>
                  <span class="ac-gate" [class.pass]="s.quality.ext" [class.fail]="!s.quality.ext"
                        [title]="'3h move: ' + s.quality.chg3hAtr + 'x ATR'">
                    {{ s.quality.ext ? '\u2713' : '\u2717' }} {{ s.quality.chg3hAtr }}x ATR
                  </span>
                </div>
              }
              <div class="ac-bar-track">
                <div class="ac-bar-fill" [class.qualifying]="s.accel > 0.20 && (!s.quality || s.quality.pass)"
                     [class.blocked-fill]="s.accel > 0.20 && s.quality && !s.quality.pass"
                     [style.width.%]="accelBarWidth(s.accel)"></div>
              </div>
              <div class="ac-stats">
                <span class="ac-accel" [class.pos]="s.accel > 0.20">+{{ (s.accel * 100).toFixed(1) }}%</span>
                <span class="ac-stat-label">acceleration</span>
              </div>
            </div>
          }
        </div>
        @if (topAccelScores().length === 0) {
          <div class="accel-empty">No acceleration data yet — engine is warming up</div>
        }
        @if (topAccelScores().length > 0 && !hasQualifyingAccel()) {
          <div class="accel-note">No coins above 20% — staying in cash until a strong uptrend confirms.</div>
        }
        @if (hasQualifyingAccel()) {
          <div class="accel-note qualifying-note">
            {{ qualifyingCount() }} coin{{ qualifyingCount() > 1 ? 's' : '' }} ready —
            engine picks the top 1 that passes quality gates.
          </div>
        }
      </div>

      <!-- Holdings + Strategy side-by-side row -->
      <div class="hold-strat-row">
        <!-- Holdings column -->
        <div class="hold-col">
          @if (isHolding()) {
            <div class="section-label">Holdings</div>
            @for (h of status()?.holdings ?? []; track h.pair) {
              <div class="compact-holding">
                <div class="ch-top">
                  <span class="ch-coin">{{ h.pair.replace('-USD', '') }}</span>
                  @if (h.trail_layer) {
                    <span class="ch-layer" [class.inactive]="h.trail_layer === 'inactive'"
                          [class.wide]="h.trail_layer === 'wide'" [class.tight]="h.trail_layer === 'tight'"
                          [class.stale]="h.trail_layer === 'stale'">
                      {{ trailLayerLabel(h.trail_layer) }}
                    </span>
                  }
                  <div class="ch-pnl-group">
                    <span class="ch-pnl-val">{{ formatCurrency(h.value) }}</span>
                    <span class="ch-pnl-pct" [class.pos]="h.pnl >= 0" [class.neg]="h.pnl < 0">
                      {{ h.pnl >= 0 ? '+' : '' }}{{ formatCurrency(h.pnl) }} ({{ h.pnl_pct.toFixed(1) }}%)
                    </span>
                  </div>
                  <button class="ch-sell"
                          [class.selling]="sellingPair() === h.pair"
                          [disabled]="sellingPair() !== null"
                          (click)="manualSell(h.pair)">
                    {{ sellingPair() === h.pair ? 'Selling...' : 'Sell' }}
                  </button>
                </div>
                <div class="ch-stats">
                  <div class="ch-stat tt-wrap">
                    <span class="ch-stat-lbl">Entry</span>
                    <span class="ch-stat-val dim">{{ formatPrice(h.entry_price) }}</span>
                    <span class="tt">Entry price when position was opened</span>
                  </div>
                  <div class="ch-stat tt-wrap">
                    <span class="ch-stat-lbl">Now</span>
                    <span class="ch-stat-val">{{ formatPrice(h.current_price) }}</span>
                    <span class="tt">Current market price (updated every ~60s)</span>
                  </div>
                  <div class="ch-stat tt-wrap">
                    <span class="ch-stat-lbl">Stop</span>
                    <span class="ch-stat-val red">{{ h.stop_price > 0 ? formatPrice(h.stop_price) : '—' }}</span>
                    <span class="tt">Trailing stop price — position sells if price drops to this level. Trail tightens as profit grows.</span>
                  </div>
                  <div class="ch-stat tt-wrap">
                    <span class="ch-stat-lbl">Dist</span>
                    <span class="ch-stat-val dim">{{ h.stop_distance_pct > 0 ? h.stop_distance_pct.toFixed(1) + '%' : '—' }}</span>
                    <span class="tt">How far current price is from the stop — lower = closer to selling</span>
                  </div>
                  <div class="ch-stat tt-wrap">
                    <span class="ch-stat-lbl">Hold</span>
                    <span class="ch-stat-val dim">{{ status()?.hours_in_position ?? 0 }}h/72h</span>
                    <span class="tt">Time held vs 72h max hold limit. Position auto-exits at 72h regardless of profit.</span>
                  </div>
                  <div class="ch-stat tt-wrap">
                    <span class="ch-stat-lbl">Accel</span>
                    <span class="ch-stat-val purple">{{ (h.accel * 100).toFixed(1) }}%</span>
                    <span class="tt">Momentum acceleration — how fast the uptrend is accelerating. Exits if this fades below 5% after 4h.</span>
                  </div>
                </div>
              </div>
            }
          }

          <!-- Sell notification banner -->
          @if (sellNotification()) {
            <div class="sell-notification" [class.success]="sellNotification()!.type === 'success'" [class.error]="sellNotification()!.type === 'error'">
              {{ sellNotification()!.message }}
            </div>
          }
        </div>

        <!-- Strategy column -->
        @if (status()?.warmup_done) {
          <div class="strat-col">
            <div class="section-label">Strategy</div>
            <div class="compact-strategy">
              <div class="cs-chip tt-wrap">
                <span class="cs-label">Regime</span>
                <span class="cs-value" [class.pos]="status()?.regime_bullish" [class.neg]="!status()?.regime_bullish">
                  {{ status()?.regime_bullish ? 'Bull' : 'Bear' }}
                </span>
                <span class="cs-detail">BTC {{ btcVsSmaShort() }}</span>
                <span class="tt">{{ regimeExplain() }}</span>
              </div>
              <div class="cs-chip tt-wrap">
                <span class="cs-label">Rebalance</span>
                <span class="cs-value">{{ formatHours(status()?.next_rebal_hours ?? 0) }}</span>
                <span class="tt">Weekly rotation — engine compares your holding to the top acceleration coin and swaps if a better one is found</span>
              </div>
              <div class="cs-chip tt-wrap">
                <span class="cs-label">Position</span>
                <span class="cs-value">{{ positionExplainShort() }}</span>
                <span class="tt">{{ positionDetail() }}</span>
              </div>
            </div>

            @if (isHolding()) {
              <div class="section-label">Would Sell If</div>
              <div class="compact-exits">
                @for (cond of exitConditions(); track cond.label) {
                  <div class="ce-tag tt-wrap" [class.ce-amber]="cond.color === 'amber'" [class.ce-red]="cond.color === 'red'" [class.ce-purple]="cond.color === 'purple'" [class.ce-blue]="cond.color === 'blue'">
                    <span class="ce-label">{{ cond.shortLabel }}</span>
                    @if (cond.pct >= 0) {
                      <div class="ce-bar"><div class="ce-fill" [class.low]="cond.pct < 50" [class.mid]="cond.pct >= 50 && cond.pct < 80" [class.high]="cond.pct >= 80" [style.width.%]="cond.pct"></div></div>
                    }
                    <span class="ce-val" [class.dim]="cond.pct < 50" [class.warn]="cond.pct >= 50 && cond.pct < 80" [class.danger]="cond.pct >= 80" [class.safe]="cond.pct < 0">{{ cond.shortDetail }}</span>
                    <span class="tt">{{ cond.tooltip }}</span>
                  </div>
                }
              </div>
            }

            <div class="section-label">Would Buy If</div>
            <div class="compact-buy">
              @for (cond of buyConditionTags(); track cond.text) {
                <div class="cb-tag tt-wrap">
                  <span class="cb-text" [class.green]="cond.met" [class.red]="cond.met === false">{{ cond.met ? '✓' : cond.met === false ? '✗' : '•' }} {{ cond.text }}</span>
                  <span class="tt">{{ cond.tooltip }}</span>
                </div>
              }
            </div>

            @if (entryRejections().length > 0) {
              <div class="section-label">Why Not Buying</div>
              <div class="compact-rejections">
                @for (r of entryRejections(); track r) {
                  <span class="cr-tag">{{ r }}</span>
                }
              </div>
            }
          </div>
        }
      </div>

      <!-- Recent trades table -->
      <div class="trades-section">
        <div class="section-header">Recent Trades</div>
        <div class="table-scroll">
        <table class="trades-table">
          <thead>
            <tr>
              <th class="left">Date</th>
              <th class="left">Pair</th>
              <th class="right">Price</th>
              <th class="right">Spent / Received</th>
              <th class="right">Result</th>
              <th class="left hide-sm">Reason</th>
            </tr>
          </thead>
          <tbody>
            @if (trades().length === 0) {
              <tr><td colspan="6" class="empty-row">No trades yet</td></tr>
            }
            @for (t of trades(); track t.timestamp; let odd = $odd) {
              <tr [class.buy-row]="t.side === 'buy'" [class.sell-row]="t.side === 'sell'" [class.odd]="odd">
                <td class="left mono time-cell">{{ shortDate(t.timestamp) }}</td>
                <td class="left">
                  <span class="pair-name">{{ shortPair(t.pair) }}</span>
                  <span class="side-tag" [class.buy]="t.side === 'buy'" [class.sell]="t.side === 'sell'">
                    {{ t.side === 'buy' ? 'BUY' : 'SELL' }}
                  </span>
                </td>
                <td class="right mono">
                  @if (t.side === 'sell' && t.entry_price) {
                    <span>{{ formatPrice(t.entry_price) }}</span>
                    <span class="trade-arrow">→</span>
                    <span>{{ formatPrice(t.price) }}</span>
                  } @else {
                    <span>{{ formatPrice(t.price) }}</span>
                  }
                </td>
                <td class="right mono">
                  @if (t.side === 'buy') {
                    <span style="color: #f87171">-{{ formatCurrency(t.cost_usd) }}</span>
                  } @else {
                    <span style="color: #4ade80">+{{ formatCurrency(t.cost_usd) }}</span>
                  }
                </td>
                <td class="right mono">
                  @if (t.side === 'sell' && t.net_pnl != null) {
                    <span [style.color]="t.net_pnl >= 0 ? '#4ade80' : '#f87171'" style="font-weight: 600">
                      {{ t.net_pnl >= 0 ? 'WIN' : 'LOSS' }} {{ t.net_pnl >= 0 ? '+' : '' }}{{ formatCurrency(t.net_pnl) }}
                    </span>
                    <span class="result-breakdown">price {{ t.net_pnl + t.fee >= 0 ? '+' : '' }}{{ formatCurrency(t.net_pnl + t.fee) }} / fees -{{ formatCurrency(t.fee) }}</span>
                  } @else if (t.side === 'buy' && t.closed) {
                    <span class="status-badge closed">Closed</span>
                  } @else if (t.side === 'buy') {
                    <span class="status-badge holding">Open</span>
                  } @else {
                    —
                  }
                </td>
                <td class="left hide-sm reason-cell">{{ t.reason || '—' }}</td>
              </tr>
            }
          </tbody>
        </table>
        </div>
      </div>

    </div>
  `,
  styles: [`
    .mp-root {
      background: #0f1117;
      color: #e2e8f0;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      min-height: 100%;
      overflow-x: hidden;
    }

    /* Scrollbars inherited from global styles.css */

    /* Engine tab */
    .engine-tab {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 20px;
      background: linear-gradient(90deg, rgba(167,139,250,0.08) 0%, transparent 100%);
      border-bottom: 1px solid rgba(167,139,250,0.3);
    }
    .engine-dot {
      width: 8px; height: 8px; border-radius: 50%;
      animation: pulse 2s ease-in-out infinite;
    }
    .engine-dot.active { background: #4ade80; box-shadow: 0 0 6px rgba(74,222,128,0.4); }
    .engine-dot.idle { background: #fbbf24; box-shadow: 0 0 6px rgba(251,191,36,0.3); }
    .engine-dot.inactive { background: #64748b; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
    .engine-name {
      font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; color: #a78bfa;
    }
    .engine-tag {
      font-size: 9px; font-weight: 700; letter-spacing: 0.06em;
      padding: 2px 8px; border-radius: 4px; text-transform: uppercase;
    }
    .engine-tag.holding { background: rgba(74,222,128,0.12); color: #4ade80; }
    .engine-tag.idle { background: rgba(251,191,36,0.1); color: #fbbf24; }
    .engine-tag.inactive { background: rgba(100,116,139,0.12); color: #64748b; }
    .engine-alloc {
      margin-left: auto; font-size: 10px; color: #6b7280;
      font-family: 'JetBrains Mono', monospace;
    }
    .export-btn {
      margin-left: auto; padding: 3px 10px; font-size: 10px; font-weight: 600;
      background: rgba(59,130,246,0.1); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3);
      border-radius: 4px; cursor: pointer; transition: all 0.15s; text-decoration: none;
    }
    .export-btn:hover { background: rgba(59,130,246,0.2); border-color: #60a5fa; }
    .reset-btn {
      margin-left: 8px; padding: 3px 10px; font-size: 10px; font-weight: 600;
      background: rgba(239,68,68,0.1); color: #f87171; border: 1px solid rgba(239,68,68,0.3);
      border-radius: 4px; cursor: pointer; transition: all 0.15s;
    }
    .reset-btn:hover { background: rgba(239,68,68,0.2); border-color: #f87171; }

    /* Hero bar */
    .hero-bar {
      display: flex; align-items: center; justify-content: center;
      gap: 0; padding: 0.75rem 1rem;
      background: linear-gradient(180deg, #141621 0%, #0f1117 100%);
      border-bottom: 1px solid #2d3148;
    }
    .hero-item { display: flex; align-items: baseline; gap: 0.4em; padding: 0 1.1em; }
    .hero-value {
      font-size: 1.25rem; font-weight: 700; color: #f1f5f9;
      font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em;
    }
    .hero-value.cash-val { color: #94a3b8; }
    .hero-value.positions-val { color: #a78bfa; }
    .hero-value.pos { color: #4ade80; }
    .hero-value.neg { color: #f87171; }
    .hero-label { font-size: 0.65rem; font-weight: 500; color: #6b7280; white-space: nowrap; }
    .hero-pnl-fees { display: flex; gap: 0.6em; margin-left: 0.5em; }
    .pnl-detail {
      font-size: 0.55rem; font-weight: 600; color: #6b7280;
      font-family: 'JetBrains Mono', monospace;
    }
    .pnl-detail.fee-detail { color: #f59e0b; }
    .hero-divider { width: 1px; height: 1.5rem; background: #2d3148; }

    /* Status banner */
    .status-banner {
      display: flex; align-items: center; gap: 8px;
      padding: 12px 20px; background: linear-gradient(135deg, #1a1d2e 0%, #242840 100%);
      border-bottom: 1px solid #2d3148;
    }
    .status-dot {
      width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
    }
    .status-dot.running { background: #4ade80; box-shadow: 0 0 8px rgba(74,222,128,0.5); }
    .status-text { font-size: 12px; color: #9ca3af; }
    .regime-info { display: flex; align-items: center; gap: 6px; }
    .regime-badge {
      font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px;
      font-family: 'JetBrains Mono', monospace; letter-spacing: 0.05em;
    }
    .regime-badge.bullish { background: rgba(74,222,128,0.15); color: #4ade80; }
    .regime-badge.bearish { background: rgba(248,113,113,0.15); color: #f87171; }
    .cooldown-badge {
      font-size: 10px; padding: 2px 8px; border-radius: 4px;
      background: rgba(251,191,36,0.15); color: #fbbf24;
      font-family: 'JetBrains Mono', monospace;
    }
    .hold-time {
      font-size: 10px; color: #64748b;
      font-family: 'JetBrains Mono', monospace;
    }
    .skip-cooldown-btn {
      font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 3px;
      background: rgba(251,191,36,0.15); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3);
      cursor: pointer; transition: all 0.15s; letter-spacing: 0.03em;
    }
    .skip-cooldown-btn:hover { background: rgba(251,191,36,0.3); border-color: #fbbf24; }
    .poll-timer {
      margin-left: auto; font-family: 'JetBrains Mono', monospace;
      font-size: 10px; color: #4b5280; letter-spacing: 0.03em;
    }

    /* Warmup progress */
    .warmup-progress {
      padding: 10px 20px; background: #12141e; border-bottom: 1px solid #2d3148;
    }
    .wp-header {
      display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
    }
    .wp-step { font-size: 11px; font-weight: 600; color: #a78bfa; }
    .wp-detail {
      font-size: 10px; color: #6b7280;
      font-family: 'JetBrains Mono', monospace;
    }
    .wp-eta { margin-left: auto; font-size: 10px; color: #4b5280; font-family: 'JetBrains Mono', monospace; }
    .wp-bar-track {
      height: 6px; background: #1e2130; border-radius: 3px; overflow: hidden;
    }
    .wp-bar-fill {
      height: 100%; border-radius: 3px; transition: width 0.5s ease;
      background: linear-gradient(90deg, #7c3aed 0%, #a78bfa 100%);
    }

    /* Equity + activity row */
    .equity-activity-row {
      display: flex; gap: 0; border-bottom: 1px solid #2d3148;
    }
    .equity-col {
      flex: 3; padding: 14px 16px; border-right: 1px solid #2d3148; min-width: 0;
    }
    .activity-col { flex: 2; min-width: 0; max-height: 260px; overflow-y: auto; padding: 14px 16px; }
    .section-header {
      font-size: 12px; font-weight: 600; color: #e2e8f0;
      margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.06em;
    }
    .chart-header {
      display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;
    }
    .chart-range-btns { display: flex; gap: 2px; margin-left: auto; }
    .range-btn {
      font-size: 0.6rem; font-weight: 600; padding: 0.2em 0.5em; border-radius: 3px;
      background: transparent; color: #4b5280; border: 1px solid transparent;
      cursor: pointer; transition: all 0.15s;
      font-family: 'JetBrains Mono', monospace; letter-spacing: 0.03em;
    }
    .range-btn:hover { color: #a78bfa; background: rgba(167,139,250,0.08); }
    .range-btn.active {
      color: #a78bfa; background: rgba(167,139,250,0.12);
      border-color: rgba(167,139,250,0.3);
    }
    .reset-zoom-btn { font-size: 0.75rem; padding: 0.15em 0.4em; }
    .zoom-hint { margin-left: auto; font-style: italic; font-size: 0.55rem; }
    .chart-slot { position: relative; height: 180px; border-radius: 8px; overflow: hidden; }
    .chart-slot canvas { display: block; width: 100% !important; height: 100% !important; }
    .equity-substats { display: flex; gap: 14px; margin-top: 8px; font-size: 10px; }
    .sub-label { color: #6b7280; }
    .pos { color: #4ade80; }
    .neg { color: #f87171; }

    /* Activity toggle */
    .activity-toggle {
      cursor: pointer; user-select: none; display: flex; align-items: center; gap: 0.4rem;
    }
    .activity-toggle:hover { color: #a78bfa; }
    .toggle-count {
      font-size: 0.6rem; font-weight: 600; padding: 0.1em 0.4em; border-radius: 3px;
      background: rgba(167,139,250,0.12); color: #a78bfa;
      font-family: 'JetBrains Mono', monospace;
    }
    .toggle-arrow {
      font-size: 0.7rem; color: #4b5280; transition: transform 0.2s;
      margin-left: auto;
    }
    .toggle-arrow.open { transform: rotate(0deg); }
    .toggle-arrow:not(.open) { transform: rotate(-90deg); }

    /* Event log */
    .event-list { display: flex; flex-direction: column; }
    .log-entry {
      display: flex; align-items: center; gap: 8px; padding: 5px 0;
      font-size: 11px; border-bottom: 1px solid rgba(45,49,72,0.5);
    }
    .log-time { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #4b5280; min-width: 50px; }
    .log-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
    .log-dot.buy { background: #4ade80; }
    .log-dot.sell { background: #f87171; }
    .log-dot.info { background: #60a5fa; }
    .log-msg { color: #9ca3af; flex: 1; }
    .no-data { font-size: 11px; color: #4b5280; font-style: italic; }

    /* Acceleration Scanner */
    .accel-section {
      padding: 14px 20px; border-bottom: 1px solid #2d3148; background: #12141e;
    }
    .accel-section .section-header {
      display: flex; align-items: center; gap: 10px;
    }
    .scanner-meta {
      font-size: 9px; font-weight: 400; color: #4b5280; letter-spacing: 0;
      text-transform: none; margin-left: auto;
    }
    .accel-cards {
      display: flex; gap: 10px; overflow-x: auto; padding-bottom: 6px;
    }
    .accel-card {
      min-width: 190px; max-width: 220px; flex-shrink: 0;
      background: #1a1d29; border: 1px solid #2d3148; border-radius: 8px;
      padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;
    }
    .accel-card.qualifying-card {
      border-color: rgba(74,222,128,0.25);
      background: linear-gradient(180deg, rgba(74,222,128,0.04) 0%, #1a1d29 100%);
    }
    .ac-top {
      display: flex; align-items: center; gap: 8px;
    }
    .ac-coin { font-weight: 700; font-size: 15px; color: #f1f5f9; }
    .ac-badge {
      font-size: 8px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
      letter-spacing: 0.06em;
    }
    .ac-badge.qual { background: rgba(74,222,128,0.12); color: #4ade80; }
    .ac-badge.below { background: rgba(100,116,139,0.12); color: #64748b; }
    .ac-price {
      margin-left: auto; font-family: 'JetBrains Mono', monospace;
      font-size: 12px; font-weight: 600; color: #e2e8f0;
    }
    .ac-desc {
      font-size: 10px; color: #6b7280; line-height: 1.4;
    }
    .ac-bar-track {
      height: 4px; background: #1e2130; border-radius: 2px; overflow: hidden;
    }
    .ac-bar-fill {
      height: 100%; background: linear-gradient(90deg, #4b5280 0%, #6366f1 100%);
      border-radius: 2px; transition: width 0.5s ease;
    }
    .ac-bar-fill.qualifying {
      background: linear-gradient(90deg, #4ade80 0%, #22c55e 100%);
    }
    .ac-bar-fill.blocked-fill {
      background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
    }
    .accel-card.quality-blocked {
      border-color: rgba(239,68,68,0.25);
      background: linear-gradient(180deg, rgba(239,68,68,0.04) 0%, #1a1d29 100%);
    }
    .ac-badge.blocked { background: rgba(239,68,68,0.12); color: #ef4444; }
    .ac-gates {
      display: flex; gap: 6px; flex-wrap: wrap;
    }
    .ac-gate {
      font-size: 9px; font-family: 'JetBrains Mono', monospace;
      padding: 2px 5px; border-radius: 3px; white-space: nowrap;
    }
    .ac-gate.pass { background: rgba(74,222,128,0.08); color: #4ade80; }
    .ac-gate.fail { background: rgba(239,68,68,0.10); color: #ef4444; font-weight: 700; }
    .ac-stats { display: flex; align-items: baseline; gap: 6px; }
    .ac-accel {
      font-family: 'JetBrains Mono', monospace; font-size: 14px;
      font-weight: 700; color: #6b7280;
    }
    .ac-accel.pos { color: #4ade80; }
    .ac-stat-label { font-size: 9px; color: #4b5280; }
    .accel-empty { font-size: 11px; color: #4b5280; font-style: italic; padding: 8px 0; }
    .accel-note {
      font-size: 10px; color: #6b7280; margin-top: 8px; padding: 6px 0;
    }
    .accel-note.qualifying-note { color: #4ade80; }

    /* Holdings + Strategy side-by-side */
    .hold-strat-row {
      display: flex; gap: 0; border-bottom: 1px solid #2d3148;
    }
    .hold-col {
      flex: 1; padding: 0.65rem 1rem; border-right: 1px solid #2d3148; min-width: 0;
    }
    .strat-col {
      flex: 1; padding: 0.65rem 1rem; min-width: 0;
      background: linear-gradient(180deg, #12141e 0%, #0f1117 100%);
    }
    @media (max-width: 900px) {
      .hold-strat-row { flex-direction: column; }
      .hold-col { border-right: none; border-bottom: 1px solid #2d3148; }
    }

    /* Holdings (compact) */
    .compact-holding {
      background: #1a1d29; border: 1px solid #2d3148;
      border-radius: 0.5rem; border-left: 3px solid #a78bfa; padding: 0.6rem 0.85rem;
    }
    .ch-top {
      display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem;
    }
    .ch-coin { font-weight: 700; font-size: 1.1rem; white-space: nowrap; }
    .ch-layer {
      font-size: 0.65rem; font-weight: 700; padding: 0.2em 0.5em; border-radius: 3px;
      letter-spacing: 0.04em; white-space: nowrap;
    }
    .ch-layer.inactive { background: rgba(100,116,139,0.12); color: #64748b; }
    .ch-layer.wide { background: rgba(96,165,250,0.12); color: #60a5fa; }
    .ch-layer.tight { background: rgba(251,191,36,0.12); color: #fbbf24; }
    .ch-layer.stale { background: rgba(248,113,113,0.15); color: #f87171; }
    .ch-stats { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
    .ch-stat { display: flex; flex-direction: column; align-items: center; }
    .ch-stat-lbl { font-size: 0.6rem; color: #4b5280; text-transform: uppercase; letter-spacing: 0.05em; line-height: 1; }
    .ch-stat-val { font-size: 0.8rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; line-height: 1.3; }
    .ch-stat-val.red { color: #f87171; }
    .ch-stat-val.green { color: #4ade80; }
    .ch-stat-val.dim { color: #6b7280; }
    .ch-stat-val.purple { color: #a78bfa; }
    .ch-pnl-group { margin-left: auto; text-align: right; white-space: nowrap; }
    .ch-pnl-val { font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 700; }
    .ch-pnl-pct { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 600; margin-left: 0.25em; }
    .ch-pnl-pct.neg { color: #f87171; }
    .ch-pnl-pct.pos { color: #4ade80; }
    .ch-sell {
      padding: 0.3em 0.8em; border: 1px solid #f87171; border-radius: 4px;
      background: rgba(248,113,113,0.08); color: #f87171; font-size: 0.7rem;
      font-weight: 700; cursor: pointer; white-space: nowrap; transition: all 0.15s;
    }
    .ch-sell:hover:not(:disabled) { background: #f87171; color: #0f1117; }
    .ch-sell:disabled { opacity: 0.5; cursor: not-allowed; }
    .ch-sell.selling {
      background: rgba(251,191,36,0.15); border-color: #fbbf24; color: #fbbf24;
      animation: pulse 1s ease-in-out infinite;
    }

    /* Sell notification banner */
    .sell-notification {
      padding: 10px 20px; font-size: 12px; font-weight: 600;
      display: flex; align-items: center; gap: 8px;
      animation: slideDown 0.2s ease-out;
    }
    .sell-notification.pending {
      background: rgba(251,191,36,0.1); color: #fbbf24;
      border-bottom: 1px solid rgba(251,191,36,0.2);
    }
    .sell-notification.success {
      background: rgba(74,222,128,0.1); color: #4ade80;
      border-bottom: 1px solid rgba(74,222,128,0.2);
    }
    .sell-notification.error {
      background: rgba(248,113,113,0.1); color: #f87171;
      border-bottom: 1px solid rgba(248,113,113,0.2);
    }
    @keyframes slideDown {
      from { opacity: 0; transform: translateY(-8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Cash state */
    .cash-state {
      display: flex; flex-direction: column; align-items: center; padding: 32px 16px; gap: 8px;
    }
    .cash-icon {
      width: 40px; height: 40px; border-radius: 50%;
      background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.2);
      display: flex; align-items: center; justify-content: center; font-size: 18px;
    }
    .cash-title { font-weight: 700; font-size: 13px; color: #fbbf24; }
    .cash-amount {
      font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; color: #f1f5f9;
    }
    .cash-reason { font-size: 11px; color: #6b7280; text-align: center; max-width: 280px; line-height: 1.5; }

    /* Trades table */
    .trades-section { padding: 14px 20px; }
    .table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .trades-table { width: 100%; border-collapse: collapse; font-size: 12px; min-width: 600px; }
    .trades-table th {
      padding: 8px 12px; font-size: 10px; font-weight: 700; color: #6b7280;
      text-transform: uppercase; letter-spacing: 0.06em; border-bottom: 1px solid #2d3148;
      white-space: nowrap;
    }
    .trades-table td { padding: 8px 12px; border-bottom: 1px solid rgba(45,49,72,0.5); white-space: nowrap; color: #e2e8f0; }
    .left { text-align: left; }
    .right { text-align: right; }
    .mono { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 11px; }
    .time-cell { color: #9ca3af; font-size: 11px; }
    .pair-name { font-weight: 700; color: #e2e8f0; margin-right: 6px; }
    .side-tag {
      display: inline-block; font-size: 9px; font-weight: 800; padding: 1px 5px;
      border-radius: 3px; letter-spacing: 0.04em; vertical-align: middle;
    }
    .side-tag.buy { background: rgba(34,197,94,0.2); color: #4ade80; }
    .side-tag.sell { background: rgba(239,68,68,0.2); color: #f87171; }
    .amount-main { display: block; }
    .amount-fee { display: block; font-size: 10px; color: #6b7280; }
    .trade-arrow { color: #6b7280; margin: 0 2px; }
    .result-breakdown { display: block; font-size: 10px; color: #6b7280; font-weight: 400; }
    .status-badge {
      font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 4px;
    }
    .status-badge.holding { background: rgba(250,204,21,0.1); color: #fbbf24; }
    .status-badge.closed { background: rgba(34,197,94,0.1); color: #4ade80; }
    .reason-cell { color: #6b7280; max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
    .empty-row { text-align: center; padding: 24px 12px; color: #6b7280; font-style: italic; }
    tr.buy-row { background: rgba(34,197,94,0.03); }
    tr.buy-row.odd { background: rgba(34,197,94,0.06); }
    tr.sell-row { background: rgba(239,68,68,0.03); }
    tr.sell-row.odd { background: rgba(239,68,68,0.06); }
    .trades-table tr:hover { background: rgba(255,255,255,0.04) !important; }
    .trades-table tr { transition: background 0.1s; }
    /* Medium screens — stack side-by-side panels */
    @media (max-width: 1024px) {
      .equity-activity-row { flex-direction: column; }
      .equity-col { border-right: none; border-bottom: 1px solid #2d3148; }
      .activity-col { max-height: 200px; }
    }

    /* Small screens — full mobile layout */
    @media (max-width: 768px) {
      .hide-sm { display: none; }

      /* Engine tab — keep inline */
      .engine-tab { flex-wrap: wrap; padding: 0.4rem 0.75rem; gap: 0.3rem; }
      .engine-alloc { font-size: 0.6rem; }
      .export-btn, .reset-btn { font-size: 0.55rem; padding: 0.1rem 0.4rem; margin-left: 0; }

      /* Hero bar — 2x2 grid on mobile */
      .hero-bar {
        display: grid; grid-template-columns: 1fr 1fr;
        gap: 0.25rem 0; padding: 0.5rem 0.75rem;
      }
      .hero-item { justify-content: center; padding: 0.2rem 0; gap: 0.3em; }
      .hero-divider { display: none; }
      .hero-value { font-size: 0.9rem; }
      .hero-label { font-size: 0.55rem; }
      .hero-pnl-fees { display: none; }

      /* Status banner — compact inline */
      .status-banner { flex-wrap: wrap; padding: 0.4rem 0.75rem; gap: 0.3rem 0.5rem; }
      .status-text { font-size: 0.65rem; }
      .poll-timer { margin-left: auto; font-size: 0.6rem; }

      /* Accel cards — smaller */
      .accel-cards { gap: 0.5rem; }
      .accel-card { min-width: 140px; max-width: 170px; padding: 0.5rem 0.6rem; }
      .ac-coin { font-size: 0.8rem; }
      .ac-price { font-size: 0.65rem; }
      .ac-desc { font-size: 0.55rem; }
      .ac-accel { font-size: 0.75rem; }

      /* Holdings — stack stats into grid */
      .ch-top { flex-wrap: wrap; }
      .ch-stats { gap: 0.5rem; }
      .ch-pnl-group { margin-left: 0; }

      /* Trades — tighter padding */
      .trades-section { padding: 0.6rem 0.75rem; }
      .trades-table { font-size: 0.7rem; }
      .trades-table th, .trades-table td { padding: 0.4rem 0.5rem; }
    }

    /* Extra small — phone portrait */
    @media (max-width: 480px) {
      .hero-value { font-size: 0.8rem; }
      .hero-label { font-size: 0.5rem; }
      .compact-holding { padding: 0.4rem 0.5rem; }
      .ch-coin { font-size: 0.9rem; }
      .ch-stat-val { font-size: 0.65rem; }
      .cs-chip { padding: 0.25em 0.5em; }
      .cs-value { font-size: 0.7rem; }
      .ce-tag { padding: 0.25em 0.4em; }
      .accel-card { min-width: 120px; }
    }
    .side-badge.buy { background: rgba(74,222,128,0.12); color: #4ade80; }
    .side-badge.sell { background: rgba(248,113,113,0.12); color: #f87171; }

    /* Strategy Logic panel (compact) — layout handled by .strat-col */
    .section-label {
      font-size: 0.7rem; font-weight: 700; color: #4b5280; text-transform: uppercase;
      letter-spacing: 0.06em; margin-bottom: 0.4rem; margin-top: 0.65rem;
    }
    .section-label:first-child { margin-top: 0; }

    /* Tooltip */
    .tt-wrap { position: relative; cursor: help; }
    .tt {
      display: none; position: absolute; bottom: calc(100% + 0.5rem); left: 50%;
      transform: translateX(-50%); z-index: 100;
      background: #1e2130; border: 1px solid #3d4168; border-radius: 0.4rem;
      padding: 0.5rem 0.75rem; font-size: 0.8rem; color: #c8cdd8; line-height: 1.5;
      white-space: normal; width: max-content; max-width: 20rem;
      box-shadow: 0 4px 16px rgba(0,0,0,0.5); pointer-events: none;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; font-weight: 400;
    }
    .tt::after {
      content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
      border: 5px solid transparent; border-top-color: #3d4168;
    }
    .tt-wrap:hover .tt { display: block; }

    /* Strategy chips */
    .compact-strategy { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .cs-chip {
      display: flex; align-items: center; gap: 0.4em;
      padding: 0.35em 0.65em; background: #1a1d29; border: 1px solid #2d3148;
      border-radius: 0.4rem; white-space: nowrap;
    }
    .cs-label { font-size: 0.65rem; font-weight: 700; color: #4b5280; text-transform: uppercase; letter-spacing: 0.05em; }
    .cs-value { font-size: 0.8rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; color: #e2e8f0; }
    .cs-detail { font-size: 0.7rem; color: #6b7280; font-family: 'JetBrains Mono', monospace; }

    /* Exit condition tags — color coded */
    .compact-exits { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
    .ce-tag {
      display: flex; align-items: center; gap: 0.4em;
      padding: 0.35em 0.6em; border-radius: 5px; background: #12141e;
      border: 1px solid #2d3148;
    }
    .ce-tag.ce-amber { border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.06); }
    .ce-tag.ce-amber .ce-label { color: #f59e0b; }
    .ce-tag.ce-red { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.06); }
    .ce-tag.ce-red .ce-label { color: #f87171; }
    .ce-tag.ce-purple { border-color: rgba(168,85,247,0.3); background: rgba(168,85,247,0.06); }
    .ce-tag.ce-purple .ce-label { color: #a855f7; }
    .ce-tag.ce-blue { border-color: rgba(59,130,246,0.3); background: rgba(59,130,246,0.06); }
    .ce-tag.ce-blue .ce-label { color: #3b82f6; }
    .ce-label { font-size: 0.7rem; font-weight: 600; color: #6b7280; white-space: nowrap; }
    .ce-bar { width: 1.75rem; height: 0.25rem; background: #1e2130; border-radius: 2px; overflow: hidden; }
    .ce-fill { height: 100%; border-radius: 2px; }
    .ce-fill.low { background: #4b5280; }
    .ce-fill.mid { background: #fbbf24; }
    .ce-fill.high { background: #f87171; }
    .ce-val { font-size: 0.7rem; font-family: 'JetBrains Mono', monospace; white-space: nowrap; }
    .ce-val.dim { color: #6b7280; }
    .ce-val.warn { color: #fbbf24; }
    .ce-val.danger { color: #f87171; }
    .ce-val.safe { color: #4ade80; }

    /* Buy condition tags */
    .compact-buy { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
    .cb-tag {
      display: flex; align-items: center; gap: 0.3em;
      padding: 0.35em 0.6em; border-radius: 5px; border: 1px solid #2d3148; background: #12141e;
      font-size: 0.75rem;
    }
    .cb-text { color: #9ca3af; white-space: nowrap; }
    .cb-text.green { color: #4ade80; }
    .cb-text.red { color: #f87171; }

    /* Rejection tags */
    .compact-rejections { display: flex; gap: 0.4rem; flex-wrap: wrap; }
    .cr-tag {
      font-size: 0.75rem; padding: 0.25em 0.6em; border-radius: 4px;
      background: rgba(251,191,36,0.08); border: 1px solid rgba(251,191,36,0.15);
      color: #fbbf24; font-family: 'JetBrains Mono', monospace;
    }
  `],
})
export class MomentumPanelComponent implements OnInit, AfterViewInit {
  private api = inject(ApiService);

  status = this.api.momentumStatus;
  trades = signal<MomentumTradeData[]>([]);
  events = signal<MomentumEventData[]>([]);
  equityData = signal<MomentumEquityData[]>([]);
  accelScores = signal<{ pair: string; accel: number; price: number; quality?: {
    green: boolean; greenCount: number;
    body: boolean; bodyRatio: number;
    ext: boolean; chg3hAtr: number;
    pass: boolean;
  } }[]>([]);
  warmupProgress = signal<{ step: string; pair?: string; done?: number; total?: number; pct?: number; estimated_remaining?: number }>({ step: 'unknown', pct: 0 });
  activityOpen = signal(window.innerWidth > 768);
  chartHours = signal(72);
  chartRanges = [
    { label: '24h', hours: 24 },
    { label: '3d', hours: 72 },
    { label: '7d', hours: 168 },
    { label: '30d', hours: 720 },
    { label: 'All', hours: 8760 },
  ];
  skippingCooldown = signal(false);
  sellingPair = signal<string | null>(null);
  sellNotification = signal<{ type: string; message: string } | null>(null);
  private progressInterval: any;
  private _pollCountdown = signal(60);
  private _countdownInterval: any;

  @ViewChild('momEquityCanvas') canvasRef!: ElementRef<HTMLCanvasElement>;
  private chart?: Chart;

  pollCountdown(): number { return this._pollCountdown(); }

  isHolding() {
    const s = this.status();
    return s && s.holdings && s.holdings.length > 0;
  }

  isRunning() {
    const s = this.status();
    return s?.status === 'holding' || s?.status === 'cash';
  }

  engineTagText() {
    if (this.isHolding()) return 'ACTIVE';
    if (this.isRunning()) return 'IDLE';
    return 'INACTIVE';
  }

  isHeldPair(pair: string) {
    return this.status()?.holdings?.some(h => h.pair === pair) ?? false;
  }

  topAccelScores() {
    return this.accelScores();
  }

  accelBarWidth(accel: number): number {
    // Log scale so outliers like NOM +139% don't crush everything else
    // 7% = ~50% width, 20%+ = ~85%, 100%+ = ~100%
    const pct = accel * 100;
    if (pct <= 0) return 0;
    return Math.min(100, (Math.log10(pct + 1) / Math.log10(150)) * 100);
  }

  hasQualifyingAccel(): boolean {
    return this.accelScores().some(s => s.accel > 0.20);
  }

  qualifyingCount(): number {
    return this.accelScores().filter(s => s.accel > 0.20).length;
  }

  formatEta(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const min = Math.floor(seconds / 60);
    const sec = seconds % 60;
    return sec > 0 ? `${min}m ${sec}s` : `${min}m`;
  }

  pnlPctStr() {
    const pct = this.status()?.pnl_pct ?? 0;
    return (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
  }

  statusSummary() {
    const s = this.status();
    if (!s || !s.enabled) return 'Momentum engine not active';
    if (s.status === 'warming_up') return 'Warming up — building price history...';
    if (s.status === 'scanning') return `Scanner ready — ${s.scanner?.pairs_count ?? 0} coins found. Bot will trade automatically when started.`;
    if (s.status === 'cash') return `In cash — watching for >10% acceleration signals (${s.trade_count} trades total)`;
    if (s.holdings?.length) {
      const held = s.holdings.map(h => h.pair.replace('-USD', '')).join(', ');
      return `Holding ${held} — ${s.trade_count} trades total`;
    }
    return `${s.status} — ${s.trade_count} trades`;
  }

  ngOnInit() {
    // Restore pending sell state from sessionStorage (survives page refresh)
    const pendingSell = sessionStorage.getItem('momentum_selling_pair');
    if (pendingSell) {
      this.sellingPair.set(pendingSell);
      this.sellNotification.set({ type: 'pending', message: `Selling ${pendingSell.replace('-USD', '')}... waiting for engine to execute` });
      this._resumeSellPoll(pendingSell);
    }

    forkJoin({
      trades: this.api.fetchMomentumTrades(20),
      events: this.api.fetchMomentumEvents(20),
      equity: this.api.fetchMomentumEquity(this.chartHours()),
      accel: this.api.fetchMomentumAccel(),
    }).subscribe({
      next: ({ trades, events, equity, accel }) => {
        this.trades.set(trades);
        this.events.set(events);
        this.equityData.set(equity);
        this.accelScores.set(accel);
      },
      error: () => {},
    });

    // Poll warmup progress every 3s while warming up
    this.pollProgress();
    this.progressInterval = setInterval(() => this.pollProgress(), 3000);

    // Countdown timer — ticks every second, reloads all data on each cycle
    this._pollCountdown.set(60);
    this._countdownInterval = setInterval(() => {
      const v = this._pollCountdown();
      if (v <= 1) {
        this._pollCountdown.set(60);
        this._refreshAllData();
      } else {
        this._pollCountdown.set(v - 1);
      }
    }, 1000);
  }

  /** Reload trades, events, equity, and accel on each poll cycle */
  private _refreshAllData(): void {
    this.api.fetchMomentumTrades(20).subscribe(t => this.trades.set(t));
    this.api.fetchMomentumEvents(20).subscribe(e => this.events.set(e));
    this.api.fetchMomentumAccel().subscribe(a => this.accelScores.set(a));
    this.api.fetchMomentumEquity(this.chartHours()).subscribe(eq => {
      this.equityData.set(eq);
      setTimeout(() => this.buildChart(), 300);
    });
  }

  private pollProgress() {
    this.api.fetchMomentumProgress().subscribe({
      next: (p) => {
        this.warmupProgress.set(p);
        if (p.step === 'ready' && this.progressInterval) {
          clearInterval(this.progressInterval);
          // Refresh all data now that warmup is done
          this.api.refreshMomentumStatus();
          forkJoin({
            trades: this.api.fetchMomentumTrades(20),
            events: this.api.fetchMomentumEvents(20),
            equity: this.api.fetchMomentumEquity(this.chartHours()),
            accel: this.api.fetchMomentumAccel(),
          }).subscribe({
            next: ({ trades, events, equity, accel }) => {
              this.trades.set(trades);
              this.events.set(events);
              this.equityData.set(equity);
              this.accelScores.set(accel);
              setTimeout(() => this.buildChart(), 300);
            },
          });
        }
      },
      error: () => {},
    });
  }

  ngAfterViewInit() {
    // Slight delay to ensure canvas is ready
    setTimeout(() => this.buildChart(), 300);
  }

  setChartRange(hours: number): void {
    this.chartHours.set(hours);
    this.api.fetchMomentumEquity(hours).subscribe(eq => {
      this.equityData.set(eq);
      setTimeout(() => this.buildChart(), 100);
    });
  }

  resetChartZoom(): void {
    if (this.chart) (this.chart as any).resetZoom();
  }

  private buildChart() {
    if (!this.canvasRef?.nativeElement) return;
    const ctx = this.canvasRef.nativeElement.getContext('2d');
    if (!ctx) return;

    // Destroy previous chart
    if (this.chart) { this.chart.destroy(); this.chart = undefined; }

    let data = this.equityData();
    const startBal = this.status()?.starting_balance ?? 3000;
    const hours = this.chartHours();

    // If no equity history, show a flat line at starting balance
    if (!data.length) {
      const now = new Date();
      data = [
        { time: new Date(now.getTime() - hours * 3600000).toISOString(), equity: startBal, cash: startBal, positions_value: 0, status: 'starting' },
        { time: now.toISOString(), equity: startBal, cash: startBal, positions_value: 0, status: 'starting' },
      ];
    }

    // Format labels based on time range
    const labels = data.map(d => {
      const dt = new Date(d.time);
      if (hours <= 24) {
        return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
      } else if (hours <= 168) {
        return dt.toLocaleDateString('en-US', { weekday: 'short', hour: 'numeric', hour12: true });
      } else {
        return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }
    });
    const values = data.map(d => d.equity);

    const allVals = [...values, startBal];
    const yMin = Math.min(...allVals) * 0.99;
    const yMax = Math.max(...allVals) * 1.01;

    const gradient = ctx.createLinearGradient(0, 0, 0, 180);
    gradient.addColorStop(0, 'rgba(167, 139, 250, 0.25)');
    gradient.addColorStop(1, 'rgba(167, 139, 250, 0.02)');

    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Starting Balance',
            data: values.map(() => startBal),
            borderColor: 'rgba(139, 143, 163, 0.4)',
            backgroundColor: 'transparent',
            borderWidth: 1,
            borderDash: [6, 4],
            pointRadius: 0,
            tension: 0,
          } as any,
          {
            label: 'Equity',
            data: values,
            borderColor: '#a78bfa',
            backgroundColor: gradient,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(20, 22, 40, 0.92)',
            borderColor: '#2d3148',
            borderWidth: 1,
            filter: (item) => item.dataset.label !== 'Starting Balance',
            callbacks: {
              title: (items) => {
                if (!items.length) return '';
                const idx = items[0].dataIndex;
                const d = data[idx];
                if (!d) return '';
                const dt = new Date(d.time);
                return dt.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
              },
              label: (item) => ` Equity: ${this.formatCurrency(item.parsed.y ?? 0)}`,
            },
          },
          zoom: {
            pan: {
              enabled: true,
              mode: 'x',
            },
            zoom: {
              wheel: { enabled: true },
              pinch: { enabled: true },
              mode: 'x',
            },
          } as any,
        },
        scales: {
          x: {
            ticks: { color: '#8b8fa3', font: { size: 9 }, maxTicksLimit: 8, maxRotation: 0 },
            grid: { color: '#2d3148' },
            border: { color: '#2d3148' },
          },
          y: {
            min: yMin, max: yMax,
            ticks: { color: '#8b8fa3', font: { size: 9 }, callback: (v) => this.formatCurrency(Number(v)) },
            grid: { color: '#2d3148' },
            border: { color: '#2d3148' },
          },
        },
      },
    });
  }

  formatCurrency(value: number): string {
    if (!value && value !== 0) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(value);
  }

  formatPrice(price: number): string {
    if (price >= 1000) return '$' + price.toLocaleString('en-US', { maximumFractionDigits: 2 });
    if (price >= 1) return '$' + price.toFixed(4);
    return '$' + price.toFixed(6);
  }

  shortTime(ts: string): string {
    try {
      const d = new Date(ts);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      if (diffMin < 60) return `${diffMin}m`;
      const diffH = Math.floor(diffMin / 60);
      if (diffH < 24) return `${diffH}h`;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ts; }
  }

  shortPair(pair: string): string {
    return pair.replace('-USD', '');
  }

  shortDate(ts: string): string {
    try {
      return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ts; }
  }

  skipCooldown(): void {
    this.skippingCooldown.set(true);
    this.api.skipMomentumCooldown().subscribe({
      next: () => {
        setTimeout(() => {
          this.skippingCooldown.set(false);
          this.api.refreshMomentumStatus();
          this._refreshAllData();
        }, 2000);
      },
      error: (err: unknown) => {
        this.skippingCooldown.set(false);
        console.error('Skip cooldown failed', err);
      },
    });
  }

  resetData(): void {
    if (!confirm('Reset all momentum data? This clears trades, equity history, and events.')) return;
    this.api.resetMomentumData().subscribe({
      next: () => {
        this.trades.set([]);
        this.events.set([]);
        this.equityData.set([]);
        this.accelScores.set([]);
        this.api.refreshMomentumStatus();
        setTimeout(() => this.buildChart(), 300);
      },
      error: (err: unknown) => console.error('Reset failed', err),
    });
  }

  manualSell(pair: string): void {
    const short = pair.replace('-USD', '');
    if (!confirm(`Sell all ${short} now at market price?`)) return;

    this.sellingPair.set(pair);
    sessionStorage.setItem('momentum_selling_pair', pair);
    this.sellNotification.set({ type: 'pending', message: `Selling ${short}... waiting for engine to execute` });

    this.api.manualSellMomentum(pair).subscribe({
      next: () => {
        this.sellNotification.set({ type: 'success', message: `${short} sell order sent — engine will execute on next cycle (~60s)` });
        this._resumeSellPoll(pair);
      },
      error: () => {
        this.sellingPair.set(null);
        sessionStorage.removeItem('momentum_selling_pair');
        this.sellNotification.set({ type: 'error', message: `Failed to send sell order for ${short}` });
        setTimeout(() => this.sellNotification.set(null), 5000);
      },
    });
  }

  private _resumeSellPoll(pair: string): void {
    const short = pair.replace('-USD', '');
    let attempts = 0;
    const pollSell = () => {
      attempts++;
      this.api.fetchMomentumStatus().subscribe({
        next: (status) => {
          this.api.momentumStatus.set(status);
          const stillHeld = status.holdings?.some(h => h.pair === pair);
          if (!stillHeld) {
            this.sellingPair.set(null);
            sessionStorage.removeItem('momentum_selling_pair');
            this.sellNotification.set({ type: 'success', message: `${short} sold successfully` });
            this.api.fetchMomentumTrades(20).subscribe(t => this.trades.set(t));
            this.api.fetchMomentumEvents(20).subscribe(e => this.events.set(e));
            this.api.fetchMomentumEquity(this.chartHours()).subscribe(eq => {
              this.equityData.set(eq);
              setTimeout(() => this.buildChart(), 300);
            });
            setTimeout(() => this.sellNotification.set(null), 5000);
          } else if (attempts < 30) {
            setTimeout(pollSell, 3000);
          } else {
            this.sellingPair.set(null);
            sessionStorage.removeItem('momentum_selling_pair');
            this.sellNotification.set({ type: 'error', message: `${short} sell is taking longer than expected — check back shortly` });
            setTimeout(() => this.sellNotification.set(null), 8000);
          }
        },
        error: () => {
          if (attempts < 30) setTimeout(pollSell, 3000);
        },
      });
    };
    setTimeout(pollSell, 3000);
  }

  // --- P&L breakdown ---

  totalFeesPaid(): number {
    return this.trades().reduce((sum, t) => sum + (t.fee || 0), 0);
  }

  priceChange(): number {
    const pnl = this.status()?.pnl ?? 0;
    const fees = this.totalFeesPaid();
    return pnl + fees; // price movement = net P&L + fees paid
  }

  // --- Strategy Logic computed methods ---

  btcVsSma(): string {
    const s = this.status();
    if (!s?.btc_price || !s?.btc_ma) return 'loading...';
    const diff = ((s.btc_price - s.btc_ma) / s.btc_ma) * 100;
    const dir = diff >= 0 ? 'above' : 'below';
    return `${this.formatCurrency(s.btc_price)} (${diff >= 0 ? '+' : ''}${diff.toFixed(1)}% ${dir} SMA)`;
  }

  regimeExplain(): string {
    const s = this.status();
    if (!s) return '';
    const hyst = ((s.regime_hysteresis ?? 0.05) * 100).toFixed(0);
    if (s.regime_bullish) {
      return `BTC is above its 500h moving average. Will flip bearish if BTC drops ${hyst}% below SMA.`;
    }
    return `BTC is below its 500h moving average. Will flip bullish once BTC rises ${hyst}% above SMA.`;
  }

  formatHours(hours: number): string {
    if (hours <= 0) return 'now';
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${Math.round(hours)}h`;
    const days = Math.floor(hours / 24);
    const rem = Math.round(hours % 24);
    return rem > 0 ? `${days}d ${rem}h` : `${days}d`;
  }

  positionExplain(): string {
    const s = this.status();
    if (!s) return '';
    if (s.holdings?.length) {
      const h = s.holdings[0];
      const short = h.pair.replace('-USD', '');
      return `Holding ${short} for ${this.formatHours(s.hours_in_position ?? 0)}`;
    }
    if ((s.exit_cooldown_remaining ?? 0) > 0) {
      return `In cash — cooldown ${s.exit_cooldown_remaining}h remaining`;
    }
    return 'In cash — scanning for entry';
  }

  positionDetail(): string {
    const s = this.status();
    if (!s) return '';
    if (s.holdings?.length) {
      const h = s.holdings[0];
      const pnlStr = h.pnl >= 0 ? `+${h.pnl_pct.toFixed(1)}%` : `${h.pnl_pct.toFixed(1)}%`;
      const layerStr = h.trail_layer ? ` Trail: ${h.trail_layer}.` : '';
      const stopStr = h.stop_price > 0
        ? `Stop at ${this.formatPrice(h.stop_price)} (${h.stop_distance_pct.toFixed(1)}% away).`
        : 'No stop set yet.';
      const holdStr = h.max_hold_remaining_hours > 0 ? ` Max hold: ${h.max_hold_remaining_hours}h left.` : ' Max hold expired.';
      return `Entry ${this.formatPrice(h.entry_price)} → now ${this.formatPrice(h.current_price)} (${pnlStr}). ${stopStr}${layerStr}${holdStr}`;
    }
    if (s.was_cash) {
      return 'Waiting for a coin with >10% acceleration in a bullish regime.';
    }
    return 'Engine just started — building acceleration data.';
  }

  sellConditions(): string {
    const s = this.status();
    if (!s?.holdings?.length) return 'N/A — not holding';
    return ''; // replaced by exitConditions() progress bars
  }

  exitConditions(): { label: string; detail: string; pct: number; shortLabel: string; shortDetail: string; tooltip: string; color: string }[] {
    const s = this.status();
    if (!s?.holdings?.length) return [];
    const h = s.holdings[0];
    const conds: { label: string; detail: string; pct: number; shortLabel: string; shortDetail: string; tooltip: string; color: string }[] = [];

    // 1. Trail stop (delayed+stale) — how close price is to stop
    const stopDist = h.stop_distance_pct ?? 0;
    const trailPct = h.stop_price > 0 ? Math.min(100, Math.max(0, (1 - stopDist / 5) * 100)) : 0;
    const layerName = h.trail_layer === 'stale' ? 'stale 2.0%' : h.trail_layer === 'tight' ? 'tight 2.5%' : h.trail_layer === 'wide' ? 'wide 5.0%' : 'inactive';
    conds.push({
      label: `Trail (${layerName})`, detail: h.stop_price > 0 ? `${stopDist.toFixed(1)}% away` : 'not active', pct: trailPct,
      shortLabel: 'Trail', shortDetail: h.stop_price > 0 ? `${stopDist.toFixed(1)}%` : '—',
      tooltip: `Trailing stop at ${h.stop_price > 0 ? this.formatPrice(h.stop_price) : '—'} (${layerName}). Activates at +2% profit with 5% trail, tightens to 2.5% after 30min above +5%, and locks to 2.0% if price stalls for 30min.`,
      color: 'amber',
    });

    // 2. ATR stop floor
    const atrDist = h.entry_price > 0 && h.atr_stop_price > 0
      ? ((h.current_price - h.atr_stop_price) / h.current_price) * 100 : 0;
    const atrPct = h.atr_stop_price > 0 ? Math.min(100, Math.max(0, (1 - atrDist / 8) * 100)) : 0;
    conds.push({
      label: 'ATR Floor', detail: h.atr_stop_price > 0 ? `${atrDist.toFixed(1)}% away` : 'not set', pct: atrPct,
      shortLabel: 'ATR', shortDetail: h.atr_stop_price > 0 ? `${atrDist.toFixed(1)}%` : '—',
      tooltip: `ATR-based stop floor at ${h.atr_stop_price > 0 ? this.formatPrice(h.atr_stop_price) : '—'}. Set at entry using Average True Range to prevent selling during normal volatility. Acts as a floor — trail stop can only be higher.`,
      color: 'red',
    });

    // 3. Accel fade
    const accel = h.accel ?? 0;
    const accelThresh = 0.05;
    const accelPct = accel > 0 ? Math.min(100, Math.max(0, (1 - (accel - accelThresh) / 0.15) * 100)) : 100;
    const hoursHeld = s.hours_in_position ?? 0;
    conds.push({
      label: 'Accel Fade', detail: hoursHeld >= 4 ? `${(accel * 100).toFixed(1)}%` : `wait ${Math.round(4 - hoursHeld)}h`, pct: hoursHeld >= 4 ? accelPct : (hoursHeld / 4) * 30,
      shortLabel: 'Accel', shortDetail: hoursHeld >= 4 ? `${(accel * 100).toFixed(1)}%` : `wait ${Math.round(4 - hoursHeld)}h`,
      tooltip: `Exits if momentum acceleration drops below 5%. Only checked after holding for 4 hours to avoid exiting during initial volatility. Current accel: ${(accel * 100).toFixed(1)}%.`,
      color: 'purple',
    });

    // 4. Max hold 72h
    const maxHoldPct = Math.min(100, (hoursHeld / 72) * 100);
    conds.push({
      label: 'Max Hold', detail: `${h.max_hold_remaining_hours}h left`, pct: maxHoldPct,
      shortLabel: 'Hold', shortDetail: `${h.max_hold_remaining_hours}h`,
      tooltip: `Force-exits after 72 hours regardless of profit. Currently held ${hoursHeld}h with ${h.max_hold_remaining_hours}h remaining. Prevents getting stuck in sideways trades.`,
      color: 'blue',
    });

    return conds;
  }

  cooldownDisplay(): string {
    const hours = this.status()?.exit_cooldown_remaining ?? 0;
    if (hours < 1) return `${Math.round(hours * 60)}min`;
    return `${hours}h`;
  }

  trailLayerLabel(layer: string): string {
    switch (layer) {
      case 'wide': return 'Wide trail (5%)';
      case 'tight': return 'Tight trail (2.5%)';
      case 'stale': return 'STALE — tight (2.0%)';
      case 'inactive': return 'Trail inactive';
      default: return layer;
    }
  }

  btcVsSmaShort(): string {
    const s = this.status();
    if (!s?.btc_price || !s?.btc_ma) return '';
    const diff = ((s.btc_price - s.btc_ma) / s.btc_ma) * 100;
    return `${diff >= 0 ? '+' : ''}${diff.toFixed(1)}% SMA`;
  }

  positionExplainShort(): string {
    const s = this.status();
    if (!s) return '';
    if (s.holdings?.length) {
      const h = s.holdings[0];
      const short = h.pair.replace('-USD', '');
      return `${short} ${this.formatHours(s.hours_in_position ?? 0)}`;
    }
    if ((s.exit_cooldown_remaining ?? 0) > 0) return `Cash (cd ${s.exit_cooldown_remaining}h)`;
    return 'Cash — scanning';
  }

  buyConditionTags(): { text: string; met: boolean | null; tooltip: string }[] {
    const s = this.status();
    const tags: { text: string; met: boolean | null; tooltip: string }[] = [];
    if (s?.holdings?.length) {
      tags.push({ text: 'Already holding', met: null, tooltip: 'Only one position at a time. Must exit current holding before buying.' });
      return tags;
    }
    tags.push({
      text: 'Regime bullish', met: s?.regime_bullish ?? false,
      tooltip: 'BTC must be above its 500h moving average. Prevents buying during market downtrends.',
    });
    tags.push({
      text: 'No cooldown', met: !((s?.exit_cooldown_remaining ?? 0) > 0),
      tooltip: `1-hour cooldown after each sell to avoid emotional re-entries. ${(s?.exit_cooldown_remaining ?? 0) > 0 ? s!.exit_cooldown_remaining + 'h remaining.' : 'Clear.'}`,
    });
    tags.push({
      text: 'Accel > 10%', met: null,
      tooltip: 'A coin must show >10% momentum acceleration — meaning the uptrend is getting stronger, not just going up.',
    });
    tags.push({
      text: 'ADX > 25', met: null,
      tooltip: 'ADX (Average Directional Index) must be above 25, confirming a strong trend is in place rather than random chop.',
    });
    tags.push({
      text: 'RSI > 50', met: null,
      tooltip: 'RSI must be above 50, confirming upward momentum. Below 50 suggests weakening or downward pressure.',
    });
    return tags;
  }

  buyConditions(): string {
    const s = this.status();
    if (s?.holdings?.length) return 'Already holding — no new entries until current position exits';
    const lines: string[] = [];
    if (!s?.regime_bullish) {
      lines.push('✗ BTC regime must be bullish (currently bearish)');
    } else {
      lines.push('✓ BTC regime is bullish');
    }
    if ((s?.exit_cooldown_remaining ?? 0) > 0) {
      lines.push(`✗ Cooldown must expire (${s!.exit_cooldown_remaining}h left)`);
    } else {
      lines.push('✓ No cooldown active');
    }
    lines.push('• Need a coin with >10% momentum acceleration');
    lines.push('• Coin must pass ADX > 25 (strong trend) and RSI > 50 (uptrend)');
    lines.push('• Engine checks every hour, buys immediately when conditions met');
    return lines.join('\n');
  }

  entryRejections(): string[] {
    return this.status()?.entry_rejections ?? [];
  }
}
