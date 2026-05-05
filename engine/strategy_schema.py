# engine/strategy_schema.py
"""Validation rules for momentum strategy config dicts.

Used by the API to reject invalid input before it reaches the engine,
and to validate user-saved profiles on load.
"""
from __future__ import annotations


class ValidationError(ValueError):
    pass


# Per-field bounds. (min, max, type) — type is for explicit type checking
# beyond what isinstance(int|float) gives us.
ENTRY_GATE_BOUNDS = {
    "adx_min":          (0, 100, (int, float)),
    "rsi_min":          (0, 100, (int, float)),
    "rsi_max":          (0, 100, (int, float)),
    "accel_min":        (0, 1, (int, float)),
    "ath_dist_max":     (-100, 0, (int, float)),
    "chg3h_atr_max":    (0, 50, (int, float)),
    "chg3h_atr_min":    (-50, 0, (int, float)),
    "green_count_min":  (0, 6, (int,)),
    "body_ratio_min":   (0, 1, (int, float)),
    "mom_age_max":      (0, 1000, (int,)),
    "time_at_level_max":(0, 100, (int,)),
}

TRAIL_BOUNDS = {
    "wide_pct":          (0, 50, (int, float)),
    "wide_activate_pct": (0, 50, (int, float)),
    "tight_pct":         (0, 50, (int, float)),
    "tight_activate_pct":(0, 50, (int, float)),
    "delay_ticks":       (0, 1000, (int,)),
    "stale_pct":         (0, 50, (int, float)),
    "stale_ticks":       (0, 1000, (int,)),
}

EXITS_BOUNDS = {
    "max_hold_hours":     (0, 720, (int, float)),
    "accel_exit_thresh":  (0, 1, (int, float)),
    "accel_exit_min_hold":(0, 100, (int, float)),
    "atr_stop_mult":      (0, 20, (int, float)),
    "equity_trail_pct":   (0, 1, (int, float)),
    "min_hold_hours":     (0, 100, (int, float)),
}

LOCKOUT_BOUNDS = {
    "same_coin_hours":    (0, 720, (int, float)),
    "loss_lockout_hours": (0, 720, (int, float)),
    "exit_cooldown_hours":(0, 100, (int, float)),
}

REGIME_BOUNDS = {
    "ma_period":      (10, 5000, (int,)),
    "hysteresis_pct": (0, 1, (int, float)),
}

POSITION_BOUNDS = {
    "allocation_usd": (10, 1_000_000, (int, float)),
    "top_n":          (1, 10, (int,)),
    "rebal_hours":    (1, 5000, (int, float)),
}

UNIVERSE_BOUNDS = {
    "min_price":  (0, 100_000, (int, float)),
}

WALL_AWARE_BOUNDS = {
    "min_size_vs_position":   (0, 1000, (int, float)),
    "min_persistence_ms":     (0, 600_000, (int,)),
    "max_dist_from_peak_pct": (0, 100, (int, float)),
    "stop_offset_pct":        (0, 1, (int, float)),
    "min_profit_buffer_pct":  (0, 1, (int, float)),
}


def _validate_bounded(label: str, fields: dict, bounds: dict) -> None:
    for key, (lo, hi, types) in bounds.items():
        if key not in fields:
            raise ValidationError(f"{label}.{key} is missing")
        v = fields[key]
        if not isinstance(v, types):
            raise ValidationError(f"{label}.{key} must be {types}, got {type(v).__name__}")
        if isinstance(v, bool):
            raise ValidationError(f"{label}.{key} must be numeric, not bool")
        if v < lo or v > hi:
            raise ValidationError(f"{label}.{key}={v} out of range [{lo}, {hi}]")


def validate_profile(profile: dict) -> None:
    """Raise ValidationError if profile is malformed. Returns None on valid."""
    required_sections = {
        "entry_gates", "trail", "exits", "lockouts", "regime",
        "position", "universe", "entry_pause", "wall_aware",
    }
    missing = required_sections - set(profile.keys())
    if missing:
        raise ValidationError(f"missing sections: {missing}")

    _validate_bounded("entry_gates", profile["entry_gates"], ENTRY_GATE_BOUNDS)
    _validate_bounded("exits",        profile["exits"],        EXITS_BOUNDS)
    _validate_bounded("lockouts",     profile["lockouts"],     LOCKOUT_BOUNDS)
    _validate_bounded("regime",       profile["regime"],       REGIME_BOUNDS)
    _validate_bounded("position",     profile["position"],     POSITION_BOUNDS)
    _validate_bounded("universe",     profile["universe"],     UNIVERSE_BOUNDS)
    _validate_bounded("wall_aware",   profile["wall_aware"],   WALL_AWARE_BOUNDS)

    # Trail (skip 'progressive' which is a list-of-pairs):
    trail = profile["trail"]
    _validate_bounded("trail", {k: v for k, v in trail.items() if k != "progressive"}, TRAIL_BOUNDS)
    if "progressive" not in trail:
        raise ValidationError("trail.progressive is missing")
    if not isinstance(trail["progressive"], list):
        raise ValidationError("trail.progressive must be a list")
    for i, tier in enumerate(trail["progressive"]):
        if not isinstance(tier, (list, tuple)) or len(tier) != 2:
            raise ValidationError(f"trail.progressive[{i}] must be [peak_pct, trail_pct]")
        for j, val in enumerate(tier):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise ValidationError(f"trail.progressive[{i}][{j}] must be numeric")
            if val < 0 or val > 100:
                raise ValidationError(f"trail.progressive[{i}][{j}]={val} out of range [0, 100]")

    # Universe blacklist
    bl = profile["universe"].get("blacklist")
    if not isinstance(bl, list):
        raise ValidationError("universe.blacklist must be a list")
    for p in bl:
        if not isinstance(p, str) or not p:
            raise ValidationError(f"universe.blacklist contains invalid pair: {p!r}")

    # Entry pause
    ep = profile["entry_pause"]
    if not isinstance(ep.get("enabled"), bool):
        raise ValidationError("entry_pause.enabled must be bool")
    wb = ep.get("weekday_block", [])
    if not isinstance(wb, list):
        raise ValidationError("entry_pause.weekday_block must be a list")
    for d in wb:
        if not isinstance(d, int) or d < 0 or d > 6:
            raise ValidationError(f"entry_pause.weekday_block has invalid weekday: {d}")

    # Wall-aware enabled
    if not isinstance(profile["wall_aware"].get("enabled"), bool):
        raise ValidationError("wall_aware.enabled must be bool")
