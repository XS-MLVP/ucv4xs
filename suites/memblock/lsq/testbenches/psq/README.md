# psq

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `physical_store_queue` | `PhysicalStoreQueue` | `PhysicalStoreQueueDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/physical-store-queue.md](../../docs/spec/design/contracts/physical-store-queue.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/psq/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/psq/tests](tests) · [testbenches/psq/tests/test_forward_safety.py](tests/test_forward_safety.py) · [testbenches/psq/tests/test_full_model.py](tests/test_full_model.py) · [testbenches/psq/tests/test_initial.py](tests/test_initial.py) · [testbenches/psq/tests/test_pool_payload.py](tests/test_pool_payload.py) · [testbenches/psq/tests/test_prefix_byte_windows.py](tests/test_prefix_byte_windows.py) · [testbenches/psq/tests/test_remaining_lines.py](tests/test_remaining_lines.py) · [testbenches/psq/tests/test_semantic_full.py](tests/test_semantic_full.py) · [testbenches/psq/tests/test_special_order.py](tests/test_special_order.py) · [testbenches/psq/tests/test_storage_expanded.py](tests/test_storage_expanded.py) · [testbenches/psq/tests/test_strict_lifetimes.py](tests/test_strict_lifetimes.py) · [testbenches/psq/tests/test_uq_page_pairs.py](tests/test_uq_page_pairs.py) · [testbenches/psq/tests/test_zero_owner.py](tests/test_zero_owner.py)
- 实现职责：[testbenches/psq/transactions.py](transactions.py) · [testbenches/psq/model.py](model.py) · [testbenches/psq/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut physical_store_queue
./scripts/ucv run lsq --dut physical_store_queue --collect-only --workers 1
./scripts/ucv run lsq --dut physical_store_queue --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
