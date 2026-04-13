import {
  Component, OnInit, AfterViewInit, inject, signal, ViewChild, ElementRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chart, registerables, ChartConfiguration } from 'chart.js';
import {
  ApiService, MomentumStatusData, MomentumTradeData,
  MomentumEquityData, MomentumEventData,
} from '../../services/api.service';
import { forkJoin } from 'rxjs';

Chart.register(...registerables);

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
          <span class="hero-value">{{ formatCurrency(status()?.equity ?? 0) }}</span>
          <span class="hero-label">Total</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-value cash-val">{{ formatCurrency(status()?.cash ?? 0) }}</span>
          <span class="hero-label">Cash</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item">
          <span class="hero-value positions-val">{{ formatCurrency(status()?.positions_value ?? 0) }}</span>
          <span class="hero-label">In positions</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-item pnl-group">
          <span class="hero-value" [class.pos]="(status()?.pnl ?? 0) >= 0" [class.neg]="(status()?.pnl ?? 0) < 0">
            {{ (status()?.pnl ?? 0) >= 0 ? '+' : '' }}{{ formatCurrency(status()?.pnl ?? 0) }}
          </span>
          <span class="hero-label">P&L ({{ pnlPctStr() }})</span>
          <div class="pnl-breakdown">
            <span class="pnl-detail fee-detail">Fees: -{{ formatCurrency(totalFeesPaid()) }}</span>
            <span class="pnl-detail" [class.pos]="priceChange() >= 0" [class.neg]="priceChange() < 0">
              Price: {{ priceChange() >= 0 ? '+' : '' }}{{ formatCurrency(priceChange()) }}
            </span>
          </div>
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
            <span class="cooldown-badge">Cooldown {{ status()!.exit_cooldown_remaining }}h</span>
            <button class="skip-cooldown-btn" (click)="skipCooldown()" title="Skip cooldown and allow immediate re-entry">Skip</button>
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
          <div class="section-header">Portfolio Equity (72h)</div>
          <div class="chart-slot">
            <canvas #momEquityCanvas></canvas>
          </div>
          <div class="equity-substats">
            <span><span class="sub-label">Trades </span>{{ status()?.trade_count ?? 0 }}</span>
          </div>
        </div>
        <div class="activity-col">
          <div class="section-header">What's Happening</div>
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
            <div class="accel-card" [class.qualifying-card]="s.accel > 0.20">
              <div class="ac-top">
                <span class="ac-coin">{{ s.pair.replace('-USD', '') }}</span>
                <span class="ac-badge" [class.qual]="s.accel > 0.20" [class.below]="s.accel <= 0.20">
                  {{ s.accel > 0.20 ? 'READY' : 'BELOW 20%' }}
                </span>
                <span class="ac-price">{{ formatPrice(s.price) }}</span>
              </div>
              <div class="ac-desc">
                {{ s.accel > 0.20
                  ? 'Uptrend accelerating — qualifies for entry.'
                  : 'Momentum building but below the 20% re-entry threshold.' }}
              </div>
              <div class="ac-bar-track">
                <div class="ac-bar-fill" [class.qualifying]="s.accel > 0.20"
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
            engine picks the top 1 and enters at market price immediately.
          </div>
        }
      </div>

      <!-- Holdings / Cash state -->
      <div class="holdings-section">
        @if (isHolding()) {
          <div class="section-header">Current Holdings</div>
          @for (h of status()?.holdings ?? []; track h.pair) {
            <div class="holding-card">
              <div class="hold-left">
                <span class="hold-coin">{{ h.pair.replace('-USD', '') }}</span>
                <span class="hold-accel">Accel: {{ (h.accel * 100).toFixed(1) }}%</span>
              </div>
              <div class="hold-mid">
                <span class="hold-stop-label">Equity Stop</span>
                <span class="hold-stop-price">{{ h.stop_price > 0 ? formatCurrency(h.stop_price) : '—' }}</span>
                <span class="hold-stop-dist">{{ h.stop_distance_pct > 0 ? h.stop_distance_pct.toFixed(1) + '% cushion' : '15% from peak' }}</span>
              </div>
              <div class="hold-right">
                <span class="hold-value">{{ formatCurrency(h.value) }}</span>
                <span class="hold-pnl" [class.pos]="h.pnl >= 0" [class.neg]="h.pnl < 0">
                  {{ h.pnl >= 0 ? '+' : '' }}{{ formatCurrency(h.pnl) }} ({{ h.pnl_pct.toFixed(1) }}%)
                </span>
                <button class="manual-sell-btn"
                        [class.selling]="sellingPair() === h.pair"
                        [disabled]="sellingPair() !== null"
                        (click)="manualSell(h.pair)"
                        title="Sell this position now">
                  {{ sellingPair() === h.pair ? 'Selling...' : 'Sell' }}
                </button>
              </div>
            </div>
          }
        }
      </div>

      <!-- Sell notification banner -->
      @if (sellNotification()) {
        <div class="sell-notification" [class.success]="sellNotification()!.type === 'success'" [class.error]="sellNotification()!.type === 'error'">
          {{ sellNotification()!.message }}
        </div>
      }

      <!-- Strategy Logic panel -->
      @if (status()?.warmup_done) {
        <div class="strategy-panel">
          <div class="section-header">Strategy Logic</div>
          <div class="strategy-grid">
            <div class="strat-item">
              <span class="strat-label">BTC Regime</span>
              <span class="strat-value" [class.pos]="status()?.regime_bullish" [class.neg]="!status()?.regime_bullish">
                {{ status()?.regime_bullish ? 'Bullish' : 'Bearish' }}
                — BTC {{ btcVsSma() }}
              </span>
              <span class="strat-explain">{{ regimeExplain() }}</span>
            </div>
            <div class="strat-item">
              <span class="strat-label">Next Rebalance</span>
              <span class="strat-value">{{ formatHours(status()?.next_rebal_hours ?? 0) }}</span>
              <span class="strat-explain">Weekly rotation — engine compares your holding to top acceleration coin</span>
            </div>
            <div class="strat-item">
              <span class="strat-label">Position</span>
              <span class="strat-value">{{ positionExplain() }}</span>
              <span class="strat-explain">{{ positionDetail() }}</span>
            </div>
            <div class="strat-item">
              <span class="strat-label">Would Sell If</span>
              <span class="strat-value sell-conditions">{{ sellConditions() }}</span>
            </div>
            <div class="strat-item">
              <span class="strat-label">Would Buy If</span>
              <span class="strat-value buy-conditions">{{ buyConditions() }}</span>
            </div>
          </div>
        </div>
      }

      <!-- Recent trades table -->
      <div class="trades-section">
        <div class="section-header">Recent Trades</div>
        <table class="trades-table">
          <thead>
            <tr>
              <th class="left">Date</th>
              <th class="left">Pair</th>
              <th class="right">Price</th>
              <th class="right">Amount</th>
              <th class="right">P&L</th>
              <th class="left">Status</th>
              <th class="left hide-sm">Reason</th>
            </tr>
          </thead>
          <tbody>
            @if (trades().length === 0) {
              <tr><td colspan="7" class="empty-row">No trades yet</td></tr>
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
                <td class="right mono">{{ formatPrice(t.price) }}</td>
                <td class="right mono">
                  <span class="amount-main">{{ formatCurrency(t.cost_usd) }}</span>
                  <span class="amount-fee">fee {{ formatCurrency(t.fee) }}</span>
                </td>
                <td class="right mono" [style.color]="t.side === 'sell' ? (t.cost_usd > 0 ? '#4ade80' : '#f87171') : '#6b7280'">
                  {{ t.side === 'sell' ? (t.cost_usd > 0 ? '+' : '') + formatCurrency(t.cost_usd) : '—' }}
                </td>
                <td class="left">
                  @if (t.side === 'buy') {
                    <span class="status-badge holding">Holding</span>
                  } @else {
                    <span class="status-badge closed">Closed</span>
                  }
                </td>
                <td class="left hide-sm reason-cell">{{ t.reason || '—' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>

    </div>
  `,
  styles: [`
    .mp-root {
      background: #0f1117;
      color: #e2e8f0;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      min-height: 100%;
    }

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
      gap: 0; padding: 18px 16px;
      background: linear-gradient(180deg, #141621 0%, #0f1117 100%);
      border-bottom: 1px solid #2d3148; flex-wrap: wrap;
    }
    .hero-item { display: flex; flex-direction: column; align-items: center; padding: 0 20px; }
    .hero-value {
      font-size: 22px; font-weight: 700; color: #f1f5f9;
      font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em;
    }
    .hero-value.cash-val { color: #94a3b8; }
    .hero-value.positions-val { color: #a78bfa; }
    .hero-value.pos { color: #4ade80; }
    .hero-value.neg { color: #f87171; }
    .hero-label { font-size: 10px; font-weight: 500; color: #6b7280; margin-top: 2px; }
    .pnl-group { position: relative; }
    .pnl-breakdown {
      display: flex; gap: 10px; margin-top: 3px;
    }
    .pnl-detail {
      font-size: 9px; font-weight: 600; color: #6b7280;
      font-family: 'JetBrains Mono', monospace;
    }
    .pnl-detail.fee-detail { color: #f59e0b; }
    .hero-divider { width: 1px; height: 32px; background: #2d3148; }

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
    .chart-slot { position: relative; height: 180px; border-radius: 8px; overflow: hidden; }
    .chart-slot canvas { display: block; width: 100% !important; height: 100% !important; }
    .equity-substats { display: flex; gap: 14px; margin-top: 8px; font-size: 10px; }
    .sub-label { color: #6b7280; }
    .pos { color: #4ade80; }
    .neg { color: #f87171; }

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

    /* Holdings */
    .holdings-section { padding: 14px 20px; border-bottom: 1px solid #2d3148; }
    .holding-card {
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 14px; background: #1a1d29; border: 1px solid #2d3148;
      border-radius: 8px; border-left: 3px solid #a78bfa; margin-bottom: 8px;
    }
    .hold-left { display: flex; align-items: center; gap: 12px; }
    .hold-coin { font-weight: 700; font-size: 15px; }
    .hold-accel { font-size: 10px; font-weight: 600; color: #a78bfa; }
    .hold-mid { text-align: center; }
    .hold-stop-label { font-size: 9px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; display: block; }
    .hold-stop-price { font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; color: #f87171; display: block; }
    .hold-stop-dist { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #6b7280; }
    .hold-right { text-align: right; }
    .hold-value { font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; display: block; }
    .hold-pnl { font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600; }
    .manual-sell-btn {
      margin-top: 6px; padding: 4px 16px; border: 1px solid #f87171; border-radius: 4px;
      background: rgba(248,113,113,0.1); color: #f87171; font-size: 11px; font-weight: 700;
      cursor: pointer; letter-spacing: 0.05em; transition: all 0.15s;
    }
    .manual-sell-btn:hover:not(:disabled) { background: #f87171; color: #0f1117; }
    .manual-sell-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .manual-sell-btn.selling {
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
    .trades-table { width: 100%; border-collapse: collapse; font-size: 12px; min-width: 500px; }
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
    @media (max-width: 768px) { .hide-sm { display: none; } }
    .side-badge.buy { background: rgba(74,222,128,0.12); color: #4ade80; }
    .side-badge.sell { background: rgba(248,113,113,0.12); color: #f87171; }

    /* Strategy Logic panel */
    .strategy-panel {
      padding: 14px 20px; border-bottom: 1px solid #2d3148;
      background: linear-gradient(180deg, #12141e 0%, #0f1117 100%);
    }
    .strategy-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    }
    @media (max-width: 768px) {
      .strategy-grid { grid-template-columns: 1fr; }
    }
    .strat-item {
      background: #1a1d29; border: 1px solid #2d3148; border-radius: 8px;
      padding: 10px 14px; display: flex; flex-direction: column; gap: 4px;
    }
    .strat-label {
      font-size: 9px; font-weight: 700; color: #6b7280;
      text-transform: uppercase; letter-spacing: 0.06em;
    }
    .strat-value {
      font-size: 12px; font-weight: 600; color: #e2e8f0;
      font-family: 'JetBrains Mono', monospace;
    }
    .strat-explain {
      font-size: 10px; color: #6b7280; line-height: 1.4;
    }
    .sell-conditions, .buy-conditions {
      font-size: 11px; line-height: 1.6; white-space: pre-line;
    }
    .sell-conditions { color: #f87171; }
    .buy-conditions { color: #4ade80; }
  `],
})
export class MomentumPanelComponent implements OnInit, AfterViewInit {
  private api = inject(ApiService);

  status = this.api.momentumStatus;
  trades = signal<MomentumTradeData[]>([]);
  events = signal<MomentumEventData[]>([]);
  equityData = signal<MomentumEquityData[]>([]);
  accelScores = signal<{ pair: string; accel: number; price: number }[]>([]);
  warmupProgress = signal<{ step: string; pair?: string; done?: number; total?: number; pct?: number; estimated_remaining?: number }>({ step: 'unknown', pct: 0 });
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

  topAccelScores(): { pair: string; accel: number; price: number }[] {
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
    if (s.status === 'cash') return `In cash — watching for >20% acceleration signals (${s.trade_count} trades total)`;
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
      equity: this.api.fetchMomentumEquity(72),
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

    // Countdown timer — ticks every second, resets to 60 on each API poll
    this._pollCountdown.set(60);
    this._countdownInterval = setInterval(() => {
      const v = this._pollCountdown();
      if (v <= 1) {
        this._pollCountdown.set(60);
      } else {
        this._pollCountdown.set(v - 1);
      }
    }, 1000);
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
            equity: this.api.fetchMomentumEquity(72),
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

  private buildChart() {
    if (!this.canvasRef?.nativeElement) return;
    const ctx = this.canvasRef.nativeElement.getContext('2d');
    if (!ctx) return;

    let data = this.equityData();
    const startBal = this.status()?.starting_balance ?? 3000;

    // If no equity history, show a flat line at starting balance
    if (!data.length) {
      const now = new Date();
      data = [
        { time: new Date(now.getTime() - 72 * 3600000).toISOString(), equity: startBal, cash: startBal, positions_value: 0, status: 'starting' },
        { time: now.toISOString(), equity: startBal, cash: startBal, positions_value: 0, status: 'starting' },
      ];
    }

    const labels = data.map(d => {
      const dt = new Date(d.time);
      return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
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
              label: (item) => ` Equity: ${this.formatCurrency(item.parsed.y ?? 0)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: '#8b8fa3', font: { size: 9 }, maxTicksLimit: 6, maxRotation: 0 },
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
    this.api.skipMomentumCooldown().subscribe({
      next: () => {
        setTimeout(() => this.api.refreshMomentumStatus(), 2000);
      },
      error: (err: unknown) => console.error('Skip cooldown failed', err),
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
            this.api.fetchMomentumEquity(72).subscribe(eq => {
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
      const stopStr = h.stop_price > 0
        ? `Equity stop at ${this.formatCurrency(h.stop_price)} (${h.stop_distance_pct.toFixed(1)}% cushion).`
        : 'Equity stop: 15% drawdown from peak.';
      return `Entry ${this.formatPrice(h.entry_price)} → now ${this.formatPrice(h.current_price)} (${pnlStr}). ${stopStr}`;
    }
    if (s.was_cash) {
      return 'Waiting for a coin with >20% acceleration in a bullish regime.';
    }
    return 'Engine just started — building acceleration data.';
  }

  sellConditions(): string {
    const s = this.status();
    if (!s?.holdings?.length) return 'N/A — not holding';
    const h = s.holdings[0];
    const lines: string[] = [];
    lines.push(`• Equity drops 15% from peak → stop-loss (stop at ${this.formatPrice(h.stop_price)})`);
    lines.push('• BTC regime flips bearish → regime exit');
    lines.push('• Weekly rebalance finds a stronger coin → rotate');
    lines.push('• You click Sell → manual exit');
    return lines.join('\n');
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
    lines.push('• Need a coin with >20% momentum acceleration');
    lines.push('• Engine checks every hour, buys immediately when conditions met');
    return lines.join('\n');
  }
}
