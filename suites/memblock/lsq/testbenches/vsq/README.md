# vsq

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `virtual_store_queue` | `VirtualStoreQueue` | `VirtualStoreQueueDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/virtual-store-queue.md](../../docs/spec/design/contracts/virtual-store-queue.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/vsq/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/vsq/tests](tests) · [testbenches/vsq/tests/test_cancel_capacity.py](tests/test_cancel_capacity.py) · [testbenches/vsq/tests/test_deep_suffix.py](tests/test_deep_suffix.py) · [testbenches/vsq/tests/test_extended.py](tests/test_extended.py) · [testbenches/vsq/tests/test_initial.py](tests/test_initial.py) · [testbenches/vsq/tests/test_recovery_flags.py](tests/test_recovery_flags.py) · [testbenches/vsq/tests/test_release_windows.py](tests/test_release_windows.py) · [testbenches/vsq/tests/test_retire_batch_width.py](tests/test_retire_batch_width.py) · [testbenches/vsq/tests/test_retire_known_width.py](tests/test_retire_known_width.py)
- 实现职责：[testbenches/vsq/transactions.py](transactions.py) · [testbenches/vsq/model](model) · [testbenches/vsq/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut virtual_store_queue
./scripts/ucv run lsq --dut virtual_store_queue --collect-only --workers 1
./scripts/ucv run lsq --dut virtual_store_queue --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
