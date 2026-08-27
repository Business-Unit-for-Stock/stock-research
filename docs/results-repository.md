# 结果仓库与数据归档

## 推荐拆分

代码、策略、测试和 Workflow 保留在私有 `stock-research`；回测报告、订单审计和运行
清单放入另一个私有仓库 `qmt-results`。这样可以避免研究代码历史和结果历史互相污染，
也方便限制结果仓库的读取权限。

在 `qmt-results` 建好之前，Workflow 只上传 GitHub Artifact（默认保留 30 天），不会
自动跨仓库推送，也不会要求在代码仓库中存放 Token。当前实现已经可以完整生成：

- `report.md`：人类可读回测报告；
- `summary.json`：机器可读指标；
- `equity_curve.csv`：净值和组合状态；
- `trades.csv`：交易流水；
- `signals.csv`：目标权重；
- `manifest.json`：数据源、时间范围、行数和错误证据。

## 数据放置规则

- 小型 Markdown、JSON、CSV 报告可以进入 `qmt-results`。
- 大型原始行情、Parquet、DuckDB 文件进入 NAS、对象存储或 MinIO，不进入 Git 历史。
- 免费接口数据仍受各提供方条款约束；保存来源和抓取参数不等于获得再分发许可。
- 结果仓库不得包含账号密码、券商会话文件、GitHub Token 或任何 `.env` 文件。

## 后续跨仓库发布

当前已创建私有 `Business-Unit-for-Stock/qmt-results`。在 `stock-research` 的
`results-publish` Environment 中配置一个只允许写入该结果仓库的 `RESULTS_TOKEN`；
不要把它配置为普通仓库 Secret，也不要在不可信 Pull Request 中注入。运行
`Backtest report` 时只有明确勾选 `publish_results=true` 并通过 Environment 审批，才会
执行跨仓库发布。
