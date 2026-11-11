# rar

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `load_queue_rar` | `LoadQueueRAR` | `LoadQueueRarDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/load-queue-rar.md](../../docs/spec/design/contracts/load-queue-rar.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/rar/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/rar/tests](tests) · [testbenches/rar/tests/test_basic.py](tests/test_basic.py) · [testbenches/rar/tests/test_extended.py](tests/test_extended.py) · [testbenches/rar/tests/test_release_boundaries.py](tests/test_release_boundaries.py)
- 实现职责：[testbenches/rar/transactions.py](transactions.py) · [testbenches/rar/model.py](model.py) · [testbenches/rar/checker.py](checker.py) · [testbenches/rar/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut load_queue_rar
./scripts/ucv run lsq --dut load_queue_rar --collect-only --workers 1
./scripts/ucv run lsq --dut load_queue_rar --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
