# vlq

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `virtual_load_queue` | `VirtualLoadQueue` | `VirtualLoadQueueDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/virtual-load-queue.md](../../docs/spec/design/contracts/virtual-load-queue.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/vlq/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/vlq/tests](tests) · [testbenches/vlq/tests/test_basic.py](tests/test_basic.py) · [testbenches/vlq/tests/test_extended.py](tests/test_extended.py) · [testbenches/vlq/tests/test_toggle_gap_closure.py](tests/test_toggle_gap_closure.py)
- 实现职责：[testbenches/vlq/transactions.py](transactions.py) · [testbenches/vlq/model.py](model.py) · [testbenches/vlq/checker.py](checker.py) · [testbenches/vlq/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut virtual_load_queue
./scripts/ucv run lsq --dut virtual_load_queue --collect-only --workers 1
./scripts/ucv run lsq --dut virtual_load_queue --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
