# load_uncache

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `load_queue_uncache` | `LoadQueueUncache` | `LoadQueueUncacheDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/load-queue-uncache.md](../../docs/spec/design/contracts/load-queue-uncache.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/load_uncache/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/load_uncache/tests](tests) · [testbenches/load_uncache/tests/test_full.py](tests/test_full.py) · [testbenches/load_uncache/tests/test_gap_closure.py](tests/test_gap_closure.py) · [testbenches/load_uncache/tests/test_initial_probes.py](tests/test_initial_probes.py) · [testbenches/load_uncache/tests/test_model.py](tests/test_model.py) · [testbenches/load_uncache/tests/test_response_payload_pool.py](tests/test_response_payload_pool.py) · [testbenches/load_uncache/tests/test_sid_boundaries.py](tests/test_sid_boundaries.py) · [testbenches/load_uncache/tests/test_timing_boundaries.py](tests/test_timing_boundaries.py) · [testbenches/load_uncache/tests/test_uncache_exception_property.py](tests/test_uncache_exception_property.py)
- 实现职责：[testbenches/load_uncache/transactions.py](transactions.py) · [testbenches/load_uncache/model](model)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut load_queue_uncache
./scripts/ucv run lsq --dut load_queue_uncache --collect-only --workers 1
./scripts/ucv run lsq --dut load_queue_uncache --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
