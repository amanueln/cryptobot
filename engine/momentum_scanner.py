from __future__ import annotations

"""Momentum Scanner — finds the best coins for momentum rotation.

Scans Coinbase for coins that meet momentum-specific criteria:
  - 24h USD volume >= $500K (liquidity floor)
  - At least 720 hourly candles available (30 days for lookback)
  - Price > $0.001 (no dust tokens)
  - NOT in the grid trading pair list (avoid collisions)
  - BTC-USD always included (needed for regime filter)

Returns a ranked list of ~30 coins by volume for the momentum engine.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta

import requests

from data.candle_store import CandleStore
from exchange.coinbase_client import CoinbaseClient

logger = logging.getLogger(__name__)

# Scanner criteria (validated by research_scanner_test.py)
MIN_VOLUME_24H = 500_000     # $500K daily volume floor
MIN_CANDLES = 720             # 30 days of hourly data
MIN_PRICE = 0.001
TARGET_UNIVERSE = 30          # top 30 by volume (sweet spot from test)
SCAN_DEPTH = 60               # scan top 60, then trim to 30

# Stablecoins — never trade these for momentum
STABLECOINS = {'USDT-USD', 'USDC-USD', 'DAI-USD', 'PYUSD-USD', 'GUSD-USD',
               'BUSD-USD', 'USDP-USD', 'TUSD-USD', 'CBETH-USD', 'PAXG-USD'}


class MomentumScanner:
    """Scans Coinbase for coins suitable for momentum rotation."""

    def __init__(self, client: CoinbaseClient, candle_store: CandleStore,
                 db_path: str = "data/candles.db"):
        self.client = client
        self.candle_store = candle_store
        self.db_path = db_path
        self.last_scan_time: datetime | None = None
        self.last_scan_results: list[dict] = []
        self.current_pairs: list[str] = []

    def scan(self, exclude_pairs: set[str] | None = None) -> list[str]:
        """Scan Coinbase and return ranked list of momentum-eligible pairs.

        Args:
            exclude_pairs: pairs to exclude (grid trading pairs)

        Returns:
            List of pair strings, e.g. ['BTC-USD', 'ETH-USD', ...]
        """
        exclude = exclude_pairs or set()
        logger.info("Momentum scanner: starting scan (excluding %d grid pairs)", len(exclude))

        # Step 1: Get all products from Coinbase
        try:
            r = requests.get('https://api.coinbase.com/api/v3/brokerage/market/products',
                             timeout=15)
            products = r.json().get('products', [])
        except Exception as e:
            logger.error("Momentum scanner: failed to fetch products: %s", e)
            return self.current_pairs  # fall back to last known good list

        # Step 2: Filter candidates
        candidates = []
        for p in products:
            if p.get('quote_currency_id') != 'USD' or p.get('status') != 'online':
                continue
            pair = p['product_id']

            # Skip stablecoins
            if pair in STABLECOINS:
                continue

            # Skip grid trading pairs
            if pair in exclude:
                continue

            try:
                vol_24h = float(p.get('volume_24h', 0)) * float(p.get('price', 0))
                price = float(p.get('price', 0))
            except (ValueError, TypeError):
                continue

            if vol_24h >= MIN_VOLUME_24H and price >= MIN_PRICE:
                candidates.append({
                    'pair': pair,
                    'volume_24h': vol_24h,
                    'price': price,
                })

        candidates.sort(key=lambda x: x['volume_24h'], reverse=True)
        candidates = candidates[:SCAN_DEPTH]

        logger.info("Momentum scanner: %d candidates above $%dK volume",
                     len(candidates), MIN_VOLUME_24H // 1000)

        # Step 3: Verify candle history for each candidate
        end = datetime.utcnow()
        start = end - timedelta(days=90)
        qualified = []

        for c in candidates:
            pair = c['pair']

            # Check cached candles first
            candles = self.candle_store.get_candles(pair, "ONE_HOUR", start, end)
            if candles and len(candles) >= MIN_CANDLES:
                qualified.append(c)
                continue

            # Fetch candles if not cached
            try:
                fetched = self.client.get_candles(pair, "ONE_HOUR", start, end)
                if fetched and len(fetched) >= MIN_CANDLES:
                    self.candle_store.save_candles(pair, "ONE_HOUR", fetched)
                    qualified.append(c)
                    logger.info("  %s: fetched %d candles OK", pair, len(fetched))
                else:
                    logger.info("  %s: only %d candles — skipped",
                                pair, len(fetched) if fetched else 0)
            except Exception as e:
                logger.warning("  %s: fetch error — %s", pair, e)
            time.sleep(0.15)  # rate limit

        # Step 4: Always include BTC-USD (needed for regime filter)
        pairs = [c['pair'] for c in qualified[:TARGET_UNIVERSE]]
        if 'BTC-USD' not in pairs:
            # BTC might be excluded as a grid pair — force it in for regime
            pairs.insert(0, 'BTC-USD')

        self.last_scan_time = datetime.utcnow()
        self.last_scan_results = qualified[:TARGET_UNIVERSE]
        self.current_pairs = pairs

        logger.info("Momentum scanner: selected %d pairs", len(pairs))
        for i, p in enumerate(pairs[:10]):
            vol = next((c['volume_24h'] for c in qualified if c['pair'] == p), 0)
            logger.info("  %2d. %-12s vol: $%.0f", i + 1, p, vol)
        if len(pairs) > 10:
            logger.info("  ... and %d more", len(pairs) - 10)

        # Persist scan info for the API to read
        self._save_scan_info()

        # Log scan event
        top_coins = ', '.join(p.replace('-USD', '') for p in pairs[:5])
        self._log_event(
            "scan_complete",
            f"Scanned {len(candidates)} coins — {len(pairs)} selected",
            f"Top by volume: {top_coins}. Excluded {len(exclude)} grid pairs.",
        )

        return pairs

    def _save_scan_info(self):
        """Write scan results to data/momentum_scan.json for the API."""
        info = self.get_scan_info()
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/momentum_scan.json", "w") as f:
                json.dump(info, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save scan info: %s", e)

    def _log_event(self, event_type: str, title: str, detail: str):
        """Write an event to the momentum_events table."""
        try:
            now = datetime.utcnow().isoformat()
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO momentum_events (timestamp, event_type, title, detail, created_at) "
                "VALUES (?,?,?,?,?)",
                (now, event_type, title, detail, now),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to log momentum event: %s", e)

    def _log_initial_equity(self, starting_balance: float):
        """Seed an initial equity snapshot so the chart has a starting point."""
        try:
            conn = sqlite3.connect(self.db_path)
            # Only seed if no equity data exists yet
            row = conn.execute("SELECT COUNT(*) FROM momentum_equity").fetchone()
            if row[0] == 0:
                conn.execute(
                    "INSERT INTO momentum_equity (timestamp, equity, cash, positions_value, status, holdings) "
                    "VALUES (?,?,?,?,?,?)",
                    (datetime.utcnow().isoformat(), starting_balance, starting_balance, 0, "scanning", "[]"),
                )
                conn.commit()
            conn.close()
        except Exception:
            pass

    def get_scan_info(self) -> dict:
        """Return scan metadata for API/dashboard."""
        return {
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "pairs_count": len(self.current_pairs),
            "pairs": self.current_pairs,
            "top_by_volume": [
                {"pair": c['pair'], "volume_24h": c['volume_24h'], "price": c['price']}
                for c in self.last_scan_results[:10]
            ],
        }
