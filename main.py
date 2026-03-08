from __future__ import annotations

import os
from binance.client import Client

from executor import Executor
from market_data import MarketData
from risk_manager import RiskManager
from strategy import DualModeStrategy

SYMBOL = os.getenv("BOT_SYMBOL", "XRPUSDT")
INTERVAL = Client.KLINE_INTERVAL_30MINUTE

# LIVE_MODE=true i GitHub Secrets för live
LIVE_MODE = os.getenv("LIVE_MODE", "false").lower() == "true"


def run_bot_once():
    md = MarketData()
    strategy = DualModeStrategy()
    executor = Executor(dry_run=not LIVE_MODE)

    account_balance = executor.get_futures_usdt_balance()

    risk_manager = RiskManager(
        account_balance_usdt=account_balance,
        risk_per_trade_pct=1.0,
        max_notional_pct=20.0,
    )

    print("Bot startad...")
    print(f"Symbol: {SYMBOL}")
    print(f"Interval: {INTERVAL}")
    print(f"Live mode: {LIVE_MODE}")
    print(f"Saldo: {account_balance}")

    if executor.has_open_position(SYMBOL):
        print("Öppen position finns redan. Ingen ny entry denna körning.")
        return

    ohlcv = md.get_ohlcv(symbol=SYMBOL, interval=INTERVAL, limit=300)

    signal = strategy.generate_signal(
        highs=ohlcv["high"],
        lows=ohlcv["low"],
        closes=ohlcv["close"],
        volumes=ohlcv["volume"],
    )

    print("\n==============================")
    print("Senaste candle analyserad")
    print("Signal:", signal.side)
    print("Mode:", signal.mode)
    print("Reason:", signal.reason)
    print("Price:", signal.last_price)
    print("ATR:", signal.atr)
    print("ADX:", signal.adx)
    print("RSI:", signal.rsi)

    if signal.side not in ["BUY", "SELL"]:
        print("Ingen trade denna körning.")
        return

    tp_distance = signal.atr * signal.tp_multiplier

    plan = risk_manager.build_plan(
        side=signal.side,
        entry_price=signal.last_price,
        stop_distance=signal.stop_distance,
        tp_distance=tp_distance,
    )

    print("Riskplan:", plan)

    entry_result = executor.open_position(
        symbol=SYMBOL,
        side=signal.side,
        quantity=plan.quantity,
    )
    print("Entry-resultat:", entry_result)

    protective_result = executor.place_protective_orders(
        symbol=SYMBOL,
        entry_side=signal.side,
        stop_loss_price=plan.stop_loss_price,
        take_profit_price=plan.take_profit_price,
    )
    print("Skyddsordrar:", protective_result)


if __name__ == "__main__":
    run_bot_once()