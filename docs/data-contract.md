# 数据契约

## 行情主键

日线唯一主键为 `(date, symbol)`。证券代码使用：

- 上海：`600519.XSHG`
- 深圳：`000001.XSHE`
- 北京：`430047.XBSE`

## 强制要求

- 同一批 OHLC 必须使用同一复权口径。
- `high >= max(open, close, low)`。
- `low <= min(open, close, high)`。
- 价格严格大于 0，成交量不得小于 0。
- 不允许重复主键。
- 停牌日应保留状态记录，不应简单删除整行。
- 优先保存交易所或可靠数据源提供的 `limit_up`、`limit_down`。
- QMT 行情统一标记 `provider=qmt`；使用公共数据时必须保留实际 provider 和抓取清单。
- `data/market/market-manifest.json` 必须记录请求来源、实际来源和 QMT 失败原因；不得把
  `public-fallback` 结果标记为 QMT 数据。

## 防止研究偏差

- 股票池必须保存历史成分，不能用今天的股票列表回测过去。
- 财务数据使用真实披露日，而不是报告期结束日。
- 退市、暂停上市、ST 和历史证券简称必须保留。
- 数据修订要保存抓取时间和版本，避免悄悄覆盖历史结果。
- 前复权序列可能随着未来公司行为变化，生产研究应保存原始价与复权因子。

## 社交信号契约

X 和小红书内容不属于行情主表，使用独立的 `social_signal` 记录，不得直接提升为官方事实。

- 去重主键为 `(platform, external_id)`，引用、转发和回复关系单独保存。
- 必须保存 `created_at`、`fetched_at`、原始 `url`、命中的账号或查询条件和 `collection_method`。
- `collection_method` 只能取 `official_api`、`authorized_api`、`manual_curated` 或 `browser_research`；浏览器研究结果默认只能作为发现线索。
- `content_class` 至少区分 `official_statement`、`professional_signal`、`market_commentary` 和 `unverified_lead`。
- 公司经营、业绩、监管、融资、产品发布和重大交易等主张，必须关联独立的官方或专业原始证据才能标记为 `corroborated`。
- 点赞、转发、评论和阅读量只能保存为带采集时间的互动快照，不得单独用于推断真实性、影响力或投资价值。
- 平台限流、权限过期、登录失败和空结果必须写入采集清单；空结果不能解释为事件不存在。
