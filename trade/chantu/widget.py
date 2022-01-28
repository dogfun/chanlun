from datetime import datetime, timedelta

from PyQt5.QtWidgets import QMessageBox

import pandas as pd
from functools import partial
from typing import List
from trade.engine import MainEngine, Event
from trade.ui import QtCore, QtWidgets, QtGui
from PyQt5.QtWebEngineWidgets import QWebEngineView
from pathlib import Path
from trade.constant import FREQS, EVENT_CHANTU, EVENT_RENDER
from trade.strategies.chan_strategy import Chan_Strategy
from trade.object import HistoryRequest, Interval, Exchange
from trade.jqdata import jqdata_client
import talib as tl
from threading import Thread
import json
import time

ENGINE = 'CHANTU'


class ChanTuManager(QtWidgets.QWidget):
    signal_chantu = QtCore.pyqtSignal(Event)
    signal_render = QtCore.pyqtSignal(Event)

    def __init__(self, main_engine: MainEngine):
        super().__init__()

        self.main_engine = main_engine
        self.tabWidget = QtWidgets.QTabWidget(self)
        self.ROOT_PATH = Path(__file__).parent
        self.URL = str(self.ROOT_PATH.joinpath("chart.html")).replace('\\', '/')

        self.ans = None
        self.thread = None
        self.state = False
        self.kline_html_map = {}
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("股票缠图")
        self.tabWidget.setObjectName("tabWidget")
        self.register_event()
        self.tabWidget.setMinimumWidth(1800)
        self.tabWidget.setMinimumHeight(900)
        for freq in FREQS:
            freq_widget = QtWidgets.QWidget()
            self.tabWidget.addTab(freq_widget, freq)
            kline_html = QWebEngineView()
            self.kline_html_map[freq] = kline_html
            kline_html.page().setBackgroundColor(QtGui.QColor(17, 17, 17))
            kline_html.load(QtCore.QUrl(self.URL))
            qhlayout = QtWidgets.QHBoxLayout()
            qhlayout.addWidget(kline_html)
            freq_widget.setLayout(qhlayout)
            part = partial(self.load, kline_html)
            kline_html.loadFinished.connect(part)

    def load(self, kline_html):
        kline_html.page().runJavaScript(self.ans)

    def run_chan(self, event: Event):
        if self.thread and self.thread.is_alive():
            self.state = True
            self.thread.join()
        self.state = False
        self.thread = Thread(
            target=self.run_strategy,
            kwargs=(event.data)
        )
        self.thread.start()

    def run_strategy(self, strategy_name, vt_symbol, jquser, jqpass, start_time, setting):
        # strategy_name = event.data['strategy_name']
        # vt_symbol = event.data['vt_symbol']
        # setting = event.data['setting']
        # include = event.data['include']
        # interval = event.data['interval']
        # include_feature = event.data['include_feature']
        # build_pivot = event.data['build_pivot']
        self.render_interval = setting['time_interval']
        chan_strategy = Chan_Strategy(engine=ENGINE, strategy_name=strategy_name, vt_symbol=vt_symbol, setting=setting)
        if len(vt_symbol.strip()) != 6:
            self.main_engine.put(event=Event(EVENT_RENDER, '错误的股票代码：' + vt_symbol))
            print('错误的股票代码：' + vt_symbol)
            return
        exchange = Exchange.SZSE
        if vt_symbol[0] == '6':
            exchange = Exchange.SSE
        now_time = datetime.now()
        req = HistoryRequest(
            symbol=vt_symbol,
            exchange=exchange,
            interval=setting['interval'],
            start=start_time,
            end=now_time.date()
        )
        time_start = time.time()

        jqdata_client.init(jquser, jqpass)
        if not jqdata_client.inited:
            self.main_engine.put(event=Event(EVENT_RENDER, '聚宽账号或者密码错误！'))
            return

        rawData, BarDataList = jqdata_client.query_history(req)
        time_end = time.time()
        if len(BarDataList) <= 0:
            self.main_engine.put(event=Event(EVENT_RENDER, '获取K线错误，请检查开始日期'))
            print('获取K线错误，请检查开始日期')
            return
        print('获取k线花费时间：', time_end - time_start)
        print('总的1分钟k线数据大小：' + str(len(BarDataList)))
        time_start = time_end
        i = 1
        for bar in BarDataList:
            chan_strategy.on_bar(bar)
            if self.state:
                break
            if self.render_interval > 0 and i % self.render_interval == 0:
                self.render_html(chan_strategy, setting['include'])
            i += 1
        self.render_html(chan_strategy, setting['include'])
        chan_map = chan_strategy.chan_freq_map
        for freq in chan_map:
            chan = chan_map[freq]
            print(freq)
            print(len(chan.chan_k_list))
            # 统计信息
            self.sum_bs(chan.buy_list, chan.sell_list, freq)
        time_end = time.time()
        print('缠论计算 totally cost', time_end - time_start)

    def render_html(self, chan_strategy, include=True):
        chan_map = chan_strategy.chan_freq_map
        for freq in chan_map:
            klist = pd.DataFrame(columns=["date", "open", "close", "low", "high", "volume"], dtype=object)
            chan = chan_map[freq]
            format_str = '%Y-%m-%d %H:%M'
            if freq == FREQS[0]:
                format_str = '%Y-%m-%d'
            for k in chan.chan_k_list:
                klist = klist.append({
                    "date": k.datetime.strftime(format_str), "open": k.open_price, "close": k.close_price,
                    "low": k.low_price,
                    "high": k.high_price, "volume": k.volume
                }, ignore_index=True)
            bl = self.reFormatBS(chan.buy_list, format_str)
            sl = self.reFormatBS(chan.sell_list, format_str)
            if len(klist) <= 0:
                continue
            dif, dea, macd = tl.MACD(klist['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
            Macd = {}
            macd *= 2
            Macd['dif'] = dif.tolist()
            Macd['dea'] = dea.tolist()
            Macd['macd'] = macd.tolist()
            Macd = json.dumps(Macd)
            self.ans = self.plot(
                klist.to_json(orient='split'),
                self.reFormatLine(chan.stroke_list, format_str),
                self.reFormatLine(chan.line_list, format_str),
                self.reFormatPivot(chan.pivot_list, format_str),
                [],
                [],
                [],
                Macd,
                bl,
                sl,
                [],
                []
            )
            kline_html = self.kline_html_map[freq]
            self.load(kline_html)

    def render_event(self, event: Event):
        QMessageBox.information(self, self.windowTitle(), event.data, QMessageBox.Yes)

    def sum_bs(self, buy, sell, freq):
        b1_valid = set()
        b1_invalid = set()
        b2_valid = set()
        b2_invalid = set()
        b3_valid = set()
        b3_invalid = set()

        s1_valid = set()
        s1_invalid = set()
        s2_valid = set()
        s2_invalid = set()
        s3_valid = set()
        s3_invalid = set()
        for data in buy:
            if data[5] == 1:
                if data[2] == 'B1':
                    b1_valid.add(data[0])
                if data[2] == 'B2':
                    b2_valid.add(data[0])
                if data[2] == 'B3':
                    b3_valid.add(data[0])
            else:
                if data[2] == 'B1':
                    b1_invalid.add(data[0])
                if data[2] == 'B2':
                    b2_invalid.add(data[0])
                if data[2] == 'B3':
                    b3_invalid.add(data[0])

        for data in sell:
            if data[5] == 1:
                if data[2] == 'S1':
                    s1_valid.add(data[0])
                if data[2] == 'S2':
                    s2_valid.add(data[0])
                if data[2] == 'S3':
                    s3_valid.add(data[0])
            else:
                if data[2] == 'S1':
                    s1_invalid.add(data[0])
                if data[2] == 'S2':
                    s2_invalid.add(data[0])
                if data[2] == 'S3':
                    s3_invalid.add(data[0])
        print(freq + ':')
        print("valid: B1\tB2\tB3")
        print(f'{len(b1_valid)}\t{len(b2_valid)}\t{len(b3_valid)}')
        print("invalid: B1\tB2\tB3")
        print(f'{len(b1_invalid)}\t{len(b2_invalid)}\t{len(b3_invalid)}')

        print("valid: S1\tS2\tS3")
        print(f'{len(s1_valid)}\t{len(s2_valid)}\t{len(s3_valid)}')
        print("invalid: S1\tS2\tS3")
        print(f'{len(s1_invalid)}\t{len(s2_invalid)}\t{len(s3_invalid)}')

    def register_event(self):
        self.signal_chantu.connect(self.run_chan)
        self.main_engine.register(EVENT_CHANTU, self.signal_chantu.emit)
        self.signal_render.connect(self.render_event)
        self.main_engine.register(EVENT_RENDER, self.signal_render.emit)

    def plot(self, kline: List,
             bi: List = [],
             xd: List = [],
             zs: List = [],
             ma10: List = [],
             ma20: List = [],
             ma30: List = [],
             macd: List = [],
             bl: List = [],
             sl: List = [],
             x_bl: List = [],
             x_sl: List = []
             ):
        pivot = self.reFormatPivotList(zs)
        b1, b2, b3, s1, s2, s3 = self.reFormatBuyAndSell(bl, sl)
        js = """
        var data = getData(%s["data"])
        var Macd = %s
        myChart.setOption({
            xAxis: [
                {data:data.date},
                {data:data.date},
                {data:data.date}],
            series: [{
                name: 'K线',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: data.values,
            },{
                name: 'MA10',
                data: %s["data"],
            },{
                name: 'MA20',
                data: %s["data"],
            },{
                name: 'MA30',
                data: %s["data"],
            },{
                name: 'MACD',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: Macd["macd"],
                itemStyle:{
                    normal:{
                        color:function(params){
                            if(params.value >0){
                                return color_red;
                            }else{
                                return color_green;
                            }
                        }
                    }
                }
            },{
                name: 'DIF',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: Macd["dif"]
            },{
                name: 'DEA',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: Macd["dea"]
            },{
                name: '成交量',
                xAxisIndex: 2,
                yAxisIndex: 2,
                data: data.volumes
            },{
                name: '笔',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: %s
            },{
                name: '一买',
                data: [],
                xAxisIndex: 0,
                yAxisIndex: 0,
                markPoint: {
                    data: %s,
                    symbolSize: 20,
                    label: {
                        formatter: function (param) {
                            return param != null ? param.data.name.split(';').join('\\n') : '';
                        },
                        show: true,
                        position: "bottom"
                    }
                }
            },{
                name: '二买',
                data: [],
                xAxisIndex: 0,
                yAxisIndex: 0,
                markPoint: {
                    data: %s,
                    symbolSize: 20,
                    label: {
                        formatter: function (param) {
                            return param != null ? param.data.name.split(';').join('\\n') : '';
                        },
                        show: true,
                        position: "bottom"
                    }
                }
            },{
                name: '三买',
                data: [],
                xAxisIndex: 0,
                yAxisIndex: 0,
                markPoint: {
                    data: %s,
                    symbolSize: 20,
                    label: {
                        formatter: function (param) {
                            return param != null ? param.data.name.split(';').join('\\n') : '';
                        },                    
                        show: true,
                        position: "bottom"
                    }
                }
            },{
                name: '一卖',
                data: [],
                xAxisIndex: 0,
                yAxisIndex: 0,
                markPoint: {
                    data: %s,
                    symbolSize: 20,
                    label: {
                        formatter: function (param) {
                            return param != null ? param.data.name.split(';').join('\\n') : '';
                        },
                        show: true,
                        position: "top"
                    }
                }
            },{
                name: '二卖',
                data: [],
                xAxisIndex: 0,
                yAxisIndex: 0,
                markPoint: {
                    data: %s,
                    symbolSize: 20,
                    label: {
                        formatter: function (param) {
                            return param != null ? param.data.name.split(';').join('\\n') : '';
                        },                    
                        show: true,
                        position: "top"
                    }
                }
            },{
                name: '三卖',
                data: [],
                xAxisIndex: 0,
                yAxisIndex: 0,
                markPoint: {
                    data: %s,
                    symbolSize: 20,
                    label: {
                        formatter: function (param) {
                            return param != null ? param.data.name.split(';').join('\\n') : '';
                        },                    
                        show: true,
                        position: "top"
                    }
                }
            }
            ,{
                name: '线段',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: %s
            },{
                name: '中枢',
                data: [],
                xAxisIndex: 0,
                yAxisIndex: 0,
                markArea: {
                    data: %s
                },
            }]
        });
        """ % (kline, macd, ma10, ma20, ma30, bi, b1, b2, b3, s1, s2, s3, xd, pivot)
        return js

    def reFormatPivotList(self, pivotList):
        """将中枢列表更改为js指定格式字符串。"""
        rePivotList = "["
        for Item in pivotList:
            rePivotList += "[{coord: ['%s', %s]},{coord: ['%s', %s]}]," % (Item[0], Item[2], Item[1], Item[3])
        rePivotList += "]"
        return rePivotList

    def reFormatPivot(self, pivot, format_str):
        reformatpivot = []
        for Item in pivot:
            reformatpivot.append(
                [Item[0].strftime(format_str), Item[1].strftime(format_str), Item[2], Item[3]])
        return reformatpivot

    def reFormatLine(self, line, format_str):
        reformatline = []
        for Item in line:
            if Item[3] == 'up':
                reformatline.append([Item[2].strftime(format_str), Item[0]])
            else:
                reformatline.append([Item[2].strftime(format_str), Item[1]])
        return reformatline

    def reFormatBS(self, BS, format_str):
        rebs = []
        for bs in BS:
            valid = '有效'
            if bs[5] == 0:
                valid = '无效'
                rebs.append([bs[0].strftime(format_str), bs[1], bs[2], bs[3].strftime(format_str),
                             valid + ':' + bs[6].strftime(format_str), bs[7], bs[8]])
            else:
                rebs.append([bs[0].strftime(format_str), bs[1], bs[2], bs[3].strftime(format_str), '', bs[7], bs[8]])
        return rebs

    def reFormatBuyAndSell(self, buy, sell):
        """将买卖点列表更改为js指定格式字符串。"""
        reBuyList_1 = "["
        reBuyList_2 = "["
        reBuyList_3 = "["
        if buy:
            for Item in buy:
                sep = ''
                if Item[4]:
                    sep = ';'
                sth = ''
                if Item[6]:
                    sth = ':' + Item[6]
                if Item[2] == 'B1':
                    reBuyList_1 += "{name:'%s', coord: ['%s', %s], value: %s}," % (
                        Item[2] + ':' + Item[3] + sep + Item[4] + ';' + Item[5] + sth, Item[0], Item[1], Item[1])
                elif Item[2] == 'B2':
                    reBuyList_2 += "{name:'%s', coord: ['%s', %s], value: %s}," % (
                        Item[2] + ':' + Item[3] + sep + Item[4] + ';' + Item[5] + sth, Item[0], Item[1], Item[1])
                elif Item[2] == 'B3':
                    reBuyList_3 += "{name:'%s', coord: ['%s', %s], value: %s}," % (
                        Item[2] + ':' + Item[3] + sep + Item[4] + ';' + Item[5] + sth, Item[0], Item[1], Item[1])
        reBuyList_1 += "]"
        reBuyList_2 += "]"
        reBuyList_3 += "]"

        reSellList_1 = "["
        reSellList_2 = "["
        reSellList_3 = "["
        if sell:
            for Item in sell:
                sep = ''
                if Item[4]:
                    sep = ';'
                sth = ''
                if Item[6]:
                    sth = ':' + Item[6]
                if Item[2] == 'S1':
                    reSellList_1 += "{name:'%s', coord: ['%s', %s], value: %s}," % (
                        Item[2] + ':' + Item[3] + sep + Item[4] + ';' + Item[5] + sth, Item[0], Item[1], Item[1])
                elif Item[2] == 'S2':
                    reSellList_2 += "{name:'%s', coord: ['%s', %s], value: %s}," % (
                        Item[2] + ':' + Item[3] + sep + Item[4] + ';' + Item[5] + sth, Item[0], Item[1], Item[1])
                elif Item[2] == 'S3':
                    reSellList_3 += "{name:'%s', coord: ['%s', %s], value: %s}," % (
                        Item[2] + ':' + Item[3] + sep + Item[4] + ';' + Item[5] + sth, Item[0], Item[1], Item[1])
        reSellList_1 += "]"
        reSellList_2 += "]"
        reSellList_3 += "]"

        return reBuyList_1, reBuyList_2, reBuyList_3, reSellList_1, reSellList_2, reSellList_3
