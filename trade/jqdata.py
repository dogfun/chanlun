import json
import calendar
from datetime import timedelta, datetime
from typing import List, Optional
import time
import pandas
from pytz import timezone
from numpy import ndarray
import jqdatasdk as jq
from trade.constant import Exchange, Interval
from trade.object import BarData, HistoryRequest
from pathlib import Path

INTERVAL_VT2RQ = {
    Interval.MINUTE: "1m",
    Interval.HOUR: "60m",
    Interval.DAILY: "1d",
}

INTERVAL_ADJUSTMENT_MAP = {
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta()  # no need to adjust for daily bar
}

CHINA_TZ = timezone("Asia/Shanghai")


class JqdataClient:
    def __init__(self):
        self.username: str = ''
        self.password: str = ''

        self.inited: bool = False
        self.symbols: ndarray = None

    def init(self, username: str = "", password: str = "") -> bool:
        if self.inited:
            return True

        if username and password:
            self.username = username
            self.password = password

        if not self.username or not self.password:
            return False

        try:
            jq.auth(self.username, self.password)
            print("jq auth success.")
            self.inited = True

        except Exception as ex:
            print("聚宽账号或者密码错误！")
            print("jq auth fail:" + repr(ex))
            return

        return True

    def to_jq_symbol(self, symbol: str, exchange: Exchange) -> str:
        """
              CZCE product of JQData has symbol like "TA1905" while
              vt symbol is "TA905.CZCE" so need to add "1" in symbol.
              """
        if exchange in [Exchange.SSE, Exchange.SZSE]:
            if exchange == Exchange.SSE:
                jq_symbol = f"{symbol}.XSHG"  # 上海证券交易所
            else:
                jq_symbol = f"{symbol}.XSHE"  # 深圳证券交易所
        elif exchange == Exchange.SHFE:
            jq_symbol = f"{symbol}.XSGE"  # 上期所
        elif exchange == Exchange.CFFEX:
            jq_symbol = f"{symbol}.CCFX"  # 中金所
        elif exchange == Exchange.DCE:
            jq_symbol = f"{symbol}.XDCE"  # 大商所
        elif exchange == Exchange.INE:
            jq_symbol = f"{symbol}.XINE"  # 上海国际能源期货交易所
        elif exchange == Exchange.CZCE:
            # 郑商所 的合约代码年份只有三位 需要特殊处理
            for count, word in enumerate(symbol):
                if word.isdigit():
                    break
            # Check for index symbol
            time_str = symbol[count:]
            if time_str in ["88", "888", "99", "8888"]:
                return f"{symbol}.XZCE"
            # noinspection PyUnboundLocalVariable
            product = symbol[:count]
            year = symbol[count]
            month = symbol[count + 1:]
            if year == "9":
                year = "1" + year
            else:
                year = "2" + year
            jq_symbol = f"{product}{year}{month}.XZCE"
        return jq_symbol.upper()

    def query_history2(self, req: HistoryRequest) -> Optional[List[BarData]]:
        # if self.symbols is None:
        #     return None

        symbol = req.symbol
        exchange = req.exchange
        interval = req.interval
        start = req.start
        end = req.end

        jq_symbol = self.to_jq_symbol(symbol, exchange)
        # if rq_symbol not in self.symbols:
        #     return None

        jq_interval = INTERVAL_VT2RQ.get(interval)
        if not jq_interval:
            return None

        # For adjust timestamp from bar close point (JQData) to open point
        adjustment = INTERVAL_ADJUSTMENT_MAP[interval]

        # For querying night trading period data
        end += timedelta(1)

        # Only query open interest for futures contract
        fields = ["open", "high", "low", "close", "volume"]

        data: List[BarData] = []
        df = self.merge_data()
        if df is not None:
            for ix, row in df.iterrows():
                bar = BarData(
                    symbol=symbol,
                    exchange=exchange,
                    interval=interval,
                    datetime=datetime.strptime(row["date"], '%Y-%m-%d %H:%M:%S'),
                    open_price=row["open"],
                    high_price=row["high"],
                    low_price=row["low"],
                    close_price=row["close"],
                    volume=row["volume"],
                    open_interest=row.get("open_interest", 0),
                    gateway_name="JQ"
                )

                data.append(bar)

        return df, data

    def query_bar(self, vt_symbol: str) -> Optional[BarData]:
        # if self.symbols is None:
        #     return None
        symbol_list = vt_symbol.split('.')
        symbol = symbol_list[0]
        exchange = Exchange.SSE
        if symbol_list[1] == 'SZSE':
            exchange = Exchange.SZSE

        jq_symbol = self.to_jq_symbol(symbol, exchange)

        df = jq.get_price(
            jq_symbol,
            frequency=INTERVAL_VT2RQ.get(Interval.MINUTE),
            fields=["open", "high", "low", "close", "volume"],
            start_date=datetime.now() - timedelta(minutes=1),
            end_date=datetime.now(),
            skip_paused=True
        )

        data: BarData = None

        if df is not None:
            for ix, row in df.iterrows():
                dt = row.name.to_pydatetime()
                dt = CHINA_TZ.localize(dt)

                data = BarData(
                    symbol=symbol,
                    exchange=exchange,
                    interval=Interval.MINUTE,
                    datetime=dt,
                    open_price=row["open"],
                    high_price=row["high"],
                    low_price=row["low"],
                    close_price=row["close"],
                    volume=row["volume"],
                    open_interest=row.get("open_interest", 0)
                )

        return data
        # return self.query_bar_xq(vt_symbol)


    def is_trade_day(self) -> bool:
        yd = datetime.now() - timedelta(days=1)
        days = jq.get_trade_days(start_date=yd.date(), end_date=None)
        if days and len(days) > 0:
            return True
        return False

    def query_history(self, req: HistoryRequest) -> Optional[List[BarData]]:
        # if self.symbols is None:
        #     return None
        symbol = req.symbol
        exchange = req.exchange
        interval = req.interval
        start = req.start
        end = req.end

        jq_symbol = self.to_jq_symbol(symbol, exchange)
        # if rq_symbol not in self.symbols:
        #     return None

        jq_interval = INTERVAL_VT2RQ.get(interval)
        if not jq_interval:
            return None

        # For querying night trading period data
        end += timedelta(1)

        # Only query open interest for futures contract
        fields = ["open", "high", "low", "close", "volume"]
        if not symbol.isdigit():
            fields.append("open_interest")

        df = jq.get_price(
            jq_symbol,
            frequency=jq_interval,
            fields=["open", "high", "low", "close", "volume"],
            start_date=start,
            end_date=end,
            skip_paused=True
        )

        data: List[BarData] = []

        if df is not None:
            for ix, row in df.iterrows():
                dt = row.name.to_pydatetime()
                dt = CHINA_TZ.localize(dt)

                bar = BarData(
                    symbol=symbol,
                    exchange=exchange,
                    interval=interval,
                    datetime=dt,
                    open_price=row["open"],
                    high_price=row["high"],
                    low_price=row["low"],
                    close_price=row["close"],
                    volume=row["volume"],
                    open_interest=row.get("open_interest", 0)
                )

                data.append(bar)

        return df, data

    def merge_data(self):
        time_start = time.time()
        symbol = '600809'
        cwd = Path.cwd()
        temp_path = cwd.joinpath('trade/data/' + symbol)
        year_start = 2016
        year_end = 2022
        month_start = 1
        month_end = 13
        df = pandas.DataFrame(columns=["date", "open", "close", "low", "high", "volume"], dtype=object)
        for year in range(year_start, year_end):
            for month in range(month_start, month_end):
                firstDay, lastDay = getMonthFirstDayAndLastDay(year, month)
                file = str(temp_path) + '/' + firstDay.strftime("%Y-%m-%d") + '.csv'
                if Path(file).exists():
                    df = pandas.concat([df, pandas.read_csv(file)], sort=True)
        time_end = time.time()
        print('totally cost', time_end - time_start)
        return df


jqdata_client = JqdataClient()


def getMonthFirstDayAndLastDay(year=None, month=None):
    """
    :param year: 年份，默认是本年，可传int或str类型
    :param month: 月份，默认是本月，可传int或str类型
    :return: firstDay: 当月的第一天，datetime.date类型
              lastDay: 当月的最后一天，datetime.date类型
    """
    if not year or year > 2021 or not month or month > 12 or month < 0:
        return None, None
    # 获取当月第一天的星期和当月的总天数
    firstDayWeekDay, monthRange = calendar.monthrange(year, month)
    # 获取当月的第一天
    firstDay = datetime(year=year, month=month, day=1)
    lastDay = datetime(year=year, month=month, day=monthRange)

    return firstDay, lastDay

