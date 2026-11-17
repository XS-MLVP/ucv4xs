# imsic_bus

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `imsic_bus` | `imsic_bus_top` | `imsic_bus_topDut` |

## 工作入口

- 设计规格：[docs/spec/design/imsic_bus.md](../../docs/spec/design/imsic_bus.md)
- 验证合同与计划：[docs/spec/verification/imsic_bus.md](../../docs/spec/verification/imsic_bus.md)
- 公开环境：[testbenches/imsic_bus/env.py](env.py)
- 用例与自检：[testbenches/imsic_bus/tests](tests)
- 实现职责：[testbenches/imsic_bus/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info aia --dut imsic_bus
./scripts/ucv run aia --dut imsic_bus --collect-only --workers 1
./scripts/ucv run aia --dut imsic_bus --workers 1 -- testbenches/imsic_bus/tests/test_imsic_bus_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
