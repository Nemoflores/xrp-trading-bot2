from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal


SignalSide = Literal["BUY", "SELL", "NONE"]
ModeType = Literal["TREND", "RANGE", "NONE"]


@dataclass
class StrategySignal:
    side: SignalSide
    mode: ModeType
    reason: str
    last_price: float
    atr: float
    adx: float
    rsi: float
    stop_distance: float
    tp_multiplier: float


class DualModeStrategy:
    def __init__(
        self,
        adx_len: int = 14,
        adx_thresh: float = 22.0,
        don_len: int = 20,
        rsi_len: int = 14,
        rsi_ob: float = 72.0,
        rsi_os: float = 28.0,
        atr_len: int = 14,
        sl_mult: float = 2.0,
        tp_trend_mult: float = 3.0,
        tp_range_mult: float = 1.5,
    ) -> None:
        self.adx_len = adx_len
        self.adx_thresh = adx_thresh
        self.don_len = don_len
        self.rsi_len = rsi_len
        self.rsi_ob = rsi_ob
        self.rsi_os = rsi_os
        self.atr_len = atr_len
        self.sl_mult = sl_mult
        self.tp_trend_mult = tp_trend_mult
        self.tp_range_mult = tp_range_mult

    @staticmethod
    def ema(values: List[float], period: int) -> float:
        if len(values) < period:
            raise ValueError(f"För få datapunkter för EMA({period}).")
        k = 2 / (period + 1)
        ema_val = sum(values[:period]) / period
        for price in values[period:]:
            ema_val = price * k + ema_val * (1 - k)
        return ema_val

    @staticmethod
    def sma(values: List[float], period: int) -> float:
        if len(values) < period:
            raise ValueError(f"För få datapunkter för SSSMA({period}).")
        return sum(values[-period:]) / period

    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            raise ValueError("För få closes för RSI.")

        gains = []
        losses = []

        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            raise ValueError("För få candles för ATR.")

        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        atr_val = sum(trs[:period]) / period
        for tr in trs[period:]:
            atr_val = ((atr_val * (period - 1)) + tr) / period
        return atr_val

    @staticmethod
    def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < period * 2:
            raise ValueError("För få candles för ADX.")

        plus_dm = []
        minus_dm = []
        trs = []

        for i in range(1, len(closes)):
            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]

            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        tr14 = sum(trs[:period])
        plus14 = sum(plus_dm[:period])
        minus14 = sum(minus_dm[:period])

        dx_values = []

        for i in range(period, len(trs)):
            if i > period:
                tr14 = tr14 - (tr14 / period) + trs[i]
                plus14 = plus14 - (plus14 / period) + plus_dm[i]
                minus14 = minus14 - (minus14 / period) + minus_dm[i]

            if tr14 == 0:
                continue

            plus_di = 100 * (plus14 / tr14)
            minus_di = 100 * (minus14 / tr14)
            di_sum = plus_di + minus_di

            if di_sum == 0:
                dx = 0.0
            else:
                dx = 100 * abs(plus_di - minus_di) / di_sum

            dx_values.append(dx)

        if len(dx_values) < period:
            raise ValueError("För få DX-värden för ADX.")

        adx_val = sum(dx_values[:period]) / period
        for dx in dx_values[period:]:
            adx_val = ((adx_val * (period - 1)) + dx) / period

        return adx_val

    def generate_signal(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
    ) -> StrategySignal:
        if min(len(highs), len(lows), len(closes), len(volumes)) < 250:
            raise ValueError("För få datapunkter. Hämta minst 250 candles.")

        last_price = closes[-1]
        ema200 = self.ema(closes, 200)
        atr_val = self.atr(highs, lows, closes, self.atr_len)
        rsi_val = self.rsi(closes, self.rsi_len)
        prev_rsi = self.rsi(closes[:-1], self.rsi_len)
        adx_val = self.adx(highs, lows, closes, self.adx_len)
        vol_ma = self.sma(volumes, 20)

        don_high = max(highs[-self.don_len - 1:-1])
        don_low = min(lows[-self.don_len - 1:-1])

        is_trending = adx_val >= self.adx_thresh
        is_ranging = adx_val < self.adx_thresh

        trend_long = is_trending and last_price > ema200 and last_price > don_high and volumes[-1] > vol_ma
        trend_short = is_trending and last_price < ema200 and last_price < don_low and volumes[-1] > vol_ma

        range_long = is_ranging and prev_rsi < self.rsi_os and rsi_val > prev_rsi and last_price > ema200 * 0.96
        range_short = is_ranging and prev_rsi > self.rsi_ob and rsi_val < prev_rsi and last_price < ema200 * 1.04

        stop_distance = atr_val * self.sl_mult

        if trend_long:
            return StrategySignal(
                side="BUY",
                mode="TREND",
                reason="Trend long: ADX hög, breakout över Donchian, över EMA200, volym OK",
                last_price=last_price,
                atr=atr_val,
                adx=adx_val,
                rsi=rsi_val,
                stop_distance=stop_distance,
                tp_multiplier=self.tp_trend_mult,
            )

        if trend_short:
            return StrategySignal(
                side="SELL",
                mode="TREND",
                reason="Trend short: ADX hög, breakout under Donchian, under EMA200, volym OK",
                last_price=last_price,
                atr=atr_val,
                adx=adx_val,
                rsi=rsi_val,
                stop_distance=stop_distance,
                tp_multiplier=self.tp_trend_mult,
            )

        if range_long:
            return StrategySignal(
                side="BUY",
                mode="RANGE",
                reason="Range long: ADX låg, RSI studsar upp från översålt, nära EMA200",
                last_price=last_price,
                atr=atr_val,
                adx=adx_val,
                rsi=rsi_val,
                stop_distance=stop_distance,
                tp_multiplier=self.tp_range_mult,
            )

        if range_short:
            return StrategySignal(
                side="SELL",
                mode="RANGE",
                reason="Range short: ADX låg, RSI vänder ner från överköpt, nära EMA200",
                last_price=last_price,
                atr=atr_val,
                adx=adx_val,
                rsi=rsi_val,
                stop_distance=stop_distance,
                tp_multiplier=self.tp_range_mult,
            )

        return StrategySignal(
            side="NONE",
            mode="NONE",
            reason="Ingen signal",
            last_price=last_price,
            atr=atr_val,
            adx=adx_val,
            rsi=rsi_val,
            stop_distance=stop_distance,
            tp_multiplier=self.tp_range_mult if is_ranging else self.tp_trend_mult,
        )