#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import pandas as pd
import sys
import numpy as np


class Config:
    """Strategy Parameters"""
    INITIAL_CAPITAL = 20000.0   # Initial capital
    BUILD_LEVELS = 5            # Number of buy levels (price from high to low)
    PROFIT_LEVELS = 5           # Number of profit levels (price from low to high)
    MAX_POSITION_RATIO = 0.20  # Max position ratio per level (20%)
    BUY_DROP = 0.01            # Buy base price = MA14 x (1 - 0.01) = 1% below MA14
    SELL_RISE = 0.001          # Sell base price = MA14 x (1 + 0.001) = 0.1% above MA14
    LEVEL_SPREAD = 0.001       # Spread between levels = 0.1%


class TradeSignal:
    """Trade signal record"""
    def __init__(self, time, signal_type, price, quantity, level):
        self.time = time           # Trade time
        self.signal_type = signal_type  # Trade type: buy/sell
        self.price = price         # Execution price
        self.quantity = quantity   # Quantity
        self.level = level         # Level (1-5)
    
    def __repr__(self):
        return f"{self.time} {self.signal_type.upper():4s} Price:{self.price:6.2f} Qty:{self.quantity:8.2f} Level:{self.level}"


class TradingStrategy:
    """Boundary trading strategy"""
    def __init__(self, config=Config()):
        self.config = config
        self.capital = config.INITIAL_CAPITAL      # Current available capital
        self.trade_log = []                        # Trade records
        self.daily_capital = config.INITIAL_CAPITAL # Daily available capital
        self.position = None                        # Current position
        
    def run_backtest(self, df):
        results = []
        current_date = None
        
        # Iterate through each K-line
        for i in range(len(df)):
            time_str = df.iloc[i]['时间']
            date = time_str.split(' ')[0]
            open_price = df.iloc[i]['开盘']
            close = df.iloc[i]['收盘']
            high = df.iloc[i]['最高']
            low = df.iloc[i]['最低']
            hour = pd.to_datetime(time_str).hour
            
            # Only buy in early trading hours (hour 0-2), avoid overnight risk
            can_buy = hour <= 2
            
            # Daily capital calculation: initial capital + 50% cumulative profit
            if date != current_date:
                self.daily_capital = self.config.INITIAL_CAPITAL + (self.capital - self.config.INITIAL_CAPITAL) * 0.5
                current_date = date
            
            # Calculate MA14
            ma14 = df.iloc[i-14:i]['收盘'].mean() if i >= 14 else close
            
            # Calculate buy price levels: from base price downward, each level 0.1% lower
            # Example: MA14=100, BUY_DROP=0.01, LEVEL_SPREAD=0.001
            # Base price = 99, buy levels = [99.00, 98.90, 98.80, 98.70, 98.60]
            build_base = ma14 * (1 - self.config.BUY_DROP)
            build_prices = [round(build_base * (1 - j * self.config.LEVEL_SPREAD), 2) for j in range(self.config.BUILD_LEVELS)]
            
            # Calculate profit price levels: from base price upward, each level 0.1% higher
            # Example: MA14=100, SELL_RISE=0.001, LEVEL_SPREAD=0.001
            # Base price = 100.1, profit levels = [100.10, 100.20, 100.30, 100.40, 100.50]
            profit_base = ma14 * (1 + self.config.SELL_RISE)
            profit_prices = [round(profit_base * (1 + j * self.config.LEVEL_SPREAD), 2) for j in range(self.config.PROFIT_LEVELS)]
            
            # Record each K-line status
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
            
            # ========== Buy Logic ==========
            # Conditions: no position AND allowed to buy AND low price touches buy level
            if self.position is None and can_buy:
                # Check from highest level (Level 1 is closest to MA14)
                for level_idx, build_price in enumerate(build_prices):
                    if low <= build_price:
                        # Buy price is the min of build price and low
                        buy_price = min(build_price, low)
                        # Calculate quantity: min of daily capital and initial capital x 20%
                        max_capital = min(self.daily_capital, self.config.INITIAL_CAPITAL)
                        max_per_level = max_capital * self.config.MAX_POSITION_RATIO
                        qty = max_per_level / buy_price
                        
                        # Check if capital is sufficient
                        if qty * buy_price <= self.capital:
                            self.capital -= qty * buy_price
                            self.position = {
                                'buy_price': buy_price,
                                'buy_level': level_idx + 1,
                                'qty': qty,
                                'date': date,
                                'profit_prices': profit_prices,
                                'entry_bar': i,       # Record entry K-line index to avoid repeated trades
                                'entry_hour': hour
                            }
                            self.trade_log.append(TradeSignal(time_str, 'buy', buy_price, qty, level_idx + 1))
                            day_result['action'] = 'BUY'
                            break  # Only buy once per K-line
            
            # ========== Sell Logic ==========
            # Conditions: has position AND not the same K-line as entry
            if self.position is not None and i > self.position.get('entry_bar', i):
                buy_price = self.position['buy_price']
                profit_prices = self.position['profit_prices']
                
                # Check if profit level is touched
                for level_idx, profit_price in enumerate(profit_prices):
                    if high >= profit_price:
                        # Sell at profit price
                        sell_price = profit_price
                        sell_qty = self.position['qty']
                        
                        self.capital += sell_qty * sell_price
                        profit_pct = (sell_price - buy_price) / buy_price * 100
                        self.trade_log.append(TradeSignal(time_str, 'sell', sell_price, sell_qty, level_idx + 1))
                        self.position = None
                        day_result['action'] = f'PROFIT {profit_pct:.1f}%'
                        break
                
                # Force close logic (when profit target not hit)
                if self.position is not None:
                    # Force close during hour 4-21 (avoid date boundary and overnight)
                    if hour >= 4 and hour < 22:
                        sell_price = close
                        profit_pct = (sell_price - buy_price) / buy_price * 100
                        # Only close when profitable, hold if loss
                        if profit_pct > 0:
                            sell_qty = self.position['qty']
                            self.capital += sell_price * sell_qty
                            self.trade_log.append(TradeSignal(time_str, 'sell', sell_price, sell_qty, 5))
                            self.position = None
                            day_result['action'] = f'CLOSE {profit_pct:.1f}%'
            
            results.append(day_result)
        
        # Calculate final return
        final_value = self.capital
        total_return = (final_value - self.config.INITIAL_CAPITAL) / self.config.INITIAL_CAPITAL * 100
        
        return {
            'results': results,
            'final_value': final_value,
            'total_return': total_return,
            'trade_log': self.trade_log
        }


def parse_data_filename(data_file):
    """Parse data filename to extract index name and interval"""
    # Extract filename without path
    filename = os.path.basename(data_file)
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Handle patterns like:
    # - TQQQ历史数据.csv -> TQQQ_1min (default)
    # - SOXL历史数据.csv -> SOXL_1min
    # - UPRO历史数据.csv -> UPRO_1min
    # - 1分钟数据/TQQQ历史数据.csv -> TQQQ_1min
    
    # Extract index name
    index_name = re.sub(r'历史数据.*', '', name_without_ext)
    index_name = index_name.replace('数据', '')
    
    # Extract time interval
    if '60分钟' in data_file or '60min' in data_file.lower():
        interval = '60min'
    elif '30分钟' in data_file or '30min' in data_file.lower():
        interval = '30min'
    elif '15分钟' in data_file or '15min' in data_file.lower():
        interval = '15min'
    elif '5分钟' in data_file or '5min' in data_file.lower():
        interval = '5min'
    else:
        interval = '1min'
    
    return f"{index_name}_{interval}"


def main(data_file=None):
    """Main function: load data, run backtest, output results"""
    # Default to 1-minute data, can be specified via command line argument
    if data_file is None:
        if len(sys.argv) > 1:
            data_file = sys.argv[1]
        else:
            data_file = 'data/分钟级数据/1分钟数据/TQQQ历史数据.csv'
    
    # Parse folder name from data file
    folder_name = parse_data_filename(data_file)
    results_dir = os.path.join('results', folder_name)
    os.makedirs(results_dir, exist_ok=True)
    
    df = pd.read_csv(data_file)
    
    # Run backtest
    strategy = TradingStrategy()
    result = strategy.run_backtest(df)
    
    # Print backtest results
    print("=" * 60)
    print(f"Boundary Trading Strategy Backtest ({data_file})")
    print("=" * 60)
    print(f"Initial Capital: ${Config.INITIAL_CAPITAL:,.2f}")
    print(f"Final Capital: ${result['final_value']:,.2f}")
    print(f"Total Return: {result['total_return']:.2f}%")
    print(f"Total Trades: {len(result['trade_log'])}")
    print("=" * 60)
    
    print("\nTrade Records (first 30):")
    print("-" * 60)
    for trade in result['trade_log'][:30]:
        print(trade)
    
    # Save detailed results to CSV
    results_df = pd.DataFrame(result['results'])
    csv_path = os.path.join(results_dir, 'backtest_results.csv')
    results_df.to_csv(csv_path, index=False)
    print(f"\nDetailed results saved to {csv_path}")

    # Save backtest summary
    summary_path = os.path.join(results_dir, 'backtest_summary.txt')
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("Boundary Trading Strategy Backtest Summary\n")
        f.write("=" * 40 + "\n")
        f.write(f"Data File: {data_file}\n")
        f.write(f"Initial Capital: {Config.INITIAL_CAPITAL:,.2f}\n")
        f.write(f"Final Capital: {result['final_value']:,.2f}\n")
        f.write(f"Total Return: {result['total_return']:.2f}%\n")
        f.write(f"Total Trades: {len(result['trade_log'])}\n")
    print(f"Backtest summary saved to {summary_path}")


if __name__ == '__main__':
    main()
