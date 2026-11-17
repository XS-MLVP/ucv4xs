# async_reset_synchronizer_shift_reg_w1_d3_i0

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `async_reset_synchronizer_shift_reg_w1_d3_i0` | `AsyncResetSynchronizerShiftReg_w1_d3_i0` | `AsyncResetSynchronizerShiftRegW1D3I0Dut` |

## 工作入口

- 设计规格：[docs/spec/design/async_reset_synchronizer_shift_reg_w1_d3_i0.md](../../docs/spec/design/async_reset_synchronizer_shift_reg_w1_d3_i0.md)
- 验证合同与计划：[docs/spec/verification/async_reset_synchronizer_shift_reg_w1_d3_i0.md](../../docs/spec/verification/async_reset_synchronizer_shift_reg_w1_d3_i0.md)
- 公开环境：[testbenches/async_reset_synchronizer_shift_reg_w1_d3_i0/env.py](env.py)
- 用例与自检：[testbenches/async_reset_synchronizer_shift_reg_w1_d3_i0/tests](tests)
- 实现职责：[testbenches/async_reset_synchronizer_shift_reg_w1_d3_i0/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info clock_reset --dut async_reset_synchronizer_shift_reg_w1_d3_i0
./scripts/ucv run clock_reset --dut async_reset_synchronizer_shift_reg_w1_d3_i0 --collect-only --workers 1
./scripts/ucv run clock_reset --dut async_reset_synchronizer_shift_reg_w1_d3_i0 --workers 1 -- testbenches/async_reset_synchronizer_shift_reg_w1_d3_i0/tests/test_async_reset_synchronizer_shift_reg_w1_d3_i0_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
