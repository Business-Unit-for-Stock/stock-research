# 行业知识库接入

`PeterKZhao/industry-analysis` 是私有 Obsidian 知识库，不是 Python 依赖，也没有被
复制进 `stock-research`。两者的职责如下：

```text
industry-analysis（行业身份、产业链、企业、来源证据）
                 |
                 v  只导出 Frontmatter + SRC-* 引用
stock-research（结构化校验、因子、回测、报告和 QMT 安全执行）
```

## 导出内容

`Industry knowledge sync` Workflow 生成 `industry-context-*` Artifact，包含：

- `industry_registry.csv`：行业 ID、国标分类、研究领域、状态和置信度；
- `company_registry.csv`：企业 ID、统一证券代码、关联行业和来源引用；
- `industry-manifest.json`：知识库提交 SHA、扫描数量和内容排除规则。

导出器不复制 Markdown 正文、附件、Obsidian 配置或任何凭据。`draft`、`to-verify` 和
`stale` 记录会保留状态，不能被自动解释为买卖信号。

## 使用行业上下文

下载 Artifact 后，可以把行业字段附加到回测信号表：

```powershell
python scripts/enrich_signals.py `
  --signals outputs\signals.csv `
  --companies outputs\industry\company_registry.csv `
  --industries outputs\industry\industry_registry.csv `
  --output outputs\signals-industry.csv
```

该步骤只增加行业和证据上下文，不修改 `target_weight`，也不会生成投资建议。没有
证券代码映射的股票会保留信号，但行业字段为空并计入覆盖率检查。

## 配置私有同步

仓库已创建 `industry-sync` Environment 并设置审批者。只在该 Environment 中添加：

| Secret | 权限 |
|---|---|
| `INDUSTRY_KB_TOKEN` | Fine-grained PAT，仅对 `PeterKZhao/industry-analysis` 授予 `Contents: Read` |

该 Token 不要放入普通 Repository secrets、代码、`.env` 或结果仓库。首次运行建议手动
指定一个已知的 `industry-analysis` commit SHA；日常更新再使用 `main`。

## 研究边界

行业知识库的事实、证据等级和复核状态用于解释和筛选上下文，不直接决定股票权重。
行业动量、估值、财务和交易规则仍必须来自有日期口径的数据表，并经过
`stock_research` 的数据契约和样本外验证。
