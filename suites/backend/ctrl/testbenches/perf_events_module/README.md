# perf_events_module

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `perf_events_module` | `perfEventsModule` | `PerfEventsModuleDut` |

## 工作入口

- 设计规格：[docs/spec/design/perf_events_module.md](../../docs/spec/design/perf_events_module.md)
- 验证合同与计划：[docs/spec/verification/perf_events_module.md](../../docs/spec/verification/perf_events_module.md)
- 公开环境：[testbenches/perf_events_module/env.py](env.py)
- 用例与自检：[testbenches/perf_events_module/tests](tests)
- 实现职责：[testbenches/perf_events_module/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut perf_events_module
./scripts/ucv run ctrl --dut perf_events_module --collect-only --workers 1
./scripts/ucv run ctrl --dut perf_events_module --workers 1 -- testbenches/perf_events_module/tests/test_perf_events_module_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
