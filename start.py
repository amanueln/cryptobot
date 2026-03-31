"""Single entry point for Docker deployment.

Runs both the bot (sim_runner) and Flask dashboard in separate processes.
Handles SIGHUP for graceful restart after git pull, SIGTERM for shutdown.
"""

import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("models", exist_ok=True)

LOG_FILE = "logs/bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("start")

# ---------------------------------------------------------------------------
# Global state shared between processes
# ---------------------------------------------------------------------------

_start_time = datetime.now()
_bot_process: multiprocessing.Process | None = None
_flask_process: multiprocessing.Process | None = None
_update_process: multiprocessing.Process | None = None


# ---------------------------------------------------------------------------
# Bot process
# ---------------------------------------------------------------------------

def run_bot(use_ml: bool = False):
    """Run the sim_runner polling loop."""
    from sim_runner import build_runner
    logger.info("Bot process starting (ML=%s)", use_ml)
    runner = build_runner(poll_seconds=60, warmup_days=30, use_ml=use_ml)
    runner.run()


# ---------------------------------------------------------------------------
# Flask process
# ---------------------------------------------------------------------------

def run_flask():
    """Run the Flask dashboard API."""
    logger.info("Flask process starting on 0.0.0.0:5001")
    from dashboard.api.app import app
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)


# ---------------------------------------------------------------------------
# Auto-update process
# ---------------------------------------------------------------------------

def run_auto_update(interval_seconds: int = 21600):
    """Periodically check for updates from git remote."""
    logger.info("Auto-update process starting (interval=%ds)", interval_seconds)
    while True:
        time.sleep(interval_seconds)
        try:
            result = subprocess.run(
                ["bash", "/app/scripts/auto_update.sh"],
                capture_output=True, text=True, timeout=120,
                env={**os.environ},
            )
            if result.stdout.strip():
                logger.info("Auto-update: %s", result.stdout.strip())
            if result.stderr.strip():
                logger.warning("Auto-update stderr: %s", result.stderr.strip())
        except Exception as e:
            logger.error("Auto-update failed: %s", e)


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

def _handle_sighup(signum, frame):
    """SIGHUP = graceful restart (after git pull)."""
    global _bot_process
    logger.info("SIGHUP received — restarting bot process")
    if _bot_process and _bot_process.is_alive():
        _bot_process.terminate()
        _bot_process.join(timeout=10)
    use_ml = os.environ.get("USE_ML", "false").lower() in ("true", "1", "yes")
    _bot_process = multiprocessing.Process(target=run_bot, args=(use_ml,), daemon=True)
    _bot_process.start()
    logger.info("Bot process restarted (pid=%d)", _bot_process.pid)


def _handle_sigterm(signum, frame):
    """SIGTERM = graceful shutdown."""
    logger.info("SIGTERM received — shutting down")
    for proc in [_bot_process, _flask_process, _update_process]:
        if proc and proc.is_alive():
            proc.terminate()
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _bot_process, _flask_process, _update_process

    logger.info("=" * 50)
    logger.info("CryptoBot starting")
    logger.info("=" * 50)

    # Save PID for auto-update restart
    with open("/tmp/cryptobot.pid", "w") as f:
        f.write(str(os.getpid()))

    # Register signal handlers (Unix only)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _handle_sighup)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    mode = os.environ.get("BOT_MODE", "simulate")
    use_ml = os.environ.get("USE_ML", "false").lower() in ("true", "1", "yes")

    logger.info("Mode: %s | ML: %s", mode, use_ml)

    # 1. Start Flask dashboard
    _flask_process = multiprocessing.Process(target=run_flask, daemon=True)
    _flask_process.start()
    logger.info("Flask started (pid=%d)", _flask_process.pid)

    # 2. Start bot
    _bot_process = multiprocessing.Process(target=run_bot, args=(use_ml,), daemon=True)
    _bot_process.start()
    logger.info("Bot started (pid=%d)", _bot_process.pid)

    # 3. Start auto-update checker
    interval_str = os.environ.get("AUTO_UPDATE_INTERVAL", "6h")
    interval_secs = _parse_interval(interval_str)
    if interval_secs > 0:
        _update_process = multiprocessing.Process(
            target=run_auto_update, args=(interval_secs,), daemon=True,
        )
        _update_process.start()
        logger.info("Auto-update started (interval=%s, pid=%d)", interval_str, _update_process.pid)

    logger.info("All processes running. Dashboard at http://0.0.0.0:5001")

    # Keep main process alive, restart children if they die
    try:
        while True:
            time.sleep(30)
            if _bot_process and not _bot_process.is_alive():
                logger.warning("Bot process died (exit=%s) — restarting", _bot_process.exitcode)
                _bot_process = multiprocessing.Process(target=run_bot, args=(use_ml,), daemon=True)
                _bot_process.start()
            if _flask_process and not _flask_process.is_alive():
                logger.warning("Flask process died (exit=%s) — restarting", _flask_process.exitcode)
                _flask_process = multiprocessing.Process(target=run_flask, daemon=True)
                _flask_process.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")
    finally:
        for proc in [_bot_process, _flask_process, _update_process]:
            if proc and proc.is_alive():
                proc.terminate()


def _parse_interval(s: str) -> int:
    """Parse interval string like '6h', '30m', '1d' to seconds."""
    s = s.strip().lower()
    if s.endswith("h"):
        return int(s[:-1]) * 3600
    if s.endswith("m"):
        return int(s[:-1]) * 60
    if s.endswith("d"):
        return int(s[:-1]) * 86400
    if s.endswith("s"):
        return int(s[:-1])
    return int(s)


if __name__ == "__main__":
    main()
