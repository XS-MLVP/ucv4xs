# replay

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `load_queue_replay` | `LoadQueueReplay` | `LoadQueueReplayDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/load-queue-replay.md](../../docs/spec/design/contracts/load-queue-replay.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/replay/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/replay/tests](tests) · [testbenches/replay/tests/test_basic.py](tests/test_basic.py) · [testbenches/replay/tests/test_cause_lifetimes.py](tests/test_cause_lifetimes.py) · [testbenches/replay/tests/test_extended.py](tests/test_extended.py) · [testbenches/replay/tests/test_gap_closure.py](tests/test_gap_closure.py) · [testbenches/replay/tests/test_normal_metadata.py](tests/test_normal_metadata.py) · [testbenches/replay/tests/test_pool_payload.py](tests/test_pool_payload.py) · [testbenches/replay/tests/test_timing.py](tests/test_timing.py)
- 实现职责：[testbenches/replay/transactions.py](transactions.py) · [testbenches/replay/model](model) · [testbenches/replay/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut load_queue_replay
./scripts/ucv run lsq --dut load_queue_replay --collect-only --workers 1
./scripts/ucv run lsq --dut load_queue_replay --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
