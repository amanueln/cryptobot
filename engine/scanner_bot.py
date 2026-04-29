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


def close_position(
    db_path: str,
    p: Position,
    exit_ts: str,
    exit_price: float,
    exit_reason: str,
    fee_pct_per_side: float = 0.6,
) -> None:
    """Move position from scanner_bot_positions → scanner_bot_trades."""
    if p.id is None:
        raise ValueError("close_position requires Position.id")

    gross = (exit_price - p.entry_price) * p.shares
    fees = p.position_usd * (fee_pct_per_side / 100.0) * 2
    net = gross - fees
    pct = (exit_price - p.entry_price) / p.entry_price * 100
    peak = p.peak_price if p.peak_price is not None else p.entry_price
    peak_pct = (peak - p.entry_price) / p.entry_price * 100

    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.execute(
            "INSERT INTO scanner_bot_trades "
            "(alert_id, combo_key, pair, entry_ts, entry_price, "
            " exit_ts, exit_price, position_usd, shares, "
            " gross_pnl_usd, fees_usd, net_pnl_usd, pct, peak_pct, exit_reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                p.alert_id, p.combo_key, p.pair, p.entry_ts, p.entry_price,
                exit_ts, exit_price, p.position_usd, p.shares,
                gross, fees, net, pct, peak_pct, exit_reason,
            ),
        )
        conn.execute("DELETE FROM scanner_bot_positions WHERE id=?", (p.id,))


@dataclass
class EntryConfig:
    eligible_combos: tuple[str, ...]
    position_usd: float
    max_concurrent: int
    starting_cash_usd: float
    same_pair_cooldown_hours: int
    stop_pct: float        # e.g. 15.0 means -15% stop
    hold_hours: int        # e.g. 24


@dataclass
class EntryDecision:
    action: str            # "open" | "skip"
    reason: str | None
    alert_id: int
    combo_key: str
    pair: str
    entry_price: float | None = None
    shares: float | None = None
    stop_price: float | None = None
    hard_close_ts: str | None = None


def _cash_available(db_path: str, cfg: EntryConfig) -> float:
    with sqlite3.connect(db_path, timeout=30) as conn:
        n = conn.execute("SELECT COUNT(*) FROM scanner_bot_positions").fetchone()[0]
    return cfg.starting_cash_usd - (n * cfg.position_usd)


def decide_entry(db_path: str, alert_id: int, cfg: EntryConfig) -> EntryDecision:
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        a = conn.execute(
            "SELECT id, timestamp, pair, price, combo_key, score_adj "
            "FROM early_scanner_alerts WHERE id=?",
            (alert_id,),
        ).fetchone()
    if a is None:
        return EntryDecision("skip", "alert_not_found",
                             alert_id=alert_id, combo_key="", pair="")

    if a["combo_key"] not in cfg.eligible_combos:
        return EntryDecision("skip", f"combo_not_eligible: {a['combo_key']}",
                             alert_id=alert_id, combo_key=a["combo_key"], pair=a["pair"])

    # Already traded this alert?
    with sqlite3.connect(db_path, timeout=30) as conn:
        already = conn.execute(
            "SELECT 1 FROM scanner_bot_positions WHERE alert_id=? "
            "UNION SELECT 1 FROM scanner_bot_trades WHERE alert_id=?",
            (alert_id, alert_id),
        ).fetchone()
    if already:
        return EntryDecision("skip", "already_traded",
                             alert_id=alert_id, combo_key=a["combo_key"], pair=a["pair"])

    # Concurrency
    with sqlite3.connect(db_path, timeout=30) as conn:
        n_open = conn.execute("SELECT COUNT(*) FROM scanner_bot_positions").fetchone()[0]
    if n_open >= cfg.max_concurrent:
        return EntryDecision("skip", f"at_capacity ({n_open}/{cfg.max_concurrent})",
                             alert_id=alert_id, combo_key=a["combo_key"], pair=a["pair"])

    # Cash
    if _cash_available(db_path, cfg) < cfg.position_usd:
        return EntryDecision("skip", "insufficient_cash",
                             alert_id=alert_id, combo_key=a["combo_key"], pair=a["pair"])

    # Same-pair cooldown
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=cfg.same_pair_cooldown_hours)).isoformat()
    with sqlite3.connect(db_path, timeout=30) as conn:
        recent = conn.execute(
            "SELECT 1 FROM scanner_bot_trades WHERE pair=? AND exit_ts > ?",
            (a["pair"], cutoff),
        ).fetchone()
    if recent:
        return EntryDecision("skip", f"same_pair_cooldown ({cfg.same_pair_cooldown_hours}h)",
                             alert_id=alert_id, combo_key=a["combo_key"], pair=a["pair"])

    # All checks passed
    entry_price = a["price"]
    shares = cfg.position_usd / entry_price
    stop_price = entry_price * (1 - cfg.stop_pct / 100)
    alert_ts = datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00"))
    if alert_ts.tzinfo is None:
        alert_ts = alert_ts.replace(tzinfo=timezone.utc)
    hard_close = (alert_ts + timedelta(hours=cfg.hold_hours)).isoformat()

    return EntryDecision(
        action="open", reason=None,
        alert_id=alert_id, combo_key=a["combo_key"], pair=a["pair"],
        entry_price=entry_price, shares=shares,
        stop_price=stop_price, hard_close_ts=hard_close,
    )


def record_decision(
    db_path: str, alert_id: int, ts: str, combo_key: str, pair: str,
    decision: str, reason: str | None,
) -> None:
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.execute(
            "INSERT INTO scanner_bot_alert_decisions "
            "(alert_id, ts, combo_key, pair, decision, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (alert_id, ts, combo_key, pair, decision, reason),
        )


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
