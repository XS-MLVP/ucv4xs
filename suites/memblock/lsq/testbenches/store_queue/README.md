# store_queue

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `store_queue` | `StoreQueue` | `StoreQueueDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/store-queue.md](../../docs/spec/design/contracts/store-queue.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/store_queue/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/store_queue/tests](tests) · [testbenches/store_queue/tests/test_bytes.py](tests/test_bytes.py) · [testbenches/store_queue/tests/test_cancel_capacity.py](tests/test_cancel_capacity.py) · [testbenches/store_queue/tests/test_forward.py](tests/test_forward.py) · [testbenches/store_queue/tests/test_initial.py](tests/test_initial.py) · [testbenches/store_queue/tests/test_pool_payload.py](tests/test_pool_payload.py) · [testbenches/store_queue/tests/test_prefix_byte_windows.py](tests/test_prefix_byte_windows.py) · [testbenches/store_queue/tests/test_recovery.py](tests/test_recovery.py) · [testbenches/store_queue/tests/test_release_windows.py](tests/test_release_windows.py) · [testbenches/store_queue/tests/test_remaining.py](tests/test_remaining.py) · [testbenches/store_queue/tests/test_retire_known_width.py](tests/test_retire_known_width.py) · [testbenches/store_queue/tests/test_scalar_reservation_pool.py](tests/test_scalar_reservation_pool.py) · [testbenches/store_queue/tests/test_special.py](tests/test_special.py) · [testbenches/store_queue/tests/test_stream.py](tests/test_stream.py) · [testbenches/store_queue/tests/test_strict_lifetimes.py](tests/test_strict_lifetimes.py) · [testbenches/store_queue/tests/test_uq_page_pairs.py](tests/test_uq_page_pairs.py)
- 实现职责：[testbenches/store_queue/transactions.py](transactions.py) · [testbenches/store_queue/model](model) · [testbenches/store_queue/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut store_queue
./scripts/ucv run lsq --dut store_queue --collect-only --workers 1
./scripts/ucv run lsq --dut store_queue --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
