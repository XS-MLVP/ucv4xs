# bus_error_unit

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `bus_error_unit` | `BusErrorUnit` | `BusErrorUnitDut` |

## 工作入口

- 设计规格：[docs/spec/design/bus_error_unit.md](../../docs/spec/design/bus_error_unit.md)
- 验证合同与计划：[docs/spec/verification/bus_error_unit.md](../../docs/spec/verification/bus_error_unit.md)
- 公开环境：[testbenches/bus_error_unit/env.py](env.py)
- 用例与自检：[testbenches/bus_error_unit/tests](tests)
- 实现职责：[testbenches/bus_error_unit/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut bus_error_unit
./scripts/ucv run l2 --dut bus_error_unit --collect-only --workers 1
./scripts/ucv run l2 --dut bus_error_unit --workers 1 -- testbenches/bus_error_unit/tests/test_bus_error_unit_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
