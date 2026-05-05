# tests/test_recommended_config.py
import pytest
from engine.recommended_config import (
    RECOMMENDED, CONSERVATIVE, AGGRESSIVE,
    RECOMMENDED_VERSION, RECOMMENDED_RELEASE_DATE, CHANGES_BY_VERSION,
    BUILTIN_PROFILES,
)


def test_recommended_version_is_string():
    assert isinstance(RECOMMENDED_VERSION, str)
    assert len(RECOMMENDED_VERSION) > 0


def test_recommended_has_all_required_sections():
    expected = {
        "entry_gates", "trail", "exits", "lockouts", "regime",
        "position", "universe", "entry_pause", "wall_aware",
    }
    assert set(RECOMMENDED.keys()) == expected


def test_recommended_entry_gates_have_known_values():
    g = RECOMMENDED["entry_gates"]
    assert g["adx_min"] == 25
    assert g["rsi_min"] == 50
    assert g["rsi_max"] == 65
    assert g["ath_dist_max"] == -10
    assert g["chg3h_atr_max"] == 3.0
    assert g["chg3h_atr_min"] == -3.0


def test_recommended_trail_progressive_safe_a():
    assert RECOMMENDED["trail"]["progressive"] == [
        [2.0, 1.0], [6.0, 2.0], [8.0, 1.0], [12.0, 0.5]
    ]


def test_recommended_blacklists_aero():
    assert "AERO-USD" in RECOMMENDED["universe"]["blacklist"]


def test_conservative_has_all_required_sections():
    assert set(CONSERVATIVE.keys()) == set(RECOMMENDED.keys())


def test_conservative_is_stricter_than_recommended():
    # Tighter chg3h_atr lower bound
    assert CONSERVATIVE["entry_gates"]["chg3h_atr_min"] > RECOMMENDED["entry_gates"]["chg3h_atr_min"]
    # Tighter ATH gate (more negative is stricter)
    assert CONSERVATIVE["entry_gates"]["ath_dist_max"] < RECOMMENDED["entry_gates"]["ath_dist_max"]
    # Tighter RSI max
    assert CONSERVATIVE["entry_gates"]["rsi_max"] < RECOMMENDED["entry_gates"]["rsi_max"]
    # Longer loss lockout
    assert CONSERVATIVE["lockouts"]["loss_lockout_hours"] > RECOMMENDED["lockouts"]["loss_lockout_hours"]


def test_aggressive_is_looser_than_recommended():
    # Looser chg3h_atr lower bound (more negative = lets in more)
    assert AGGRESSIVE["entry_gates"]["chg3h_atr_min"] < RECOMMENDED["entry_gates"]["chg3h_atr_min"]
    # Looser ATH gate (less negative = closer to ATH allowed)
    assert AGGRESSIVE["entry_gates"]["ath_dist_max"] > RECOMMENDED["entry_gates"]["ath_dist_max"]
    # Shorter loss lockout
    assert AGGRESSIVE["lockouts"]["loss_lockout_hours"] < RECOMMENDED["lockouts"]["loss_lockout_hours"]


def test_builtin_profiles_dict_exposes_all_three():
    assert set(BUILTIN_PROFILES.keys()) == {"recommended", "conservative", "aggressive"}
    assert BUILTIN_PROFILES["recommended"] is RECOMMENDED


def test_changes_by_version_v2_0_includes_recent_fixes():
    v20 = CHANGES_BY_VERSION["2.0"]
    paths = {c["path"] for c in v20}
    assert "entry_gates.ath_dist_max" in paths
    assert "entry_gates.chg3h_atr_min" in paths
    assert "trail.progressive[0]" in paths
    assert "universe.blacklist" in paths
