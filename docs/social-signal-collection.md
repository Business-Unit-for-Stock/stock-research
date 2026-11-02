# 金融社交信号采集

## 结论

X 和小红书可以帮助发现公司动态、产业讨论、产品反馈和市场关注点，但不能替代交易所公告、监管披露、上市公司 IR、基金文件或正式统计数据。两者统一进入 `social_signal` 层，不能直接写入 `official_fact`。

推荐顺序：

1. X：优先评估官方 X API，使用 `Tweepy` 等官方 API 客户端实现受控读取。
2. 小红书：优先等待授权能力，或从人工精选的公开链接开始；不把逆向接口、Cookie 池和反检测逻辑当作生产方案。
3. 研究阶段：可以用 `Agent-Reach`、`OpenCLI`、`twitter-cli` 或 `xiaohongshu-cli` 辅助发现和人工核验，但采集结果必须经过本仓库的统一契约。

## 开源项目排序

| 项目 | 适用范围 | 当前定位 | 主要风险 |
| --- | --- | --- | --- |
| [tweepy/tweepy](https://github.com/tweepy/tweepy) | X 官方 API | X 生产候选客户端 | 需要 X 开发者凭据、配额、成本和再分发条款核对 |
| [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | X、小红书及其他渠道 | 研究发现层；已纳入资源目录 | 底层路由可能依赖登录态或第三方工具，不能自动继承生产准入 |
| [jackwener/OpenCLI](https://github.com/jackwener/OpenCLI) | 使用登录浏览器访问多个网站 | 人工核验和一次性研究辅助 | 依赖桌面浏览器会话，不适合无头的每日生产任务 |
| [public-clis/twitter-cli](https://github.com/public-clis/twitter-cli) | X 读取和结构化导出 | 研究候选 | Cookie/登录态访问和平台条款需要单独审核 |
| [jackwener/xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) | 小红书搜索、阅读和导出 | 研究候选，不进入生产 | 项目明确使用逆向接口、签名和反检测逻辑，且仓库未声明可直接用于生产再分发 |
| [vladkens/twscrape](https://github.com/vladkens/twscrape) | X 搜索和 GraphQL 访问 | 研究参考 | 账号池、Cookie 和非官方接口路线带来封禁、合规和审计风险 |
| [JustAnotherArchivist/snscrape](https://github.com/JustAnotherArchivist/snscrape) | 多社交平台抓取 | 过时研究参考 | 最近维护时间为 2023 年 11 月 15 日，超过本项目 183 天过时门槛 |

项目状态按 2026 年 10 月 6 日快照核验；“活跃”只代表值得评估，不代表准入。业务相关性、授权、来源稳定性、数据权利和可复现性优先于 star 数量。

## 采集边界

- X：只收集预先登记的官方机构、上市公司、行业协会、研究机构和重点企业账号；搜索词和账号列表都版本化。
- 小红书：第一阶段只保存人工精选或授权入口的链接、标题、发布时间、作者标识和短摘要；不批量复制全文，不自动操作账号，不绕过验证码、登录限制或访问控制。
- 社交内容只用于发现线索、补充市场语境和识别待核查事件。涉及公司经营、产品发布、监管、业绩、融资或重大交易的内容，必须链接到独立的原始证据。
- 互动量只能作为排序信号，不能直接解释为影响力、真实性、市场影响或投资价值。
- 每个平台单独记录失败、限流、权限过期和降级路径，不能把“没有采集到”解释为“没有发生”。

## 最小数据契约

每条社交信号至少保留：

| 字段 | 含义 |
| --- | --- |
| `platform` | `x` 或 `xiaohongshu` |
| `external_id` | 平台原始帖子或笔记 ID |
| `author_id` / `author_name` | 作者标识；能获得时保存 |
| `created_at` | 原帖发布时间，带时区 |
| `fetched_at` | 本次采集时间，带时区 |
| `url` | 原始链接 |
| `query` | 命中的账号、关键词或主题 |
| `content_class` | `official_statement`、`professional_signal`、`market_commentary` 或 `unverified_lead` |
| `matched_entities` | 公司、品牌、产品和证券代码匹配结果 |
| `engagement_snapshot` | 采集时的互动数据，明确这是快照 |
| `collection_method` | `official_api`、`authorized_api`、`manual_curated` 或 `browser_research` |
| `source_status` | `discovery_only`、`needs_corroboration` 或 `corroborated` |

去重主键为 `(platform, external_id)`；引用、转发、回复关系单独保存。原始内容应按平台条款和必要性最小化保存，简报优先输出原链接、短摘要、来源状态和交叉验证结果。

## 简报处理

日报中建议单列“社交信号与待核查线索”，不混入“已确认市场事实”：

1. 先按主体、证券代码、主题和时间去重。
2. 把官方账号发文与普通市场观点分开。
3. 为重大主张寻找公告、财报、交易所或公司 IR 证据。
4. 没有独立证据时明确写“待核实”，不生成确定性结论。
5. 没有符合质量门槛的信号时，简报显示“本日无合格社交信号”，而不是填充低质量内容。
