# time_async

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `time_async` | `TimeAsync` | `TimeAsyncDut` |

## 工作入口

- 设计规格：[docs/spec/design/time_async.md](../../docs/spec/design/time_async.md)
- 验证合同与计划：[docs/spec/verification/time_async.md](../../docs/spec/verification/time_async.md)
- 公开环境：[testbenches/time_async/env.py](env.py)
- 用例与自检：[testbenches/time_async/tests](tests)
- 实现职责：[testbenches/time_async/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info timer --dut time_async
./scripts/ucv run timer --dut time_async --collect-only --workers 1
./scripts/ucv run timer --dut time_async --workers 1 -- testbenches/time_async/tests/test_time_async_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
