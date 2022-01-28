from abc import ABC
from copy import copy
from typing import Any, Callable

from trade.constant import Interval, Direction, Offset
from trade.object import BarData, TickData, OrderData, TradeData, StopOrder
from trade.utility import virtual


class Template(ABC):
    parameters = []
    variables = []

    def __init__(
            self,
            engine: Any,
            strategy_name: str,
            vt_symbol: str,
            setting: dict,
    ):
        self.engine = engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol
        self.setting = setting
        self.trading = False
        self.pos = 0

        # Copy a new variables list here to avoid duplicate insert when multiple
        # strategy instances are created with the same strategy class.
        self.variables = copy(self.variables)
        self.variables.insert(0, "trading")
        self.variables.insert(1, "pos")

        self.update_setting(setting)

    def update_setting(self, setting: dict):
        for name in self.parameters:
            if name in setting:
                setattr(self, name, setting[name])

    def get_parameters(self):
        strategy_parameters = {}
        for name in self.parameters:
            strategy_parameters[name] = getattr(self, name)
        return strategy_parameters

    def get_variables(self):
        strategy_variables = {}
        for name in self.variables:
            strategy_variables[name] = getattr(self, name)
        return strategy_variables

    def get_data(self):

        strategy_data = {
            "strategy_name": self.strategy_name,
            "vt_symbol": self.vt_symbol,
            "class_name": self.__class__.__name__,
            "parameters": self.get_parameters(),
            "variables": self.get_variables(),
        }
        return strategy_data

    @virtual
    def on_start(self):
        pass

    @virtual
    def on_stop(self):
        pass

    @virtual
    def on_tick(self, tick: TickData):
        pass

    @virtual
    def on_bar(self, bar: BarData):
        pass

    @virtual
    def on_trade(self, trade: TradeData):
        pass

    @virtual
    def on_order(self, order: OrderData):
        pass

    @virtual
    def on_stop_order(self, stop_order: StopOrder):
        pass

    def buy(self, price: float, volume: float, freq: str = '', stop: bool = False, lock: bool = False):
        return self.send_order(Direction.LONG, Offset.OPEN, price, volume, freq, stop, lock)

    def sell(self, price: float, volume: float, freq: str = '', stop: bool = False, lock: bool = False):
        return self.send_order(Direction.SHORT, Offset.CLOSE, price, volume, freq, stop, lock)

    def send_order(
            self,
            direction: Direction,
            offset: Offset,
            price: float,
            volume: float,
            freq: str,
            stop: bool = False,
            lock: bool = False
    ):
        if self.trading:
            vt_orderids = self.engine.send_order(
                self, direction, offset, price, volume, stop, lock
            )
            return vt_orderids
        else:
            return []

    def cancel_order(self, vt_orderid: str):
        if self.trading:
            self.engine.cancel_order(self, vt_orderid)

    def cancel_all(self):
        if self.trading:
            self.engine.cancel_all(self)

    def write_log(self, msg: str):
        self.engine.write_log(msg, self)

    def get_engine_type(self):
        return self.engine.get_engine_type()

    def put_event(self):
        self.engine.put_strategy_event(self)

    def put_render_event(self):
        self.engine.put_render_event(self)

    def send_msg(self, msg):
        self.engine.send_msg(msg, self)

    def sync_data(self):
        if self.trading:
            self.engine.sync_strategy_data(self)
