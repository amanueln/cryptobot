from __future__ import annotations

"""Save/restore grid bot state across process restarts.

The grid bot's in-memory state (held positions, cash balance, trailing grid
bounds, learned spacing) is lost whenever the process restarts — git pulls,
auto-update, container restart, anything. Open positions are then silently
abandoned, the equity curve resets to starting balance, and the bot has no
way to know it ever traded.

This module persists per-pair state to disk after every trade and restores
it on startup. Reconciliation is implicit: after restore, the bot's normal
on_candle loop sees current prices and continues from where it left off.
"""

import json
import logging
import os
from datetime import datetime, timezone

from exchange.models import Position

logger = logging.getLogger(__name__)

STATE_DIR = "/app/persistent/grid_state"
VERSION = 1


def _state_path(pair: str) -> str:
    safe = pair.replace("/", "_").replace("\\", "_")
    return os.path.join(STATE_DIR, f"{safe}.json")


def save_state(pair: str, strategy, simulator) -> None:
    """Write per-pair state to disk. Called after every trade."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        pos = simulator.positions.get(pair)
        state = {
            "version": VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "balance_usd": float(simulator.balance_usd),
            "position": None if pos is None else {
                "amount": float(pos.amount),
                "avg_entry_price": float(pos.avg_entry_price),
                "cost_basis": float(pos.cost_basis),
            },
            "upper_price": float(strategy.upper_price),
            "lower_price": float(strategy.lower_price),
            "num_grids": int(strategy.num_grids),
            "original_investment_usd": float(strategy.original_investment_usd),
            "learned_spacing_multiplier": float(
                getattr(strategy, "_learned_spacing_multiplier", 1.0)
            ),
            "grid_levels": [
                {
                    "price": float(gl.price),
                    "holding": bool(gl.holding),
                    "crypto_amount": float(gl.crypto_amount),
                    "entry_price": float(gl.entry_price),
                    "active": bool(gl.active),
                }
                for gl in strategy.grid_levels
            ],
        }
        path = _state_path(pair)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except Exception:
        logger.exception("grid_persistence save_state failed for %s (non-fatal)", pair)


def load_state(pair: str) -> dict | None:
    """Load per-pair state from disk if it exists. Returns None if missing or stale."""
    path = _state_path(pair)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            state = json.load(f)
        if state.get("version") != VERSION:
            logger.warning(
                "grid_persistence: version mismatch for %s (saved=%s, expected=%d) — ignoring",
                pair, state.get("version"), VERSION,
            )
            return None
        return state
    except Exception:
        logger.exception("grid_persistence load_state failed for %s (non-fatal)", pair)
        return None


def restore_into(state: dict, strategy, simulator) -> bool:
    """Apply loaded state to a freshly configured strategy + simulator.

    Returns True if state was restored, False if skipped (mismatched config,
    stale state, etc). Skipping is non-fatal — the bot just starts fresh.
    """
    if not state or state.get("pair") != strategy.pair:
        return False

    # If num_grids changed between runs, the saved grid_levels won't map cleanly.
    # Skip restoration in that case — safer than partial restore.
    if state.get("num_grids") != strategy.num_grids:
        logger.warning(
            "grid_persistence: num_grids changed for %s (saved=%s, current=%d) — skipping restore",
            strategy.pair, state.get("num_grids"), strategy.num_grids,
        )
        return False

    try:
        simulator.balance_usd = float(state["balance_usd"])

        pos_state = state.get("position")
        if pos_state and pos_state["amount"] > 0:
            simulator.positions[strategy.pair] = Position(
                pair=strategy.pair,
                amount=float(pos_state["amount"]),
                avg_entry_price=float(pos_state["avg_entry_price"]),
                cost_basis=float(pos_state["cost_basis"]),
            )

        # Restore grid bounds (may have shifted via trailing)
        strategy.upper_price = float(state.get("upper_price", strategy.upper_price))
        strategy.lower_price = float(state.get("lower_price", strategy.lower_price))

        # Restore learned spacing preference
        if hasattr(strategy, "_learned_spacing_multiplier"):
            strategy._learned_spacing_multiplier = float(
                state.get("learned_spacing_multiplier", 1.0)
            )

        # Restore per-level holding state
        saved_levels = state.get("grid_levels", [])
        if len(saved_levels) == len(strategy.grid_levels):
            for live, saved in zip(strategy.grid_levels, saved_levels):
                live.price = float(saved["price"])
                live.holding = bool(saved["holding"])
                live.crypto_amount = float(saved["crypto_amount"])
                live.entry_price = float(saved.get("entry_price", 0))
                live.active = bool(saved.get("active", True))

        n_held = sum(1 for gl in strategy.grid_levels if gl.holding)
        logger.info(
            "grid_persistence: restored %s — balance=$%.2f, position_amount=%.4f, held_levels=%d",
            strategy.pair, simulator.balance_usd,
            pos_state["amount"] if pos_state else 0.0,
            n_held,
        )
        return True
    except Exception:
        logger.exception(
            "grid_persistence restore_into failed for %s (non-fatal)", strategy.pair,
        )
        return False
