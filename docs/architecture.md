# 架构说明

## 原则

1. 能调用现有模块就不重写，第三方能力通过组织 Fork 固定和审计。
2. 自有 Workflow 只负责编排调用；自有代码负责标准化、校验、整理和分析。
3. Fork 保持接近上游，不在多个 Fork 中重复实现组织业务逻辑。
4. 原始数据不可覆盖；标准化数据由确定性转换生成。
5. 因子在 `t` 日收盘后生成，最早在 `t+1` 执行。
6. 数据、信号、参数、上游版本、自有代码版本和结果必须可以一起归档。
7. 回测规则显式配置，不把手续费、涨跌停和 T+1 隐藏在策略中。

## 模块

```text
stock_research.data       证券代码、数据读取与质量校验
stock_research.factors    时间序列因子和截面组合目标
stock_research.rules      涨跌停、费用、手数和交易许可
stock_research.backtest   下一交易日执行及组合记账
stock_research.metrics    收益、波动、夏普和回撤
stock_research.cli        端到端离线入口
stock_research.qmt        可选 QMT paper/dry-run 订单适配层
```

## 复用边界

```text
组织 Fork（外部能力）
  数据：AKShare / a-stock-data / TradingAgents-astock
  方向：plate-rotation-skill / tickflow-stock-panel / stock-screener
  验证：quant-momentum-lab / Qlib
                    |
                    v
stock-research Workflow（调度、参数、失败隔离、版本记录）
                    |
                    v
Raw Artifact（保留来源、抓取时间、上游提交和请求参数）
                    |
                    v
stock_research 自有代码（统一契约、去重、对账、方向评分、回测）
```

外部项目的 UI、数据库、Agent 编排和交易建议不会整体进入本仓库。只调用其稳定
CLI/API，或在许可证允许时复用可独立测试的算法模块。LLM 只能解释结构化信号，
不能替代确定性评分和样本外验证。

## 建议的生产拓扑

```text
组织 Fork / 免费公开接口 / 券商数据
             |
             v
Raw Parquet（不可变） -> 标准化 Parquet + DuckDB -> 数据质量报告
                                      |
                                      v
                         市场状态/行业方向/因子/股票池
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

当前实际执行边界为：GitHub-hosted Runner 负责免费数据、研究、回测和报告 Artifact；
Windows 自托管 Runner 只负责已审核订单的 QMT dry-run 或 paper 提交。实盘、账户密码和
券商会话不进入 GitHub-hosted Runner，也不由本仓库自动开启。

达到多人协作规模后，可以拆分为 `stock-data`、`stock-research`、`stock-backtest`、`portfolio-risk` 和 `deploy`。拆分前先确保本仓库中的端到端契约稳定。
