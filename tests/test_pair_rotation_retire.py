"""Regression test for engine retirement on pair swap.

Pre-fix bug: `_rebuild_engines` kept any engine with open positions when its
pair was deselected by the scanner, with no exit condition. Result: engines
accumulated indefinitely. After 8 swaps the bot had 8 engines × $1000 = $8000
of tracked starting capital instead of the configured 3 × $1000 = $3000,
making the equity dashboard show illusory +$4,848 P&L.

This test asserts that:
  - Engines for retired (deselected, not in new selection) pairs are removed
  - Their held positions are liquidated at current price before removal
  - The persisted grid_state JSON for the retired pair is deleted
"""
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock
from datetime import datetime
from dataclasses import dataclass

from exchange.models import Candle, Position
from engine.simulator import Simulator
from strategies.grid_strategy import GridStrategy
from sim_runner import SimRunner, PairEngine


GRID_CONFIG = {
    "pair": "OLD-USD",
    "granularity": "ONE_HOUR",
    "upper_price": 1.10, "lower_price": 0.90,
    "num_grids": 5,
    "total_investment_usd": 1000,
    "stop_loss_pct": 0.15, "take_profit_pct": 0.10,
}


@dataclass
class _FakeScore:
    pair: str


class _FakeScanResult:
    def __init__(self, selected_pairs):
        self.selected = [_FakeScore(p) for p in selected_pairs]


def _build_engine_with_position(pair: str, balance: float = 800.0, held_qty: float = 200.0):
    strat = GridStrategy()
    cfg = {**GRID_CONFIG, "pair": pair}
    strat.configure(cfg)
    # Mark level 2 as held
    strat.grid_levels[2].holding = True
    strat.grid_levels[2].crypto_amount = held_qty
    strat.grid_levels[2].entry_price = strat.grid_levels[2].price

    engine = PairEngine(
        name=f"{pair.split('-')[0]}-grid",
        strategy=strat, pair=pair, granularity="ONE_HOUR",
        allocation_usd=1000.0,
    )
    # Wire the simulator's positions dict so liquidation can actually sell
    engine.simulator.balance_usd = balance
    engine.simulator.positions[pair] = Position(
        pair=pair, amount=held_qty,
        avg_entry_price=strat.grid_levels[2].price,
        cost_basis=held_qty * strat.grid_levels[2].price,
    )
    engine.last_price = strat.grid_levels[2].price * 1.05  # simulate price rise
    return engine


def test_rebuild_retires_deselected_pair_with_position(tmp_path, monkeypatch):
    """Deselected engine with open positions must be liquidated + dropped,
    not silently kept."""
    # Point persistence at temp dir
    from engine import grid_persistence
    monkeypatch.setattr(grid_persistence, "STATE_DIR", str(tmp_path))

    runner = SimRunner.__new__(SimRunner)
    runner.engines = []
    runner.total_allocation = 0.0
    runner.pair_selector = MagicMock()
    runner.pair_selector.get_active_configs = MagicMock(return_value={})

    # Seed: two engines, one of them will be retired
    keep = _build_engine_with_position("KEEP-USD")
    retire = _build_engine_with_position("RETIRE-USD")
    runner.engines = [keep, retire]
    runner.total_allocation = 2000.0

    # Write a stale state file for the retire-target so we can check cleanup
    grid_persistence.save_state("RETIRE-USD", retire.strategy, retire.simulator)
    assert os.path.exists(grid_persistence._state_path("RETIRE-USD"))

    # Build a fake scan result that selects ONLY the keeper
    scan = _FakeScanResult(["KEEP-USD"])

    runner._rebuild_engines(scan)

    # Expectation 1: only the keeper survives
    surviving_pairs = [e.pair for e in runner.engines]
    assert "KEEP-USD" in surviving_pairs
    assert "RETIRE-USD" not in surviving_pairs, \
        f"retired pair leaked into engines: {surviving_pairs}"

    # Expectation 2: the retired engine's positions were liquidated
    # (its strategy's grid_levels[2] should no longer be holding)
    assert not retire.strategy.grid_levels[2].holding, \
        "retired engine's held level was not liquidated"
    assert retire.strategy.grid_levels[2].crypto_amount == 0.0

    # Expectation 3: the simulator's position was reduced/zeroed by the sell
    assert retire.simulator.positions["RETIRE-USD"].amount < 1e-6

    # Expectation 4: the persisted state file was deleted
    assert not os.path.exists(grid_persistence._state_path("RETIRE-USD")), \
        "retired pair's grid_state JSON was not cleaned up"


def test_rebuild_retires_deselected_pair_with_no_position(tmp_path, monkeypatch):
    """Deselected engine with NO positions also gets dropped (was already
    correct behavior, but include for completeness)."""
    from engine import grid_persistence
    monkeypatch.setattr(grid_persistence, "STATE_DIR", str(tmp_path))

    runner = SimRunner.__new__(SimRunner)
    runner.engines = []
    runner.total_allocation = 0.0
    runner.pair_selector = MagicMock()
    runner.pair_selector.get_active_configs = MagicMock(return_value={})

    keep = _build_engine_with_position("KEEP-USD")
    empty = _build_engine_with_position("EMPTY-USD")
    # Clear positions on empty
    empty.strategy.grid_levels[2].holding = False
    empty.strategy.grid_levels[2].crypto_amount = 0.0
    empty.simulator.positions = {}

    runner.engines = [keep, empty]
    scan = _FakeScanResult(["KEEP-USD"])

    runner._rebuild_engines(scan)
    surviving = [e.pair for e in runner.engines]
    assert surviving == ["KEEP-USD"]


def test_engine_count_stays_bounded_after_many_swaps(tmp_path, monkeypatch):
    """Repeated swaps from one selection set to another must keep engine count
    bounded — the bug was that engines with held positions stayed forever.
    We pre-create configs for all candidate pairs so _rebuild_engines doesn't
    fall through to _default_grid_config (which needs a real candle store)."""
    from engine import grid_persistence
    monkeypatch.setattr(grid_persistence, "STATE_DIR", str(tmp_path))

    pair_pool = ["AAA-USD", "BBB-USD", "CCC-USD", "DDD-USD", "EEE-USD"]

    runner = SimRunner.__new__(SimRunner)
    runner.engines = []
    runner.total_allocation = 0.0
    runner.pair_selector = MagicMock()
    # Pre-build configs for every candidate so we never hit _default_grid_config
    runner.pair_selector.get_active_configs = MagicMock(return_value={
        p: {**GRID_CONFIG, "pair": p} for p in pair_pool
    })
    # _default_grid_config is called eagerly by `dict.get(k, default)` even when
    # the key hits; stub candle_store so that branch doesn't AttributeError.
    runner.candle_store = MagicMock()
    runner.candle_store.get_candles = MagicMock(return_value=[])

    # Seed: 1 engine with an open position
    initial = _build_engine_with_position("AAA-USD")
    runner.engines = [initial]

    # Swap to each subsequent pair; old engine must retire each time
    for sel in ["BBB-USD", "CCC-USD", "DDD-USD", "EEE-USD"]:
        # Mark current engines' positions so the old "keep with positions" bug
        # path WOULD trigger if it still existed
        for e in runner.engines:
            e.strategy.grid_levels[2].holding = True
            e.strategy.grid_levels[2].crypto_amount = 100.0
            e.simulator.positions[e.pair] = Position(
                pair=e.pair, amount=100.0,
                avg_entry_price=e.strategy.grid_levels[2].price,
                cost_basis=100.0 * e.strategy.grid_levels[2].price,
            )
            e.last_price = e.strategy.grid_levels[2].price * 1.01

        runner._rebuild_engines(_FakeScanResult([sel]))
        active = [e.pair for e in runner.engines]
        assert len(active) == 1, f"engine count leaked: {active}"
        assert active == [sel], f"wrong pair selected: {active}"
