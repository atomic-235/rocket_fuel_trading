"""
Background trailing stop service.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from ..models.config import TradingConfig
from ..trading import HyperliquidExchange
from ..models.trading import SignalType


@dataclass
class TrailingState:
    highest_price: float
    lowest_price: float


class TrailingStopService:
    """Polls positions and adjusts stop-loss upwards (or downwards for shorts)."""

    def __init__(self, exchange: HyperliquidExchange, config: TradingConfig):
        self.exchange = exchange
        self.config = config
        self._task: Optional[asyncio.Task] = None
        self._running = False
        # Symbol → state to track recent extremes
        self._state: dict[str, TrailingState] = {}

    def start(self) -> None:
        if not self.config.trailing_stop_enabled:
            logger.info("Trailing stop service disabled by config")
            return
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("📈 TrailingStopService started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2)
            except Exception:
                pass
        logger.info("🛑 TrailingStopService stopped")

    async def _run(self) -> None:
        interval = self.config.trailing_check_interval_seconds
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"TrailingStopService tick error: {e}")
            await asyncio.sleep(interval)

    async def _tick(self) -> None:
        positions = await self.exchange.get_positions()
        for pos in positions:
            symbol = pos.symbol
            entry = float(pos.entry_price)
            current = float(pos.current_price or pos.entry_price)

            if symbol not in self._state:
                self._state[symbol] = TrailingState(highest_price=current, lowest_price=current)
            state = self._state[symbol]

            if pos.side in [SignalType.LONG, SignalType.BUY]:
                # Update highest
                if current > state.highest_price:
                    state.highest_price = current
                # Only activate trailing after activation threshold in profit
                activation = entry * (1 + self.config.trailing_activation_percent)
                if current < activation:
                    logger.info(
                        f"[Trailing] {symbol} LONG | price={current:.6f} | entry={entry:.6f} | "
                        f"activation>={activation:.6f} | highest={state.highest_price:.6f} | decision=not_activated"
                    )
                    continue
                # Desired SL = highest - distance
                desired_sl = state.highest_price * (1 - self.config.trailing_distance_percent)
                logger.info(
                    f"[Trailing] {symbol} LONG | price={current:.6f} | entry={entry:.6f} | "
                    f"highest={state.highest_price:.6f} | desired_sl={desired_sl:.6f}"
                )
                # Only move SL up in steps
                await self._maybe_update_sl(symbol, desired_sl, is_long=True, current_price=current)
            else:
                # SHORT: track lowest
                if current < state.lowest_price:
                    state.lowest_price = current
                activation = entry * (1 - self.config.trailing_activation_percent)
                if current > activation:
                    logger.info(
                        f"[Trailing] {symbol} SHORT | price={current:.6f} | entry={entry:.6f} | "
                        f"activation<={activation:.6f} | lowest={state.lowest_price:.6f} | decision=not_activated"
                    )
                    continue
                desired_sl = state.lowest_price * (1 + self.config.trailing_distance_percent)
                logger.info(
                    f"[Trailing] {symbol} SHORT | price={current:.6f} | entry={entry:.6f} | "
                    f"lowest={state.lowest_price:.6f} | desired_sl={desired_sl:.6f}"
                )
                await self._maybe_update_sl(symbol, desired_sl, is_long=False, current_price=current)

    async def _maybe_update_sl(self, symbol: str, desired_sl: float, is_long: bool, current_price: float) -> None:
        try:
            # Fetch existing SL via open orders to compare and enforce monotonic move
            open_orders = await self.exchange.get_open_orders(symbol)
            current_sl: Optional[float] = None
            current_tp: Optional[float] = None
            for o in open_orders or []:
                params = o.get('info') or {}
                # Identify SL
                sl_val = params.get('stopPrice') or params.get('stopLossPrice')
                if sl_val:
                    try:
                        current_sl = float(sl_val)
                    except Exception:
                        current_sl = None
                # Identify TP (may be set via takeProfitPrice)
                tp_val = params.get('takeProfitPrice')
                if tp_val and current_tp is None:
                    try:
                        current_tp = float(tp_val)
                    except Exception:
                        current_tp = None
            logger.info(
                f"[Trailing] {symbol} | price={current_price:.6f} | current_sl={current_sl} | "
                f"current_tp={current_tp} | desired_sl={desired_sl:.6f}"
            )
            # Step gating
            step = self.config.trailing_update_step_percent
            if current_sl is not None:
                if is_long:
                    # Move only up and if improved by step
                    if desired_sl <= current_sl * (1 + step):
                        logger.info(
                            f"[Trailing] {symbol} decision=keep | reason=step_too_small | "
                            f"desired_sl={desired_sl:.6f} <= current_sl*step={current_sl*(1+step):.6f}"
                        )
                        return
                else:
                    # Move only down and if improved by step (for shorts SL is above price, so lower is improvement)
                    if desired_sl >= current_sl * (1 - step):
                        logger.info(
                            f"[Trailing] {symbol} decision=keep | reason=step_too_small | "
                            f"desired_sl={desired_sl:.6f} >= current_sl*step={current_sl*(1-step):.6f}"
                        )
                        return
            # Apply update
            ok = await self.exchange.update_stop_loss(symbol, desired_sl)
            if not ok:
                logger.warning(f"[Trailing] {symbol} decision=update_failed | desired_sl={desired_sl:.6f}")
            else:
                logger.info(f"[Trailing] {symbol} decision=updated_sl | new_sl={desired_sl:.6f}")
        except Exception as e:
            logger.error(f"_maybe_update_sl error for {symbol}: {e}")

