# vtype_gen

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `vtype_gen` | `VTypeGen` | `VTypeGenDut` |

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md) · [docs/spec/design/contracts.md](../../docs/spec/design/contracts.md) · [docs/spec/design/functional-points.md](../../docs/spec/design/functional-points.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/coverage/coverage-loop.md](../../docs/spec/verification/coverage/coverage-loop.md) · [docs/spec/verification/coverage/coverage-summary.md](../../docs/spec/verification/coverage/coverage-summary.md) · [docs/spec/verification/defects.md](../../docs/spec/verification/defects.md) · [docs/spec/verification/exit-criteria.md](../../docs/spec/verification/exit-criteria.md) · [docs/spec/verification/reports/verification-report.md](../../docs/spec/verification/reports/verification-report.md)
- 公开环境：[testbenches/vtype_gen/env/agent.py](env/agent.py)
- 用例与自检：[testbenches/vtype_gen/tests](tests)
- 实现职责：[testbenches/vtype_gen/transactions.py](transactions.py) · [testbenches/vtype_gen/model.py](model.py) · [testbenches/vtype_gen/checker.py](checker.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ibuffer --dut vtype_gen
./scripts/ucv run ibuffer --dut vtype_gen --collect-only --workers 1
./scripts/ucv run ibuffer --dut vtype_gen --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
