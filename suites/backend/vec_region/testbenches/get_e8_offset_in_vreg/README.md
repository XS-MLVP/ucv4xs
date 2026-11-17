# get_e8_offset_in_vreg

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `get_e8_offset_in_vreg` | `GetE8OffsetInVreg` | `GetE8OffsetInVregDut` |

## 工作入口

- 设计规格：[docs/spec/design/get_e8_offset_in_vreg.md](../../docs/spec/design/get_e8_offset_in_vreg.md)
- 验证合同与计划：[docs/spec/verification/get_e8_offset_in_vreg.md](../../docs/spec/verification/get_e8_offset_in_vreg.md)
- 公开环境：[testbenches/get_e8_offset_in_vreg/env.py](env.py)
- 用例与自检：[testbenches/get_e8_offset_in_vreg/tests](tests)
- 实现职责：[testbenches/get_e8_offset_in_vreg/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vec_region --dut get_e8_offset_in_vreg
./scripts/ucv run vec_region --dut get_e8_offset_in_vreg --collect-only --workers 1
./scripts/ucv run vec_region --dut get_e8_offset_in_vreg --workers 1 -- testbenches/get_e8_offset_in_vreg/tests/test_get_e8_offset_in_vreg_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
