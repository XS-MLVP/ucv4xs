# clock_gate

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `clock_gate` | `ClockGate` | `ClockGateDut` |

## 工作入口

- 设计规格：[docs/spec/design/clock_gate.md](../../docs/spec/design/clock_gate.md)
- 验证合同与计划：[docs/spec/verification/clock_gate.md](../../docs/spec/verification/clock_gate.md)
- 公开环境：[testbenches/clock_gate/env.py](env.py)
- 用例与自检：[testbenches/clock_gate/tests](tests)
- 实现职责：[testbenches/clock_gate/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info clock_reset --dut clock_gate
./scripts/ucv run clock_reset --dut clock_gate --collect-only --workers 1
./scripts/ucv run clock_reset --dut clock_gate --workers 1 -- testbenches/clock_gate/tests/test_clock_gate_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
