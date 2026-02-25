#!/usr/bin/env python3
import pandas as pd
import numpy as np


class Config:
    INITIAL_CAPITAL = 20000.0
    BUILD_LEVELS = 5
    PROFIT_LEVELS = 5
    MAX_POSITION_RATIO = 0.20
    BUY_DROP = 0.01  # 1% below MA14 for first build level
    SELL_RISE = 0.001  # 0.2% above MA14 for first profit level
    LEVEL_SPREAD = 0.001  # 0.2% between each level


class TradeSignal:
    def __init__(self, time, signal_type, price, quantity, level):
        self.time = time
        self.signal_type = signal_type
        self.price = price
        self.quantity = quantity
        self.level = level
    
    def __repr__(self):
        return f"{self.time} {self.signal_type.upper():4s} Price:{self.price:6.2f} Qty:{self.quantity:8.2f} Level:{self.level}"


class TradingStrategy:
    def __init__(self, config=Config()):
        self.config = config
        self.capital = config.INITIAL_CAPITAL
        self.trade_log = []
        self.daily_capital = config.INITIAL_CAPITAL
        self.position = None
        
    def run_backtest(self, df):
        results = []
        current_date = None
        
        for i in range(len(df)):
            time_str = df.iloc[i]['时间']
            date = time_str.split(' ')[0]
            open_price = df.iloc[i]['开盘']
            close = df.iloc[i]['收盘']
            high = df.iloc[i]['最高']
            low = df.iloc[i]['最低']
            hour = pd.to_datetime(time_str).hour
            
            # Only trade during first half of session (hours 22-1)
            # This avoids overnight gap-downs
            can_buy = hour <= 2  # Only buy in first 2 hours of session
            
            # Daily capital reset
            if date != current_date:
                self.daily_capital = self.config.INITIAL_CAPITAL + (self.capital - self.config.INITIAL_CAPITAL) * 0.5
                current_date = date
            
            # Calculate MA14 and price levels
            ma14 = df.iloc[i-14:i]['收盘'].mean() if i >= 14 else close
            
            # Build prices: from MA14*(1-BUY_DROP) down to MA14*(1-BUY_DROP-4*LEVEL_SPREAD)
            build_base = ma14 * (1 - self.config.BUY_DROP)
            build_prices = [round(build_base * (1 - j * self.config.LEVEL_SPREAD), 2) for j in range(self.config.BUILD_LEVELS)]
            
            # Profit prices: from MA14*(1+SELL_RISE) up to MA14*(1+SELL_RISE+4*LEVEL_SPREAD)
            profit_base = ma14 * (1 + self.config.SELL_RISE)
            profit_prices = [round(profit_base * (1 + j * self.config.LEVEL_SPREAD), 2) for j in range(self.config.PROFIT_LEVELS)]
            
            day_result = {
                'time': time_str,
                'close': round(close, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'ma14': round(ma14, 2),
                'build_prices': str(build_prices[:3]) + '...',
                'profit_prices': str(profit_prices[:3]) + '...',
                'capital': round(self.capital, 2),
                'has_position': self.position is not None,
                'action': ''
            }
            
            # Entry: Buy when price drops to build levels
            if self.position is None and can_buy:
                # Check if low touched any build level
                for level_idx, build_price in enumerate(build_prices):
                    if low <= build_price:
                        # Buy at build_price (or low, whichever is lower)
                        buy_price = min(build_price, low)
                        max_capital = min(self.daily_capital, self.config.INITIAL_CAPITAL)
                        max_per_level = max_capital * self.config.MAX_POSITION_RATIO
                        qty = max_per_level / buy_price
                        
                        if qty * buy_price <= self.capital:
                            self.capital -= qty * buy_price
                            self.position = {
                                'buy_price': buy_price,
                                'buy_level': level_idx + 1,
                                'qty': qty,
                                'date': date,
                                'profit_prices': profit_prices,
                                'entry_bar': i,
                                'entry_hour': hour
                            }
                            self.trade_log.append(TradeSignal(time_str, 'buy', buy_price, qty, level_idx + 1))
                            day_result['action'] = '建仓'
                            break  # Only buy once per bar
            
            # Exit: Sell when high hits profit levels (but not on the same bar as entry)
            if self.position is not None and i > self.position.get('entry_bar', i):
                buy_price = self.position['buy_price']
                profit_prices = self.position['profit_prices']
                
                # Check each profit level
                for level_idx, profit_price in enumerate(profit_prices):
                    if high >= profit_price:
                        # Sell at profit_price
                        sell_price = profit_price
                        sell_qty = self.position['qty']
                        
                        self.capital += sell_qty * sell_price
                        profit_pct = (sell_price - buy_price) / buy_price * 100
                        self.trade_log.append(TradeSignal(time_str, 'sell', sell_price, sell_qty, level_idx + 1))
                        self.position = None
                        day_result['action'] = f'获利{profit_pct:.1f}%'
                        break
                
                # If no profit target hit, close at late night (hour >= 4) or session end
                if self.position is not None:
                    # Only close at hour >= 4 (late session) to avoid date-change losses
                    if hour >= 4 and hour < 22:
                        sell_price = close
                        sell_qty = self.position['qty']
                        profit_pct = (sell_price - buy_price) / buy_price * 100
                        self.capital += sell_price * sell_qty
                        self.trade_log.append(TradeSignal(time_str, 'sell', sell_price, sell_qty, 5))
                        self.position = None
                        day_result['action'] = f'平仓{profit_pct:.1f}%'
            
            results.append(day_result)
        
        final_value = self.capital
        total_return = (final_value - self.config.INITIAL_CAPITAL) / self.config.INITIAL_CAPITAL * 100
        
        return {
            'results': results,
            'final_value': final_value,
            'total_return': total_return,
            'trade_log': self.trade_log
        }


def main():
    df = pd.read_csv('data/分钟级数据/1分钟数据/TQQQ历史数据.csv')
    
    strategy = TradingStrategy()
    result = strategy.run_backtest(df)
    
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
    
    results_df = pd.DataFrame(result['results'])
    results_df.to_csv('backtest_results.csv', index=False)
    print("\n详细结果已保存到 backtest_results.csv")


if __name__ == '__main__':
    main()
