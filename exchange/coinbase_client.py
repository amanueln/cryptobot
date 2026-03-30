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


class CoinbaseClient:
    def __init__(self):
        self.session = requests.Session()

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
