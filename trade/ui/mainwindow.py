import webbrowser
from functools import partial
from importlib import import_module
from typing import Callable, Dict, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets
from .widget import (
    ChanTuWidget,
    AboutDialog
)
from trade.chantu import ChanTuManager
from ..constant import EVENT_CHANTU, Interval
from ..engine import MainEngine, Event
from ..utility import get_icon_path


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, main_engine: MainEngine):
        super(MainWindow, self).__init__()
        self.main_engine: MainEngine = main_engine

        self.window_title: str = f"缠论图形工具项目"

        self.widgets: Dict[str, QtWidgets.QWidget] = {}

        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle(self.window_title)
        self.init_dock()
        self.init_toolbar()
        self.init_menu()
        self.load_window_setting("custom")
        event = Event(type=EVENT_CHANTU, data={
            'strategy_name': 'chantu',
            'vt_symbol': '600519',
            'setting': {
                'start_time': "2021-11-01",
                'include': True,
                'interval': Interval.MINUTE,
                'include_feature': False,
                'qjt': True,
                'gz': True,
                'build_pivot': False,
                'time_interval': 0
            },
        })
        # self.main_engine.put(event)


    def init_dock(self) -> None:
        market_widget, market_dock = self.create_dock(
            ChanTuManager, "行情", QtCore.Qt.LeftDockWidgetArea
        )
        market_dock.raise_()

        self.save_window_setting("default")

    def init_menu(self) -> None:
        bar = self.menuBar()

        # System menu
        sys_menu = bar.addMenu("功能")
        self.add_menu_action(
            sys_menu,
            "股票缠图",
            "cw.ico",
            partial(self.open_widget, ChanTuWidget, "股票缠图"),
        )
        sys_menu.addSeparator()

        self.add_menu_action(sys_menu, "退出", "exit.ico", self.close)

        # Help menu
        help_menu = bar.addMenu("帮助")

        self.add_menu_action(
            help_menu, "还原窗口", "restore.ico", self.restore_window_setting
        )

        self.add_menu_action(
            help_menu, "系统源码", "GitHub.ico", self.open_github
        )

        self.add_menu_action(
            help_menu,
            "关于",
            "about.ico",
            partial(self.open_widget, AboutDialog, "about"),
        )

    def init_toolbar(self) -> None:
        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setObjectName("工具栏")
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)

        # Set button size
        w = 40
        size = QtCore.QSize(w, w)
        self.toolbar.setIconSize(size)

        # Set button spacing
        self.toolbar.layout().setSpacing(10)

        self.addToolBar(QtCore.Qt.LeftToolBarArea, self.toolbar)

    def add_menu_action(
            self,
            menu: QtWidgets.QMenu,
            action_name: str,
            icon_name: str,
            func: Callable,
    ) -> None:
        icon = QtGui.QIcon(get_icon_path(__file__, icon_name))

        action = QtWidgets.QAction(action_name, self)
        action.triggered.connect(func)
        action.setIcon(icon)

        menu.addAction(action)

    def add_toolbar_action(
            self,
            action_name: str,
            icon_name: str,
            func: Callable,
    ) -> None:
        icon = QtGui.QIcon(get_icon_path(__file__, icon_name))

        action = QtWidgets.QAction(action_name, self)
        action.triggered.connect(func)
        action.setIcon(icon)

        self.toolbar.addAction(action)

    def create_dock(
            self,
            widget_class: QtWidgets.QWidget,
            name: str,
            area: int
    ) -> Tuple[QtWidgets.QWidget, QtWidgets.QDockWidget]:
        widget = widget_class(self.main_engine)

        dock = QtWidgets.QDockWidget(name)
        dock.setWidget(widget)
        dock.setObjectName(name)
        dock.setFeatures(dock.DockWidgetFloatable | dock.DockWidgetMovable)
        self.addDockWidget(area, dock)
        return widget, dock

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "退出",
            "确认退出？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply == QtWidgets.QMessageBox.Yes:
            for widget in self.widgets.values():
                widget.close()
            self.save_window_setting("custom")

            self.main_engine.close()

            event.accept()
        else:
            event.ignore()

    def open_widget(self, widget_class: QtWidgets.QWidget, name: str) -> None:
        widget = self.widgets.get(name, None)
        if not widget:
            widget = widget_class(self.main_engine)
            self.widgets[name] = widget

        if isinstance(widget, QtWidgets.QDialog):
            widget.exec_()
        else:
            widget.show()

    def save_window_setting(self, name: str):
        settings = QtCore.QSettings(self.window_title, name)
        settings.setValue("state", self.saveState())
        settings.setValue("geometry", self.saveGeometry())

    def load_window_setting(self, name: str) -> None:
        settings = QtCore.QSettings(self.window_title, name)
        state = settings.value("state")
        geometry = settings.value("geometry")

        if isinstance(state, QtCore.QByteArray):
            self.restoreState(state)
            self.restoreGeometry(geometry)

    def restore_window_setting(self) -> None:
        self.load_window_setting("default")
        self.showMaximized()

    def open_github(self) -> None:
        webbrowser.open("https://github.com/dogfun/chan")
