# 方向数据 Workflow

`Direction data snapshot` 在每个工作日北京时间 18:35 运行，也可由其他 Workflow
或 Actions 页面手动调用。它不提交行情和方向数据到 Git，而是生成保留 30 天的
Artifact。

## 复用关系

- `plate-rotation-skill`：直接调用其 `fetch.py` 和 `parsers.py`，获取同花顺涨幅榜和
  开盘啦强度榜；完整原始响应保留在 Artifact，标准化阶段采用最新交易日完整榜单；
- `akshare`：直接安装组织 Fork，获取东方财富的行业和概念板块结构化快照；
- `a-stock-data`：当前代码只存在于 `SKILL.md`，不是可导入包。Workflow 固定并记录
  该 Fork 的提交，作为东财行业排名和板块资金流接口的方法来源；运行时使用 AKShare
  的结构化接口，而不从 Markdown 动态执行代码。

这种分工避免复制或执行不受版本控制的 Markdown 代码，同时确保每次运行都可追溯
到组织 Fork 的具体提交。

## Artifact

| 文件 | 内容 |
|---|---|
| `raw/*.json` | 各 Fork 返回的原始 JSON；不作为最终分析输入直接使用 |
| `direction_evidence.csv` | 统一方向证据表，保留来源、名称、排名、原始量纲和上游提交 |
| `direction_analysis.csv` | 当前交易日按名称聚合的多源证据和持续性标签 |
| `confirmed_directions.csv` | 至少两个独立来源共同出现的当前候选 |
| `summary.md` | GitHub Actions 摘要 |
| `manifest.json` | 参数、Fork SHA、文件 SHA-256、行数、错误和方法约束 |

## 交叉验证规则

1. 同一 `source_family` 只计一次证据。东方财富的行业和概念快照同属一个来源，不能
   因同名出现而提高一致性计数。
2. 同花顺涨幅百分比、开盘啦强度分和东方财富涨跌幅不混合计算。只将各自榜单位置换为
   该榜单内部的 `rank_score`，再计算证据的平均位置。
3. `cross_source` 表示至少两个独立来源共同出现，不表示交易信号，更不代表收益预测。
4. 上游历史矩阵解析器在空单元格场景存在日期错位风险，因此当前版本不依据它生成
   历史持续性结论。数据为空、非交易日或接口异常时保留错误，绝不以旧数据或模型
   常识补齐。
5. AKShare 的东财行业与概念接口遇到临时连接错误时默认短退避重试两次；重试耗尽后
   保留该来源失败状态，其他成功来源仍正常产出。
6. 当前榜单不设置 Top-N 截断。AKShare 返回的全部行业和概念、板块轮动接口返回的
   全部当前记录均进入证据表和分析；`rank_score` 按各自实际榜单长度计算。

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
