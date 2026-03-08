from dataclasses import dataclass


@dataclass
class RiskPlan:
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    risk_amount_usdt: float
    quantity: float
    notional_usdt: float


class RiskManager:
    def __init__(
        self,
        account_balance_usdt: float,
        risk_per_trade_pct: float = 1.0,
        max_notional_pct: float = 20.0,
    ) -> None:
        self.account_balance_usdt = account_balance_usdt
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_notional_pct = max_notional_pct

    def build_plan(
        self,
        side: str,
        entry_price: float,
        stop_distance: float,
        tp_distance: float,
    ) -> RiskPlan:
        if entry_price <= 0:
            raise ValueError("entry_price måste vara > 0.")
        if stop_distance <= 0:
            raise ValueError("stop_distance måste vara > 0.")

        risk_amount = self.account_balance_usdt * (self.risk_per_trade_pct / 100.0)
        raw_qty = risk_amount / stop_distance

        max_notional = self.account_balance_usdt * (self.max_notional_pct / 100.0)
        max_qty_from_notional = max_notional / entry_price

        qty = min(raw_qty, max_qty_from_notional)
        qty = round(qty, 1)

        if qty <= 0:
            raise ValueError("Beräknad quantity blev 0.")

        if side == "BUY":
            stop_loss_price = entry_price - stop_distance
            take_profit_price = entry_price + tp_distance
        elif side == "SELL":
            stop_loss_price = entry_price + stop_distance
            take_profit_price = entry_price - tp_distance
        else:
            raise ValueError("side måste vara BUY eller SELL.")

        return RiskPlan(
            entry_price=entry_price,
            stop_loss_price=round(stop_loss_price, 5),
            take_profit_price=round(take_profit_price, 5),
            risk_amount_usdt=round(risk_amount, 4),
            quantity=qty,
            notional_usdt=round(qty * entry_price, 4),
        )