# 方向数据 Workflow

`Direction data snapshot` 在每个工作日北京时间 18:35 运行，也可由其他 Workflow
或 Actions 页面手动调用。它不提交行情和方向数据到 Git，而是生成保留 30 天的
Artifact，并将最新标准化结果发布到
[GitHub Pages](https://business-unit-for-stock.github.io/stock-research/)。

## 复用关系

- `plate-rotation-skill`：直接调用其 `fetch.py` 和 `parsers.py`，获取同花顺涨幅榜和
  开盘啦强度榜；完整原始响应保留在 Artifact，标准化阶段采用最新交易日上游精选
  Top10；
- `akshare`：直接安装组织 Fork，获取东方财富的行业和概念板块结构化快照；
- `a-stock-data`：44 项 A 股数据接口方法的目录，覆盖行情、财报、公告、资金流、涨停、
  情绪和信号等类别。当前代码只存在于 `SKILL.md`，不是可导入包。Workflow 只固定并
  记录该 Fork 的提交，不由它发起数据请求；运行时板块请求使用 AKShare 的结构化接口。

这种分工避免复制或执行不受版本控制的 Markdown 代码，同时确保每次运行都可追溯
到组织 Fork 的具体提交。

## Artifact

| 文件 | 内容 |
|---|---|
| `raw/*.json` | 各 Fork 返回的原始 JSON；不作为最终分析输入直接使用 |
| `direction_evidence.csv` | 统一方向证据表，保留来源、名称、排名、原始量纲和上游提交 |
| `direction_analysis.csv` | 当前交易日按名称聚合的覆盖、强势和持续性标签 |
| `multi_source_strong.csv` | 至少两个独立来源分别满足其强势规则的方向 |
| `multi_source_coverage.csv` | 至少两个独立来源出现的方向，包含多源强势方向 |
| `summary.md` | GitHub Actions 摘要 |
| `manifest.json` | 参数、Fork SHA、文件 SHA-256、行数、错误和方法约束 |

## GitHub Pages

公开页面将四个运行数据源与 `a-stock-data` 方法参考分开显示，并分别展示多源强势、
多源覆盖和完整方向分析。页面支持名称、分类、来源及范围筛选，并提供标准化 CSV 与
运行清单下载。页面每次由 Workflow 重新生成，不将运行结果提交到 Git 历史。为避免
无边界复制第三方响应，`raw/*.json` 只保留在 30 天 Artifact 中，不发布到 Pages。
若任一运行时来源失败，该次诊断 Artifact 仍会上传，但不会覆盖此前发布的完整页面。

## 覆盖与强势规则

1. 同一 `source_family` 只计一次证据。东方财富的行业和概念快照同属一个来源，不能
   因同名出现而重复提高覆盖或强势计数。
2. `multi_source_coverage` 表示至少两个独立来源出现同一标准化名称，只证明名称覆盖，
   不证明这些来源都看强。
3. `multi_source_strong` 表示至少两个独立来源分别满足自身规则：同花顺与开盘啦当前
   接口本身就是上游精选强榜，因此返回项均算强势；东方财富必须位于对应完整榜单前
   20%，且当日涨幅大于 0。
4. 同花顺涨幅百分比、开盘啦强度分和东方财富涨跌幅不混合计算，也不再换算“相对位置”
   或跨来源平均排名。证据表仍保留原始 `rank`、`list_size`、指标值和量纲，便于追溯。
5. 上游历史矩阵解析器在空单元格场景存在日期错位风险，因此当前版本不依据它生成
   历史持续性结论。数据为空、非交易日或接口异常时保留错误，绝不以旧数据或模型
   常识补齐。
6. AKShare 的东财行业与概念接口遇到临时连接错误时默认短退避重试两次；重试耗尽后
   使用同一 AKShare 加载器改走东方财富官方 `push2delay` 备用主机。字段映射、分页与
   DataFrame 解析仍由 AKShare 完成；备用主机也失败时保留失败状态，不发布残缺页面。
7. 本地不设置 Top-N 截断：每个接口返回的全部可解析记录均进入证据表和分析。但这不
   等同于每个上游都是全市场榜单：同花顺与开盘啦接口固定返回精选 Top10，东方财富
   行业和概念接口返回完整表。

## 同花顺与开盘啦宽榜接口检索

截至 2026-07-28，已对组织 Fork 和 GitHub 公开仓库中的可复用实现做过检索与实际试验：

| 候选 | 结果 | 决策 |
|---|---|---|
| `plate-rotation-skill/getPlateRotatData` | 同花顺与开盘啦均固定返回当前 Top10 | 保留；这是当前稳定、免费、可复用的强榜 |
| `icekale/strong-stock-screener` | 仍封装同一个接口；即使传 `limit=50` 也只有 10 条 | 不重复 Fork |
| AKShare `stock_board_industry_summary_ths` | 可表达更宽同花顺行业排名，但匿名请求出现 401/登录态问题，本地试验也超时 | 暂不接入 Workflow |
| AKShare `stock_board_concept_name_ths` | 只有概念名称和代码，没有当前强度排名 | 不用于强势判定 |
| 开盘啦 `GetZSHQPlate` 旧实现 | 2019 年代码、无许可证，并内置他人 `UserID`/`Token` | 不复用，不使用他人凭据 |

`plate-rotation-skill` 另有历史曲线、板块龙头和单板块日线接口，但都不能替代“更宽的
当前板块强度榜”。后续若发现无需登录、许可证明确且能稳定返回宽榜的接口，再按
Fork 固定版本、Workflow 调用、保留原始响应的现有模式接入。

## 手动运行

先 checkout 组织 Fork 并安装 AKShare，然后运行：

```powershell
$env:PYTHONPATH = "src"
python scripts/fetch_direction_data.py `
  --output-dir data/direction `
  --plate-repo ..\plate-rotation-skill `
  --akshare-repo ..\akshare `
  --a-stock-data-repo ..\a-stock-data `
  --days 20
```

运行失败时仍会尽量写出 `manifest.json`、`summary.md` 和各成功来源的原始文件，便于
定位某个免费接口的失效或风控问题。
