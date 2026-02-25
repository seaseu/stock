#!/usr/bin/env python3
import pandas as pd
import numpy as np


class Config:
    """策略参数配置"""
    INITIAL_CAPITAL = 20000.0   # 初始资金
    BUILD_LEVELS = 5            # 建仓档位数量（价格从高到低）
    PROFIT_LEVELS = 5           # 止盈档位数量（价格从低到高）
    MAX_POSITION_RATIO = 0.20  # 单档位最大仓位比例（20%）
    BUY_DROP = 0.01            # 建仓基准价 = MA14 × (1 - 0.01) = MA14下方1%
    SELL_RISE = 0.001          # 止盈基准价 = MA14 × (1 + 0.001) = MA14上方0.1%
    LEVEL_SPREAD = 0.001       # 相邻档位间距 = 0.1%


class TradeSignal:
    """交易信号记录"""
    def __init__(self, time, signal_type, price, quantity, level):
        self.time = time           # 交易时间
        self.signal_type = signal_type  # 交易类型：buy/sell
        self.price = price         # 成交价格
        self.quantity = quantity   # 成交数量
        self.level = level         # 档位（1-5）
    
    def __repr__(self):
        return f"{self.time} {self.signal_type.upper():4s} Price:{self.price:6.2f} Qty:{self.quantity:8.2f} Level:{self.level}"


class TradingStrategy:
    """边界交易策略"""
    def __init__(self, config=Config()):
        self.config = config
        self.capital = config.INITIAL_CAPITAL      # 当前可用资金
        self.trade_log = []                        # 交易记录
        self.daily_capital = config.INITIAL_CAPITAL # 每日可用资金
        self.position = None                        # 当前持仓
        
    def run_backtest(self, df):
        results = []
        current_date = None
        
        # 遍历每一根K线
        for i in range(len(df)):
            time_str = df.iloc[i]['时间']
            date = time_str.split(' ')[0]
            open_price = df.iloc[i]['开盘']
            close = df.iloc[i]['收盘']
            high = df.iloc[i]['最高']
            low = df.iloc[i]['最低']
            hour = pd.to_datetime(time_str).hour
            
            # 只在交易时段早期建仓（小时0-2），避免隔夜风险
            can_buy = hour <= 2
            
            # 每日资金计算：初始资金 + 50%累计利润
            if date != current_date:
                self.daily_capital = self.config.INITIAL_CAPITAL + (self.capital - self.config.INITIAL_CAPITAL) * 0.5
                current_date = date
            
            # 计算MA14均线
            ma14 = df.iloc[i-14:i]['收盘'].mean() if i >= 14 else close
            
            # 计算建仓价格档位：从基准价往下，每档低0.1%
            # 例如：MA14=100, BUY_DROP=0.01, LEVEL_SPREAD=0.001
            # 基准价 = 99，建仓档位 = [99.00, 98.90, 98.80, 98.70, 98.60]
            build_base = ma14 * (1 - self.config.BUY_DROP)
            build_prices = [round(build_base * (1 - j * self.config.LEVEL_SPREAD), 2) for j in range(self.config.BUILD_LEVELS)]
            
            # 计算止盈价格档位：从基准价往上，每档高0.1%
            # 例如：MA14=100, SELL_RISE=0.001, LEVEL_SPREAD=0.001
            # 基准价 = 100.1，止盈档位 = [100.10, 100.20, 100.30, 100.40, 100.50]
            profit_base = ma14 * (1 + self.config.SELL_RISE)
            profit_prices = [round(profit_base * (1 + j * self.config.LEVEL_SPREAD), 2) for j in range(self.config.PROFIT_LEVELS)]
            
            # 记录每根K线的状态
            day_result = {
                'time': time_str,
                'close': round(close, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'ma14': round(ma14, 2),
                'build_prices': str([float(p) for p in build_prices[:3]]) + '...',
                'profit_prices': str([float(p) for p in profit_prices[:3]]) + '...',
                'capital': round(self.capital, 2),
                'has_position': self.position is not None,
                'action': ''
            }
            
            # ========== 建仓逻辑 ==========
            # 条件：无持仓 且 允许建仓 且 最低价触及建仓档位
            if self.position is None and can_buy:
                # 从最高档位开始检查（Level 1是最接近MA14的建仓位）
                for level_idx, build_price in enumerate(build_prices):
                    if low <= build_price:
                        # 买入价格取建仓档位和最低价的较小值
                        buy_price = min(build_price, low)
                        # 计算买入数量：取每日资金和初始资金的较小值 × 20%
                        max_capital = min(self.daily_capital, self.config.INITIAL_CAPITAL)
                        max_per_level = max_capital * self.config.MAX_POSITION_RATIO
                        qty = max_per_level / buy_price
                        
                        # 检查资金是否充足
                        if qty * buy_price <= self.capital:
                            self.capital -= qty * buy_price
                            self.position = {
                                'buy_price': buy_price,
                                'buy_level': level_idx + 1,
                                'qty': qty,
                                'date': date,
                                'profit_prices': profit_prices,
                                'entry_bar': i,       # 记录入场K线索引，避免同根K线反复交易
                                'entry_hour': hour
                            }
                            self.trade_log.append(TradeSignal(time_str, 'buy', buy_price, qty, level_idx + 1))
                            day_result['action'] = '建仓'
                            break  # 每根K线只建仓一次
            
            # ========== 平仓逻辑 ==========
            # 条件：持有仓位 且 不是入场的同一根K线
            if self.position is not None and i > self.position.get('entry_bar', i):
                buy_price = self.position['buy_price']
                profit_prices = self.position['profit_prices']
                
                # 检查是否触及止盈档位
                for level_idx, profit_price in enumerate(profit_prices):
                    if high >= profit_price:
                        # 按止盈价卖出
                        sell_price = profit_price
                        sell_qty = self.position['qty']
                        
                        self.capital += sell_qty * sell_price
                        profit_pct = (sell_price - buy_price) / buy_price * 100
                        self.trade_log.append(TradeSignal(time_str, 'sell', sell_price, sell_qty, level_idx + 1))
                        self.position = None
                        day_result['action'] = f'获利{profit_pct:.1f}%'
                        break
                
                # 强制平仓逻辑（止盈未触发时）
                if self.position is not None:
                    # 在小时4-21之间强制平仓（避开date boundary和隔夜）
                    if hour >= 4 and hour < 22:
                        sell_price = close
                        profit_pct = (sell_price - buy_price) / buy_price * 100
                        # 只在盈利时平仓，亏损则继续持有
                        if profit_pct > 0:
                            sell_qty = self.position['qty']
                            self.capital += sell_price * sell_qty
                            self.trade_log.append(TradeSignal(time_str, 'sell', sell_price, sell_qty, 5))
                            self.position = None
                            day_result['action'] = f'平仓{profit_pct:.1f}%'
            
            results.append(day_result)
        
        # 计算最终收益
        final_value = self.capital
        total_return = (final_value - self.config.INITIAL_CAPITAL) / self.config.INITIAL_CAPITAL * 100
        
        return {
            'results': results,
            'final_value': final_value,
            'total_return': total_return,
            'trade_log': self.trade_log
        }


def main():
    """主函数：加载数据、运行回测、输出结果"""
    # 读取1分钟K线数据
    df = pd.read_csv('data/分钟级数据/1分钟数据/TQQQ历史数据.csv')
    
    # 运行回测
    strategy = TradingStrategy()
    result = strategy.run_backtest(df)
    
    # 打印回测结果
    print("=" * 60)
    print("TQQQ 1分钟 边界交易策略 回测结果")
    print("=" * 60)
    print(f"初始资金: ${Config.INITIAL_CAPITAL:,.2f}")
    print(f"最终资金: ${result['final_value']:,.2f}")
    print(f"总收益率: {result['total_return']:.2f}%")
    print(f"总交易次数: {len(result['trade_log'])}")
    print("=" * 60)
    
    print("\n交易记录 (前30条):")
    print("-" * 60)
    for trade in result['trade_log'][:30]:
        print(trade)
    
    # 保存详细结果到CSV
    results_df = pd.DataFrame(result['results'])
    results_df.to_csv('backtest_results.csv', index=False)
    print("\n详细结果已保存到 backtest_results.csv")


if __name__ == '__main__':
    main()
