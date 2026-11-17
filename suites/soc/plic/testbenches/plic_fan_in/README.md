# plic_fan_in

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `plic_fan_in` | `PLICFanIn` | `PlicFanInDut` |

## 工作入口

- 设计规格：[docs/spec/design/plic_fan_in.md](../../docs/spec/design/plic_fan_in.md)
- 验证合同与计划：[docs/spec/verification/plic_fan_in.md](../../docs/spec/verification/plic_fan_in.md)
- 公开环境：[testbenches/plic_fan_in/env.py](env.py)
- 用例与自检：[testbenches/plic_fan_in/tests](tests)
- 实现职责：[testbenches/plic_fan_in/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info plic --dut plic_fan_in
./scripts/ucv run plic --dut plic_fan_in --collect-only --workers 1
./scripts/ucv run plic --dut plic_fan_in --workers 1 -- testbenches/plic_fan_in/tests/test_plic_fan_in_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
