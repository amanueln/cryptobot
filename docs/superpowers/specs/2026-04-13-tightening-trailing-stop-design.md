# Tightening Hourly Trailing Stop — Design Spec

## Goal

Replace the static ATR stop with a per-position tightening trailing stop that locks in profit as gains grow. Checked hourly only (not on every ticker) to avoid noise shake-outs on volatile altcoins.

## Problem

1. ATR stop is set at entry and never moves up — a coin can run +26% and the stop sits at -12.5%
2. The only trailing mechanism is the 15% equity stop (portfolio-level emergency backstop)
3. `stop_price` can be 0 for scanner-added coins without enough candle history
4. Simulations proved: IRYS ran +26% but system held at +6.4%; INX peaked +16.9% then round-tripped to +1.3%

## Design

### Trailing stop tiers (checked hourly in `feed_candle`)

| PnL from entry | Trail % from peak price |
|---|---|
| < 3% | No trail — ATR stop only |
| 3-5% | 8% below peak |
| 5-10% | 8% below peak |
| 10-20% | 6% below peak |
| 20%+ | 5% below peak |

- **Activation**: Trail activates when position PnL reaches +3% from entry
- **ATR floor**: The trailing stop never goes below the original ATR stop (or fallback stop)
- **Ratchet**: The trailing stop only moves up, never down
- **Hourly only**: Computed in `feed_candle` on BTC hourly tick, NOT on every `check_stop_ticker` call

### `check_stop_ticker` changes

- Still checks ATR stop (now stored as `atr_stop_price`, the floor)
- Also checks `trail_stop_price` (the ratcheting trail, updated hourly)
- Fires whichever stop is higher (trail >= ATR floor by design)

### `MomentumHolding` changes

```python
@dataclass
class MomentumHolding:
    pair: str
    shares: float
    entry_price: float
    entry_time: datetime
    peak_price: float = 0.0
    atr_stop_price: float = 0.0    # renamed from stop_price, set at entry, never moves
    trail_stop_price: float = 0.0  # tightening trail, updated hourly, ratchets up
```

### stop_price=0 fix

In `_buy()`, if ATR is unavailable AND there aren't enough candles, use 8% fallback. This already exists but the field rename ensures both stops are always initialized:
- `atr_stop_price`: ATR-based or 8% fallback, guaranteed > 0
- `trail_stop_price`: starts at 0, activates when PnL hits +3%

### Dashboard API

`get_holdings_info()` returns both stops so the UI can display them:
- `atr_stop_price`: the floor
- `trail_stop_price`: the active trailing level (0 if not yet activated)
- `stop_price`: the effective stop (max of both, for backward compat)

## Simulation Results

### IRYS (current live trade)
- Current system: holding at +6.4% ($192 unrealized on $3K)
- Tightening trail: would have exited at +16.6% ($498 locked)

### INX (scanner alert, peaked +16.9%)
- Current system: holding at +1.3% ($39 unrealized)
- Tightening trail: exited at +1.1% ($34 locked) — prevented full round-trip

## Files Changed

- `engine/momentum_engine.py` — all changes here:
  1. Rename `stop_price` to `atr_stop_price` in MomentumHolding
  2. Add `trail_stop_price` field
  3. Add `_update_trail_stop()` method with tier logic
  4. Call it from `feed_candle` exit logic (hourly)
  5. Update `check_stop_ticker` to check trail stop
  6. Update `get_holdings_info()` to expose both stops
  7. Update `_buy()` to use renamed field

No dashboard UI changes needed — existing stop display will show the effective stop.
