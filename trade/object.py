from dataclasses import dataclass, field
from datetime import datetime, date
from logging import INFO
from .constant import Direction, Exchange, Interval, Offset, Status, OrderType, StopOrderStatus, STATUS_MAP, \
    ORDERTYPE_MAP

ACTIVE_STATUSES = set([Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED])


@dataclass
class TickData:
    symbol: str
    exchange: Exchange
    datetime: datetime

    name: str = ""
    volume: float = 0
    open_interest: float = 0
    last_price: float = 0
    last_volume: float = 0
    limit_up: float = 0
    limit_down: float = 0

    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    pre_close: float = 0

    bid_price_1: float = 0
    bid_price_2: float = 0
    bid_price_3: float = 0
    bid_price_4: float = 0
    bid_price_5: float = 0

    ask_price_1: float = 0
    ask_price_2: float = 0
    ask_price_3: float = 0
    ask_price_4: float = 0
    ask_price_5: float = 0

    bid_volume_1: float = 0
    bid_volume_2: float = 0
    bid_volume_3: float = 0
    bid_volume_4: float = 0
    bid_volume_5: float = 0

    ask_volume_1: float = 0
    ask_volume_2: float = 0
    ask_volume_3: float = 0
    ask_volume_4: float = 0
    ask_volume_5: float = 0

    def __post_init__(self):
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class BarData:
    symbol: str
    exchange: Exchange
    datetime: datetime

    interval: Interval = None
    volume: float = 0
    open_interest: float = 0
    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    close_price: float = 0

    def __post_init__(self):
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class OrderData:
    """
    Order data
    """

    symbol: str
    exchange: Exchange
    orderid: str

    type: OrderType = OrderType.LIMIT
    direction: Direction = None
    offset: Offset = Offset.NONE
    price: float = 0
    volume: float = 0
    traded: float = 0
    status: Status = Status.SUBMITTING
    datetime: datetime = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.orderid}"

    def is_active(self) -> bool:
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False

    def create_cancel_request(self) -> "CancelRequest":
        req = CancelRequest(
            orderid=self.orderid, symbol=self.symbol, exchange=self.exchange
        )
        return req


@dataclass
class TradeData:
    """
    Trade data
    """

    symbol: str
    exchange: Exchange
    orderid: str
    tradeid: str
    direction: Direction = None

    offset: Offset = Offset.NONE
    price: float = 0
    volume: float = 0
    datetime: datetime = None

    def __post_init__(self):
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.orderid}"
        self.vt_tradeid = f"{self.tradeid}"


@dataclass
class GMOrderData:
    """
    GMOrder data
    """

    order_id: str
    symbol: str
    ord_rej_reason_detail: str
    order_type: OrderType = OrderType.LIMIT
    side: Direction = None
    # offset: Offset = Offset.NONE
    price: float = 0
    volume: float = 0
    filled_vwap: float = 0
    status: Status = Status.SUBMITTING
    created_at: datetime = None

    def __post_init__(self):
        if self.order_type not in ORDERTYPE_MAP.keys():
            self.order_type = ORDERTYPE_MAP.UNKNOWN
        else:
            self.order_type = STATUS_MAP[self.order_type]
        if self.status not in STATUS_MAP.keys():
            self.status = Status.UNKNOWN
        else:
            self.status = STATUS_MAP[self.status]
        if self.side == 1:
            self.side = Direction.LONG
        else:
            self.side = Direction.SHORT

        self.vt_orderid = f"{self.order_id}.{self.symbol}"

    def is_active(self) -> bool:
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False

    def create_cancel_request(self) -> "CancelRequest":
        req = CancelRequest(
            order_id=self.order_id, symbol=self.symbol
        )
        return req


@dataclass
class PositionData:
    """
    Positon data
    """
    symbol: str
    side: Direction
    volume: float = 0
    volume_today: float = 0
    available: float = 0
    cost: float = 0
    vwap: float = 0
    fpnl: float = 0
    order_frozen: float = 0

    def __post_init__(self):
        self.volume=round(self.volume,2)
        self.volume_today=round(self.volume_today,2)
        self.available=round(self.available,2)
        self.cost=round(self.cost,2)
        self.vwap=round(self.vwap,2)
        self.fpnl=round(self.fpnl,2)
        if self.side == 1:
            self.side = Direction.LONG
        else:
            self.side = Direction.SHORT
        self.available = self.volume - self.volume_today - self.order_frozen
        self.vt_positionid = f"{self.symbol}"


@dataclass
class AccountData:
    """
    Account data
    """

    account_id: str
    nav: float = 0
    pnl: float = 0
    available: float = 0
    cum_trade: float = 0
    cum_commission: float = 0
    order_frozen: float = 0

    def __post_init__(self):
        self.nav=round(self.nav, 2)
        self.pnl=round(self.pnl, 2)
        self.available=round(self.available, 2)
        self.cum_trade=round(self.cum_trade, 2)
        self.cum_commission=round(self.cum_commission, 2)
        self.order_frozen=round(self.order_frozen, 2)
        self.vt_accountid = f"{self.account_id}"


@dataclass
class LogData:
    msg: str
    level: int = INFO

    def __post_init__(self):
        self.time = datetime.now()


@dataclass
class OrderRequest:
    symbol: str
    exchange: Exchange
    direction: Direction
    type: OrderType
    volume: float
    price: float = 0
    offset: Offset = Offset.NONE
    reference: str = ""

    def __post_init__(self):
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def create_order_data(self, order_id: str) -> OrderData:
        order = OrderData(
            symbol=self.symbol,
            price=self.price,
            volume=self.volume
        )
        return order


@dataclass
class CancelRequest:
    order_id: str
    symbol: str
    exchange: Exchange

    def __post_init__(self):
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class HistoryRequest:
    symbol: str
    exchange: Exchange
    start: date
    end: date = None
    interval: Interval = None

    def __post_init__(self):
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class StopOrder:
    vt_symbol: str
    direction: Direction
    offset: Offset
    price: float
    volume: float
    stop_orderid: str
    strategy_name: str
    lock: bool = False
    vt_orderids: list = field(default_factory=list)
    status: StopOrderStatus = StopOrderStatus.WAITING
