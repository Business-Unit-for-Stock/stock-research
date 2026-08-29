# QMT 行情分析与模拟盘运行

QMT 是本体系的首选行情来源。`xtdata` 读取历史行情用于因子、回测和报告；如果 QMT
行情服务不可用，只有选择 `qmt-first` 时才会按顺序回退到公共数据，并在
`market-manifest.json` 记录原因。订单部分仍默认是 `dry-run`，读取已审核的
`trades.csv` 后只生成订单审计 JSON，不连接券商。

## QMT 行情分析

QMT 客户端需要在 Windows 自托管 Runner 上运行，并提供本地 `xtdata` 服务。启动 QMT
并完成客户端登录后，可以在仓库根目录执行：

```powershell
python -m pip install -e ".[data]"
python scripts/fetch_market_data.py `
  --symbols config\symbols.txt `
  --start-date 20250101 `
  --end-date 20251231 `
  --source qmt
python -m stock_research.cli `
  --bars data\market\market_daily.csv `
  --lookback 20 `
  --top-n 5 `
  --output outputs
```

`--source qmt` 在 QMT 不可用时直接失败，适合验证数据链路；`--source qmt-first` 才允许
回退公共数据。每次输出的 `data/market/market-manifest.json` 会标记 `source_used`，不要
把回退结果误认为 QMT 数据。

GitHub Actions 中的 `QMT-first market analysis` 只运行在
`[self-hosted, windows, qmt]` Runner。该 Workflow 不读取证券密码，QMT 行情服务使用
本机客户端会话；若选择 `qmt-first`，Runner 还需要安装可选的公共数据依赖。

## 运行边界

- 当前只支持股票账户（`STOCK`）。
- QMT 行情读取是只读操作，不使用交易账户，也不提交订单。
- 订单数量必须是正数且为 100 股整数倍。
- `qmt-paper.yml` 只允许 `paper` 模式；本仓库不会从 GitHub Actions 提交实盘订单。
- 只有 Windows 自托管 Runner 标签 `[self-hosted, windows, qmt]` 才能执行该 Workflow。
- 真实 QMT/`xtquant` 构造参数应以本机 QMT 版本文档和模拟盘实测为准，本适配层不承诺成交。

## Windows Runner

在安装 QMT 的 Windows 机器上安装 GitHub Actions 自托管 Runner，并添加标签：

```text
self-hosted, windows, qmt
```

Runner 应使用已安装 `xtquant` 的 Python 环境。不要在 Runner 工作目录保存账号密码、
Token 或 `.env` 文件；QMT 客户端登录状态和会话目录只留在本机受保护位置。

## Environment Secrets

仓库已创建 `qmt-paper` Environment，并配置 `PeterKZhao` 为必需审批者。只在该
Environment 中配置下列 Secret 名称，实际值由你自行填写，不要提交到代码仓库：

| Secret | 用途 |
|---|---|
| `QMT_ACCOUNT_ID` | QMT 股票账户标识 |
| `QMT_SESSION_PATH` | QMT 会话/连接目录 |
| `QMT_SESSION_ID` | xtquant 会话号，可留空使用默认值 |
| `QMT_RUNNER_CONFIRMED` | 确认 Runner 是本机 QMT 主机 |
| `QMT_APPROVED` | 经过 Environment 审批后的 paper 提交确认 |

不要配置或传递证券登录密码给本仓库脚本。若你的 QMT 版本必须单独登录，请在本机
QMT 客户端完成登录，并让 Runner 使用该本地会话。

## 执行方式

1. 先运行 `Backtest report`，下载 Artifact 中的 `trades.csv`，人工检查日期、数量、价格和涨跌停约束。
2. 手动触发 `QMT paper execution`：可以选择 `backtest-artifact` 并填写回测 Run ID，或将已审核的 `trades.csv` 放到 Runner 工作区之外（例如 `C:\qmt-approved\trades.csv`）后选择 `runner-file`。
3. 首次只选择 `dry-run`，确认 `qmt-orders.json` 的代码和数量正确。
4. 只有在模拟盘确认、Environment 审批通过、并填写 `PAPER-ONLY-APPROVED` 后，才选择 `paper-submit`。

紧急停止时暂停 `qmt-paper` Environment、停止 Runner 服务，并在 QMT 客户端撤销未成交委托。

## 本地 dry-run

```powershell
cd D:\project\codex\stock-research
python -m pip install -e .
python scripts/run_qmt.py --trades outputs\trades.csv
```

本地真实提交也必须显式设置 `QMT_RUNNER_CONFIRMED=true`、`QMT_APPROVED=true`，并保持
`QMT_MODE=paper` 与 `PAPER_ONLY=true`；默认不提交。
