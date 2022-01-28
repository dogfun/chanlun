import csv
import platform
from datetime import datetime, timedelta
from typing import Any, Dict
from copy import copy
from tzlocal import get_localzone
from PyQt5 import QtCore, QtGui, QtWidgets, Qt
import numpy as np
from trade.constant import (
    EVENT_CHANTU,
    EVENT_TRADE,
    EVENT_ORDER,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_LOG, Direction, Interval
)
from ..engine import MainEngine, Event

COLOR_LONG = QtGui.QColor("red")
COLOR_SHORT = QtGui.QColor("green")
COLOR_BID = QtGui.QColor(255, 174, 201)
COLOR_ASK = QtGui.QColor(160, 255, 160)
COLOR_BLACK = QtGui.QColor("black")


class BaseCell(QtWidgets.QTableWidgetItem):

    def __init__(self, content: Any, data: Any):
        super(BaseCell, self).__init__()
        self.setTextAlignment(QtCore.Qt.AlignCenter)
        self.set_content(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        self.setText(str(content))
        self._data = data

    def get_data(self) -> Any:
        return self._data


class EnumCell(BaseCell):
    """
    Cell used for showing enum data.
    """

    def __init__(self, content: str, data: Any):
        super(EnumCell, self).__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        Set text using enum.constant.value.
        """
        if content:
            super(EnumCell, self).set_content(content.value, data)


class DirectionCell(EnumCell):
    """
    Cell used for showing direction data.
    """

    def __init__(self, content: str, data: Any):
        """"""
        super(DirectionCell, self).__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        Cell color is set according to direction.
        """
        super(DirectionCell, self).set_content(content, data)
        if content is Direction.SHORT:
            self.setForeground(COLOR_SHORT)
        else:
            self.setForeground(COLOR_LONG)


class BidCell(BaseCell):
    """
    Cell used for showing bid price and volume.
    """

    def __init__(self, content: Any, data: Any):
        super(BidCell, self).__init__(content, data)

        self.setForeground(COLOR_BID)


class AskCell(BaseCell):
    """
    Cell used for showing ask price and volume.
    """

    def __init__(self, content: Any, data: Any):
        super(AskCell, self).__init__(content, data)

        self.setForeground(COLOR_ASK)


class PnlCell(BaseCell):
    """
    Cell used for showing pnl data.
    """

    def __init__(self, content: Any, data: Any):
        """"""
        super(PnlCell, self).__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        Cell color is set based on whether pnl is
        positive or negative.
        """
        super(PnlCell, self).set_content(content, data)

        if str(content).startswith("-"):
            self.setForeground(COLOR_SHORT)
        else:
            self.setForeground(COLOR_LONG)


class TimeCell(BaseCell):
    """
    Cell used for showing time string from datetime object.
    """

    local_tz = get_localzone()

    def __init__(self, content: Any, data: Any):
        super(TimeCell, self).__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        if content is None:
            return

        content = content.astimezone(self.local_tz)
        timestamp = content.strftime("%H:%M:%S")

        millisecond = int(content.microsecond / 1000)
        if millisecond:
            timestamp = f"{timestamp}.{millisecond}"

        self.setText(timestamp)
        self._data = data


class MsgCell(BaseCell):
    """
    Cell used for showing msg data.
    """

    def __init__(self, content: str, data: Any):
        super(MsgCell, self).__init__(content, data)
        self.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)


class BaseMonitor(QtWidgets.QTableWidget):
    event_type: str = ""
    data_key: str = ""
    sorting: bool = False
    headers: Dict[str, dict] = {}

    signal: QtCore.pyqtSignal = QtCore.pyqtSignal(Event)

    def __init__(self, main_engine: MainEngine):
        super(BaseMonitor, self).__init__()

        self.main_engine: MainEngine = main_engine
        self.cells: Dict[str, dict] = {}

        self.init_ui()
        self.register_event()

    def init_ui(self) -> None:
        self.init_table()
        self.init_menu()

    def init_table(self) -> None:
        self.setColumnCount(len(self.headers))

        labels = [d["display"] for d in self.headers.values()]
        self.setHorizontalHeaderLabels(labels)

        self.verticalHeader().setVisible(False)
        self.setEditTriggers(self.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(self.sorting)

    def init_menu(self) -> None:
        """
        Create right click menu.
        """
        self.menu = QtWidgets.QMenu(self)

        resize_action = QtWidgets.QAction("调整列宽", self)
        resize_action.triggered.connect(self.resize_columns)
        self.menu.addAction(resize_action)

        save_action = QtWidgets.QAction("保存数据", self)
        save_action.triggered.connect(self.save_csv)
        self.menu.addAction(save_action)

    def register_event(self) -> None:
        """
        Register event handler into event engine.
        """
        if self.event_type:
            self.signal.connect(self.process_event)
            self.main_engine.register(self.event_type, self.signal.emit)

    def process_event(self, event: Event) -> None:
        """
        Process new data from event and update into table.
        """
        # Disable sorting to prevent unwanted error.
        if self.sorting:
            self.setSortingEnabled(False)

        # Update data into table.
        data = event.data

        if not self.data_key:
            self.insert_new_row(data)
        else:
            key = data.__getattribute__(self.data_key)

            if key in self.cells:
                self.update_old_row(data)
            else:
                self.insert_new_row(data)

        # Enable sorting
        if self.sorting:
            self.setSortingEnabled(True)

    def insert_new_row(self, data: Any):
        self.insertRow(0)

        row_cells = {}
        for column, header in enumerate(self.headers.keys()):
            setting = self.headers[header]

            content = data.__getattribute__(header)
            cell = setting["cell"](content, data)
            self.setItem(0, column, cell)

            if setting["update"]:
                row_cells[header] = cell

        if self.data_key:
            key = data.__getattribute__(self.data_key)
            self.cells[key] = row_cells

    def update_old_row(self, data: Any) -> None:
        """
        Update an old row in table.
        """
        key = data.__getattribute__(self.data_key)
        row_cells = self.cells[key]

        for header, cell in row_cells.items():
            content = data.__getattribute__(header)
            cell.set_content(content, data)

    def resize_columns(self) -> None:
        """
        Resize all columns according to contents.
        """
        self.horizontalHeader().resizeSections(QtWidgets.QHeaderView.ResizeToContents)

    def save_csv(self) -> None:
        """
        Save table data into a csv file
        """
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存数据", "", "CSV(*.csv)")

        if not path:
            return

        with open(path, "w") as f:
            writer = csv.writer(f, lineterminator="\n")

            writer.writerow(self.headers.keys())

            for row in range(self.rowCount()):
                row_data = []
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if item:
                        row_data.append(str(item.text()))
                    else:
                        row_data.append("")
                writer.writerow(row_data)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """
        Show menu with right click.
        """
        self.menu.popup(QtGui.QCursor.pos())


class LogMonitor(BaseMonitor):
    event_type = EVENT_LOG
    data_key = ""
    sorting = False

    headers = {
        "time": {"display": "时间", "cell": TimeCell, "update": False},
        "msg": {"display": "信息", "cell": MsgCell, "update": False}
    }


class TradeMonitor(BaseMonitor):
    event_type = EVENT_TRADE
    data_key = ""
    sorting = True

    headers: Dict[str, dict] = {
        "tradeid": {"display": "成交号 ", "cell": BaseCell, "update": False},
        "orderid": {"display": "委托号", "cell": BaseCell, "update": False},
        "symbol": {"display": "代码", "cell": BaseCell, "update": False},
        "exchange": {"display": "交易所", "cell": EnumCell, "update": False},
        "direction": {"display": "方向", "cell": DirectionCell, "update": False},
        "offset": {"display": "开平", "cell": EnumCell, "update": False},
        "price": {"display": "价格", "cell": BaseCell, "update": False},
        "volume": {"display": "数量", "cell": BaseCell, "update": False},
        "datetime": {"display": "时间", "cell": TimeCell, "update": False}
    }


class OrderMonitor(BaseMonitor):
    """
    Monitor for order data.
    """

    event_type = EVENT_ORDER
    data_key = "vt_orderid"
    sorting = True

    headers: Dict[str, dict] = {
        "order_id": {"display": "委托ID", "cell": BaseCell, "update": False},
        "symbol": {"display": "股票代码", "cell": BaseCell, "update": False},
        # "exchange": {"display": "交易所", "cell": EnumCell, "update": False},
        "order_type": {"display": "委托类型", "cell": EnumCell, "update": False},
        "side": {"display": "方向", "cell": DirectionCell, "update": False},
        # "offset": {"display": "开平", "cell": EnumCell, "update": False},
        "price": {"display": "委托价格", "cell": BaseCell, "update": False},
        "volume": {"display": "委托量", "cell": BaseCell, "update": True},
        "filled_vwap": {"display": "成交均价", "cell": BaseCell, "update": True},
        "status": {"display": "委托状态", "cell": EnumCell, "update": True},
        "created_at": {"display": "委托时间", "cell": TimeCell, "update": True},
        "ord_rej_reason_detail": {"display": "委托拒绝原因", "cell": BaseCell, "update": True}
    }

    def init_ui(self):
        """
        Connect signal.
        """
        super(OrderMonitor, self).init_ui()

        self.setToolTip("双击单元格撤单")
        self.itemDoubleClicked.connect(self.cancel_order)

    def cancel_order(self, cell: BaseCell) -> None:
        """
        Cancel order if cell double clicked.
        """
        order = cell.get_data()
        req = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)


class PositionMonitor(BaseMonitor):
    """
    Monitor for position data.
    """

    event_type = EVENT_POSITION
    data_key = "vt_positionid"
    sorting = True

    headers = {
        "symbol": {"display": "股票代码", "cell": BaseCell, "update": False},
        "side": {"display": "方向", "cell": DirectionCell, "update": False},
        "volume": {"display": "总持仓量", "cell": BaseCell, "update": True},
        "volume_today": {"display": "今日持仓量", "cell": BaseCell, "update": True},
        "available": {"display": "可平仓位", "cell": BaseCell, "update": False},
        "order_frozen": {"display": "冻结仓位", "cell": BaseCell, "update": False},
        "cost": {"display": "持仓成本", "cell": BaseCell, "update": True},
        "vwap": {"display": "持仓均价", "cell": BaseCell, "update": True},
        "fpnl": {"display": "盈亏", "cell": PnlCell, "update": True}
    }


class AccountMonitor(BaseMonitor):
    event_type = EVENT_ACCOUNT
    data_key = "vt_accountid"
    sorting = True

    headers = {
        "account_id": {"display": "账号", "cell": BaseCell, "update": False},
        "nav": {"display": "净值", "cell": BaseCell, "update": True},
        "pnl": {"display": "净收益", "cell": BaseCell, "update": True},
        "available": {"display": "可用资金", "cell": BaseCell, "update": True},
        "cum_trade": {"display": "累计交易额", "cell": BaseCell, "update": True},
        "cum_commission": {"display": "累计手续费", "cell": BaseCell, "update": True},
        "order_frozen": {"display": "冻结资金", "cell": BaseCell, "update": True}
    }


class ChanTuWidget(QtWidgets.QDialog):

    def __init__(self, main_engine: MainEngine):
        super().__init__()

        self.main_engine: MainEngine = main_engine

        self.vt_symbol: str = ""
        self.price_digits: int = 0

        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("股票缠图")
        self.setFixedWidth(400)
        self.jquser_line = QtWidgets.QLineEdit()
        self.jqpass_line = QtWidgets.QLineEdit()
        self.symbol_line = QtWidgets.QLineEdit()
        self.symbol_line.setText("600809")
        self.k_line_include_combo = QtWidgets.QComboBox()
        self.k_line_include_combo.addItems(['缠论K线', '普通K线'])
        self.k_line_include_combo.setCurrentIndex(0)
        self.xd_zs_combo = QtWidgets.QComboBox()
        self.xd_zs_combo.addItems(['笔中枢', '线段中枢'])
        self.xd_zs_combo.setCurrentIndex(0)
        # self.feature_include_combo = QtWidgets.QComboBox()
        # self.feature_include_combo.addItems(['True', 'False'])
        # self.feature_include_combo.setCurrentIndex(1)
        self.qjt_combo = QtWidgets.QComboBox()
        self.qjt_combo.addItems(['是', '否'])
        self.qjt_combo.setCurrentIndex(0)
        self.gz_combo = QtWidgets.QComboBox()
        self.gz_combo.addItems(['是', '否'])
        self.gz_combo.setCurrentIndex(0)
        self.time_interval_line = QtWidgets.QLineEdit()
        self.time_interval_line.setText("10")
        self.start_time_line = QtWidgets.QLineEdit()
        self.start_time_line.setText("2022-01-01")

        chan_button = QtWidgets.QPushButton("确定")
        chan_button.clicked.connect(self.show_chan)

        grid = QtWidgets.QGridLayout()
        grid.addWidget(QtWidgets.QLabel("聚宽账号"), 0, 0)
        grid.addWidget(QtWidgets.QLabel("聚宽密码"), 1, 0)
        grid.addWidget(QtWidgets.QLabel("股票代码"), 2, 0)
        grid.addWidget(QtWidgets.QLabel("开始日期"), 3, 0)
        grid.addWidget(QtWidgets.QLabel("K线类型"), 4, 0)
        grid.addWidget(QtWidgets.QLabel("中枢类型"), 5, 0)
        # grid.addWidget(QtWidgets.QLabel("特序包含"), 3, 0)
        grid.addWidget(QtWidgets.QLabel("用区间套"), 6, 0)
        grid.addWidget(QtWidgets.QLabel("使用共振"), 7, 0)
        grid.addWidget(QtWidgets.QLabel("展现间隔"), 8, 0)
        grid.addWidget(self.jquser_line, 0, 1, 1, 2)
        grid.addWidget(self.jqpass_line, 1, 1, 1, 2)
        grid.addWidget(self.symbol_line, 2, 1, 1, 2)
        grid.addWidget(self.start_time_line, 3, 1, 1, 2)
        grid.addWidget(self.k_line_include_combo, 4, 1, 1, 2)
        grid.addWidget(self.xd_zs_combo, 5, 1, 1, 2)
        # grid.addWidget(self.feature_include_combo, 3, 1, 1, 2)
        grid.addWidget(self.qjt_combo, 6, 1, 1, 2)
        grid.addWidget(self.gz_combo, 7, 1, 1, 2)
        grid.addWidget(self.time_interval_line, 8, 1, 1, 2)
        grid.addWidget(chan_button, 9, 0, 1, 3)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(grid)
        self.setLayout(vbox)

    def show_chan(self):
        jquser = self.jquser_line.text()
        jqpass = self.jqpass_line.text()
        vt_symbol = self.symbol_line.text()
        start_time = self.start_time_line.text()
        k_line_include = self.k_line_include_combo.currentText()
        if k_line_include == '缠论K线':
            k_line_include = True
        else:
            k_line_include = False
        xd_zs = self.xd_zs_combo.currentText()
        if xd_zs == '线段中枢':
            xd_zs = True
        else:
            xd_zs = False
        # feature_include = self.feature_include_combo.currentText()
        # if feature_include == 'True':
        #     feature_include=True
        # else:
        #     feature_include=False
        qjt = self.qjt_combo.currentText()
        if qjt == '是':
            qjt = True
        else:
            qjt = False
        gz = self.gz_combo.currentText()
        if gz == '是':
            gz = True
        else:
            gz = False
        time_interval = self.time_interval_line.text()
        self.bt_engine = self.main_engine
        event = Event(type=EVENT_CHANTU, data={
            'strategy_name': 'chantu',
            'jquser': jquser,
            'jqpass': jqpass,
            'vt_symbol': vt_symbol,
            'start_time': start_time,
            'setting': {
                'include': k_line_include,
                'interval': Interval.MINUTE,
                # 'include_feature': feature_include,
                'include_feature': False,
                'qjt': qjt,
                'gz': gz,
                'build_pivot': xd_zs,
                'time_interval': int(time_interval)
            },

        })
        self.main_engine.put(event)
        self.accept()

    def set_vt_symbol(self) -> None:
        """
        Set the tick depth data to monitor by vt_symbol.
        """
        symbol = str(self.symbol_line.text())
        if not symbol:
            return

        # Generate vt_symbol from symbol and exchange
        exchange_value = str(self.exchange_combo.currentText())
        vt_symbol = f"{symbol}.{exchange_value}"

        if vt_symbol == self.vt_symbol:
            return
        self.vt_symbol = vt_symbol

        # Update name line widget and clear all labels
        contract = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.name_line.setText("")
            gateway_name = self.gateway_combo.currentText()
        else:
            self.name_line.setText(contract.name)
            gateway_name = contract.gateway_name
            ix = self.gateway_combo.findText(gateway_name)
            self.gateway_combo.setCurrentIndex(ix)
            self.price_digits = 2

        self.clear_label_text()
        self.volume_line.setText("")
        self.price_line.setText("")

    def clear_label_text(self) -> None:
        self.lp_label.setText("")
        self.return_label.setText("")

        self.bv1_label.setText("")
        self.bv2_label.setText("")
        self.bv3_label.setText("")
        self.bv4_label.setText("")
        self.bv5_label.setText("")

        self.av1_label.setText("")
        self.av2_label.setText("")
        self.av3_label.setText("")
        self.av4_label.setText("")
        self.av5_label.setText("")

        self.bp1_label.setText("")
        self.bp2_label.setText("")
        self.bp3_label.setText("")
        self.bp4_label.setText("")
        self.bp5_label.setText("")

        self.ap1_label.setText("")
        self.ap2_label.setText("")
        self.ap3_label.setText("")
        self.ap4_label.setText("")
        self.ap5_label.setText("")


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, main_engine: MainEngine):
        super().__init__()
        self.main_engine: MainEngine = main_engine
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle(f"关于<缠论图形工具项目>")

        text = f"""
            License：MIT
            URL：https://github.com/dogfun/chan

            Python - {platform.python_version()}
            PyQt5 - {Qt.PYQT_VERSION_STR}
            Numpy - {np.__version__}
            """

        label = QtWidgets.QLabel()
        label.setText(text)
        label.setMinimumWidth(500)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(label)
        self.setLayout(vbox)

