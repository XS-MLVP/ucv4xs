# load_queue

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `load_queue` | `LoadQueue` | `LoadQueueDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/load-queue.md](../../docs/spec/design/contracts/load-queue.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/load_queue/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/load_queue/tests](tests) · [testbenches/load_queue/tests/test_capacity.py](tests/test_capacity.py) · [testbenches/load_queue/tests/test_cause_lifetimes.py](tests/test_cause_lifetimes.py) · [testbenches/load_queue/tests/test_checkpoint_pool.py](tests/test_checkpoint_pool.py) · [testbenches/load_queue/tests/test_concurrent.py](tests/test_concurrent.py) · [testbenches/load_queue/tests/test_initial.py](tests/test_initial.py) · [testbenches/load_queue/tests/test_line_gaps.py](tests/test_line_gaps.py) · [testbenches/load_queue/tests/test_normal_replay_metadata.py](tests/test_normal_replay_metadata.py) · [testbenches/load_queue/tests/test_nuke.py](tests/test_nuke.py) · [testbenches/load_queue/tests/test_pool_recovery.py](tests/test_pool_recovery.py) · [testbenches/load_queue/tests/test_priority_special.py](tests/test_priority_special.py) · [testbenches/load_queue/tests/test_raw_checkpoint_owners.py](tests/test_raw_checkpoint_owners.py) · [testbenches/load_queue/tests/test_recovery.py](tests/test_recovery.py) · [testbenches/load_queue/tests/test_replay.py](tests/test_replay.py) · [testbenches/load_queue/tests/test_response_payload_pool.py](tests/test_response_payload_pool.py) · [testbenches/load_queue/tests/test_uncache.py](tests/test_uncache.py) · [testbenches/load_queue/tests/test_uncache_pressure.py](tests/test_uncache_pressure.py)
- 实现职责：[testbenches/load_queue/transactions.py](transactions.py) · [testbenches/load_queue/model](model) · [testbenches/load_queue/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut load_queue
./scripts/ucv run lsq --dut load_queue --collect-only --workers 1
./scripts/ucv run lsq --dut load_queue --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
