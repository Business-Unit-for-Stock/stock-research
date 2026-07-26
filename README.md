# A 股研究平台 MVP

这是 `Business-Unit-for-Stock` 的自有研究核心，目标不是再收藏一批第三方仓库，而是建立一条可复现的研究流水线：

```text
标准化行情 -> 因子计算 -> 下一交易日执行 -> A 股成交约束 -> 组合净值与交易记录
```

当前版本提供：

- 统一证券代码与日线数据契约；
- OHLCV、重复数据和前收盘价校验；
- 动量、均线偏离等基础因子；
- 截面 Top-N 等权组合；
- 信号在收盘产生、下一交易日开盘执行，避免同日未来函数；
- 100 股一手、T+1、停牌、涨跌停、佣金、过户费和卖出印花税；
- 净值、回撤、波动率、夏普率、换手和交易流水；
- 完整的离线样例及标准库单元测试。
- 调用组织 AKShare/yfinance Fork 的免费数据 Workflow，结果以 Artifact 保存。

## 快速开始

```powershell
cd D:\project\codex\stock-research
python -m pip install -e .
stock-research --bars examples/data/sample_bars.csv --lookback 3 --top-n 1
```

不安装项目也可以运行：

```powershell
$env:PYTHONPATH = "src"
python -m stock_research.cli --bars examples/data/sample_bars.csv --lookback 3 --top-n 1
```

结果默认写入 `outputs/`：

- `equity_curve.csv`：每日净值、现金、持仓市值、费用和换手；
- `trades.csv`：成交记录；
- `signals.csv`：因子值及目标权重；
- `summary.json`：回测指标。

运行测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 免费数据

GitHub Actions 中的 `Free market data snapshot` 会在工作日北京时间 18:30 自动运行，也支持手动指定日期、数据源和复权方式。默认调用 AKShare、Baostock 与 yfinance，单个来源失败不会丢失其他来源的结果。

数据不会自动提交到 Git 历史，而是作为保留 30 天的 Workflow Artifact 下载。配置和授权边界见 [免费数据获取说明](docs/free-data.md)。

## 数据格式

最小输入字段如下：

| 字段 | 含义 |
|---|---|
| `date` | 交易日期 |
| `symbol` | 股票代码，如 `600519` 或 `600519.XSHG` |
| `open/high/low/close` | 不复权或同一复权口径的 OHLC |
| `volume` | 成交量，停牌可为 0 |
| `prev_close` | 前收盘价；缺失时按股票自动推导 |
| `suspended` | 是否停牌，可选 |
| `st` | 是否 ST，可选 |
| `limit_up/limit_down` | 交易所公布的涨跌停价格，可选且优先于推导值 |

生产研究必须保证价格、财务数据、成分股和股票状态均为 point-in-time 数据。详细约束见 [数据契约](docs/data-contract.md)。

## 设计边界

这是研究 MVP，不连接券商、不承诺实盘成交，也不构成投资建议。新股无涨跌幅阶段、集合竞价、分红配股、可转债、融资融券和逐笔撮合尚未实现，不能把当前结果直接当作实盘收益。

整体架构及后续拆仓方案见 [架构说明](docs/architecture.md)、[组织治理方案](docs/organization-plan.md) 和 [路线图](docs/roadmap.md)。
