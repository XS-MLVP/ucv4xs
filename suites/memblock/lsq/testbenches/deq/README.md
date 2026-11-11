# deq

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `deq_module` | `DeqModule` | `DeqModuleDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/deq-module.md](../../docs/spec/design/contracts/deq-module.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/deq/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/deq/tests](tests) · [testbenches/deq/tests/test_cbo_fault_consumption.py](tests/test_cbo_fault_consumption.py) · [testbenches/deq/tests/test_initial.py](tests/test_initial.py) · [testbenches/deq/tests/test_lifecycle.py](tests/test_lifecycle.py) · [testbenches/deq/tests/test_special_order.py](tests/test_special_order.py) · [testbenches/deq/tests/test_split_control_consumption.py](tests/test_split_control_consumption.py) · [testbenches/deq/tests/test_uncache_and_queue.py](tests/test_uncache_and_queue.py)
- 实现职责：[testbenches/deq/transactions.py](transactions.py) · [testbenches/deq/model.py](model.py) · [testbenches/deq/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut deq_module
./scripts/ucv run lsq --dut deq_module --collect-only --workers 1
./scripts/ucv run lsq --dut deq_module --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
