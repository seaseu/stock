# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
从polygon.io下载股票数据
需要先安装: pip install polygon-api-client
设置API key: export POLYGON_API_KEY=your_api_key
"""
import os
import sys
import argparse
from datetime import datetime, timedelta
import polygon

# 默认参数
DEFAULT_TICKERS = ['SOXL', 'UPRO']
DEFAULT_MULTIPLIER = 1
DEFAULT_TIMESPAN = 'minute'
DEFAULT_FROM_DATE = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
DEFAULT_TO_DATE = datetime.now().strftime('%Y-%m-%d')


def download_stock_data(ticker, from_date, to_date, multiplier=1, timespan='minute'):
    """下载股票分钟数据"""
    api_key = os.environ.get('POLYGON_API_KEY')
    if not api_key:
        print("错误: 请设置POLYGON_API_KEY环境变量")
        print("例如: export POLYGON_API_KEY=your_api_key")
        return None
    
    client = polygon.RESTClient(api_key)
    
    print(f"正在下载 {ticker} {multiplier}-{timespan} 数据...")
    print(f"  日期范围: {from_date} 至 {to_date}")
    
    try:
        # 获取聚合数据（K线）
        response = client.get_aggs(
            ticker=ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_=from_date,
            to=to_date,
            limit=50000  # 每次最多获取50000条
        )
        
        if response:
            print(f"  成功获取 {len(response)} 条数据")
            return response
        else:
            print(f"  警告: 未获取到数据")
            return None
            
    except Exception as e:
        print(f"  错误: {e}")
        return None


def save_to_csv(data, ticker, output_dir='data'):
    """保存数据到CSV文件"""
    if not data:
        return
    
    # 创建目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 转换数据格式
    rows = []
    for bar in data:
        rows.append({
            '时间': datetime.fromtimestamp(bar.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            '开盘': bar.open,
            '最高': bar.high,
            '最低': bar.low,
            '收盘': bar.close,
            '成交量': bar.volume,
        })
    
    # 保存到CSV
    filename = os.path.join(output_dir, f'{ticker}历史数据.csv')
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"数据已保存到: {filename}")
    return filename


def main():
    parser = argparse.ArgumentParser(description='从polygon.io下载股票数据')
    parser.add_argument('--tickers', nargs='+', default=DEFAULT_TICKERS, help='股票代码列表')
    parser.add_argument('--from', dest='from_date', default=DEFAULT_FROM_DATE, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--to', dest='to_date', default=DEFAULT_TO_DATE, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--multiplier', type=int, default=DEFAULT_MULTIPLIER, help='时间乘数')
    parser.add_argument('--timespan', default=DEFAULT_TIMESPAN, choices=['minute', 'hour', 'day', 'week', 'month'], help='时间跨度')
    parser.add_argument('--output', default='data', help='输出目录')
    
    args = parser.parse_args()
    
    # 检查API key
    api_key = os.environ.get('POLYGON_API_KEY')
    if not api_key:
        print("错误: 请设置POLYGON_API_KEY环境变量")
        print("")
        print("使用方法:")
        print("  1. 注册 polygon.io 账号获取API key")
        print("  2. 设置环境变量:")
        print("     Linux/Mac: export POLYGON_API_KEY=your_api_key")
        print("     Windows: set POLYGON_API_KEY=your_api_key")
        print("  3. 运行脚本")
    
    print("=" * 60)
    print("Polygon.io 股票数据下载工具")
    print("=" * 60)
    print(f"股票代码: {args.tickers}")
    print(f"日期范围: {args.from_date} 至 {args.to_date}")
    print(f"时间粒度: {args.multiplier}-{args.timespan}")
    print("=" * 60)
    
    # 下载每个股票的数据
    for ticker in args.tickers:
        data = download_stock_data(
            ticker=ticker,
            from_date=args.from_date,
            to_date=args.to_date,
            multiplier=args.multiplier,
            timespan=args.timespan
        )
        if data:
            save_to_csv(data, ticker, args.output)
        print()
    
    print("下载完成!")


if __name__ == '__main__':
    main()
