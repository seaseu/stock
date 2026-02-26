# 边界交易策略 (Boundary Trading Strategy)

基于MA14均线的日内边界交易策略，适合杠杆ETF（如TQQQ、SOXL、UPRO）的分钟级K线数据。

## 项目结构

```
stock/
├── trading_strategy.py        # 策略回测
├── trading_realtime.py        # 实时交易版本（富途API）
├── download_massive.py       # 数据下载脚本（Massive.com API）
├── results/                  # 回测结果目录
│   ├── TQQQ_1min/          # TQQQ 1分钟回测结果
│   ├── SOXL_1min/          # SOXL 1分钟回测结果
│   └── UPRO_1min/          # UPRO 1分钟回测结果
└── data/                    # 数据目录
    ├── TQQQ历史数据.csv     # TQQQ 1分钟数据
    ├── SOXL历史数据.csv     # SOXL 1分钟数据
    └── UPRO历史数据.csv     # UPRO 1分钟数据
```

## 核心参数

| 参数 | 值 | 说明 |
|------|-----|------|
| INITIAL_CAPITAL | 20000 | 初始资金（美元） |
| BUILD_LEVELS | 5 | 建仓档位数量（价格从高到低） |
| PROFIT_LEVELS | 5 | 止盈档位数量（价格从低到高） |
| MAX_POSITION_RATIO | 0.20 | 单档位最大仓位比例（20%） |
| BUY_DROP | 0.01 | 建仓基准价 = MA14 × (1 - 0.01) = MA14下方1% |
| SELL_RISE | 0.001 | 止盈基准价 = MA14 × (1 + 0.001) = MA14上方0.1% |
| LEVEL_SPREAD | 0.001 | 相邻档位间距 = 0.1% |

## 交易规则

### 建仓条件
- 当前无持仓
- 当前小时 <= 2（仅在交易时段开始后前3小时内建仓，避免隔夜）
- 最低价触及建仓档位
- 建仓价格档位：从MA14下方1%开始，每档再低0.1%
  - 例：MA14=100，建仓档位 = [99.00, 98.90, 98.80, 98.70, 98.60]

### 止盈规则
- 最高价触及任一止盈档位时卖出
- 止盈价格档位：从MA14上方0.1%开始，每档再高0.1%
  - 例：MA14=100，止盈档位 = [100.10, 100.20, 100.30, 100.40, 100.50]

### 强制平仓
- 小时 >= 4 且小时 < 22 时强制平仓（避免隔夜持仓）
- 仅在盈利时平仓（亏损不卖，继续持有）

### 资金管理
- 每日可用资金 = 初始资金 + 累计盈利 × 50%
- 单档位最大仓位 = min(每日可用资金, 初始资金) × 20%

## 策略特点

1. **日内交易**: 仅在交易时段早期建仓，傍晚前平仓，不过夜
2. **趋势追踪**: 在价格回调至MA14下方时建仓，反弹时止盈
3. **风险控制**: 
   - 单档位最大仓位20%
   - 强制平仓机制避免隔夜风险
   - 只在价格触及建仓档位时才买入
   - 强制平仓时只允许盈利卖出
4. **分档交易**: 5档建仓 + 5档止盈，精细化仓位管理

## 运行方式

### 回测
```bash
cd /Users/jihai/GitHub/stock
source .venv312/bin/activate
python trading_strategy.py                                    # 默认使用TQQQ 1分钟数据
python trading_strategy.py data/TQQQ历史数据.csv             # 指定数据文件
```

### 下载数据
```bash
# 使用Massive.com API下载数据
source .venv312/bin/activate
export POLYGON_API_KEY=your_api_key
python download_massive.py
```

### 实时交易（模拟）
```bash
python trading_realtime.py           # 模拟交易
python trading_realtime.py real      # 实盘交易（需谨慎）
```

## 回测结果汇总

### 数据范围: 2025-01-01 ~ 2026-02-25

| 指数 | 数据行数 | 日期范围 | 收益率 | 交易次数 |
|------|----------|----------|--------|----------|
| TQQQ | 267,993 | 2025-01-02 ~ 2026-02-25 | **+8.30%** | 84 |
| SOXL | 187,526 | 2025-05-12 ~ 2026-02-25 | **+22.96%** | 214 |
| UPRO | 39,218 | 2025-11-24 ~ 2026-02-25 | +0.50% | 4 |

### 分析

- **TQQQ 更新后**: 从-13.41%变为+8.30%，新增数据（2025-11~2026-02）表现较好
- **SOXL 表现最佳**: +22.96%，214次交易，策略在高波动环境中效果较好
- **UPRO 数据有限**: 仅3个月数据，统计意义有限

### 回测结果文件

详细回测结果保存在 `results/` 目录：

```
results/
├── TQQQ_1min/
│   ├── backtest_results.csv    # 逐K线详细数据
│   └── backtest_summary.txt    # 回测摘要
├── SOXL_1min/
│   ├── backtest_results.csv
│   └── backtest_summary.txt
└── UPRO_1min/
    ├── backtest_results.csv
    └── backtest_summary.txt
```

## 数据来源

- **API**: Massive.com (原Polygon.io)
- **数据频率**: 1分钟
- **交易品种**: TQQQ、SOXL、UPRO（3倍杠杆ETF）
- **数据限制**: 每次请求最多50,000条，需分批下载后合并

## 注意事项

1. 回测结果不代表未来收益
2. 实际交易需考虑滑点、手续费等成本
3. 策略适用于高波动市场，单边下跌可能导致亏损
4. 建议使用模拟盘验证后再实盘
