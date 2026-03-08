from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional

from binance.client import Client


class Executor:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        self.client: Optional[Client] = None

        if not self.dry_run:
            if not self.api_key or not self.api_secret:
                raise ValueError("Sätt BINANCE_API_KEY och BINANCE_API_SECRET i miljövariabler.")
            self.client = Client(self.api_key, self.api_secret)

    def _require_client(self) -> Client:
        if self.client is None:
            raise ValueError("Binance-klient saknas. Sätt dry_run=False och giltiga API-nycklar.")
        return self.client

    def _get_symbol_rules(self, symbol: str) -> Dict[str, float]:
        if self.dry_run:
            # Rimliga standardvärden för XRPUSDT futures i testläge
            return {
                "tick_size": 0.0001,
                "step_size": 1.0,
                "min_qty": 1.0,
            }

        client = self._require_client()
        info = client.futures_exchange_info()

        for s in info["symbols"]:
            if s["symbol"] == symbol:
                tick_size = 0.0001
                step_size = 1.0
                min_qty = 1.0

                for f in s["filters"]:
                    if f["filterType"] == "PRICE_FILTER":
                        tick_size = float(f["tickSize"])
                    elif f["filterType"] == "LOT_SIZE":
                        step_size = float(f["stepSize"])
                        min_qty = float(f["minQty"])

                return {
                    "tick_size": tick_size,
                    "step_size": step_size,
                    "min_qty": min_qty,
                }

        raise ValueError(f"Kunde inte hitta symbolregler för {symbol}.")

    @staticmethod
    def _round_to_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step) * step

    def normalize_quantity(self, symbol: str, quantity: float) -> float:
        rules = self._get_symbol_rules(symbol)
        qty = self._round_to_step(quantity, rules["step_size"])
        qty = round(qty, 8)
        if qty < rules["min_qty"]:
            raise ValueError(f"Quantity {qty} är under minQty {rules['min_qty']} för {symbol}.")
        return qty

    def normalize_price(self, symbol: str, price: float) -> float:
        rules = self._get_symbol_rules(symbol)
        p = self._round_to_step(price, rules["tick_size"])
        return round(p, 8)

    def get_futures_usdt_balance(self) -> float:
        if self.dry_run:
            return 10000.0

        client = self._require_client()
        balances = client.futures_account_balance()
        for b in balances:
            if b["asset"] == "USDT":
                return float(b["balance"])

        raise ValueError("Hittade inget USDT-saldo.")

    def get_position_amt(self, symbol: str) -> float:
        if self.dry_run:
            return 0.0

        client = self._require_client()
        positions = client.futures_position_information(symbol=symbol)
        for p in positions:
            if p["symbol"] == symbol:
                return float(p["positionAmt"])
        return 0.0

    def has_open_position(self, symbol: str) -> bool:
        return self.get_position_amt(symbol) != 0.0

    def cancel_open_orders(self, symbol: str) -> None:
        if self.dry_run:
            print(f"DRY RUN - skulle avbryta alla öppna ordrar för {symbol}")
            return

        client = self._require_client()
        client.futures_cancel_all_open_orders(symbol=symbol)

    def open_position(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        if side not in ("BUY", "SELL"):
            raise ValueError("side måste vara BUY eller SELL.")
        if quantity <= 0:
            raise ValueError("quantity måste vara större än 0.")

        quantity = self.normalize_quantity(symbol, quantity)

        order_data = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }

        if self.dry_run:
            print("DRY RUN - order som skulle skickas:")
            print(order_data)
            return {"dry_run": True, **order_data}

        client = self._require_client()
        return client.futures_create_order(**order_data)

    def place_protective_orders(
        self,
        symbol: str,
        entry_side: str,
        stop_loss_price: float,
        take_profit_price: float,
    ) -> Dict[str, Any]:
        close_side = "SELL" if entry_side == "BUY" else "BUY"

        stop_loss_price = self.normalize_price(symbol, stop_loss_price)
        take_profit_price = self.normalize_price(symbol, take_profit_price)

        sl_order = {
            "symbol": symbol,
            "side": close_side,
            "type": "STOP_MARKET",
            "stopPrice": stop_loss_price,
            "closePosition": "true",
            "workingType": "CONTRACT_PRICE",
        }

        tp_order = {
            "symbol": symbol,
            "side": close_side,
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": take_profit_price,
            "closePosition": "true",
            "workingType": "CONTRACT_PRICE",
        }

        if self.dry_run:
            print("DRY RUN - skyddsordrar som skulle skickas:")
            print("SL:", sl_order)
            print("TP:", tp_order)
            return {
                "dry_run": True,
                "stop_loss_order": sl_order,
                "take_profit_order": tp_order,
            }

        client = self._require_client()
        sl_result = client.futures_create_order(**sl_order)
        tp_result = client.futures_create_order(**tp_order)

        return {
            "stop_loss_order": sl_result,
            "take_profit_order": tp_result,
        }