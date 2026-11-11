# pred_checker

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `pred_checker` | `PredChecker` | `PredCheckerDut` |

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md) · [docs/spec/design/functional-points.md](../../docs/spec/design/functional-points.md) · [docs/spec/design/behavior-matrix.md](../../docs/spec/design/behavior-matrix.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/transaction-adapters.md](../../docs/spec/verification/transaction-adapters.md) · [docs/spec/verification/observation-coverage.md](../../docs/spec/verification/observation-coverage.md) · [docs/spec/verification/coverage/coverage-loop.md](../../docs/spec/verification/coverage/coverage-loop.md) · [docs/spec/verification/coverage/coverage-summary.md](../../docs/spec/verification/coverage/coverage-summary.md) · [docs/spec/verification/exit-criteria.md](../../docs/spec/verification/exit-criteria.md)
- 公开环境：[testbenches/pred_checker/env/agent.py](env/agent.py)
- 用例与自检：[testbenches/pred_checker/tests](tests)
- 实现职责：[testbenches/pred_checker/transactions.py](transactions.py) · [testbenches/pred_checker/model](model) · [testbenches/pred_checker/checker.py](checker.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ifu --dut pred_checker
./scripts/ucv run ifu --dut pred_checker --collect-only --workers 1
./scripts/ucv run ifu --dut pred_checker --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
