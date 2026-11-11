# instr_uncache

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `instr_uncache` | `InstrUncache` | `InstrUncacheDut` |

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md) · [docs/spec/design/contracts.md](../../docs/spec/design/contracts.md) · [docs/spec/design/functional-points.md](../../docs/spec/design/functional-points.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/coverage/coverage-loop.md](../../docs/spec/verification/coverage/coverage-loop.md) · [docs/spec/verification/coverage/coverage-summary.md](../../docs/spec/verification/coverage/coverage-summary.md) · [docs/spec/verification/defects.md](../../docs/spec/verification/defects.md) · [docs/spec/verification/exit-criteria.md](../../docs/spec/verification/exit-criteria.md) · [docs/spec/verification/reports/verification-report.md](../../docs/spec/verification/reports/verification-report.md) · [docs/spec/verification/evidence/flush-closure.json](../../docs/spec/verification/evidence/flush-closure.json)
- 公开环境：[testbenches/instr_uncache/env/agent.py](env/agent.py)
- 用例与自检：[testbenches/instr_uncache/tests](tests)
- 实现职责：[testbenches/instr_uncache/transactions.py](transactions.py) · [testbenches/instr_uncache/model.py](model.py) · [testbenches/instr_uncache/checker.py](checker.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info instr_uncache --dut instr_uncache
./scripts/ucv run instr_uncache --dut instr_uncache --collect-only --workers 1
./scripts/ucv run instr_uncache --dut instr_uncache --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
