from enum import Enum
from datetime import timedelta

EVENT_TRADE = "eTrade."
EVENT_BAR = "eBar."
EVENT_ORDER = "eOrder."
EVENT_POSITION = "ePosition."
EVENT_ACCOUNT = "eAccount."
EVENT_CONTRACT = "eContract."
EVENT_LOG = "eLog"
EVENT_RENDER = 'eRender'
EVENT_LOAD = "eLoad"
EVENT_STRATEGY = "eStrategy"
EVENT_STRATEGY_LOG = "eStrategyLog"
EVENT_STRATEGY_STOPORDER = "eStopOrder"
EVENT_CHANTU = "eCHANTU"
EVENT_BACKTEST_LOG = "eBacktestLog"
EVENT_BACKTEST_FINISHED = "eBacktestFinished"
EVENT_BACKTEST_OPTIMIZATION_FINISHED = "eBacktestOptimizationFinished"


class Direction(Enum):
    LONG = "多"  # 1
    SHORT = "空"  # 2


class Offset(Enum):
    NONE = ""
    OPEN = "开"
    CLOSE = "平"
    CLOSETODAY = "平今"
    CLOSEYESTERDAY = "平昨"


class Status(Enum):
    """
    OrderStatus_Unknown = 0
    OrderStatus_New = 1                   ## 已报
    OrderStatus_PartiallyFilled = 2       ## 部成
    OrderStatus_Filled = 3                ## 已成
    OrderStatus_Canceled = 5              ## 已撤
    OrderStatus_PendingCancel = 6         ## 待撤
    OrderStatus_Rejected = 8              ## 已拒绝
    OrderStatus_Suspended = 9             ## 挂起
    OrderStatus_PendingNew = 10           ## 待报
    OrderStatus_Expired = 12              ## 已过期
    """
    UNKNOWN = "UNKNOWN"
    SUBMITTING = "已提交"
    PARTTRADED = "部分成交"
    ALLTRADED = "全部成交"
    CANCELLED = "已撤销"
    WAIT_CANCELLED = "待撤销"
    REJECTED = "拒单"
    SUSPENDED = "挂起"
    PENDINGNEW = "待提交"
    EXPIRED = "已过期"
    NOTTRADED = "未成交"


STATUS_MAP = {
    1: Status.SUBMITTING,
    2: Status.PARTTRADED,
    3: Status.ALLTRADED,
    5: Status.CANCELLED,
    6: Status.WAIT_CANCELLED,
    8: Status.REJECTED,
    9: Status.SUSPENDED,
    10: Status.PENDINGNEW,
    12: Status.EXPIRED,
}


class StopOrderStatus(Enum):
    WAITING = "等待中"
    CANCELLED = "已撤销"
    TRIGGERED = "已触发"


class EngineType(Enum):
    LIVE = "实盘"
    BACKTEST = "回测"


class OrderType(Enum):
    """
    OrderType_Unknown = 0
OrderType_Limit = 1            ## 限价委托
OrderType_Market = 2           ## 市价委托
OrderType_Stop = 3             ## 止损止盈委托
    """
    UNKNOWN = "UNKNOWN"
    LIMIT = "限价委托"
    MARKET = "市价委托"
    STOP = "止损止盈委托"


ORDERTYPE_MAP = {
    1: OrderType.LIMIT,
    2: OrderType.MARKET,
    3: OrderType.STOP,
}


class Exchange(Enum):
    SZSE = "SZSE"
    SSE = "SSE"


class Interval(Enum):
    MINUTE = "1m"
    MINUTE5 = "5m"
    MINUTE30 = "30m"

    HOUR = "1h"
    DAILY = "d"
    WEEKLY = "w"


class METHOD(Enum):
    BZ = '标准操作方法'
    JJ = '激进操作方法'
    DX = '短线反弹操作方法'


INTERVAL_DAYS = 30

INTERVAL_DELTA_MAP = {
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(days=1),
}

# ['月线', '周线', '日线', '60分钟', '30分钟', '15分钟', '5分钟', '1分钟']
FREQS = ['日线', '30分钟', '5分钟', '1分钟']

FREQS_INV = list(FREQS)
FREQS_INV.reverse()

FREQS_WINDOW = {
    '日线': [240, Interval.MINUTE, Interval.DAILY],
    '30分钟': [30, Interval.MINUTE, Interval.MINUTE30],
    '5分钟': [5, Interval.MINUTE, Interval.MINUTE5],
    '1分钟': [1, Interval.MINUTE, Interval.MINUTE],
}

INTERVAL_FREQ = {
    'd': '日线',
    '30m': '30分钟',
    '5m': '5分钟',
    '1m': '1分钟'
}

STOPORDER_PREFIX = 'stop_order'

PARAM_ZH_MAP = {'method': '交易方法', 'vt_symbol': '股票代码', 'symbol': '股票代码', 'strategy_name': '策略名称', 'include': 'K线包含',
                'build_pivot': '中枢类型', 'qjt': '用区间套',
                'gz': '使用共振', 'jb': '操作级别'}

PARAM_ZH_MAP_INV = {'股票代码': 'vt_symbol', '策略名称': 'strategy_name', 'K线包含': 'include', '中枢类型': 'build_pivot',
                    '用区间套': 'qjt', '使用共振': 'gz'}

SETTING_ZH_MAP = {

}

ZH_TRANS_MAP = {'标准操作方法': 'Chan_Strategy_STD', '激进操作方法': 'Chan_Strategy_JJ', '短线反弹操作方法': 'Chan_Strategy_DXFT',
                '缠论K线': True, '普通K线': False, '笔中枢': False, '线段中枢': True, '是': True, '否': False
                }
