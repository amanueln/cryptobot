# engine/scanner_bot.py
"""Paper-trading bot driven by Early Momentum Scanner +1 alerts.

Spec: docs/superpowers/specs/2026-04-29-scanner-bot-design.md
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger("scanner_bot")

MILESTONES = [10, 15, 20, 30, 50]


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
        committed = conn.execute(
            "SELECT COALESCE(SUM(position_usd), 0) FROM scanner_bot_positions"
        ).fetchone()[0]
    return cfg.starting_cash_usd - committed


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


@dataclass
class ExitDecision:
    action: str            # "close" | "hold"
    exit_price: float | None = None
    exit_reason: str | None = None


def tick_position(p: Position, current_price: float, now: datetime) -> ExitDecision:
    """Mutate Position with current_price/peak/pct then decide whether to exit.

    Exit priority: manual > stop > time-cap.
    Manual exits at current_price; stop exits at stop_price; time-cap at current_price.
    """
    p.current_price = current_price
    p.current_pct = (current_price - p.entry_price) / p.entry_price * 100
    # Peak is the highest price seen since entry, but never below entry — a
    # position whose price only ever fell shouldn't report a "peak" below cost.
    floor = p.entry_price
    candidate = max(current_price, floor)
    if p.peak_price is None or candidate > p.peak_price:
        p.peak_price = candidate
    p.last_tick_ts = now.isoformat()

    if p.manual_sell_requested:
        return ExitDecision("close", exit_price=current_price, exit_reason="manual")

    if current_price <= p.stop_price:
        return ExitDecision("close", exit_price=p.stop_price, exit_reason="stop_15pct")

    hard_close = datetime.fromisoformat(p.hard_close_ts.replace("Z", "+00:00"))
    if hard_close.tzinfo is None:
        hard_close = hard_close.replace(tzinfo=timezone.utc)
    if now >= hard_close:
        return ExitDecision("close", exit_price=current_price, exit_reason="time_24h")

    return ExitDecision("hold")


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


def check_milestones(p: Position, webhook: str | None) -> list[int]:
    """Fire and persist milestone pings for any newly crossed thresholds.

    Returns the list of milestones fired this tick. Mutates p.milestones_hit.
    """
    if p.current_pct is None:
        return []
    fired: list[int] = []
    for m in MILESTONES:
        if p.current_pct >= m and m not in p.milestones_hit:
            p.milestones_hit.append(m)
            fired.append(m)
            if webhook:
                try:
                    _send_discord(webhook, p, m)
                except Exception as e:
                    logger.warning("discord milestone ping failed: %s", e)
    return fired


def _send_discord(webhook: str, p: Position, milestone: int) -> None:
    """Send a Discord webhook for a profit milestone."""
    held_min = 0
    try:
        entry = datetime.fromisoformat(p.entry_ts.replace("Z", "+00:00"))
        if entry.tzinfo is None:
            entry = entry.replace(tzinfo=timezone.utc)
        held_min = int((datetime.now(timezone.utc) - entry).total_seconds() / 60)
    except Exception:
        pass
    held_str = f"{held_min // 60}h {held_min % 60}m"

    peak = p.peak_price if p.peak_price is not None else p.current_price
    peak_pct = (peak - p.entry_price) / p.entry_price * 100

    coin = p.pair.replace("-USD", "")
    embed = {
        "title": f"🚀 +{milestone}% milestone hit on {coin}",
        "description": (
            f"**Combo:** {p.combo_key}\n"
            f"**Entry:** ${p.entry_price:.6f}  →  **Now:** ${p.current_price:.6f}  "
            f"(**{p.current_pct:+.1f}%**)\n"
            f"**Position:** ${p.position_usd:.0f} ({p.shares:.4f} shares)\n"
            f"**Held:** {held_str}\n"
            f"**Peak:** +{peak_pct:.1f}%\n\n"
            f"Hit \"Sell Now\" on the dashboard to take it."
        ),
        "color": 0x00ff88,
    }
    resp = requests.post(webhook, json={"embeds": [embed]}, timeout=10)
    if resp.status_code >= 400:
        logger.warning("discord webhook returned %s for %s milestone +%d%%",
                       resp.status_code, p.pair, milestone)


def _fetch_coinbase_price(pair: str) -> float | None:
    """Fetch current trade price from Coinbase Advanced Trade public REST."""
    try:
        url = f"https://api.exchange.coinbase.com/products/{pair}/ticker"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()["price"])
    except Exception as e:
        logger.warning("price fetch failed for %s: %s", pair, e)
    return None


class ScannerBot:
    def __init__(
        self,
        db_path: str,
        cfg: EntryConfig,
        discord_webhook: str | None,
        price_fn=None,                # injectable for tests
        poll_interval_sec: int = 30,
        alert_max_age_minutes: int = 5,
        seed_cursor_from_max: bool = True,
    ):
        self.db_path = db_path
        self.cfg = cfg
        self.discord_webhook = discord_webhook
        self.price_fn = price_fn or _fetch_coinbase_price
        self.poll_interval_sec = poll_interval_sec
        self.alert_max_age_minutes = alert_max_age_minutes
        # On startup, seed the cursor to the current max alert id so historical
        # alerts (already-pinged on Discord weeks ago) aren't replayed as new
        # trades. Tests can opt out with seed_cursor_from_max=False.
        self._last_alert_check_id: int = (
            self._fetch_max_alert_id() if seed_cursor_from_max else 0
        )

    def _fetch_max_alert_id(self) -> int:
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                row = conn.execute(
                    "SELECT COALESCE(MAX(id), 0) FROM early_scanner_alerts"
                ).fetchone()
                return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            # Alerts table doesn't exist yet (early scanner hasn't initialized).
            return 0

    def tick(self, now: datetime | None = None) -> None:
        """One iteration: poll alerts, manage positions, snapshot equity."""
        now = now or datetime.now(timezone.utc)
        try:
            self._poll_alerts(now)
            self._manage_positions(now)
            self._snapshot_equity(now)
        except Exception:
            logger.exception("scanner_bot tick failed")

    def run(self) -> None:
        """Forever loop. Crash-tolerant — exceptions inside tick() are swallowed."""
        logger.info("scanner_bot starting (poll=%ds, combos=%s)",
                    self.poll_interval_sec, self.cfg.eligible_combos)
        while True:
            self.tick()
            time.sleep(self.poll_interval_sec)

    def _poll_alerts(self, now: datetime) -> None:
        # Freshness floor — even if the cursor falls behind (long bot downtime),
        # never trade an alert older than alert_max_age_minutes. The Discord
        # ping has long since fired; replaying the alert as a "new" trade would
        # buy at a stale price.
        cutoff = (now - timedelta(minutes=self.alert_max_age_minutes)).isoformat()
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            new_alerts = conn.execute(
                "SELECT id FROM early_scanner_alerts "
                "WHERE id > ? AND score_adj = 1 AND combo_key IN ({}) "
                "AND created_at > ? "
                "ORDER BY id".format(",".join("?" * len(self.cfg.eligible_combos))),
                (self._last_alert_check_id, *self.cfg.eligible_combos, cutoff),
            ).fetchall()

        for row in new_alerts:
            d = decide_entry(self.db_path, alert_id=row["id"], cfg=self.cfg)
            record_decision(self.db_path, alert_id=d.alert_id, ts=now.isoformat(),
                            combo_key=d.combo_key, pair=d.pair,
                            decision=d.action, reason=d.reason)
            if d.action == "open":
                p = Position(
                    alert_id=d.alert_id, combo_key=d.combo_key, pair=d.pair,
                    entry_ts=now.isoformat(),
                    entry_price=d.entry_price, position_usd=self.cfg.position_usd,
                    shares=d.shares, stop_price=d.stop_price,
                    hard_close_ts=d.hard_close_ts,
                )
                save_position(self.db_path, p)
                logger.info("scanner_bot opened %s @ %.6f (alert %d)",
                            d.pair, d.entry_price, d.alert_id)
            # Only advance the cursor after the alert has been fully processed,
            # so a DB write failure mid-loop doesn't silently skip the alert.
            self._last_alert_check_id = max(self._last_alert_check_id, row["id"])

    def _manage_positions(self, now: datetime) -> None:
        for p in load_open_positions(self.db_path):
            cp = self.price_fn(p.pair)
            if cp is None:
                continue
            decision = tick_position(p, current_price=cp, now=now)
            check_milestones(p, webhook=self.discord_webhook)
            update_position(self.db_path, p)
            if decision.action == "close":
                close_position(
                    self.db_path, p,
                    exit_ts=now.isoformat(),
                    exit_price=decision.exit_price,
                    exit_reason=decision.exit_reason,
                )
                logger.info("scanner_bot closed %s @ %.6f reason=%s",
                            p.pair, decision.exit_price, decision.exit_reason)

    def _snapshot_equity(self, now: datetime) -> None:
        opens = load_open_positions(self.db_path)
        positions_value = sum((p.current_price or p.entry_price) * p.shares for p in opens)
        unrealized = sum(((p.current_price or p.entry_price) - p.entry_price) * p.shares for p in opens)
        cash = self.cfg.starting_cash_usd - sum(p.position_usd for p in opens)

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            realized = conn.execute(
                "SELECT COALESCE(SUM(net_pnl_usd), 0) FROM scanner_bot_trades"
            ).fetchone()[0]
            # ignore concurrent equity collisions (PRIMARY KEY ts) — same-second writes are fine to drop
            conn.execute(
                "INSERT OR REPLACE INTO scanner_bot_equity "
                "(ts, cash_usd, positions_value_usd, total_equity_usd, "
                " open_positions, realized_pnl_usd, unrealized_pnl_usd) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now.isoformat(), cash, positions_value,
                 cash + positions_value, len(opens), realized, unrealized),
            )
