from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


def test_get_candles_calls_sdk():
    from exchange.coinbase_client import CoinbaseClient

    mock_candle = {
        "start": str(int(datetime(2026, 1, 1, 0, 0).timestamp())),
        "open": "85000",
        "high": "85500",
        "low": "84800",
        "close": "85200",
        "volume": "123.45",
    }

    with patch("exchange.coinbase_client.RESTClient") as MockClient:
        instance = MockClient.return_value
        instance.get_candles.return_value = {"candles": [mock_candle]}

        client = CoinbaseClient()
        result = client.get_candles(
            pair="BTC-USD",
            granularity="ONE_HOUR",
            start=datetime(2026, 1, 1, 0, 0),
            end=datetime(2026, 1, 1, 1, 0),
        )

        assert len(result) == 1
        assert result[0].pair == "BTC-USD"
        assert result[0].close == 85200.0
        assert result[0].open == 85000.0


def test_get_candles_pagination():
    from exchange.coinbase_client import CoinbaseClient

    start = datetime(2026, 1, 1)
    end = start + timedelta(hours=400)

    mock_candles_batch = [
        {
            "start": str(int((start + timedelta(hours=i)).timestamp())),
            "open": "85000",
            "high": "85500",
            "low": "84800",
            "close": "85200",
            "volume": "100",
        }
        for i in range(300)
    ]

    with patch("exchange.coinbase_client.RESTClient") as MockClient:
        instance = MockClient.return_value
        instance.get_candles.side_effect = [
            {"candles": mock_candles_batch},
            {"candles": mock_candles_batch[:100]},
        ]

        client = CoinbaseClient()
        result = client.get_candles("BTC-USD", "ONE_HOUR", start, end)

        assert instance.get_candles.call_count == 2
        assert len(result) == 400


def test_get_candles_empty_response():
    from exchange.coinbase_client import CoinbaseClient

    with patch("exchange.coinbase_client.RESTClient") as MockClient:
        instance = MockClient.return_value
        instance.get_candles.return_value = {"candles": []}

        client = CoinbaseClient()
        result = client.get_candles(
            pair="BTC-USD",
            granularity="ONE_HOUR",
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 2),
        )
        assert result == []
