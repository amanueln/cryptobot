from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import requests

from exchange.models import Candle

GRANULARITY_MAP = {
    "ONE_MINUTE": timedelta(minutes=1),
    "FIVE_MINUTE": timedelta(minutes=5),
    "FIFTEEN_MINUTE": timedelta(minutes=15),
    "THIRTY_MINUTE": timedelta(minutes=30),
    "ONE_HOUR": timedelta(hours=1),
    "TWO_HOUR": timedelta(hours=2),
    "SIX_HOUR": timedelta(hours=6),
    "ONE_DAY": timedelta(days=1),
}

# Coinbase Advanced Trade API public endpoint
BASE_URL = "https://api.coinbase.com/api/v3/brokerage/market/products"

MAX_CANDLES_PER_REQUEST = 300


BOOK_URL = "https://api.coinbase.com/api/v3/brokerage/market/product_book"


class CoinbaseClient:
    # Thread-safe rate limiter: max N requests per second
    _rate_lock = threading.Lock()
    _request_times: list[float] = []
    _max_rps = 8  # stay under Coinbase's ~10 req/s public limit

    def __init__(self):
        self.session = requests.Session()

    def _rate_limit(self):
        """Block until we can make a request without exceeding rate limit."""
        while True:
            with self._rate_lock:
                now = time.monotonic()
                self._request_times = [t for t in self._request_times if now - t < 1.0]
                if len(self._request_times) < self._max_rps:
                    self._request_times.append(now)
                    return
                sleep_for = 1.0 - (now - self._request_times[0])
            # Sleep outside the lock so other threads aren't blocked
            time.sleep(max(sleep_for, 0.05))

    def get_product_book(self, pair: str, limit: int = 50) -> dict:
        """Fetch order book for a pair. Returns {bids: [(price, size)], asks: [(price, size)]}."""
        self._rate_limit()
        resp = self.session.get(
            BOOK_URL,
            params={"product_id": pair, "limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        pb = resp.json().get("pricebook", {})
        return {
            "bids": [(float(b["price"]), float(b["size"])) for b in pb.get("bids", [])],
            "asks": [(float(a["price"]), float(a["size"])) for a in pb.get("asks", [])],
        }

    def get_ticker_price(self, pair: str) -> float | None:
        """Fetch current spot price for a pair. Free, no auth needed."""
        url = f"{BASE_URL}/{pair}"
        try:
            self._rate_limit()
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return float(resp.json().get("price", 0))
        except (requests.RequestException, ValueError, KeyError):
            return None

    def get_latest_candles(self, pair: str, granularity: str, count: int = 5) -> list[Candle]:
        """Fetch the most recent N candles. Used for live polling in simulate mode."""
        interval = GRANULARITY_MAP.get(granularity, timedelta(hours=1))
        end = datetime.now()
        start = end - interval * count

        url = f"{BASE_URL}/{pair}/candles"
        params = {
            "start": str(int(start.timestamp())),
            "end": str(int(end.timestamp())),
            "granularity": granularity,
        }

        try:
            self._rate_limit()
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            return []

        candles = []
        for raw in data.get("candles", []):
            candles.append(Candle(
                pair=pair,
                granularity=granularity,
                timestamp=datetime.fromtimestamp(int(raw["start"])),
                open=float(raw["open"]),
                high=float(raw["high"]),
                low=float(raw["low"]),
                close=float(raw["close"]),
                volume=float(raw["volume"]),
            ))

        candles.sort(key=lambda c: c.timestamp)
        return candles

    def get_candles(
        self,
        pair: str,
        granularity: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        interval = GRANULARITY_MAP.get(granularity, timedelta(hours=1))
        chunk_duration = interval * MAX_CANDLES_PER_REQUEST

        all_candles: list[Candle] = []
        chunk_start = start

        while chunk_start < end:
            chunk_end = min(chunk_start + chunk_duration, end)

            url = f"{BASE_URL}/{pair}/candles"
            params = {
                "start": str(int(chunk_start.timestamp())),
                "end": str(int(chunk_end.timestamp())),
                "granularity": granularity,
            }

            self._rate_limit()
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            raw_candles = data.get("candles", [])
            if not raw_candles:
                break

            for raw in raw_candles:
                all_candles.append(Candle(
                    pair=pair,
                    granularity=granularity,
                    timestamp=datetime.fromtimestamp(int(raw["start"])),
                    open=float(raw["open"]),
                    high=float(raw["high"]),
                    low=float(raw["low"]),
                    close=float(raw["close"]),
                    volume=float(raw["volume"]),
                ))

            chunk_start = chunk_end

        all_candles.sort(key=lambda c: c.timestamp)
        return all_candles
