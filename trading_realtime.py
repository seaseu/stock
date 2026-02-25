#!/usr/bin/env python3
"""
TQQQ 边界交易策略 - 实时交易版本
使用富途API进行实盘交易
"""
import sys
import time
from futu import *


# 富途API配置
FUTU_HOST = '127.0.0.1'
FUTU_PORT = 11111

# 交易标的
STOCK_CODE = 'US.TQQQ'  # TQQQ

# 策略参数
INITIAL_CAPITAL = 20000.0
MAX_POSITION_RATIO = 0.20
BUY_DROP = 0.01      # 建仓基准价 = MA14 × (1 - 0.01)
SELL_RISE = 0.001    # 止盈基准价 = MA14 × (1 + 0.001)
LEVEL_SPREAD = 0.001  # 相邻档位间距 = 0.1%


class RealTimeTrading:
    def __init__(self, trade_env=TrdEnv.SIMULATE):
        self.trade_env = trade_env
        self.quote_ctx = OpenQuoteContext(host=FUTU_HOST, port=FUTU_PORT)
        self.trade_ctx = OpenTradeContext(host=FUTU_HOST, port=FUTU_PORT)
        
        self.capital = INITIAL_CAPITAL
        self.position = None
        self.ma14_history = []
        
    def close(self):
        """关闭连接"""
        self.quote_ctx.close()
        self.trade_ctx.close()
    
    def get_realtime_quote(self, code):
        """获取实时行情"""
        ret, data = self.quote_ctx.get_market_snapshot([code])
        if ret == 0:
            return data.iloc[0]
        return None
    
    def get_kline(self, code, count=100):
        """获取K线数据"""
        ret, data = self.quote_ctx.get_kline(code, count=count, ktype=KLType.K_1M)
        if ret == 0:
            return data
        return None
    
    def calculate_ma14(self, kline_df):
        """计算MA14"""
        if len(kline_df) >= 14:
            return kline_df['close'].tail(14).mean()
        return kline_df['close'].mean()
    
    def get_position(self):
        """获取当前持仓"""
        ret, data = self.trade_ctx.get_position_list(acc_id=0, acc_index=0)
        if ret == 0:
            for _, row in data.iterrows():
                if row['code'] == STOCK_CODE:
                    return {
                        'qty': row['qty'],
                        'cost': row['cost']
                    }
        return None
    
    def place_buy_order(self, price, qty):
        """下买单"""
        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=qty,
            code=STOCK_CODE,
            trd_side=TrdSide.BUY,
            order_type=OrderType.NORMAL,
            trd_env=self.trade_env
        )
        if ret == 0:
            print(f"买单已提交: 价格={price}, 数量={qty}")
            return True
        else:
            print(f"买单失败: {data}")
            return False
    
    def place_sell_order(self, price, qty):
        """下卖单"""
        ret, data = self.trade_ctx.place_order(
            price=price,
            qty=qty,
            code=STOCK_CODE,
            trd_side=TrdSide.SELL,
            order_type=OrderType.NORMAL,
            trd_env=self.trade_env
        )
        if ret == 0:
            print(f"卖单已提交: 价格={price}, 数量={qty}")
            return True
        else:
            print(f"卖单失败: {data}")
            return False
    
    def run(self):
        """运行交易策略"""
        print("=" * 60)
        print("TQQQ 边界交易策略 - 实时交易")
        print("=" * 60)
        print(f"交易环境: {'模拟交易' if self.trade_env == TrdEnv.SIMULATE else '实盘交易'}")
        print(f"交易标的: {STOCK_CODE}")
        print("=" * 60)
        
        # 订阅实时行情
        self.quote_ctx.subscribe([STOCK_CODE], [SubType.QUOTE, SubType.K_1M])
        
        try:
            while True:
                # 获取K线数据计算MA14
                kline_df = self.get_kline(STOCK_CODE, count=100)
                if kline_df is None or len(kline_df) < 14:
                    time.sleep(5)
                    continue
                
                ma14 = self.calculate_ma14(kline_df)
                self.ma14_history.append(ma14)
                if len(self.ma14_history) > 14:
                    self.ma14_history.pop(0)
                
                # 获取当前行情
                quote = self.get_realtime_quote(STOCK_CODE)
                if quote is None:
                    time.sleep(5)
                    continue
                
                current_price = quote['last_price']
                high_price = quote['high_price']
                low_price = quote['low_price']
                
                # 计算建仓和止盈价格
                build_base = ma14 * (1 - BUY_DROP)
                build_prices = [round(build_base * (1 - j * LEVEL_SPREAD), 2) for j in range(5)]
                
                profit_base = ma14 * (1 + SELL_RISE)
                profit_prices = [round(profit_base * (1 + j * LEVEL_SPREAD), 2) for j in range(5)]
                
                print(f"\n[{time.strftime('%H:%M:%S')}]")
                print(f"  当前价: {current_price:.2f}, MA14: {ma14:.2f}")
                print(f"  建仓档位: {build_prices[:3]}...")
                print(f"  止盈档位: {profit_prices[:3]}...")
                
                # 获取当前时间（小时）
                current_hour = int(time.strftime('%H'))
                
                # 建仓逻辑
                if self.position is None:
                    if current_hour <= 2:  # 只在交易时段早期建仓
                        for level_idx, build_price in enumerate(build_prices):
                            if low_price <= build_price:
                                buy_price = min(build_price, low_price)
                                max_capital = min(self.capital, INITIAL_CAPITAL)
                                max_per_level = max_capital * MAX_POSITION_RATIO
                                qty = int(max_per_level / buy_price)
                                
                                if qty > 0 and self.place_buy_order(buy_price, qty):
                                    self.position = {
                                        'buy_price': buy_price,
                                        'qty': qty,
                                        'profit_prices': profit_prices
                                    }
                                    print(f"  >> 建仓: 价格={buy_price}, 数量={qty}")
                                break
                else:
                    # 平仓逻辑
                    buy_price = self.position['buy_price']
                    
                    # 检查是否触及止盈档位
                    for level_idx, profit_price in enumerate(profit_prices):
                        if high_price >= profit_price:
                            if self.place_sell_order(profit_price, self.position['qty']):
                                profit_pct = (profit_price - buy_price) / buy_price * 100
                                print(f"  >> 止盈平仓: 价格={profit_price}, 数量={self.position['qty']}, 收益={profit_pct:.2f}%")
                                self.capital += self.position['qty'] * profit_price
                                self.position = None
                            break
                    
                    # 强制平仓（仅在盈利时）
                    if self.position is not None:
                        if current_hour >= 4 and current_hour < 22:
                            sell_price = current_price
                            profit_pct = (sell_price - buy_price) / buy_price * 100
                            if profit_pct > 0:
                                if self.place_sell_order(sell_price, self.position['qty']):
                                    print(f"  >> 强制平仓: 价格={sell_price}, 数量={self.position['qty']}, 收益={profit_pct:.2f}%")
                                    self.capital += self.position['qty'] * sell_price
                                    self.position = None
                
                time.sleep(10)  # 每10秒检查一次
                
        except KeyboardInterrupt:
            print("\n策略停止")
        finally:
            self.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'real':
        trade_env = TrdEnv.REAL
        print("使用实盘交易模式")
    else:
        trade_env = TrdEnv.SIMULATE
        print("使用模拟交易模式")
    
    trading = RealTimeTrading(trade_env=trade_env)
    trading.run()


if __name__ == '__main__':
    main()
