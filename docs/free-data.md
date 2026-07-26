# 免费数据获取

## 当前策略

Workflow 只安装并调用公开数据接口：

- AKShare：默认主源，A 股日线；
- yfinance：默认补充源，主要用于跨市场或接口交叉检查；
- Tushare：代码已保留在组织 Fork，但 Pro 数据权限依赖 Token 和积分，本 Workflow 不把它作为“零配置免费源”。

数据结果通过 GitHub Actions Artifact 保存，不自动把完整行情数据提交到 Git 仓库。这样可以避免仓库无限膨胀，也避免误将第三方数据重新公开分发。

## 手动运行

在 GitHub Actions 中选择 `Free market data snapshot`，可以输入：

- `start_date`：如 `20250101`；
- `end_date`：如 `20250726`；
- `providers`：默认 `akshare,yfinance`，也可以只填写 `akshare`；
- `adjust`：`none`、`qfq` 或 `hfq`。

本地运行：

```powershell
cd D:\project\codex\stock-research
python -m pip install -e .
python scripts/fetch_free_data.py --start-date 20250101 --end-date 20250726
```

输出目录为 `data/snapshot/`：

- `akshare_daily.csv`；
- `yfinance_daily.csv`（启用时）；
- `manifest.json`，记录时间范围、来源、行数和错误。

每个 AKShare 股票请求在独立子进程中运行，默认 45 秒超时，避免某个免费接口长时间无响应拖死整次 Workflow。失败明细会写入 `manifest.json`。

## 重要边界

免费接口适合学习和研究，不代表可以稳定商用或对外再分发。每次下载都应保留来源、抓取时间、参数和授权备注；生产研究还需要增加数据去重、缺口检测、复权因子、历史股票池和 point-in-time 财务数据。
