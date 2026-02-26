#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用Massive.com API下载股票分钟数据
每次最多50000条，约可覆盖66天（758条/天）
"""
import os
import time
from datetime import datetime, timedelta
from massive import RESTClient
import pandas as pd

# 计算：50k / 758条/天 ≈ 66天
DAYS_PER_BATCH = 65  # 保守一点
TICKERS = ['TQQQ', 'SOXL', 'UPRO']
START_DATE = '2025-01-01'
# END_DATE = datetime.now().strftime('%Y-%m-%d')
END_DATE = '2026-02-24'


def download_ticker(ticker, start_date, end_date, api_key):
    """下载单个股票数据"""
    client = RESTClient(api_key)
    
    temp_dir = f'data/temp_{ticker}'
    os.makedirs(temp_dir, exist_ok=True)
    
    current = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    batch = 1
    total_rows = 0
    
    print(f"\n>>> {ticker}: {start_date} -> {end_date}")
    
    while current < end:
        batch_end = current + timedelta(days=DAYS_PER_BATCH)
        if batch_end > end:
            batch_end = end
        
        from_str = current.strftime('%Y-%m-%d')
        to_str = batch_end.strftime('%Y-%m-%d')
        
        print(f"  {from_str} -> {to_str}...", end=" ", flush=True)
        
        try:
            aggs = []
            for a in client.list_aggs(
                ticker,
                1,
                "minute",
                from_str,
                to_str,
                limit=50000,
            ):
                aggs.append(a)
            
            if aggs:
                rows = []
                for bar in aggs:
                    rows.append({
                        '时间': datetime.fromtimestamp(bar.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                        '开盘': bar.open,
                        '最高': bar.high,
                        '最低': bar.low,
                        '收盘': bar.close,
                        '成交量': bar.volume,
                    })
                df = pd.DataFrame(rows)
                df.to_csv(f'{temp_dir}/b{batch:03d}.csv', index=False, encoding='utf-8-sig')
                print(f"{len(rows)} rows")
                total_rows += len(rows)
            else:
                print("无数据")
            
        except Exception as e:
            print(f"错误: {str(e)[:50]}")
            time.sleep(5)
        
        current = batch_end
        batch += 1
        time.sleep(1)  # 避免rate limit
    
    # 合并
    import glob
    files = sorted(glob.glob(f'{temp_dir}/*.csv'))
    if files:
        dfs = [pd.read_csv(f) for f in files]
        merged = pd.concat(dfs, ignore_index=True)
        merged['时间'] = pd.to_datetime(merged['时间'])
        merged = merged.sort_values('时间')
        merged = merged.drop_duplicates(subset=['时间'], keep='first')
        merged['时间'] = merged['时间'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        output_path = f'data/{ticker}历史数据.csv'
        merged.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        # 清理临时文件
        for f in files:
            os.remove(f)
        os.rmdir(temp_dir)
        
        print(f"  完成: {ticker} {len(merged)} 行 ({merged['时间'].min()} to {merged['时间'].max()})")
        return True
    
    return False


if __name__ == '__main__':
    api_key = os.environ.get('POLYGON_API_KEY') or os.environ.get('MASSIVE_API_KEY')
    if not api_key:
        print("请设置 POLYGON_API_KEY 或 MASSIVE_API_KEY 环境变量")
        exit(1)
    
    print(f"使用API下载: {TICKERS}")
    print(f"日期范围: {START_DATE} -> {END_DATE}")
    print(f"每批天数: {DAYS_PER_BATCH}")
    
    for ticker in TICKERS:
        download_ticker(ticker, START_DATE, END_DATE, api_key)
        time.sleep(2)
    
    print("\n全部完成!")
