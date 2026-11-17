# sms_prefetcher

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `sms_prefetcher` | `SMSPrefetcher` | `SmsPrefetcherDut` |

## 工作入口

- 设计规格：[docs/spec/design/sms_prefetcher.md](../../docs/spec/design/sms_prefetcher.md)
- 验证合同与计划：[docs/spec/verification/sms_prefetcher.md](../../docs/spec/verification/sms_prefetcher.md)
- 公开环境：[testbenches/sms_prefetcher/env.py](env.py)
- 用例与自检：[testbenches/sms_prefetcher/tests](tests)
- 实现职责：[testbenches/sms_prefetcher/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info prefetch --dut sms_prefetcher
./scripts/ucv run prefetch --dut sms_prefetcher --collect-only --workers 1
./scripts/ucv run prefetch --dut sms_prefetcher --workers 1 -- testbenches/sms_prefetcher/tests/test_sms_prefetcher_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
