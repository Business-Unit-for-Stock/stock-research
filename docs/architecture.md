# 架构说明

## 原则

1. 第三方项目作为可替换依赖，不把 Fork 数量当作平台能力。
2. 原始数据不可覆盖；标准化数据由确定性转换生成。
3. 因子在 `t` 日收盘后生成，最早在 `t+1` 执行。
4. 数据、信号、参数、代码版本和结果必须可以一起归档。
5. 回测规则显式配置，不把手续费、涨跌停和 T+1 隐藏在策略中。

## 模块

```text
stock_research.data       证券代码、数据读取与质量校验
stock_research.factors    时间序列因子和截面组合目标
stock_research.rules      涨跌停、费用、手数和交易许可
stock_research.backtest   下一交易日执行及组合记账
stock_research.metrics    收益、波动、夏普和回撤
stock_research.cli        端到端离线入口
```

## 建议的生产拓扑

```text
AKShare / Tushare / 券商数据
             |
             v
Raw Parquet（不可变） -> 标准化 Parquet + DuckDB -> 数据质量报告
                                      |
                                      v
                             因子/标签/股票池
                                      |
                                      v
                         VectorBT/Qlib 快速研究
                                      |
                                      v
                         A 股规则事件回测/RQAlpha
                                      |
                                      v
                          组合风险 -> 模拟盘 -> 实盘
```

达到多人协作规模后，可以拆分为 `stock-data`、`stock-research`、`stock-backtest`、`portfolio-risk` 和 `deploy`。拆分前先确保本仓库中的端到端契约稳定。

