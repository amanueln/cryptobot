# CryptoBot

CLI-driven crypto grid trading backtester. Tests grid strategies against historical Coinbase data with adaptive range detection, trend filtering, and trade cost modeling.

## Results (365-day backtest, Mar 2025 - Mar 2026)

| Pair | Mode | P&L | Max Drawdown | Trades |
|------|------|-----|-------------|--------|
| DOGE | Adaptive + Floor | **+2.2%** | -1.8% | 99 |
| PEPE | Adaptive | **+0.2%** | -1.7% | 45 |
| ETH | Adaptive | **+0.8%** | -4.4% | 141 |
| ADA | Death Cross | -6.6% | -10.3% | 100 |
| SOL | Death Cross | -5.9% | -12.7% | 85 |
| AVAX | Death Cross | -6.4% | -11.4% | 51 |
| DOT | Death Cross | -7.6% | -10.2% | 42 |
| LINK | Death Cross | -7.1% | -12.4% | 59 |
| BTC | Death Cross | -13.4% | -20.1% | 71 |

3 pairs profitable with adaptive grids. 6 pairs use death cross filter for capital preservation (30-50% drawdown reduction vs static grids).

## Quick Start

```bash
pip install -r requirements.txt

# Backtest a single pair (fetches + caches Coinbase candle data)
python main.py --backtest --strategy doge --days 90

# Backtest all 9 pairs across multiple time windows
python multi_window_backtest.py

# Run targeted comparison (adaptive vs death cross per pair)
python run_targeted_backtest.py

# Run tests
pytest
```

## Strategy Features

**Grid Trading**: Places limit buy/sell orders at evenly-spaced price levels. Profits from price oscillation within a range.

**Adaptive Grid Range**: Recalculates grid boundaries every 24 hours from the last 14 days of price action. Keeps grids tight around current price for maximum cycle frequency.

**Range-Only Filter**: Pauses the grid when 50/200 EMA diverge beyond 3% (trending market). Only trades when the market is range-bound.

**Death Cross Filter**: Blocks new buys when price is below both 50 and 200 EMA and 50 EMA is below 200 EMA. Sells always allowed.

**Min Spacing Floor**: Grid spacing never falls below 2% of current price, preventing micro-grids where fees eat profits.

**Daily Trade Cap**: Configurable max trades per 24-hour window (default 20). Stop-loss and take-profit bypass the cap.

## Project Structure

```
cryptobot/
  main.py                    # CLI entry point
  multi_window_backtest.py   # Multi-window comparison tool
  run_targeted_backtest.py   # Per-pair optimized backtest
  config/
    bot_config.yaml          # Global settings (balance, fees, slippage)
    strategies/              # Per-pair YAML configs (9 pairs)
  strategies/
    base_strategy.py         # BaseStrategy ABC
    grid_strategy.py         # GridStrategy with all filters
  engine/
    backtester.py            # Candle replay engine
    simulator.py             # Trade execution with fees/slippage
  exchange/
    models.py                # Candle, Signal, Trade, BacktestResult
    coinbase_client.py       # Coinbase public REST API client
  data/
    candle_store.py          # SQLite candle cache
    performance.py           # Win rate, drawdown, Sharpe ratio, P&L
  tests/                     # 74 tests (pytest)
```

## Configuration

Each pair has a YAML config in `config/strategies/`. Example (`doge.yaml` - adaptive mode):

```yaml
pair: "DOGE-USD"
granularity: "ONE_HOUR"
upper_price: 0.16
lower_price: 0.075
num_grids: 17
total_investment_usd: 1000
stop_loss_pct: 0.15
take_profit_pct: 0.10
adaptive_range: true
range_lookback_days: 14
recalc_interval_hours: 24
min_spacing_pct: 0.02
max_trades_per_day: 20
range_only_filter: true
ema_convergence_pct: 3.0
ema_fast_period: 50
ema_slow_period: 200
```

Example (`sol.yaml` - death cross mode):

```yaml
pair: "SOL-USD"
granularity: "ONE_HOUR"
upper_price: 160
lower_price: 65
num_grids: 20
total_investment_usd: 1600
stop_loss_pct: 0.15
take_profit_pct: 0.10
use_trend_filter: true
ema_fast_period: 50
ema_slow_period: 200
```

## How It Works

1. Fetches hourly OHLCV candles from Coinbase public API (no auth required)
2. Caches candles in SQLite (`data/candles.db`) for fast re-runs
3. Replays candles through the grid strategy, generating buy/sell signals
4. Simulates trade execution with configurable maker/taker fees and slippage
5. Reports P&L, win rate, max drawdown, Sharpe ratio, and ASCII equity curve

## Requirements

- Python 3.12+
- No API keys needed (uses Coinbase public endpoints)
