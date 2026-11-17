# prefetch_controller

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `prefetch_controller` | `PrefetchController` | `PrefetchControllerDut` |

## 工作入口

- 设计规格：[docs/spec/design/prefetch_controller.md](../../docs/spec/design/prefetch_controller.md)
- 验证合同与计划：[docs/spec/verification/prefetch_controller.md](../../docs/spec/verification/prefetch_controller.md)
- 公开环境：[testbenches/prefetch_controller/env.py](env.py)
- 用例与自检：[testbenches/prefetch_controller/tests](tests)
- 实现职责：[testbenches/prefetch_controller/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut prefetch_controller
./scripts/ucv run l2 --dut prefetch_controller --collect-only --workers 1
./scripts/ucv run l2 --dut prefetch_controller --workers 1 -- testbenches/prefetch_controller/tests/test_prefetch_controller_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
