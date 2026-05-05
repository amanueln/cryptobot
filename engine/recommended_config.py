# engine/recommended_config.py
"""Built-in strategy profiles for the momentum bot.

This file is the single source of truth for the bot-curated profiles
(Recommended, Conservative, Aggressive). When code-driven research updates
the recommended values, bump RECOMMENDED_VERSION and add an entry to
CHANGES_BY_VERSION so the dashboard can show the diff and rationale.

Conservative and Aggressive are calibrated against live trade outcomes
where data supports a directional move; otherwise they fall through to
Recommended values. See the spec methodology section for sample size and
threshold-scan results.
"""
from __future__ import annotations

RECOMMENDED_VERSION = "2.0"
RECOMMENDED_RELEASE_DATE = "2026-05-02"
RECOMMENDED_RELEASE_NOTES = """\
Tightened ATH gate (-5 to -10), added chg3h_atr lower bound (-3),
new (2.0, 1.0) trail tier, AERO blacklist.
"""

RECOMMENDED: dict = {
    "entry_gates": {
        "adx_min": 25,
        "rsi_min": 50,
        "rsi_max": 65,
        "accel_min": 0.10,
        "ath_dist_max": -10,
        "chg3h_atr_max": 3.0,
        "chg3h_atr_min": -3.0,
        "green_count_min": 2,
        "body_ratio_min": 0.3,
        "mom_age_max": 100,
        "time_at_level_max": 30,
    },
    "trail": {
        "progressive": [[2.0, 1.0], [6.0, 2.0], [8.0, 1.0], [12.0, 0.5]],
        "wide_pct": 5.0,
        "wide_activate_pct": 2.0,
        "tight_pct": 2.5,
        "tight_activate_pct": 5.0,
        "delay_ticks": 30,
        "stale_pct": 2.0,
        "stale_ticks": 30,
    },
    "exits": {
        "max_hold_hours": 72,
        "accel_exit_thresh": 0.05,
        "accel_exit_min_hold": 4,
        "atr_stop_mult": 2.5,
        "equity_trail_pct": 0.15,
        "min_hold_hours": 0,
    },
    "lockouts": {
        "same_coin_hours": 24,
        "loss_lockout_hours": 72,
        "exit_cooldown_hours": 1,
    },
    "regime": {
        "ma_period": 500,
        "hysteresis_pct": 0.05,
    },
    "position": {
        "allocation_usd": 3000,
        "top_n": 1,
        "rebal_hours": 168,
    },
    "universe": {
        "min_price": 0.01,
        "blacklist": ["AERO-USD"],
    },
    "entry_pause": {
        "enabled": True,
        "weekday_block": [6],
    },
    "wall_aware": {
        "enabled": True,
        "min_size_vs_position": 3.0,
        "min_persistence_ms": 10000,
        "max_dist_from_peak_pct": 1.5,
        "stop_offset_pct": 0.001,
        "min_profit_buffer_pct": 0.012,
    },
}


def _override(base: dict, path: list[str], value):
    """Helper: deep-copy base and override a nested path."""
    import copy
    out = copy.deepcopy(base)
    cur = out
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value
    return out


CONSERVATIVE: dict = (
    _override(RECOMMENDED, ["entry_gates", "rsi_min"], 52)
)
# Apply Conservative entry-gate adjustments (data-backed where noted)
CONSERVATIVE["entry_gates"].update({
    "rsi_max": 62,             # data-backed: blocks 3 losers, 1 winner at threshold
    "ath_dist_max": -12,       # data-backed: blocks 6 losers (40%) at cost of 2 winners (20%)
    "chg3h_atr_min": -2.0,     # data-backed: dominates -3 (catches 2 more losers, 0 winner cost)
})
CONSERVATIVE["lockouts"].update({
    "same_coin_hours": 48,     # heuristic
    "loss_lockout_hours": 120, # heuristic
    "exit_cooldown_hours": 2,  # heuristic
})
CONSERVATIVE["trail"]["progressive"] = [
    [1.5, 1.5], [5.0, 2.5], [7.0, 1.5], [10.0, 0.75]  # heuristic
]


AGGRESSIVE: dict = _override(RECOMMENDED, ["entry_gates", "rsi_min"], 48)
AGGRESSIVE["entry_gates"].update({
    "rsi_max": 65,             # same as Recommended (no winner exceeds 65 in data)
    "ath_dist_max": -8,        # data-backed: still blocks 2 losers, 0 winners
    "chg3h_atr_min": -5.0,     # data-backed: still blocks 2 losers, 0 winners
})
AGGRESSIVE["lockouts"].update({
    "same_coin_hours": 12,     # heuristic
    "loss_lockout_hours": 48,  # heuristic
    "exit_cooldown_hours": 0.5,# heuristic
})
AGGRESSIVE["trail"]["progressive"] = [
    [2.0, 1.0], [7.0, 1.5], [9.0, 0.75], [14.0, 0.35]  # heuristic
]


BUILTIN_PROFILES: dict = {
    "recommended": RECOMMENDED,
    "conservative": CONSERVATIVE,
    "aggressive": AGGRESSIVE,
}


# Per-version change history for the post-update notification.
# Each version lists what changed FROM the previous version, with a
# user-friendly label and rationale.
CHANGES_BY_VERSION: dict = {
    "2.0": [
        {
            "path": "entry_gates.ath_dist_max",
            "old": -5, "new": -10,
            "label": "ATH proximity gate",
            "rationale": "Losers cluster -7% to -8% from ATH; winners stay further away.",
        },
        {
            "path": "entry_gates.chg3h_atr_min",
            "old": None, "new": -3.0,
            "label": "3h crash gate (new)",
            "rationale": "Block falling-knife entries (FARTCOIN -50 ATR was a -$169 loser).",
        },
        {
            "path": "trail.progressive[0]",
            "old": None, "new": [2.0, 1.0],
            "label": "New trail tier 1",
            "rationale": "Catches small-peak trades before they fall to the -3% ATR stop.",
        },
        {
            "path": "universe.blacklist",
            "old": [], "new": ["AERO-USD"],
            "label": "Blacklist AERO-USD",
            "rationale": "AERO had 0% win rate over 3 trades, -$298 total — structural loser.",
        },
    ],
}
