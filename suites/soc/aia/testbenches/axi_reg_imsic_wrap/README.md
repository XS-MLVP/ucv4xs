# axi_reg_imsic_wrap

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `axi_reg_imsic_wrap` | `AXIRegIMSIC_WRAP` | `AXIRegIMSIC_WRAPDut` |

## 工作入口

- 设计规格：[docs/spec/design/axi_reg_imsic_wrap.md](../../docs/spec/design/axi_reg_imsic_wrap.md)
- 验证合同与计划：[docs/spec/verification/axi_reg_imsic_wrap.md](../../docs/spec/verification/axi_reg_imsic_wrap.md)
- 公开环境：[testbenches/axi_reg_imsic_wrap/env.py](env.py)
- 用例与自检：[testbenches/axi_reg_imsic_wrap/tests](tests)
- 实现职责：[testbenches/axi_reg_imsic_wrap/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info aia --dut axi_reg_imsic_wrap
./scripts/ucv run aia --dut axi_reg_imsic_wrap --collect-only --workers 1
./scripts/ucv run aia --dut axi_reg_imsic_wrap --workers 1 -- testbenches/axi_reg_imsic_wrap/tests/test_axi_reg_imsic_wrap_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
