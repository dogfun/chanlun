from trade.utility import BarGenerator
from trade.template import Template
from trade.object import (
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
)
from trade.constant import FREQS, INTERVAL_FREQ, Interval, FREQS_WINDOW, METHOD, Direction, Offset
from .chan_class import Chan_Class


class Chan_Strategy(Template):
    """首页展示行情"""

    method = METHOD.BZ
    symbol = ''
    include = True
    build_pivot = False
    qjt = False
    gz = False
    jb = Interval.MINUTE

    parameters = ['method', 'symbol', 'include', 'build_pivot', 'qjt', 'gz', 'jb']
    buy1 = 100
    buy2 = 200
    buy3 = 200
    sell1 = 100
    sell2 = 200
    sell3 = 200
    variables = ['buy1', 'buy2', 'buy3', 'sell1', 'sell2', 'sell3']

    # parameters = ["period", "stroke_type", "pivot_type", "buy1", "buy2", "buy3", "sell1", "sell2", "sell3",
    #               "dynamic_reduce"]
    # variables = ["stroke_list", "line_list", "pivot_list", "trend_list", "buy_list", "sell_list"]

    def __init__(self, engine, strategy_name, vt_symbol, setting):
        """
        从1分钟->5->30->1d
        先做一个级别，之后再做其他的级别
        """
        if setting:
            if 'method' in setting.keys():
                self.method = setting['method']
            if 'symbol' in setting.keys():
                self.symbol = setting['symbol']
            # 笔生成方法，new, old
            # 是否进行K线包含处理
            if 'include' in setting.keys():
                self.include = setting['include']
            # 中枢生成方法，stroke, line
            # 使用笔还是线段作为中枢的构成, true使用线段
            if 'build_pivot' in setting.keys():
                self.build_pivot = setting['build_pivot']
            if 'qjt' in setting.keys():
                self.qjt = setting['qjt']
            if 'gz' in setting.keys():
                self.gz = setting['gz']
            # 买卖的级别
            if 'jb' in setting.keys():
                self.jb = setting['jb']
            # 线段生成方法
            # if 'include_feature' in setting.keys():
            #     self.include_feature = setting['include_feature']

        super().__init__(engine, strategy_name, vt_symbol, setting)
        self.engine = engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol
        self.include_feature = False

        # map
        self.chan_freq_map = {}
        self.bg_freq_map = {}

        # 初始化缠论类和bg
        self.bg = BarGenerator(on_bar=self.on_bar, interval=Interval.MINUTE)
        i = 0
        prev = None

        for freq in FREQS:
            chan = Chan_Class(freq=freq, symbol=self.vt_symbol, sell=self.sell, buy=self.buy, include=self.include,
                              include_feature=self.include_feature, build_pivot=self.build_pivot, qjt=self.qjt,
                              gz=self.gz)
            self.chan_freq_map[freq] = chan
            if prev:
                prev.set_next(chan)
                chan.set_prev(prev)
            prev = chan
            # 限定共振作用级别
            if chan.prev == None or chan.freq != FREQS[-1]:
                chan.gz = False
            if i > 0:
                wlist = FREQS_WINDOW[FREQS[i - 1]]
                self.bg_freq_map[freq] = BarGenerator(on_bar=self.on_pass, on_window_bar=self.on_bar, window=wlist[0],
                                                      interval=wlist[1], target=wlist[2])
            i += 1

    def on_start(self):
        self.write_log("chan策略启动")

        self.put_event()

    def on_stop(self):
        self.write_log("chan策略停止")
        self.put_event()

    def on_tick(self, tick: TickData):
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        # print(bar)
        freq = INTERVAL_FREQ[bar.interval.value]
        if bar.interval.value == Interval.MINUTE.value:
            for freq in self.bg_freq_map:
                self.bg_freq_map[freq].update_bar(bar)
            # self.put_render_event()
        self.chan_freq_map[freq].on_bar(bar)

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
        if self.trading and self.jb == freq:
            vt_orderids = self.engine.send_order(
                self, direction, offset, price, volume, stop, lock
            )
            return vt_orderids
        return []

    def on_order(self, order: OrderData):
        pass

    def on_trade(self, trade: TradeData):
        pass

    def on_stop_order(self, stop_order: StopOrder):
        pass

    def on_pass(self):
        pass
