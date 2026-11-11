# uncache_unit

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `uncache_unit` | `IfuUncacheUnit` | `IfuUncacheUnitDut` |

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md) · [docs/spec/design/functional-points.md](../../docs/spec/design/functional-points.md) · [docs/spec/design/behavior-matrix.md](../../docs/spec/design/behavior-matrix.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/transaction-adapters.md](../../docs/spec/verification/transaction-adapters.md) · [docs/spec/verification/observation-coverage.md](../../docs/spec/verification/observation-coverage.md) · [docs/spec/verification/coverage/coverage-loop.md](../../docs/spec/verification/coverage/coverage-loop.md) · [docs/spec/verification/coverage/coverage-summary.md](../../docs/spec/verification/coverage/coverage-summary.md) · [docs/spec/verification/exit-criteria.md](../../docs/spec/verification/exit-criteria.md)
- 公开环境：[testbenches/uncache_unit/env/agent.py](env/agent.py)
- 用例与自检：[testbenches/uncache_unit/tests](tests)
- 实现职责：[testbenches/uncache_unit/transactions.py](transactions.py) · [testbenches/uncache_unit/model](model) · [testbenches/uncache_unit/checker.py](checker.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ifu --dut uncache_unit
./scripts/ucv run ifu --dut uncache_unit --collect-only --workers 1
./scripts/ucv run ifu --dut uncache_unit --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
