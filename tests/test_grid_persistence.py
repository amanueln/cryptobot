import os
import tempfile
from datetime import datetime, timedelta

from engine.simulator import Simulator
from exchange.models import Position, Signal
from strategies.grid_strategy import GridStrategy


GRID_CONFIG = {
    "pair": "BTC-USD",
    "granularity": "ONE_HOUR",
    "upper_price": 90000,
    "lower_price": 80000,
    "num_grids": 10,
    "total_investment_usd": 1000,
    "stop_loss_pct": 0.15,
    "take_profit_pct": 0.10,
}


def _setup(state_dir: str):
    """Patch the persistence module to use a temp state dir for this test."""
    from engine import grid_persistence
    grid_persistence.STATE_DIR = state_dir
    return grid_persistence


def _build_strategy_with_held_levels():
    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    # Simulate two grid levels being held with crypto
    gs.grid_levels[2].holding = True
    gs.grid_levels[2].crypto_amount = 0.0015
    gs.grid_levels[2].entry_price = gs.grid_levels[2].price
    gs.grid_levels[5].holding = True
    gs.grid_levels[5].crypto_amount = 0.0012
    gs.grid_levels[5].entry_price = gs.grid_levels[5].price
    gs._learned_spacing_multiplier = 1.114
    return gs


def test_save_and_load_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        gp = _setup(tmp)

        # Source state
        gs1 = _build_strategy_with_held_levels()
        sim1 = Simulator(starting_balance_usd=1000.0)
        sim1.balance_usd = 750.50
        sim1.positions["BTC-USD"] = Position(
            pair="BTC-USD", amount=0.0027,
            avg_entry_price=82500.0, cost_basis=222.75,
        )

        gp.save_state("BTC-USD", gs1, sim1)

        # Confirm file was written
        files = os.listdir(tmp)
        assert "BTC-USD.json" in files

        # Fresh strategy + simulator (post-restart state)
        gs2 = GridStrategy()
        gs2.configure(GRID_CONFIG)
        sim2 = Simulator(starting_balance_usd=1000.0)
        assert sim2.balance_usd == 1000.0  # fresh, not yet restored
        assert "BTC-USD" not in sim2.positions
        assert all(not gl.holding for gl in gs2.grid_levels)

        # Restore
        state = gp.load_state("BTC-USD")
        assert state is not None
        ok = gp.restore_into(state, gs2, sim2)
        assert ok is True

        # Verify state matches
        assert sim2.balance_usd == 750.50
        pos = sim2.positions["BTC-USD"]
        assert pos.amount == 0.0027
        assert pos.avg_entry_price == 82500.0
        assert pos.cost_basis == 222.75
        assert gs2.grid_levels[2].holding is True
        assert gs2.grid_levels[2].crypto_amount == 0.0015
        assert gs2.grid_levels[5].holding is True
        assert gs2.grid_levels[5].crypto_amount == 0.0012
        assert gs2._learned_spacing_multiplier == 1.114


def test_load_returns_none_when_no_file():
    with tempfile.TemporaryDirectory() as tmp:
        gp = _setup(tmp)
        assert gp.load_state("NEVER-USD") is None


def test_restore_skips_when_num_grids_changed():
    """If user changes num_grids between runs, saved state shouldn't be applied."""
    with tempfile.TemporaryDirectory() as tmp:
        gp = _setup(tmp)
        gs1 = _build_strategy_with_held_levels()
        sim1 = Simulator(starting_balance_usd=1000.0)
        sim1.balance_usd = 800.0
        gp.save_state("BTC-USD", gs1, sim1)

        # Reconfigure with different num_grids
        gs2 = GridStrategy()
        gs2.configure({**GRID_CONFIG, "num_grids": 5})
        sim2 = Simulator(starting_balance_usd=1000.0)
        state = gp.load_state("BTC-USD")
        ok = gp.restore_into(state, gs2, sim2)
        assert ok is False
        # Simulator stays fresh
        assert sim2.balance_usd == 1000.0


def test_save_overwrites_atomically():
    """Saving twice should leave a valid file (atomic replace), not a corrupted tmp."""
    with tempfile.TemporaryDirectory() as tmp:
        gp = _setup(tmp)
        gs = _build_strategy_with_held_levels()
        sim = Simulator(starting_balance_usd=1000.0)
        sim.balance_usd = 500.0
        gp.save_state("BTC-USD", gs, sim)

        sim.balance_usd = 600.0
        gp.save_state("BTC-USD", gs, sim)

        state = gp.load_state("BTC-USD")
        assert state["balance_usd"] == 600.0
        # No stray .tmp files
        files = os.listdir(tmp)
        assert all(not f.endswith(".tmp") for f in files)


def test_version_mismatch_returns_none():
    """Old/incompatible versions should be ignored (None) not crash."""
    import json
    with tempfile.TemporaryDirectory() as tmp:
        gp = _setup(tmp)
        path = os.path.join(tmp, "BTC-USD.json")
        with open(path, "w") as f:
            json.dump({"version": 99, "pair": "BTC-USD"}, f)
        assert gp.load_state("BTC-USD") is None
