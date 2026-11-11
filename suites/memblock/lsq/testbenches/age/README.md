# age

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `age_replay` | `AgeDetector_36` | `AgeReplayDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/age.md](../../docs/spec/design/contracts/age.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/age/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/age/tests](tests) · [testbenches/age/tests/test_basic.py](tests/test_basic.py) · [testbenches/age/tests/test_extended.py](tests/test_extended.py)
- 实现职责：[testbenches/age/transactions.py](transactions.py) · [testbenches/age/model.py](model.py) · [testbenches/age/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut age_replay
./scripts/ucv run lsq --dut age_replay --collect-only --workers 1
./scripts/ucv run lsq --dut age_replay --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
