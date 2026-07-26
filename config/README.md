# 数据获取配置

`symbols.txt` 是 Workflow 的默认观察池。每行一个 A 股代码，可写成：

```text
600519
000001.XSHE
```

代码会在进入数据源前统一为 `XXXXXX.XSHG/XSHE/XBSE`。

当前 Workflow 默认使用 AKShare 和 yfinance 的公开日线接口，不需要 Token。只想使用 AKShare 时，可以在手动运行中指定：

```text
--providers akshare
```

不要把付费数据、Token 或券商凭证提交到仓库。
