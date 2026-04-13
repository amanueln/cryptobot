from __future__ import annotations

"""Early Momentum Scanner — detects coins starting big moves for manual trading.

Fetches live hourly candles directly from the Coinbase public API (no local DB needed).

Multi-signal detection (validated via VVV-USD backtesting: 76% win rate):
  - Volume spike (2.5x avg) with price rising (+1% 1h) => score 2
  - New 72h high breakout with 3h momentum > 3%     => score 2
  - Momentum reversal (flat/down -> +3% in 3h)       => score 1
  - Strong 3h move (>5%)                             => score 1

Requires score >= 2 to fire an alert.  8h min gap between alerts per pair.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

# Detection thresholds (validated by simulation)
VOL_SPIKE_MULT = 2.5       # volume must be 2.5x the 24h average
PRICE_RISE_1H = 0.01       # +1% in last hour for volume spike signal
BREAKOUT_LOOKBACK_H = 72   # 72h high breakout
MOM_3H_THRESH = 0.03       # +3% in 3 hours
STRONG_MOVE_3H = 0.05      # +5% in 3 hours
MIN_SCORE = 2              # minimum combined score to save alert to DB
DISCORD_MIN_SCORE = 3      # minimum score to send Discord notification
ALERT_COOLDOWN_H = 8       # hours between alerts for same pair
MIN_VOLUME_24H = 300_000   # $300K daily volume floor
MIN_PRICE = 0.01           # skip sub-penny coins
VOL_AVG_WINDOW = 24        # hours for volume average

# Coinbase public API
CANDLE_URL = "https://api.coinbase.com/api/v3/brokerage/market/products"

# Stablecoins — never alert on these
STABLECOINS = {'USDT-USD', 'USDC-USD', 'DAI-USD', 'PYUSD-USD', 'GUSD-USD',
               'BUSD-USD', 'USDP-USD', 'TUSD-USD', 'CBETH-USD', 'PAXG-USD',
               'WBTC-USD', 'STETH-USD'}

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "candles.db")


def _generate_ai_take(coin: str, score: int, range_pct: float, change_1h: float,
                      change_3h: float, vol_24h: float, alert_type: str,
                      signals: list) -> tuple[str, str]:
    """Generate an AI-style analysis for a Discord alert.

    Returns (verdict_line, ai_take) where verdict_line is the bold header
    and ai_take is a 2-3 sentence opinion.
    """
    signal_tags = [s.split(' ')[0] for s in signals]
    has_accumulation = 'accumulation' in signal_tags
    has_squeeze = 'squeeze' in signal_tags
    has_bounce = 'bottom_bounce' in signal_tags
    has_vol_spike = 'vol_spike' in signal_tags
    has_breakout = '72h_breakout' in signal_tags
    has_reversal = 'mom_reversal' in signal_tags

    vol_strong = vol_24h >= 1_000_000
    vol_decent = vol_24h >= 500_000
    price_moving = abs(change_1h) >= 1.0 or abs(change_3h) >= 2.0
    price_flat = abs(change_1h) < 0.5 and abs(change_3h) < 1.0

    parts = []

    # --- Setup-type alerts ---
    if alert_type == 'setup':
        if has_accumulation and has_squeeze and range_pct <= 15:
            verdict = f"Strong setup -- {coin} coiling near the bottom with volume building"
            parts.append(f"Price is at just {range_pct:.0f}% of its 72h range with volume picking up while price stays flat -- that's typically smart money loading before a move.")
            if vol_strong:
                parts.append("Liquidity is solid so entries and exits should be clean.")
            elif vol_decent:
                parts.append("Decent volume to work with.")
            else:
                parts.append(f"Volume is on the thin side (${vol_24h:,.0f}) so use small size and wide stops.")
            parts.append("Watch for the first green 1h candle with above-average volume -- that's your confirmation to enter.")

        elif has_accumulation and price_flat:
            verdict = f"Accumulation detected -- {coin} volume building near bottom"
            if range_pct <= 10:
                parts.append(f"Sitting at {range_pct:.0f}% of 72h range with volume picking up. This is the kind of early setup that can lead to a strong move.")
            else:
                parts.append(f"At {range_pct:.0f}% of 72h range with volume increasing. Could be accumulation before a breakout.")
            if price_flat:
                parts.append("Price hasn't moved yet though -- need to see an actual uptick before committing money.")
            parts.append("Eyes on, not hands on yet.")

        elif has_bounce:
            verdict = f"Bottom bounce -- {coin} showing first signs of life"
            parts.append(f"First green candle after sitting near the 72h low ({range_pct:.0f}% of range).")
            if change_3h <= -5:
                parts.append(f"Careful though -- 3h trend is still {change_3h:+.1f}% which means this was dumping hard and just ticked up. Could be a dead cat bounce. Don't catch the knife.")
            elif has_squeeze:
                parts.append("Range has been compressing too, so when it moves it could move fast.")
            parts.append("Wait for a second green candle to confirm it's not just noise.")

        elif has_squeeze:
            verdict = f"Compression squeeze -- {coin} range tightening near bottom"
            parts.append(f"Price range is narrowing at {range_pct:.0f}% of 72h range. Historically this leads to a sharp move in one direction.")
            parts.append("No directional confirmation yet -- this is a watchlist add, not a buy signal.")

        else:
            verdict = f"Setup forming -- {coin} showing early signs near bottom"
            parts.append(f"At {range_pct:.0f}% of 72h range with {score}/4 signals firing.")
            parts.append("Watch for follow-through before entering.")

    # --- Breakout-type alerts ---
    else:
        if has_vol_spike and has_breakout:
            verdict = f"Breakout with volume -- {coin} breaking out on heavy buying"
            parts.append(f"New 72h high with a volume spike -- this is the real deal when it happens at {range_pct:.0f}% of range.")
            if change_3h > 10:
                parts.append(f"Already +{change_3h:.1f}% in 3h though. Don't chase -- set a limit order below current price and let it come to you.")
            else:
                parts.append(f"Only +{change_3h:.1f}% in 3h so you're still early if you act now.")

        elif has_vol_spike:
            verdict = f"Volume spike -- {coin} unusual buying detected"
            parts.append(f"Volume just spiked hard with price rising. At {range_pct:.0f}% of 72h range there's room to run.")
            if price_moving:
                parts.append(f"Already moving (+{change_1h:.1f}% 1h) -- act quick or wait for a pullback.")
            else:
                parts.append("Price is just starting to react. Good window if it holds.")

        elif has_breakout:
            verdict = f"72h breakout -- {coin} hitting new highs"
            parts.append(f"Just broke above the 72h high with +{change_3h:.1f}% momentum over 3h.")
            if has_reversal:
                parts.append("This is a reversal breakout -- was flat/down, now pushing up. These can be powerful.")
            parts.append("Confirmation is the next 1h candle closing above this level.")

        elif has_reversal:
            verdict = f"Momentum reversal -- {coin} flipping from down to up"
            parts.append(f"Was flat or falling, now +{change_3h:.1f}% in 3h. At {range_pct:.0f}% of range there's room if this continues.")
            parts.append("These can be fakeouts. Wait for a volume confirmation candle before sizing in.")

        else:
            verdict = f"Move detected -- {coin} showing momentum"
            parts.append(f"Multiple signals firing at {range_pct:.0f}% of 72h range.")
            parts.append("Watch the next 1-2 hours for confirmation before entering.")

    # Global warning: if 3h trend is heavily negative on any alert type, flag it
    if change_3h <= -5 and 'knife' not in ' '.join(parts):
        parts.append(f"Note: 3h trend is {change_3h:+.1f}% so this is still falling. Be extra cautious -- a single green candle doesn't reverse a dump.")

    ai_take = " ".join(parts)
    return verdict, ai_take


def _init_table(db_path: str):
    """Create the early_scanner_alerts table if it doesn't exist."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS early_scanner_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pair TEXT NOT NULL,
            price REAL NOT NULL,
            score INTEGER NOT NULL,
            signals TEXT NOT NULL,
            volume_24h REAL,
            change_1h_pct REAL,
            change_3h_pct REAL,
            notified INTEGER DEFAULT 0,
            outcome_12h_pct REAL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_esa_pair_ts
        ON early_scanner_alerts (pair, timestamp)
    """)
    conn.commit()
    conn.close()


def _fetch_candles_live(pair: str, hours: int = 76) -> list[dict] | None:
    """Fetch hourly candles directly from the Coinbase public API.

    Returns list of dicts with keys: close, high, volume, sorted oldest-first.
    Returns None on failure.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    url = f"{CANDLE_URL}/{pair}/candles"
    params = {
        "start": str(int(start.timestamp())),
        "end": str(int(now.timestamp())),
        "granularity": "ONE_HOUR",
    }
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                wait = 2 ** attempt + 1  # 1s, 3s, 5s
                logger.debug("Rate limited on %s, waiting %ds", pair, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw = resp.json().get("candles", [])
            if not raw:
                return None
            # Coinbase returns newest first — reverse to oldest first
            candles = []
            for c in reversed(raw):
                candles.append({
                    'close': float(c['close']),
                    'high': float(c['high']),
                    'volume': float(c['volume']),
                })
            return candles
        except Exception as e:
            logger.debug("Failed to fetch candles for %s: %s", pair, e)
            return None
    return None


class EarlyScanner:
    """Scans all Coinbase USD pairs for early momentum signals using live data."""

    def __init__(self, db_path: str = DB_PATH, discord_webhook: str | None = None):
        self.db_path = os.path.abspath(db_path)
        self.discord_webhook = discord_webhook
        _init_table(self.db_path)
        self._last_alert_time: dict[str, datetime] = {}  # pair -> last alert time
        self._load_recent_alerts()

    def _load_recent_alerts(self):
        """Load recent alert times from DB to restore cooldowns across restarts."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=ALERT_COOLDOWN_H)).isoformat()
            rows = conn.execute(
                "SELECT pair, MAX(timestamp) FROM early_scanner_alerts "
                "WHERE timestamp > ? GROUP BY pair", (cutoff,)
            ).fetchall()
            for pair, ts in rows:
                try:
                    self._last_alert_time[pair] = datetime.fromisoformat(ts)
                except Exception:
                    pass
            conn.close()
        except Exception:
            pass

    def scan(self) -> list[dict]:
        """Run a full scan across all Coinbase USD pairs. Returns new alerts."""
        logger.info("Early scanner: starting scan")
        now = datetime.now(timezone.utc)

        # Step 1: Get all products from Coinbase
        try:
            r = requests.get(
                'https://api.coinbase.com/api/v3/brokerage/market/products',
                timeout=15,
            )
            products = r.json().get('products', [])
        except Exception as e:
            logger.error("Early scanner: failed to fetch products: %s", e)
            return []

        # Step 2: Filter to eligible pairs
        eligible = []
        for p in products:
            if p.get('quote_currency_id') != 'USD' or p.get('status') != 'online':
                continue
            pair = p['product_id']
            if pair in STABLECOINS:
                continue
            try:
                price = float(p.get('price', 0))
                vol_24h = float(p.get('volume_24h', 0)) * price
            except (ValueError, TypeError):
                continue
            if price < MIN_PRICE or vol_24h < MIN_VOLUME_24H:
                continue
            base_name = p.get('base_name', '')
            eligible.append({'pair': pair, 'price': price, 'volume_24h': vol_24h, 'base_name': base_name})

        logger.info("Early scanner: %d eligible pairs to check", len(eligible))

        # Step 3: Fetch live candles and check each pair for signals
        alerts = []
        checked = 0

        for item in eligible:
            pair = item['pair']

            # Cooldown check
            last = self._last_alert_time.get(pair)
            if last and (now - last).total_seconds() < ALERT_COOLDOWN_H * 3600:
                continue

            # Fetch live candles from Coinbase
            candles = _fetch_candles_live(pair, hours=76)
            if not candles or len(candles) < 24:
                continue

            checked += 1
            try:
                alert = self._check_pair(candles, pair, item['price'], item['volume_24h'], now)
                if alert:
                    alert['base_name'] = item.get('base_name', '')
                    alerts.append(alert)
                    self._last_alert_time[pair] = now
            except Exception as e:
                logger.debug("Early scanner: error checking %s: %s", pair, e)

            # Rate limit: 250ms between API calls to stay under Coinbase limits
            time.sleep(0.25)

        logger.info("Early scanner: checked %d pairs, %d new alerts", checked, len(alerts))

        # Step 4: Save alerts to DB and notify
        if alerts:
            self._save_alerts(alerts)
            for a in alerts:
                if a['score'] >= DISCORD_MIN_SCORE:
                    self._notify_discord(a)

        return alerts

    def _check_pair(self, candles: list[dict], pair: str, price: float,
                    vol_24h: float, now: datetime) -> dict | None:
        """Check a single pair for early momentum signals using live candle data."""
        closes = [c['close'] for c in candles]
        volumes = [c['volume'] for c in candles]
        highs = [c['high'] for c in candles]

        cur_price = closes[-1]
        if cur_price <= 0:
            return None

        # Where is price in its 72h range?
        low_72h = min(closes)
        high_72h = max(closes)
        range_pct = ((cur_price - low_72h) / (high_72h - low_72h) * 100) if high_72h > low_72h else 50

        score = 0
        signals = []
        alert_type = 'move'  # 'setup' for early accumulation, 'move' for breakout

        # ============================================================
        # EARLY SETUP SIGNALS (catch BEFORE the move)
        # ============================================================

        # Signal A: Accumulation — volume building near range bottom (score = 2)
        # This is the "$0.075 alert" — volume picking up while price is still low
        if len(volumes) >= VOL_AVG_WINDOW + 4 and range_pct <= 30:
            vol_avg = sum(volumes[-VOL_AVG_WINDOW - 4:-4]) / VOL_AVG_WINDOW
            # Average volume of last 3 candles
            recent_vol_avg = sum(volumes[-3:]) / 3
            price_flat = abs(closes[-1] - closes[-4]) / closes[-4] < 0.02 if closes[-4] > 0 else True

            if vol_avg > 0 and recent_vol_avg >= 1.8 * vol_avg and price_flat:
                score += 2
                alert_type = 'setup'
                signals.append(f"accumulation (vol {recent_vol_avg / vol_avg:.1f}x avg, price flat near bottom at {range_pct:.0f}%)")

        # Signal B: Range bottom bounce — price near 72h low + first green candle (score = 2)
        if len(closes) >= 3 and range_pct <= 25:
            # Price was falling or flat, now ticking up
            prev_change = (closes[-2] - closes[-3]) / closes[-3] if closes[-3] > 0 else 0
            cur_change = (cur_price - closes[-2]) / closes[-2] if closes[-2] > 0 else 0
            if prev_change <= 0.005 and cur_change >= 0.005:
                score += 2
                alert_type = 'setup'
                signals.append(f"bottom_bounce (range {range_pct:.0f}%, first uptick +{cur_change * 100:.1f}%)")

        # Signal C: Compression squeeze — range tightening (score = 1)
        # Price range of last 6h is much smaller than last 24h = coiling for a move
        if len(closes) >= 24:
            range_24h = max(closes[-24:]) - min(closes[-24:])
            range_6h = max(closes[-6:]) - min(closes[-6:])
            if range_24h > 0 and range_6h / range_24h < 0.25 and range_pct <= 40:
                score += 1
                alert_type = 'setup'
                signals.append(f"squeeze (6h range is {range_6h / range_24h * 100:.0f}% of 24h range)")

        # ============================================================
        # BREAKOUT SIGNALS (catch the first candle of the move)
        # ============================================================

        # Signal 1: Volume spike with price rising (score = 2)
        # Only if still in the lower half of the range — not already pumped
        if len(volumes) >= VOL_AVG_WINDOW + 1 and range_pct <= 50:
            vol_avg = sum(volumes[-VOL_AVG_WINDOW - 1:-1]) / VOL_AVG_WINDOW
            cur_vol = volumes[-1]
            price_1h_ago = closes[-2] if len(closes) >= 2 else cur_price
            change_1h = (cur_price - price_1h_ago) / price_1h_ago if price_1h_ago > 0 else 0

            if vol_avg > 0 and cur_vol >= VOL_SPIKE_MULT * vol_avg and change_1h >= PRICE_RISE_1H:
                score += 2
                signals.append(f"vol_spike ({cur_vol / vol_avg:.1f}x avg, +{change_1h * 100:.1f}% 1h)")

        # Signal 2: New 72h high breakout with 3h momentum (score = 2)
        # Only if price hasn't already run too far (< 85% of range)
        if len(closes) >= 4 and len(highs) >= 72 and range_pct <= 85:
            high_72h_prev = max(highs[:-1])  # exclude current candle
            price_3h_ago = closes[-4]
            mom_3h = (cur_price - price_3h_ago) / price_3h_ago if price_3h_ago > 0 else 0

            if cur_price > high_72h_prev and mom_3h >= MOM_3H_THRESH:
                score += 2
                signals.append(f"72h_breakout (new high ${cur_price:.4f}, +{mom_3h * 100:.1f}% 3h)")

        # Signal 3: Momentum reversal — was flat/down, now +3% in 3h (score = 1)
        if len(closes) >= 7:
            price_6h_ago = closes[-7]
            price_3h_ago = closes[-4]
            prev_3h_change = (price_3h_ago - price_6h_ago) / price_6h_ago if price_6h_ago > 0 else 0
            cur_3h_change = (cur_price - price_3h_ago) / price_3h_ago if price_3h_ago > 0 else 0

            if prev_3h_change <= 0.005 and cur_3h_change >= MOM_3H_THRESH:
                score += 1
                signals.append(f"mom_reversal (was {prev_3h_change * 100:+.1f}%, now +{cur_3h_change * 100:.1f}%)")

        # Signal 4: Strong 3h move > 5% (score = 1)
        # Only count if still in lower half of range
        if len(closes) >= 4 and range_pct <= 50:
            price_3h_ago = closes[-4]
            change_3h = (cur_price - price_3h_ago) / price_3h_ago if price_3h_ago > 0 else 0

            if change_3h >= STRONG_MOVE_3H:
                score += 1
                signals.append(f"strong_move (+{change_3h * 100:.1f}% in 3h)")

        if score < MIN_SCORE:
            return None

        # Compute stats for the alert
        change_1h = 0
        if len(closes) >= 2:
            change_1h = (cur_price - closes[-2]) / closes[-2] * 100 if closes[-2] > 0 else 0
        change_3h = 0
        if len(closes) >= 4:
            change_3h = (cur_price - closes[-4]) / closes[-4] * 100 if closes[-4] > 0 else 0

        return {
            'timestamp': now.isoformat(),
            'pair': pair,
            'price': cur_price,
            'score': score,
            'signals': signals,
            'volume_24h': vol_24h,
            'change_1h_pct': round(change_1h, 2),
            'change_3h_pct': round(change_3h, 2),
            'range_pct': round(range_pct, 0),
            'low_72h': low_72h,
            'high_72h': high_72h,
            'alert_type': alert_type,
        }

    def _save_alerts(self, alerts: list[dict]):
        """Persist alerts to the database."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        now = datetime.now(timezone.utc).isoformat()
        for a in alerts:
            conn.execute(
                "INSERT INTO early_scanner_alerts "
                "(timestamp, pair, price, score, signals, volume_24h, change_1h_pct, change_3h_pct, notified, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,0,?)",
                (a['timestamp'], a['pair'], a['price'], a['score'],
                 json.dumps(a['signals']), a['volume_24h'],
                 a['change_1h_pct'], a['change_3h_pct'], now),
            )
        conn.commit()
        conn.close()

    def _notify_discord(self, alert: dict):
        """Send a Discord webhook notification for an alert."""
        if not self.discord_webhook:
            return
        try:
            coin = alert['pair'].replace('-USD', '')
            # Build simple Coinbase URL using full coin name slug
            base_name = alert.get('base_name', '')
            if base_name:
                slug = base_name.lower().replace(' ', '-').replace('.', '-')
                coinbase_url = f"https://www.coinbase.com/price/{slug}"
            else:
                coinbase_url = f"https://www.coinbase.com/trade/{alert['pair']}"

            # AI-style analysis based on the numbers
            score = alert['score']
            range_pct = alert.get('range_pct', 50)
            change_1h = alert['change_1h_pct']
            change_3h = alert['change_3h_pct']
            vol_24h = alert['volume_24h']
            alert_type = alert.get('alert_type', 'move')

            verdict, ai_take = _generate_ai_take(
                coin, score, range_pct, change_1h, change_3h, vol_24h, alert_type,
                alert.get('signals', []),
            )

            # Color based on conviction
            if 'watch closely' in verdict.lower() or 'strong setup' in verdict.lower():
                color = 0x00ff88  # green
            elif 'wait' in verdict.lower() or 'need to see' in verdict.lower():
                color = 0xffaa00  # amber
            else:
                color = 0x38bdf8  # blue

            # Human-readable signal names
            signal_names = []
            for s in alert['signals']:
                tag = s.split(' ')[0]
                labels = {
                    'vol_spike': 'Volume Spike',
                    '72h_breakout': '72h High Breakout',
                    'mom_reversal': 'Momentum Reversal',
                    'strong_move': 'Strong 3h Move',
                    'accumulation': 'Accumulation',
                    'bottom_bounce': 'Bottom Bounce',
                    'squeeze': 'Compression Squeeze',
                }
                signal_names.append(labels.get(tag, tag))

            low = alert.get('low_72h', 0)
            high = alert.get('high_72h', 0)

            if alert_type == 'setup':
                title = f"👀 {coin} -- setup forming near bottom"
            elif range_pct >= 70:
                title = f"⚠️ {coin} already pumped"
            else:
                title = f"🟢 {coin} breakout starting"

            embed = {
                "title": title,
                "description": (
                    f"**{verdict}**\n\n"
                    f"**Price now:** ${alert['price']:.4f}\n"
                    f"**1h change:** {alert['change_1h_pct']:+.1f}%  |  "
                    f"**3h change:** {alert['change_3h_pct']:+.1f}%\n"
                    f"**24h volume:** ${alert['volume_24h']:,.0f}\n\n"
                    f"**72h range:** ${low:.4f} - ${high:.4f} "
                    f"(price at **{range_pct:.0f}%** of range)\n\n"
                    f"**Signals:** {' + '.join(signal_names)} "
                    f"({score}/4 confidence)\n\n"
                    f"**AI Take:** {ai_take}\n\n"
                    f"[Open on Coinbase]({coinbase_url})"
                ),
                "color": color,
                "timestamp": alert['timestamp'],
                "footer": {"text": "CryptoBot Early Scanner -- for manual trading, not financial advice"},
            }

            requests.post(
                self.discord_webhook,
                json={"embeds": [embed]},
                timeout=10,
            )
            logger.info("Discord notification sent for %s", alert['pair'])

            # Mark as notified
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute(
                "UPDATE early_scanner_alerts SET notified = 1 "
                "WHERE pair = ? AND timestamp = ?",
                (alert['pair'], alert['timestamp']),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Discord notification failed: %s", e)

    def get_recent_alerts(self, limit: int = 50) -> list[dict]:
        """Get recent alerts from DB."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM early_scanner_alerts ORDER BY score DESC, timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {
                'id': r['id'],
                'timestamp': r['timestamp'],
                'pair': r['pair'],
                'price': r['price'],
                'score': r['score'],
                'signals': json.loads(r['signals']),
                'volume_24h': r['volume_24h'],
                'change_1h_pct': r['change_1h_pct'],
                'change_3h_pct': r['change_3h_pct'],
                'notified': bool(r['notified']),
                'outcome_12h_pct': r['outcome_12h_pct'],
            }
            for r in rows
        ]

    def get_stats(self) -> dict:
        """Get scanner statistics."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        total = conn.execute("SELECT COUNT(*) FROM early_scanner_alerts").fetchone()[0]
        last_24h = conn.execute(
            "SELECT COUNT(*) FROM early_scanner_alerts WHERE timestamp > ?",
            ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),),
        ).fetchone()[0]
        evaluated = conn.execute(
            "SELECT COUNT(*) FROM early_scanner_alerts WHERE outcome_12h_pct IS NOT NULL"
        ).fetchone()[0]
        wins = conn.execute(
            "SELECT COUNT(*) FROM early_scanner_alerts WHERE outcome_12h_pct > 0"
        ).fetchone()[0]
        conn.close()
        return {
            'total_alerts': total,
            'alerts_24h': last_24h,
            'evaluated': evaluated,
            'wins': wins,
            'win_rate': round(wins / evaluated * 100, 1) if evaluated > 0 else 0,
        }

    def evaluate_outcomes(self):
        """Check 12h outcomes for alerts old enough. Fetches live candle to compare."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        unevaluated = conn.execute(
            "SELECT id, pair, price, timestamp FROM early_scanner_alerts "
            "WHERE outcome_12h_pct IS NULL AND timestamp < ?",
            (cutoff,),
        ).fetchall()

        for row in unevaluated:
            try:
                # Fetch current price from Coinbase
                candles = _fetch_candles_live(row['pair'], hours=2)
                if candles:
                    current = candles[-1]['close']
                    outcome = (current - row['price']) / row['price'] * 100
                    conn.execute(
                        "UPDATE early_scanner_alerts SET outcome_12h_pct = ? WHERE id = ?",
                        (round(outcome, 2), row['id']),
                    )
                time.sleep(0.1)
            except Exception:
                continue

        conn.commit()
        conn.close()
