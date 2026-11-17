# berti_prefetcher

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `berti_prefetcher` | `BertiPrefetcher` | `BertiPrefetcherDut` |

## 工作入口

- 设计规格：[docs/spec/design/berti_prefetcher.md](../../docs/spec/design/berti_prefetcher.md)
- 验证合同与计划：[docs/spec/verification/berti_prefetcher.md](../../docs/spec/verification/berti_prefetcher.md)
- 公开环境：[testbenches/berti_prefetcher/env.py](env.py)
- 用例与自检：[testbenches/berti_prefetcher/tests](tests)
- 实现职责：[testbenches/berti_prefetcher/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info prefetch --dut berti_prefetcher
./scripts/ucv run prefetch --dut berti_prefetcher --collect-only --workers 1
./scripts/ucv run prefetch --dut berti_prefetcher --workers 1 -- testbenches/berti_prefetcher/tests/test_berti_prefetcher_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
