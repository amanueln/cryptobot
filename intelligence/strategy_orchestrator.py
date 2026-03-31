"""Strategy Orchestrator — routes candles to the right strategy based on market regime.

Regime -> Strategy mapping:
  RANGING:       Grid (adaptive) at 100% size — grid prints money here
  TRENDING_UP:   DCA safety orders at 75% size — buy pullbacks in uptrend
  TRENDING_DOWN: PAUSE buying, exits only at 25% size — preserve capital
  VOLATILE:      Grid (tight) at 50% size — smaller positions, wider stops
  SQUEEZE:       Prepare breakout at 50% size — limit orders above/below BB
"""

from exchange.models import Candle, Signal
from intelligence.regime_detector import RegimeDetector, MarketRegime
from strategies.base_strategy import BaseStrategy
from strategies.grid_strategy import GridStrategy
from strategies.dca_safety import DCASafetyStrategy


# Position size multipliers per regime
REGIME_SIZE_MULT = {
    MarketRegime.RANGING: 1.0,
    MarketRegime.TRENDING_UP: 0.75,
    MarketRegime.TRENDING_DOWN: 0.25,
    MarketRegime.VOLATILE: 0.5,
    MarketRegime.SQUEEZE: 0.5,
    MarketRegime.UNKNOWN: 0.0,
}


class StrategyOrchestrator(BaseStrategy):
    name = "intelligent"

    def __init__(self):
        self.pair: str = ""
        self.starting_balance: float = 3000.0
        self.detector: RegimeDetector | None = None
        self.grid_strategy: GridStrategy | None = None
        self.dca_strategy: DCASafetyStrategy | None = None
        self._current_regime = MarketRegime.UNKNOWN
        self._prev_regime = MarketRegime.UNKNOWN
        self._regime_changes: list[dict] = []
        self._candles_processed: int = 0

    def configure(self, config: dict) -> None:
        """Configure from a single config dict containing all sub-configs."""
        self.pair = config["pair"]
        self.starting_balance = float(config.get("starting_balance", 3000))
        self._init_from_configs(
            pair=self.pair,
            detector_config=config.get("detector", {}),
            grid_config=config.get("grid", {}),
            dca_config=config.get("dca"),
            starting_balance=self.starting_balance,
        )

    def _init_from_configs(
        self,
        pair: str,
        detector_config: dict,
        grid_config: dict,
        dca_config: dict | None = None,
        starting_balance: float = 3000.0,
    ):
        self.pair = pair
        self.starting_balance = starting_balance

        # Regime detector
        self.detector = RegimeDetector(detector_config)

        # Strategies — pre-configured, selected by regime
        self.grid_strategy = GridStrategy()
        self.grid_strategy.configure(grid_config)

        self.dca_strategy: DCASafetyStrategy | None = None
        if dca_config:
            self.dca_strategy = DCASafetyStrategy()
            self.dca_strategy.configure(dca_config)

        # State
        self._current_regime: MarketRegime = MarketRegime.UNKNOWN
        self._prev_regime: MarketRegime = MarketRegime.UNKNOWN
        self._regime_changes: list[dict] = []
        self._candles_processed: int = 0

    def on_candle(self, candle: Candle) -> list[Signal]:
        """Process candle: detect regime, route to appropriate strategy, scale signals."""
        self._candles_processed += 1

        # Step 1: Detect regime BEFORE running any strategy
        self._prev_regime = self._current_regime
        self._current_regime = self.detector.update(candle)

        # Inject ADX/RSI snapshot into grid strategy for trade annotations
        if self.detector and self.grid_strategy:
            self.grid_strategy._last_adx = self.detector._last_adx or 0.0
            self.grid_strategy._last_rsi = self.detector._last_rsi or 0.0

        # Log regime changes
        if self._current_regime != self._prev_regime and self._prev_regime != MarketRegime.UNKNOWN:
            self._regime_changes.append({
                "candle": self._candles_processed,
                "from": self._prev_regime.value,
                "to": self._current_regime.value,
                "timestamp": candle.timestamp.isoformat(),
            })

        # Step 2: Route to strategy based on regime
        signals = self._route_to_strategy(candle)

        # Step 3: Scale signal sizes based on regime
        size_mult = REGIME_SIZE_MULT.get(self._current_regime, 0.5)
        scaled_signals = self._scale_signals(signals, size_mult)

        return scaled_signals

    def _route_to_strategy(self, candle: Candle) -> list[Signal]:
        """Select which strategy processes this candle based on regime."""
        regime = self._current_regime

        if regime == MarketRegime.UNKNOWN:
            # During warmup, feed candles to all strategies but don't trade
            self.grid_strategy.on_candle(candle)
            if self.dca_strategy:
                self.dca_strategy.on_candle(candle)
            return []

        if regime == MarketRegime.RANGING:
            # Grid is king in ranging markets
            return self.grid_strategy.on_candle(candle)

        if regime == MarketRegime.TRENDING_UP:
            # DCA safety orders — buy pullbacks in uptrend
            if self.dca_strategy:
                return self.dca_strategy.on_candle(candle)
            # Fallback to grid if no DCA configured
            return self.grid_strategy.on_candle(candle)

        if regime == MarketRegime.TRENDING_DOWN:
            # Sell-only mode — only process sells from existing positions
            signals = self.grid_strategy.on_candle(candle)
            return [s for s in signals if s.action == "sell"]

        if regime == MarketRegime.VOLATILE:
            # Grid with reduced size (scaling handled in step 3)
            return self.grid_strategy.on_candle(candle)

        if regime == MarketRegime.SQUEEZE:
            # Feed to grid but let the scaling handle reduced exposure
            return self.grid_strategy.on_candle(candle)

        return []

    def _scale_signals(self, signals: list[Signal], multiplier: float) -> list[Signal]:
        """Scale position sizes by regime multiplier."""
        if multiplier >= 1.0:
            return signals

        scaled = []
        for signal in signals:
            # ATR-based sizing from the detector
            detector_size = self.detector.calc_position_size(
                self.starting_balance, signal.price
            )

            new_signal = Signal(
                action=signal.action,
                pair=signal.pair,
                price=signal.price,
                order_type=signal.order_type,
                amount_usd=(signal.amount_usd * multiplier) if signal.amount_usd else None,
                amount_crypto=(signal.amount_crypto * multiplier) if signal.amount_crypto else None,
                limit_price=signal.limit_price,
                reason=f"[{self._current_regime.value}] {signal.reason}",
                regime=signal.regime,
                adx=signal.adx,
                rsi=signal.rsi,
                atr_multiplier=signal.atr_multiplier,
            )
            scaled.append(new_signal)
        return scaled

    def get_state(self) -> dict:
        return {
            "regime": self._current_regime.value,
            "prev_regime": self._prev_regime.value,
            "regime_changes": len(self._regime_changes),
            "recent_changes": self._regime_changes[-5:] if self._regime_changes else [],
            "candles_processed": self._candles_processed,
            "detector": self.detector.get_state(),
            "grid_state": self.grid_strategy.get_state(),
        }
