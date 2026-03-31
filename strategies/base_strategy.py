from abc import ABC, abstractmethod

from exchange.models import Candle, Signal


class BaseStrategy(ABC):
    name: str

    @abstractmethod
    def configure(self, config: dict) -> None:
        """Load strategy params from YAML config dict."""

    @abstractmethod
    def on_candle(self, candle: Candle, warmup: bool = False) -> list[Signal]:
        """Process a new candle. Returns zero or more signals.
        When warmup=True, update indicators but skip trade logic."""

    @abstractmethod
    def get_state(self) -> dict:
        """Return current strategy state for logging/debugging."""
