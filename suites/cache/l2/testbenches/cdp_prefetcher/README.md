# cdp_prefetcher

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `cdp_prefetcher` | `CDPPrefetcher` | `CdpPrefetcherDut` |

## 工作入口

- 设计规格：[docs/spec/design/cdp_prefetcher.md](../../docs/spec/design/cdp_prefetcher.md)
- 验证合同与计划：[docs/spec/verification/cdp_prefetcher.md](../../docs/spec/verification/cdp_prefetcher.md)
- 公开环境：[testbenches/cdp_prefetcher/env.py](env.py)
- 用例与自检：[testbenches/cdp_prefetcher/tests](tests)
- 实现职责：[testbenches/cdp_prefetcher/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut cdp_prefetcher
./scripts/ucv run l2 --dut cdp_prefetcher --collect-only --workers 1
./scripts/ucv run l2 --dut cdp_prefetcher --workers 1 -- testbenches/cdp_prefetcher/tests/test_cdp_prefetcher_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
