# 复用仓库清单

本清单记录方向研究所需的外部能力。组织 Fork 用于固定版本、跟踪上游和审计；
业务编排、数据契约、质量控制和最终分析统一保留在 `stock-research`。

| 组织 Fork | 上游 | 许可证 | 复用职责 | 接入方式与边界 |
|---|---|---|---|---|
| [akshare](https://github.com/Business-Unit-for-Stock/akshare) | [akfamily/akshare](https://github.com/akfamily/akshare) | MIT | A 股免费行情主适配器 | Workflow 安装组织 Fork；输出统一标准化 |
| [a-stock-data](https://github.com/Business-Unit-for-Stock/a-stock-data) | [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) | Apache-2.0 | 行业排名、板块资金流、热点、龙虎榜等免费接口 | 按端点调用并拆成可测试适配器；iwencai 不进入零 Key 流程 |
| [plate-rotation-skill](https://github.com/Business-Unit-for-Stock/plate-rotation-skill) | [hssqz/plate-rotation-skill](https://github.com/hssqz/plate-rotation-skill) | MIT | 短线板块排名、轮动曲线和龙头持续性 | 调用 CLI/API 保存原始 JSON；第三方聚合接口不得作为唯一真值 |
| [tickflow-stock-panel](https://github.com/Business-Unit-for-Stock/tickflow-stock-panel) | [shy3130/tickflow-stock-panel](https://github.com/shy3130/tickflow-stock-panel) | MIT | 概念轮动、市场状态和 walk-forward 回测参考 | 复用独立算法与测试方法；不绑定其完整 UI/数据库/付费数据服务 |
| [stock-screener](https://github.com/Business-Unit-for-Stock/stock-screener) | [xang1234/stock-screener](https://github.com/xang1234/stock-screener) | Apache-2.0 | 多周期相对强度、行业排名、RRG 和市场状态 | 提取确定性计算模块；不引入完整 PostgreSQL/Redis/前端系统 |
| [TradingAgents-astock](https://github.com/Business-Unit-for-Stock/TradingAgents-astock) | [simonlin1212/TradingAgents-astock](https://github.com/simonlin1212/TradingAgents-astock) | Apache-2.0 | A 股数据适配、政策/新闻/游资解释 | 数据函数可复用；LLM 为可选解释层，不能直接产生方向分数 |
| [quant-momentum-lab](https://github.com/Business-Unit-for-Stock/quant-momentum-lab) | [David-Wu1119/quant-momentum-lab](https://github.com/David-Wu1119/quant-momentum-lab) | MIT | 无未来函数、成本、样本外和稳健性测试基准 | 复用回测约束和测试；美股 ETF 参数不能直接用于 A 股 |
| [qlib](https://github.com/Business-Unit-for-Stock/qlib) | [microsoft/qlib](https://github.com/microsoft/qlib) | MIT | 因子、模型、组合与研究基础设施 | 作为后续主研究引擎适配，不重复实现其通用能力 |

## Workflow 调用规范

每次调用 Fork 必须记录：

- 组织 Fork 地址、提交 SHA 和对应上游地址；
- 数据日期、请求参数、数据源及复权口径；
- 原始文件校验值、行数、错误和降级路径；
- 自有标准化代码提交 SHA、数据契约版本和分析参数；
- 第三方数据授权与再分发限制。

外部调用失败时保留错误证据，不使用旧数据冒充当前数据，也不让 LLM 根据常识补齐。
未经过标准化和质量检查的外部结果不得直接进入方向评分或回测。

## 不引入的仓库

`Healermm/AlphaLab`、`RockyChen0205/sector-rotation-dashboard` 等仓库没有明确
开源许可证，只研究公开思路，不 Fork、不复制实现。
