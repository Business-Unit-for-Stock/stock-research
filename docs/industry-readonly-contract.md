# 行业仓库只读金融结果契约

股票、ETF、行情、财报和交易所数据归 `Business-Unit-for-Stock/stock-research`
维护。节能、AI 等行业仓库不得安装或调用本仓库的行情适配器，也不得把金融抓取失败
作为行业简报失败条件。

## 当前结果

免费行情 Workflow 将股票和 ETF 分开写入快照目录：

```text
data/snapshot/manifest.json
data/snapshot/<provider>_daily.csv
data/snapshot/etf/manifest.json
data/snapshot/etf/<provider>_daily.csv
```

每份 `manifest.json` 至少包含生成时间、数据日期范围、请求标的、提供方结果、输出
文件、行数和错误信息。CSV 使用统一字段：
`date`、`symbol`、`open`、`high`、`low`、`close`、`adj_close`、`volume`、
`amount`、`provider`、`fetched_at`、`adjust`。

## 行业侧使用规则

- 行业仓库只消费已经发布、带数据日期和来源的脱敏结果；不读取股票仓库私有数据库、
  原始响应、运行日志或凭据。
- 金融结果只能作为行业分析的可选背景证据，不能替代行业政策、技术、项目、企业和
  产业链原始信源，也不能由涨跌推导订单、市场规模或因果结论。
- 没有可用金融结果时，行业简报仍应正常生成；不得用旧值冒充当天数据。
- 跨仓库消费必须通过后续明确版本化的发布 artifact 或公开结果文件完成，不能通过
  `git` 直接读取另一个仓库的工作区。
