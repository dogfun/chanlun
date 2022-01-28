import math
import talib as tl
from trade.object import BarData
from copy import copy
import numpy as np
from trade.chanlog import ChanLog


class Chan_Class:

    def __init__(self, freq, symbol, sell, buy, include=True, include_feature=False, build_pivot=False, qjt=True,
                 gz=False, buy1=100, buy2=200, buy3=200, sell1=100, sell2=200, sell3=200):

        self.freq = freq
        self.symbol = symbol
        self.prev = None
        self.next = None
        self.k_list = []
        self.chan_k_list = []
        self.fx_list = []
        self.stroke_list = []
        self.stroke_index_in_k = {}
        self.line_list = []
        self.line_index = {}
        self.line_index_in_k = {}
        self.line_feature = []
        self.s_feature = []
        self.x_feature = []

        self.pivot_list = []
        self.trend_list = []
        self.buy_list = []
        self.sell_list = []
        self.macd = {}
        self.buy = buy
        self.sell = sell
        self.buy1 = buy1
        self.buy2 = buy2
        self.buy3 = buy3
        self.sell1 = sell1
        self.sell2 = sell2
        self.sell3 = sell3
        # 动力减弱最小指标
        self.dynamic_reduce = 0
        # 笔生成方法，new, old
        # 是否进行K线包含处理
        self.include = include
        # 中枢生成方法，stroke, line
        # 使用笔还是线段作为中枢的构成, true使用线段
        self.build_pivot = build_pivot
        # 线段生成方法
        # 是否进行K线包含处理
        self.include_feature = include_feature
        # 是否使用区间套
        self.qjt = qjt
        # 是否使用共振
        # 采用买卖点共振组合方法，1分钟一类买卖点+5分钟二类买卖点或三类买卖点，都属于共振
        self.gz = gz
        # 计数
        self.gz_delay_k_num = 0
        # 最大
        self.gz_delay_k_max = 12
        # 潜在bs
        self.gz_tmp_bs = None
        # 高级别bs
        self.gz_prev_last_bs = None

    def set_prev(self, chan):
        self.prev = chan

    def set_next(self, chan):
        self.next = chan

    def on_bar(self, bar: BarData):
        self.k_list.append(bar)
        if self.gz and self.gz_tmp_bs:
            self.gz_delay_k_num += 1
            self.on_gz()
        if self.include:
            self.on_process_k_include(bar)
        else:
            self.on_process_k_no_include(bar)

    def on_process_k_include(self, bar: BarData):
        """合并k线"""
        if len(self.chan_k_list) < 2:
            self.chan_k_list.append(bar)
        else:
            pre_bar = self.chan_k_list[-2]
            last_bar = self.chan_k_list[-1]
            if (last_bar.high_price >= bar.high_price and last_bar.low_price <= bar.low_price) or (
                    last_bar.high_price <= bar.high_price and last_bar.low_price >= bar.low_price):
                if last_bar.high_price > pre_bar.high_price:
                    new_bar = copy(bar)
                    new_bar.high_price = max(last_bar.high_price, new_bar.high_price)
                    new_bar.low_price = max(last_bar.low_price, new_bar.low_price)
                    new_bar.open_price = max(last_bar.open_price, new_bar.open_price)
                    new_bar.close_price = max(last_bar.close_price, new_bar.close_price)
                else:
                    new_bar = copy(bar)
                    new_bar.high_price = min(last_bar.high_price, new_bar.high_price)
                    new_bar.low_price = min(last_bar.low_price, new_bar.low_price)
                    new_bar.open_price = min(last_bar.open_price, new_bar.open_price)
                    new_bar.close_price = min(last_bar.close_price, new_bar.close_price)

                self.chan_k_list[-1] = new_bar
                ChanLog.log(self.freq, self.symbol, "combine k line: " + str(new_bar.datetime))
            else:
                self.chan_k_list.append(bar)
            # 包含和非包含处理的k线都需要判断是否分型了
            self.on_process_fx(self.chan_k_list)

    def on_process_k_no_include(self, bar: BarData):
        """不用合并k线"""
        self.chan_k_list.append(bar)
        self.on_process_fx(self.chan_k_list)

    def on_process_fx(self, data):
        if len(data) > 2:
            flag = False
            if data[-2].high_price >= data[-1].high_price and data[-2].high_price >= data[-3].high_price:
                # 形成顶分型 [high_price, low, dt, direction, index of k_list]
                self.fx_list.append([data[-2].high_price, data[-2].low_price, data[-2].datetime, 'up', len(data) - 2])
                flag = True

            if data[-2].low_price <= data[-1].low_price and data[-2].low_price <= data[-3].low_price:
                # 形成底分型
                self.fx_list.append([data[-2].high_price, data[-2].low_price, data[-2].datetime, 'down', len(data) - 2])
                flag = True

            if flag:
                self.on_stroke(self.fx_list[-1])
                ChanLog.log(self.freq, self.symbol, "fx_list: ")
                ChanLog.log(self.freq, self.symbol, self.fx_list[-1])

    def on_stroke(self, data):
        """生成笔"""
        if len(self.stroke_list) < 1:
            self.stroke_list.append(data)
            ChanLog.log(self.freq, self.symbol, self.stroke_list)
        else:
            last_fx = self.stroke_list[-1]
            cur_fx = data
            pivot_flag = False
            # 分型之间需要超过三根chank线
            # 延申也是需要条件的
            if last_fx[3] == cur_fx[3]:
                if (last_fx[3] == 'down' and cur_fx[1] < last_fx[1]) or (
                        last_fx[3] == 'up' and cur_fx[0] > last_fx[0]):
                    # 笔延申
                    self.stroke_list[-1] = cur_fx
                    pivot_flag = True

            else:
                # if (cur_fx[4] - last_fx[4] > 3) and (
                #         (cur_fx[3] == 'down' and cur_fx[1] < last_fx[1] and cur_fx[0] < last_fx[0]) or (
                #         cur_fx[3] == 'up' and cur_fx[0] > last_fx[0] and cur_fx[1] > last_fx[1])):
                if (cur_fx[4] - last_fx[4] > 3) and (
                        (cur_fx[3] == 'down' and cur_fx[0] < last_fx[1]) or (
                        cur_fx[3] == 'up' and cur_fx[1] > last_fx[0])):
                    # 笔新增
                    self.stroke_list.append(cur_fx)
                    ChanLog.log(self.freq, self.symbol, "stroke_list: ")
                    ChanLog.log(self.freq, self.symbol, self.stroke_list[-1])
                    # ChanLog.log(self.freq, self.symbol, self.stroke_list)
                    pivot_flag = True

            # 修正倒数第二个分型是否是最高的顶分型或者是否是最低的底分型
            # 只修一笔，不修多笔
            start = -2
            stroke_change = None
            if pivot_flag and len(self.stroke_list) > 1:
                stroke_change = self.stroke_list[-2]
                if cur_fx[3] == 'down':
                    while len(self.fx_list) > abs(start) and self.fx_list[start][2] > self.stroke_list[-2][2]:
                        if self.fx_list[start][3] == 'up' and self.fx_list[start][0] > stroke_change[0]:
                            if len(self.stroke_list) < 3 or (cur_fx[4] - self.fx_list[start][4] > 3):
                                stroke_change = self.fx_list[start]
                        start -= 1
                else:
                    while len(self.fx_list) > abs(start) and self.fx_list[start][2] > self.stroke_list[-2][2]:
                        if self.fx_list[start][3] == 'down' and self.fx_list[start][1] < stroke_change[1]:
                            if len(self.stroke_list) < 3 or (cur_fx[4] - self.fx_list[start][4] > 3):
                                stroke_change = self.fx_list[start]
                        start -= 1
            if stroke_change and not stroke_change == self.stroke_list[-2]:
                ChanLog.log(self.freq, self.symbol, 'stroke_change')
                ChanLog.log(self.freq, self.symbol, stroke_change)
                self.stroke_list[-2] = stroke_change
                if len(self.stroke_list) > 2:
                    cur_fx = self.stroke_list[-2]
                    last_fx = self.stroke_list[-3]
                    self.macd[cur_fx[2]] = self.cal_macd(last_fx[4], cur_fx[4])
                # if cur_fx[4] - self.stroke_list[-2][4] < 4:
                #     self.stroke_list.pop()

            if self.build_pivot:
                self.on_line(self.stroke_list)
            else:
                if len(self.stroke_list) > 1:
                    cur_fx = self.stroke_list[-1]
                    last_fx = self.stroke_list[-2]
                    self.macd[cur_fx[2]] = self.cal_macd(last_fx[4], cur_fx[4])
                self.on_line(self.stroke_list)
                if pivot_flag:
                    self.on_pivot(self.stroke_list, None)

    def on_line(self, data):
        # line_list保持和stroke_list结构相同，都是由分型构成的
        # 特征序列则不同，
        if len(data) > 4:
            # ChanLog.log(self.freq, self.symbol, 'line_index:')
            # ChanLog.log(self.freq, self.symbol, self.line_index)
            pivot_flag = False
            if data[-1][3] == 'up' and data[-3][0] >= data[-1][0] and data[-3][0] >= data[-5][0]:
                if not self.line_list or self.line_list[-1][3] == 'down':
                    if not self.line_list or ((len(self.stroke_list) - 3) - self.line_index[
                        str(self.line_list[-1][2])] > 2 and self.line_list[-1][1] < data[-3][0]):
                        # 出现顶
                        self.line_list.append(data[-3])
                        self.line_index[str(self.line_list[-1][2])] = len(self.stroke_list) - 3
                        pivot_flag = True
                else:
                    # 延申顶
                    if self.line_list[-1][0] < data[-3][0]:
                        self.line_list[-1] = data[-3]
                        self.line_index[str(self.line_list[-1][2])] = len(self.stroke_list) - 3
                        pivot_flag = True
            if data[-1][3] == 'down' and data[-3][1] <= data[-1][1] and data[-3][1] <= data[-5][1]:
                if not self.line_list or self.line_list[-1][3] == 'up':
                    if not self.line_list or ((len(self.stroke_list) - 3) - self.line_index[
                        str(self.line_list[-1][2])] > 2 and self.line_list[-1][0] > data[-3][1]):
                        # 出现底
                        self.line_list.append(data[-3])
                        self.line_index[str(self.line_list[-1][2])] = len(self.stroke_list) - 3
                        pivot_flag = True
                else:
                    # 延申底
                    if self.line_list[-1][1] > data[-3][1]:
                        self.line_list[-1] = data[-3]
                        self.line_index[str(self.line_list[-1][2])] = len(self.stroke_list) - 3
                        pivot_flag = True

            line_change = None
            if pivot_flag and len(self.line_list) > 1:
                last_fx = self.line_list[-2]
                line_change = last_fx
                cur_fx = self.line_list[-1]
                cur_index = self.line_index[str(cur_fx[2])]
                start = -6
                last_index = self.line_index[str(last_fx[2])]
                if cur_index - last_index > 3:
                    while len(self.stroke_list) >= abs(start - 2) and self.stroke_list[start][2] > last_fx[2]:
                        if cur_fx[3] == 'down' and self.stroke_list[start][0] > self.stroke_list[start + 2][0] and \
                                self.stroke_list[start][0] > self.stroke_list[start - 2][0] and self.stroke_list[start][
                            0] > line_change[0]:
                            line_change = self.stroke_list[start]
                        if cur_fx[3] == 'up' and self.stroke_list[start][1] < self.stroke_list[start + 2][1] and \
                                self.stroke_list[start][1] < self.stroke_list[start - 2][1] and self.stroke_list[start][
                            1] < line_change[1]:
                            line_change = self.stroke_list[start]
                        start -= 2

            if line_change and not line_change == self.line_list[-2]:
                ChanLog.log(self.freq, self.symbol, 'line_change')
                ChanLog.log(self.freq, self.symbol, line_change)
                ChanLog.log(self.freq, self.symbol, self.line_list)
                self.line_index[str(line_change[2])] = self.line_index[str(self.line_list[-2][2])]
                self.line_list[-2] = line_change
                if len(self.line_list) > 2:
                    cur_fx = self.line_list[-2]
                    last_fx = self.line_list[-3]
                    self.macd[cur_fx[2]] = self.cal_macd(last_fx[4], cur_fx[4])

            if self.line_list and self.build_pivot:
                if len(self.line_list) > 1:
                    cur_fx = self.line_list[-1]
                    last_fx = self.line_list[-2]
                    self.macd[cur_fx[2]] = self.cal_macd(last_fx[4], cur_fx[4])
                ChanLog.log(self.freq, self.symbol, 'line_list:')
                ChanLog.log(self.freq, self.symbol, self.line_list[-1])
                self.on_pivot(self.line_list, None)

    def on_pivot(self, data, type):
        # 中枢列表[[日期1，日期2，中枢低点，中枢高点, 中枢类型，中枢进入段，中枢离开段, 形成时间, GG, DD,BS,BS,TS]]]
        # 日期1：中枢开始的时间
        # 日期2：中枢结束的时间，可能延申
        # 中枢类型： ‘up', 'down'
        # BS: 买点
        # BS: 卖点
        # TS: 背驰段
        if len(data) > 5:
            # 构成笔或者是线段的分型
            cur_fx = data[-1]
            last_fx = data[-2]
            new_pivot = None
            flag = False
            # 构成新的中枢
            # 判断形成新的中枢的可能性
            if not self.pivot_list or (len(self.pivot_list) > 0 and len(data) - self.pivot_list[-1][6] > 4):
                cur_pivot = [data[-5][2], last_fx[2]]
                if cur_fx[3] == 'down' and data[-2][0] > data[-5][1]:
                    ZD = max(data[-3][1], data[-5][1])
                    ZG = min(data[-2][0], data[-4][0])
                    DD = min(data[-3][1], data[-5][1])
                    GG = max(data[-2][0], data[-4][0])
                    if ZG > ZD:
                        cur_pivot.append(ZD)
                        cur_pivot.append(ZG)
                        cur_pivot.append('down')
                        cur_pivot.append(len(data) - 5)
                        cur_pivot.append(len(data) - 2)
                        cur_pivot.append(cur_fx[2])
                        cur_pivot.append(GG)
                        cur_pivot.append(DD)
                        cur_pivot.append([[], [], []])
                        cur_pivot.append([[], [], []])
                        cur_pivot.append([])
                        new_pivot = cur_pivot
                        # 中枢形成，判断背驰
                if cur_fx[3] == 'up' and data[-2][1] < data[-5][0]:
                    ZD = max(data[-2][1], data[-4][1])
                    ZG = min(data[-3][0], data[-5][0])
                    DD = min(data[-2][1], data[-4][1])
                    GG = max(data[-3][0], data[-5][0])
                    if ZG > ZD:
                        cur_pivot.append(ZD)
                        cur_pivot.append(ZG)
                        cur_pivot.append('up')
                        cur_pivot.append(len(data) - 5)
                        cur_pivot.append(len(data) - 2)
                        cur_pivot.append(cur_fx[2])
                        cur_pivot.append(GG)
                        cur_pivot.append(DD)
                        cur_pivot.append([[], [], []])
                        cur_pivot.append([[], [], []])
                        cur_pivot.append([])
                        new_pivot = cur_pivot
                if not self.pivot_list:
                    if new_pivot:
                        flag = True
                else:
                    last_pivot = self.pivot_list[-1]
                    if new_pivot and ((new_pivot[2] > last_pivot[3] and cur_fx[3] == 'up') or (
                            new_pivot[3] < last_pivot[2] and cur_fx[3] == 'down')):
                        flag = True
                    if type and new_pivot and type == new_pivot[4]:
                        flag = True

            if len(self.pivot_list) > 0 and not flag:
                last_pivot = self.pivot_list[-1]
                ts = last_pivot[12]
                # 由于stroke/line_change，不断change中枢
                start = last_pivot[5]
                # 防止异常
                if len(data) <= start:
                    self.pivot_list.pop()
                    if not self.pivot_list:
                        return
                    last_pivot = self.pivot_list[-1]
                    start = last_pivot[5]
                buy = last_pivot[10]
                sell = last_pivot[11]
                enter = data[start][2]
                exit = cur_fx[2]
                ee_data = [[data[start - 1], data[start]],
                           [data[len(data) - 2], data[len(data) - 1]]]

                if last_pivot[4] == 'up':
                    # stroke_change导致的笔减少了
                    if len(data) > start + 3:
                        last_pivot[2] = max(data[start + 1][1], data[start + 3][1])
                        last_pivot[3] = min(data[start][0], data[start + 2][0])
                        last_pivot[8] = max(data[start][0], data[start + 2][0])
                        last_pivot[9] = min(data[start + 1][1], data[start + 3][1])
                    if cur_fx[3] == 'up':
                        if sell[0]:
                            # 一卖后的顶分型判断一卖是否有效，无效则将上一个一卖置为无效
                            if sell[0][1] < cur_fx[0] and len(data) - last_pivot[6] < 3:
                                # 置一卖无效
                                sell[0][5] = 0
                                sell[0][6] = self.k_list[-1].datetime
                                sell[0] = []
                                # 置二卖无效
                                if sell[1]:
                                    sell[1][5] = 0
                                    sell[1][6] = self.k_list[-1].datetime
                                    sell[1] = []
                        # 判断背驰
                        if self.on_turn(enter, exit, ee_data, last_pivot[4]) and cur_fx[0] > last_pivot[8]:
                            ts.append([last_fx[2], cur_fx[2]])
                            if not sell[0]:
                                # 形成一卖
                                ans, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'up')
                                if ans:
                                    sell[0] = [cur_fx[2], cur_fx[0], 'S1', self.k_list[-1].datetime, len(data) - 1, 1,
                                               None, self.cal_bs_type(), None, qjt_pivot_list]
                                    self.on_buy_sell(sell[0])
                        if sell[0] and not sell[1]:
                            pos_sell1 = sell[0][4]
                            if len(data) > pos_sell1 + 2:
                                pos_fx = data[pos_sell1 + 2]
                                if pos_fx[3] == 'up':
                                    if pos_fx[1] < sell[0][1]:
                                        # 形成二卖
                                        ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'up')
                                        if ans:
                                            sell[1] = [pos_fx[2], pos_fx[0], 'S2', self.k_list[-1].datetime,
                                                       pos_sell1 + 2, 1, None, self.cal_bs_type(), None, qjt_pivot_list]
                                        self.on_buy_sell(sell[1])
                                    else:
                                        # 一卖无效
                                        sell[0][5] = 0
                                        sell[0][6] = self.k_list[-1].datetime
                                        sell[0] = []

                        if cur_fx[0] < last_pivot[2] and not sell[2] and not buy[0]:
                            # 形成三卖
                            ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'up')
                            if ans:
                                condition = len(data) > 2 and data[-3][0] < last_pivot[2] and data[-3][2] > last_pivot[
                                    1]
                                if not condition:
                                    sell[2] = [cur_fx[2], cur_fx[0], 'S3', self.k_list[-1].datetime, len(data) - 1, 1,
                                               None, self.cal_bs_type(), None, qjt_pivot_list]
                                    self.on_buy_sell(sell[2])

                        # if (not last_fx[1] > last_pivot[3]) and (not cur_fx[0] < last_pivot[2]):
                        #     last_pivot[1] = cur_fx[2]
                        #     last_pivot[6] = len(data) - 1

                    else:
                        # 判断是否延申
                        if (not cur_fx[1] > last_pivot[3]) and (not last_fx[0] < last_pivot[2]):
                            last_pivot[1] = cur_fx[2]
                            last_pivot[6] = len(data) - 1
                        else:
                            # 判断形成第三类买点
                            if cur_fx[1] > last_pivot[2] and not buy[2] and not sell[0]:
                                ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'down')
                                if ans:
                                    condition = len(data) > 2 and data[-3][1] > last_pivot[3] and data[-3][2] > \
                                                last_pivot[1]
                                    if not condition:
                                        sth_pivot = last_pivot
                                        # if len(self.pivot_list) > 1:
                                        #     sth_pivot = self.pivot_list[-2]
                                        buy[2] = [cur_fx[2], cur_fx[1], 'B3', self.k_list[-1].datetime, len(data) - 1,
                                                  1, None, self.cal_bs_type(),
                                                  self.cal_b3_strength(cur_fx[1], sth_pivot), qjt_pivot_list]
                                        ChanLog.log(self.freq, self.symbol, 'B3-pivot')
                                        ChanLog.log(self.freq, self.symbol, sth_pivot)
                                        ChanLog.log(self.freq, self.symbol, buy[2])
                                        self.on_buy_sell(buy[2])


                else:
                    # stroke_change导致的笔减少了
                    if len(data) > start + 3:
                        last_pivot[2] = max(data[start][1], data[start + 2][1])
                        last_pivot[3] = min(data[start + 1][0], data[start + 3][0])
                        last_pivot[8] = max(data[start + 1][0], data[start + 3][0])
                        last_pivot[9] = min(data[start][1], data[start + 2][1])
                    if cur_fx[3] == 'down':
                        if buy[0]:
                            # 一买后的底分型判断一买是否有效，无效则将上一个一买置为无效
                            if buy[0][1] > cur_fx[1] and len(data) - last_pivot[6] < 3:
                                # 置一买无效
                                buy[0][5] = 0
                                buy[0][6] = self.k_list[-1].datetime
                                buy[0] = []
                                # 置二买无效
                                if buy[1]:
                                    buy[1][5] = 0
                                    buy[1][6] = self.k_list[-1].datetime
                                    buy[1] = []

                        # 判断背驰
                        if self.on_turn(enter, exit, ee_data, last_pivot[4]) and cur_fx[1] < last_pivot[9]:
                            ts.append([last_fx[2], cur_fx[2]])
                            if not buy[0]:
                                # 形成一买
                                ans, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'down')
                                if ans:
                                    buy[0] = [cur_fx[2], cur_fx[1], 'B1', self.k_list[-1].datetime, len(data) - 1, 1,
                                              None, self.cal_bs_type(), None, qjt_pivot_list]
                                    if self.gz:
                                        self.gz_prev_last_bs = self.get_prev_last_bs()
                                        self.gz_tmp_bs = buy
                                        buy[0][5] = 0
                                    else:
                                        self.on_buy_sell(buy[0])

                        if buy[0] and buy[0][5] == 1 and not buy[1]:
                            pos_buy1 = buy[0][4]
                            if len(data) > pos_buy1 + 2:
                                pos_fx = data[pos_buy1 + 2]
                                if pos_fx[3] == 'down':
                                    if pos_fx[1] > buy[0][1]:
                                        # 形成二买
                                        ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'down')
                                        if ans:
                                            sth_pivot = last_pivot
                                            # if len(self.pivot_list) > 1:
                                            #     sth_pivot = self.pivot_list[-2]
                                            buy[1] = [pos_fx[2], pos_fx[1], 'B2', self.k_list[-1].datetime,
                                                      pos_buy1 + 2, 1, None, self.cal_bs_type(),
                                                      self.cal_b2_strength(pos_fx[1], last_fx, sth_pivot),
                                                      qjt_pivot_list]
                                            self.on_buy_sell(buy[1])
                                    else:
                                        # 一买无效
                                        buy[0][5] = 0
                                        buy[0][6] = self.k_list[-1].datetime
                                        buy[0] = []

                        if cur_fx[1] > last_pivot[3] and not buy[2] and not sell[0]:
                            # 形成三买
                            ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'down')
                            if ans:
                                condition = len(data) > 2 and data[-3][1] > last_pivot[3] and data[-3][2] > \
                                            last_pivot[1]
                                if not condition:
                                    sth_pivot = last_pivot
                                    # if len(self.pivot_list) > 1:
                                    #     sth_pivot = self.pivot_list[-2]
                                    buy[2] = [cur_fx[2], cur_fx[1], 'B3', self.k_list[-1].datetime, len(data) - 1, 1,
                                              None, self.cal_bs_type(), self.cal_b3_strength(cur_fx[1], sth_pivot),
                                              qjt_pivot_list]
                                    ChanLog.log(self.freq, self.symbol, 'B3-pivot')
                                    ChanLog.log(self.freq, self.symbol, sth_pivot)
                                    ChanLog.log(self.freq, self.symbol, buy[2])
                                    self.on_buy_sell(buy[2])

                        # if (not cur_fx[1] > last_pivot[3]) and (not last_fx[0] < last_pivot[2]):
                        #     last_pivot[1] = cur_fx[2]
                        #     last_pivot[6] = len(data) - 1
                    else:
                        # 判断是否延申
                        if (not last_fx[1] > last_pivot[3]) and (not cur_fx[0] < last_pivot[2]):
                            last_pivot[1] = cur_fx[2]
                            last_pivot[6] = len(data) - 1
                        else:
                            # 判断形成第三类卖点
                            if cur_fx[1] < last_pivot[3] and not sell[2] and not buy[0]:
                                ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'up')
                                if ans:
                                    condition = len(data) > 2 and data[-3][0] < last_pivot[2] and data[-3][2] > \
                                                last_pivot[1]
                                    if not condition:
                                        sell[2] = [cur_fx[2], cur_fx[0], 'S3', self.k_list[-1].datetime, len(data) - 1,
                                                   1, None, self.cal_bs_type(), None, qjt_pivot_list]
                                        self.on_buy_sell(sell[2])

                # 判断一二类买卖点失效
                if len(self.pivot_list) > 1:
                    pre = self.pivot_list[-2]
                    pre_buy = pre[10]
                    pre_sell = pre[11]
                    if pre_sell[0] and not pre_sell[1]:
                        pos_sell1 = pre_sell[0][4]
                        if len(data) > pos_sell1 + 2:
                            pos_fx = data[pos_sell1 + 2]
                            if pos_fx[3] == 'up':
                                if pos_fx[0] < pre_sell[0][1]:
                                    # 形成二卖
                                    pre_sell[1] = [pos_fx[2], pos_fx[0], 'S2', self.k_list[-1].datetime, pos_sell1 + 2,
                                                   1, None, pre_sell[0][7], None]
                                    self.on_buy_sell(pre_sell[1])
                                else:
                                    # 一卖无效
                                    pre_sell[0][5] = 0
                                    pre_sell[0][6] = self.k_list[-1].datetime
                                    pre_sell[0] = []

                    if pre_buy[0] and pre_buy[0][5] == 1 and not pre_buy[1]:
                        pos_buy1 = pre_buy[0][4]
                        if len(data) > pos_buy1 + 2:
                            pos_fx = data[pos_buy1 + 2]
                            if pos_fx[3] == 'down':
                                if pos_fx[1] > pre_buy[0][1]:
                                    sth_pivot = None
                                    # if len(self.pivot_list) > 2:
                                    #     sth_pivot = self.pivot_list[-3]
                                    if len(self.pivot_list) > 1:
                                        sth_pivot = self.pivot_list[-2]
                                    # 形成二买
                                    pre_buy[1] = [pos_fx[2], pos_fx[1], 'B2', self.k_list[-1].datetime, pos_buy1 + 2, 1,
                                                  None, pre_buy[0][7],
                                                  self.cal_b2_strength(pos_fx[1], data[pos_buy1 + 1], sth_pivot)]
                                    self.on_buy_sell(pre_buy[1])
                                else:
                                    # 一买无效
                                    pre_buy[0][5] = 0
                                    pre_buy[0][6] = self.k_list[-1].datetime
                                    pre_buy[0] = []

                    # B2失效的判断标准：以B2为起点的笔的顶不大于反转笔的顶。
                    # 判断条件有问题
                    if pre_buy[1] and len(data) > pre_buy[1][4] + 2:
                        start = pre_buy[1][4] + 1
                        if data[start] < data[start - 2]:
                            if pre_buy[0]:
                                # 一买无效
                                pre_buy[0][5] = 0
                                pre_buy[0][6] = self.k_list[-1].datetime
                                pre_buy[0] = []
                                pre_buy[1][5] = 0
                                pre_buy[1][6] = self.k_list[-1].datetime
                                pre_buy[1] = []

                    sth_pivot = None
                    # if len(self.pivot_list) > 2:
                    #     sth_pivot = self.pivot_list[-3]
                    if len(self.pivot_list) > 1:
                        sth_pivot = self.pivot_list[-2]
                    self.x_bs_pos(data, pre_buy, pre_sell, pre, sth_pivot)

                if len(self.pivot_list) > 2:
                    pre2 = self.pivot_list[-3]
                    pre_buy = pre2[10]
                    pre_sell = pre2[11]
                    pre1 = self.pivot_list[-2]
                    if pre1[3] < last_pivot[2] and pre2[3] < pre1[2]:
                        # 上升趋势
                        if pre_sell[0]:
                            # 置一卖无效
                            pre_sell[0][5] = 0
                            pre_sell[0][6] = self.k_list[-1].datetime
                            pre_sell[0] = []

                        if pre_sell[1]:
                            # 置二卖无效
                            pre_sell[1][5] = 0
                            pre_sell[1][6] = self.k_list[-1].datetime
                            pre_sell[1] = []
                    # if pre1[2] > last_pivot[3]:
                    #     # 下降趋势
                    #     if pre_buy[0]:
                    #         # 置一买无效
                    #         pre_buy[0][5] = 0
                    #         pre_buy[0][6] = self.k_list[-1].datetime
                    #         pre_buy[0] = []
                    #
                    #     if pre_buy[1]:
                    #         # 置二买无效
                    #         pre_buy[1][5] = 0
                    #         pre_buy[1][6] = self.k_list[-1].datetime
                    #         pre_buy[1] = []
                # 判断三类买卖点失效
                if sell[2] and sell[2][0] < last_pivot[1]:
                    sell[2][5] = 0
                    sell[2][6] = self.k_list[-1].datetime
                    sell[2] = []

                if buy[2] and buy[2][0] < last_pivot[1]:
                    buy[2][5] = 0
                    buy[2][6] = self.k_list[-1].datetime
                    buy[2] = []
                sth_pivot = last_pivot
                # if len(self.pivot_list) > 1:
                #     sth_pivot = self.pivot_list[-2]
                self.x_bs_pos(data, buy, sell, last_pivot, sth_pivot)

            if flag:
                if new_pivot:
                    self.pivot_list.append(new_pivot)
                    # 中枢形成，判断背驰
                    ts = new_pivot[12]
                    buy = new_pivot[10]
                    sell = new_pivot[11]
                    enter = data[new_pivot[5]][2]
                    exit = data[new_pivot[6]][2]
                    ee_data = [[data[new_pivot[5] - 1], data[new_pivot[5]]],
                               [data[new_pivot[6] - 1], data[new_pivot[6]]]]
                    if new_pivot[4] == 'up':
                        if self.on_turn(enter, exit, ee_data, new_pivot[4]) and cur_fx[0] > new_pivot[8]:
                            ts.append([last_fx[2], cur_fx[2]])
                            if not sell[0]:
                                # 形成一卖
                                ans, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'up')
                                if ans:
                                    sell[0] = [cur_fx[2], cur_fx[0], 'S1', self.k_list[-1].datetime, len(data) - 1, 1,
                                               None, self.cal_bs_type(), None, qjt_pivot_list]
                                    self.on_buy_sell(sell[0])

                    if new_pivot[4] == 'down':
                        if self.on_turn(enter, exit, ee_data, new_pivot[4]) and cur_fx[1] < new_pivot[9]:
                            ts.append([last_fx[2], cur_fx[2]])
                            if not buy[0]:
                                # 形成一买
                                ans, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'down')
                                if ans:
                                    buy[0] = [cur_fx[2], cur_fx[1], 'B1', self.k_list[-1].datetime, len(data) - 1, 1,
                                              None, self.cal_bs_type(), None, qjt_pivot_list]
                                    if self.gz:
                                        self.gz_prev_last_bs = self.get_prev_last_bs()
                                        self.gz_tmp_bs = buy
                                        buy[0][5] = 0
                                    else:
                                        self.on_buy_sell(buy[0])

                    ChanLog.log(self.freq, self.symbol, "pivot_list:")
                    ChanLog.log(self.freq, self.symbol, new_pivot)
                    self.on_trend(new_pivot, data)

    def x_bs_pos(self, data, buy, sell, last_pivot, sth_pivot):
        if not self.gz:
            if buy[0] and len(data) > buy[0][4] and data[buy[0][4]][2] != buy[0][0]:
                pos_fx = data[buy[0][4]]
                buy[0][5] = 0
                buy[0][6] = self.k_list[-1].datetime
                # B1<DD
                buy[0] = [pos_fx[2], pos_fx[1], 'B1', self.k_list[-1].datetime, buy[0][4], 1, None, buy[0][7], None]
                self.on_buy_sell(buy[0])

        if sell[0] and len(data) > sell[0][4] and data[sell[0][4]][2] != sell[0][0]:
            pos_fx = data[sell[0][4]]
            sell[0][5] = 0
            sell[0][6] = self.k_list[-1].datetime
            # S1>GG
            sell[0] = [pos_fx[2], pos_fx[0], 'S1', self.k_list[-1].datetime, sell[0][4], 1, None, sell[0][7], None]
            self.on_buy_sell(sell[0])

        if buy[1] and len(data) > buy[1][4] and data[buy[1][4]][2] != buy[1][0]:
            pos_fx = data[buy[1][4]]
            buy[1][5] = 0
            buy[1][6] = self.k_list[-1].datetime
            if buy[0]:
                if pos_fx[1] > buy[0][1]:
                    # todo 笔延申重新判断为强弱
                    buy[1] = [pos_fx[2], pos_fx[1], 'B2', self.k_list[-1].datetime, buy[1][4], 1, None, buy[1][7],
                              self.cal_b2_strength(pos_fx[1], data[buy[1][4]], sth_pivot)]
                    self.on_buy_sell(buy[1])
                else:
                    # 一买无效
                    buy[0][5] = 0
                    buy[0][6] = self.k_list[-1].datetime

        if sell[1] and len(data) > sell[1][4] and data[sell[1][4]][2] != sell[1][0]:
            pos_fx = data[sell[1][4]]
            sell[1][5] = 0
            sell[1][6] = self.k_list[-1].datetime

            if pos_fx[0] < sell[0][1]:
                sell[1] = [pos_fx[2], pos_fx[0], 'S2', self.k_list[-1].datetime, sell[1][4], 1, None, sell[1][7], None]
                self.on_buy_sell(sell[1])
            else:
                # 一卖无效
                sell[0][5] = 0
                sell[0][6] = self.k_list[-1].datetime

        if buy[2] and len(data) > buy[2][4] and data[buy[2][4]][2] != buy[2][0] and buy[2][0] > last_pivot[1]:
            pos_fx = data[buy[2][4]]
            buy[2][5] = 0
            buy[2][6] = self.k_list[-1].datetime
            if pos_fx[1] > last_pivot[3]:
                buy[2] = [pos_fx[2], pos_fx[1], 'B3', self.k_list[-1].datetime, buy[2][4], 1, None, buy[2][7],
                          self.cal_b3_strength(pos_fx[1], sth_pivot)]
                ChanLog.log(self.freq, self.symbol, 'B3-pivot')
                ChanLog.log(self.freq, self.symbol, sth_pivot)
                ChanLog.log(self.freq, self.symbol, buy[2])
                self.on_buy_sell(buy[2])
        if sell[2] and len(data) > sell[2][4] and data[sell[2][4]][2] != sell[2][0] and sell[2][0] > last_pivot[1]:
            pos_fx = data[sell[2][4]]
            sell[2][5] = 0
            sell[2][6] = self.k_list[-1].datetime
            if pos_fx[0] < last_pivot[2]:
                sell[2] = [pos_fx[2], pos_fx[0], 'S3', self.k_list[-1].datetime, sell[2][4], 1, None, sell[2][7], None]
                self.on_buy_sell(sell[2])

    def cal_bs_type(self):
        if len(self.pivot_list) > 1 and self.pivot_list[-1][4] == self.pivot_list[-2][4]:
            return '趋势'
        return '盘整'

    def cal_b3_strength(self, price, last_pivot):
        if last_pivot:
            if price > last_pivot[8]:
                return '强'
        return '弱'

    def cal_b2_strength(self, price, fx, last_pivot):
        if last_pivot:
            if price > last_pivot[3]:
                return '超强'
            if fx[0] > last_pivot[3]:
                return '强'
            if fx[0] > last_pivot[2]:
                return '中'
        return '弱'

    def cal_macd(self, start, end):
        sum = 0
        if start >= end:
            return sum
        if self.include:
            close_list = np.array([x.close_price for x in self.chan_k_list], dtype=np.double)
        else:
            close_list = np.array([x.close_price for x in self.k_list], dtype=np.double)
        dif, dea, macd = tl.MACD(close_list, fastperiod=12,
                                 slowperiod=26, signalperiod=9)
        for i, v in enumerate(macd.tolist()):
            if start <= i <= end:
                sum += abs(round(v, 4))
        return round(sum, 4)

    def on_turn(self, start, end, ee_data, type):
        # ee_data: 笔/段列表 [[start, end]]
        # 判断背驰
        start_macd = None
        if start in self.macd:
            start_macd = self.macd[start]
        end_macd = None
        if end in self.macd:
            end_macd = self.macd[end]
        if start_macd and end_macd:
            if math.isnan(start_macd) or math.isnan(end_macd):
                if len(ee_data) > 1:
                    if type == 'down':
                        enter_slope = (ee_data[0][0][0] - ee_data[0][1][1]) / (ee_data[0][1][4] - ee_data[0][0][4] + 1)
                        exit_slope = (ee_data[1][0][0] - ee_data[1][1][1]) / (ee_data[1][1][4] - ee_data[1][0][4] + 1)
                        return abs(enter_slope) > abs(exit_slope)
                    else:
                        enter_slope = (ee_data[0][0][1] - ee_data[0][1][0]) / (ee_data[0][1][4] - ee_data[0][0][4] + 1)
                        exit_slope = (ee_data[1][0][1] - ee_data[1][1][0]) / (ee_data[1][1][4] - ee_data[1][0][4] + 1)
                        return abs(enter_slope) > abs(exit_slope)
            else:
                return start_macd > end_macd
        return False

    def qjt_turn0(self, start, end, type):
        # 区间套判断背驰：判断有无中枢和qjt_trend相同
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        ChanLog.log(self.freq, self.symbol, '区间套判断背驰：')
        ChanLog.log(self.freq, self.symbol, self.freq)
        ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]) + ':' + str(start))
        while chan:
            last_pivot = chan.pivot_list[-1]
            tmp = False
            if last_pivot[1] > start:
                if last_pivot[11][0]:
                    tmp = True
                    start = chan.stroke_list[last_pivot[11][0][4] - 1][2]
                    if chan.build_pivot:
                        start = chan.stroke_list[last_pivot[11][0][4] - 1][2]
                if last_pivot[10][0]:
                    tmp = True
                    start = chan.stroke_list[last_pivot[10][0][4] - 1][2]
                    if chan.build_pivot:
                        start = chan.stroke_list[last_pivot[10][0][4] - 1][2]
            ChanLog.log(self.freq, self.symbol, chan.freq + ':' + str(tmp))
            ChanLog.log(self.freq, self.symbol, str(last_pivot) + ':' + str(start))
            ans = ans or tmp
            chan = chan.next
        return ans, qjt_pivot_list

    def qjt_turn1(self, start, end, type):
        # 区间套判断背驰: 利用低级别的买卖点
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        ChanLog.log(self.freq, self.symbol, '区间套判断背驰：')
        ChanLog.log(self.freq, self.symbol, self.freq)
        ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]) + ':' + str(start))
        while chan:
            tmp = False
            for i in range(-1, -len(chan.buy_list), -1):
                buy_dt = chan.buy_list[i]
                if buy_dt >= end and buy_dt < start:
                    tmp = True
                    break
            tmp = False
            for i in range(-1, -len(chan.sell_list), -1):
                sell_dt = chan.sell_list[i]
                if sell_dt >= end and sell_dt < start:
                    tmp = True
                    break
            ans = ans or tmp
            chan = chan.next
        return ans, qjt_pivot_list

    def qjt_pivot(self, data, type):
        chan_pivot = Chan_Class(freq=self.freq, symbol=self.symbol, sell=None, buy=None, include=self.include,
                                include_feature=self.include_feature, build_pivot=self.build_pivot, qjt=False)
        chan_pivot.macd = self.macd
        chan_pivot.k_list = self.chan_k_list
        new_data = []
        for d in data:
            new_data.append(d)
            chan_pivot.on_pivot(new_data, type)
        return chan_pivot.pivot_list

    def qjt_turn(self, start, end, type):
        # 区间套判断背驰：重新形成新的中枢和买卖点
        qjt_pivot_list = []
        # if not self.qjt:
        #     return True, qjt_pivot_list
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = True
        ChanLog.log(self.freq, self.symbol, '区间套判断背驰：')
        ChanLog.log(self.freq, self.symbol, self.freq)

        while chan:
            tmp = False
            data = []
            if chan.build_pivot:
                for i in range(-1, -len(chan.line_list), -1):
                    d = chan.line_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            else:
                for i in range(-1, -len(chan.stroke_list), -1):
                    d = chan.stroke_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            data.reverse()
            chan_pivot_list = chan.qjt_pivot(data, type)
            ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]) + ':' + str(start))
            ChanLog.log(self.freq, self.symbol, chan_pivot_list)
            qjt_pivot_list.append(chan_pivot_list)
            if chan_pivot_list and len(chan_pivot_list[-1][12]) > 0:
                ts_item = chan_pivot_list[-1][12][-1]
                start = ts_item[0]
                end = ts_item[1]
                tmp = True
                chan = chan.next

            ans = tmp and ans
            if not ans:
                break

        return ans, qjt_pivot_list

    def qjt_trend0(self, start, end, type):
        # 区间套判断有无走势：判断有无中枢
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        ChanLog.log(self.freq, self.symbol, '区间套判断有无走势：')
        ChanLog.log(self.freq, self.symbol, str(start) + '--' + str(end))
        ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]))
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        while chan:
            tmp = False
            for i in range(-1, -len(chan.pivot_list), -1):
                last_pivot = chan.pivot_list[i]
                if last_pivot[1] <= end and last_pivot[0] >= start:
                    tmp = True
                    break
            ans = ans or tmp
            ChanLog.log(self.freq, self.symbol, chan.freq + ':' + str(tmp))
            chan = chan.next
        return ans, qjt_pivot_list

    def qjt_trend(self, start, end, type):
        # 区间套判断有无走势：重新形成中枢
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        ChanLog.log(self.freq, self.symbol, '区间套判断背驰：')
        ChanLog.log(self.freq, self.symbol, self.freq)

        while chan:
            tmp = False
            data = []
            if chan.build_pivot:
                for i in range(-1, -len(chan.line_list), -1):
                    d = chan.line_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            else:
                for i in range(-1, -len(chan.stroke_list), -1):
                    d = chan.stroke_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            data.reverse()
            chan_pivot_list = chan.qjt_pivot(data, type)
            ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]) + ':' + str(start))
            ChanLog.log(self.freq, self.symbol, chan_pivot_list)
            qjt_pivot_list.append(chan_pivot_list)
            if not len(chan_pivot_list) > 0:
                chan = chan.next
            else:
                tmp = True
            ans = tmp or ans
            if ans:
                break

        return ans, qjt_pivot_list

    def on_gz(self):
        """共振处理：只关联上一个级别"""
        # 暂时 只处理买点B1
        chan = self.prev
        if not chan:
            return
        last_bs = None
        if len(chan.buy_list) > 0:
            last_bs = chan.buy_list[-1]
        # B1不成立
        if self.gz_delay_k_num >= self.gz_delay_k_max or (len(self.gz_tmp_bs) > 4 and self.gz_tmp_bs[0][5] == 0) or not \
                self.gz_tmp_bs[0]:
            self.gz_delay_k_num = 0
            self.gz_prev_last_bs = None
            self.gz_tmp_bs[0] = []
            self.gz_tmp_bs = None
        else:
            if last_bs and last_bs != self.gz_prev_last_bs and (
                    last_bs[1] == 'B2' or last_bs[2] == 'B3' or last_bs[2] == 'B1'):
                ChanLog.log(self.freq, self.symbol, 'gz:' + str(self.gz_delay_k_num) + ':')
                ChanLog.log(self.freq, self.symbol, last_bs)
                ChanLog.log(self.freq, self.symbol, self.gz_prev_last_bs)
                ChanLog.log(self.freq, self.symbol, self.gz_tmp_bs[0])
                if self.gz_tmp_bs[0]:
                    self.gz_tmp_bs[0][3] = self.k_list[-1].datetime
                    self.gz_tmp_bs[0][5] = 1
                    self.on_buy_sell(self.gz_tmp_bs[0])
                self.gz_delay_k_num = 0
                self.gz_prev_last_bs = None
                self.gz_tmp_bs = None

    def get_prev_last_bs(self):
        chan = self.prev
        if not chan or len(chan.buy_list) < 1:
            return None
        return chan.buy_list[-1]

    def on_trend(self, new_pivot, data):
        # 走势列表[[日期1，日期2，走势类型，[背驰点], [中枢]]]
        if not self.trend_list:
            type = 'pzup'
            if new_pivot[4] == 'down':
                type = 'pzdown'
            self.trend_list.append([new_pivot[0], new_pivot[1], type, [], [len(self.pivot_list) - 1]])
        else:
            last_trend = self.trend_list[-1]
            if last_trend[2] == 'up':
                if new_pivot[4] == 'up':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzdown', [], [len(self.pivot_list) - 1]])
            if last_trend[2] == 'down':
                if new_pivot[4] == 'down':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzup', [], [len(self.pivot_list) - 1]])
            if last_trend[2] == 'pzup':
                if new_pivot[4] == 'up':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                    last_trend[2] = 'up'
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzdown', [], [len(self.pivot_list) - 1]])
            if last_trend[2] == 'pzdown':
                if new_pivot[4] == 'down':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                    last_trend[2] = 'down'
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzup', [], [len(self.pivot_list) - 1]])

    def on_buy_sell(self, data, valid=True):
        if not data:
            return
        # 买点列表[[日期，值，类型, evaluation_time, 买点位置=index of stroke/line, valid, invalid_time, 类型, 强弱, qjt_pivot_list]]
        # 卖点列表[[日期，值，类型, evaluation_time, 买点位置=index of stroke/line, valid, invalid_time, 类型, 强弱, qjt_pivot_list]]
        if valid:
            if data[2].startswith('B'):
                ChanLog.log(self.freq, self.symbol, 'buy:')
                ChanLog.log(self.freq, self.symbol, data)
                self.buy_list.append(data)
                if self.buy:
                    self.buy(self.k_list[-1].close_price, 100, self.freq)
            else:
                ChanLog.log(self.freq, self.symbol, 'sell:')
                ChanLog.log(self.freq, self.symbol, data)
                self.sell_list.append(data)
                if self.sell:
                    self.sell(self.k_list[-1].close_price, 100, self.freq)
        else:
            pass
