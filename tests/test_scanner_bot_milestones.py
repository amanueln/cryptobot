# tests/test_scanner_bot_milestones.py
from unittest.mock import patch

from engine.scanner_bot import Position, check_milestones


def _p(milestones=None):
    return Position(
        id=1, alert_id=1, combo_key="mom_reversal+strong_move", pair="HIGH-USD",
        entry_ts="2026-04-29T10:00:00+00:00", entry_price=1.0,
        position_usd=1000.0, shares=1000.0,
        stop_price=0.85, hard_close_ts="2026-04-30T10:00:00+00:00",
        milestones_hit=milestones or [],
    )


def test_no_milestones_below_10():
    p = _p(); p.current_pct = 9.5
    fired = check_milestones(p, webhook=None)
    assert fired == []
    assert p.milestones_hit == []


def test_fires_first_milestone_at_10():
    p = _p(); p.current_pct = 10.5
    with patch("engine.scanner_bot._send_discord") as mock:
        fired = check_milestones(p, webhook="https://hook")
    assert fired == [10]
    assert p.milestones_hit == [10]
    mock.assert_called_once()


def test_fires_multiple_milestones_when_jumping():
    p = _p(); p.current_pct = 22.0  # straight to 22 → 10, 15, 20 all fire
    with patch("engine.scanner_bot._send_discord") as mock:
        fired = check_milestones(p, webhook="https://hook")
    assert fired == [10, 15, 20]
    assert p.milestones_hit == [10, 15, 20]
    assert mock.call_count == 3


def test_already_hit_doesnt_re_fire():
    p = _p(milestones=[10, 15]); p.current_pct = 16.0
    with patch("engine.scanner_bot._send_discord") as mock:
        fired = check_milestones(p, webhook="https://hook")
    assert fired == []
    mock.assert_not_called()


def test_retracement_keeps_hit_status():
    p = _p(milestones=[10, 15]); p.current_pct = 12.0  # dropped back below 15
    with patch("engine.scanner_bot._send_discord") as mock:
        fired = check_milestones(p, webhook="https://hook")
    assert fired == []
    assert p.milestones_hit == [10, 15]
    mock.assert_not_called()


def test_no_webhook_still_records_milestone():
    """Even without a webhook (e.g., in tests), milestone tracking still updates."""
    p = _p(); p.current_pct = 10.5
    fired = check_milestones(p, webhook=None)
    assert fired == [10]
    assert p.milestones_hit == [10]
