from typing import Any, Sequence, Type, Dict, List, Optional, Set
from trade.constant import (
    Status,
    INTERVAL_DELTA_MAP,
    StopOrderStatus,
    EVENT_BAR, EVENT_RENDER
)

from trade.utility import load_json, save_json, extract_vt_symbol, round_to, check_run_time, trans_setting
import os
from trade.jqdata import jqdata_client

STOP_STATUS_MAP = {
    Status.SUBMITTING: StopOrderStatus.WAITING,
    Status.NOTTRADED: StopOrderStatus.WAITING,
    Status.PARTTRADED: StopOrderStatus.TRIGGERED,
    Status.ALLTRADED: StopOrderStatus.TRIGGERED,
    Status.CANCELLED: StopOrderStatus.CANCELLED,
    Status.REJECTED: StopOrderStatus.CANCELLED
}
from .utility import get_folder_path, TRADER_DIR
from collections import defaultdict
from queue import Empty, Queue
from threading import Thread
from time import sleep
from typing import Any, Callable, List

EVENT_TIMER = "eTimer"


class Event:
    def __init__(self, type: str, data: Any = None):
        self.type: str = type
        self.data: Any = data


HandlerType = Callable[[Event], None]


class MainEngine:

    def __init__(self, interval: int = 1):
        self._interval: int = interval
        self._queue: Queue = Queue()
        self._active: bool = False
        self._thread: Thread = Thread(target=self._run)
        self._timer: Thread = Thread(target=self._run_timer)
        self._bar: Thread = Thread(target=self._run_bar)
        self._bar_map: defaultdict = defaultdict(str)
        self._handlers: defaultdict = defaultdict(list)
        self._symbol_set: Set[str] = set()
        self._general_handlers: List = []
        os.chdir(TRADER_DIR)
        self.start()

    def _run(self) -> None:
        while self._active:
            try:
                event = self._queue.get(block=True, timeout=1)
                self._process(event)
            except Empty:
                pass

    def _process(self, event: Event) -> None:
        if event.type in self._handlers:
            [handler(event) for handler in self._handlers[event.type]]

        if self._general_handlers:
            [handler(event) for handler in self._general_handlers]

    def _run_bar(self) -> None:
        while self._active:
            if check_run_time():
                for vt_symbol in self._symbol_set:
                    data = jqdata_client.query_bar_xq(vt_symbol)
                    if data and (not self._bar_map[vt_symbol] or self._bar_map[vt_symbol] != str(data.datetime)):
                        event = Event(EVENT_BAR, data)
                        self.put(event)
                        self._bar_map[vt_symbol] = str(data.datetime)
            sleep(5)

    def _run_timer(self) -> None:
        while self._active:
            sleep(self._interval)
            event = Event(EVENT_TIMER)
            self.put(event)

    def subscribe(self, vt_sybmol: str) -> None:
        self._symbol_set.add(vt_sybmol)

    def unsubscribe(self, vt_sybmol: str) -> None:
        self._symbol_set.remove(vt_sybmol)

    def start(self) -> None:
        self._active = True
        self._thread.start()
        self._timer.start()
        self._bar.start()

    def stop(self) -> None:
        self._active = False
        self._timer.join()
        self._thread.join()
        self._bar.join()

    def put(self, event: Event) -> None:
        self._queue.put(event)

    def register(self, type: str, handler: HandlerType) -> None:
        handler_list = self._handlers[type]
        if handler not in handler_list:
            handler_list.append(handler)

    def unregister(self, type: str, handler: HandlerType) -> None:
        handler_list = self._handlers[type]

        if handler in handler_list:
            handler_list.remove(handler)

        if not handler_list:
            self._handlers.pop(type)

    def register_general(self, handler: HandlerType) -> None:
        if handler not in self._general_handlers:
            self._general_handlers.append(handler)

    def unregister_general(self, handler: HandlerType) -> None:
        if handler in self._general_handlers:
            self._general_handlers.remove(handler)

    def write_log(self, msg: str, source: str = "") -> None:
        print(msg)

    def close(self) -> None:
        self.stop()