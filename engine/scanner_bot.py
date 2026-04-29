# engine/scanner_bot.py
"""Paper-trading bot driven by Early Momentum Scanner +1 alerts.

Spec: docs/superpowers/specs/2026-04-29-scanner-bot-design.md
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Position:
    alert_id: int
    combo_key: str
    pair: str
    entry_ts: str
    entry_price: float
    position_usd: float
    shares: float
    stop_price: float
    hard_close_ts: str
    id: int | None = None
    manual_sell_requested: int = 0
    milestones_hit: list[int] = field(default_factory=list)
    current_price: float | None = None
    current_pct: float | None = None
    peak_price: float | None = None
    last_tick_ts: str | None = None


def save_position(db_path: str, p: Position) -> int:
    with sqlite3.connect(db_path, timeout=30) as conn:
        cur = conn.execute(
            "INSERT INTO scanner_bot_positions "
            "(alert_id, combo_key, pair, entry_ts, entry_price, position_usd, shares, "
            " stop_price, hard_close_ts, manual_sell_requested, milestones_hit, "
            " current_price, current_pct, peak_price, last_tick_ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                p.alert_id, p.combo_key, p.pair, p.entry_ts, p.entry_price,
                p.position_usd, p.shares, p.stop_price, p.hard_close_ts,
                p.manual_sell_requested, json.dumps(p.milestones_hit),
                p.current_price, p.current_pct, p.peak_price, p.last_tick_ts,
            ),
        )
        p.id = cur.lastrowid
        return p.id


def load_open_positions(db_path: str) -> list[Position]:
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM scanner_bot_positions").fetchall()
    return [_row_to_position(r) for r in rows]


def update_position(db_path: str, p: Position) -> None:
    if p.id is None:
        raise ValueError("update_position requires Position.id")
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.execute(
            "UPDATE scanner_bot_positions SET "
            "manual_sell_requested=?, milestones_hit=?, "
            "current_price=?, current_pct=?, peak_price=?, last_tick_ts=? "
            "WHERE id=?",
            (
                p.manual_sell_requested, json.dumps(p.milestones_hit),
                p.current_price, p.current_pct, p.peak_price, p.last_tick_ts,
                p.id,
            ),
        )


def delete_position(db_path: str, position_id: int) -> None:
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.execute("DELETE FROM scanner_bot_positions WHERE id=?", (position_id,))


def _row_to_position(r) -> Position:
    return Position(
        id=r["id"],
        alert_id=r["alert_id"],
        combo_key=r["combo_key"],
        pair=r["pair"],
        entry_ts=r["entry_ts"],
        entry_price=r["entry_price"],
        position_usd=r["position_usd"],
        shares=r["shares"],
        stop_price=r["stop_price"],
        hard_close_ts=r["hard_close_ts"],
        manual_sell_requested=r["manual_sell_requested"],
        milestones_hit=json.loads(r["milestones_hit"] or "[]"),
        current_price=r["current_price"],
        current_pct=r["current_pct"],
        peak_price=r["peak_price"],
        last_tick_ts=r["last_tick_ts"],
    )
