# fp_rf_read_arbiter

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `fp_rf_read_arbiter` | `FpRFReadArbiter` | `FpRfReadArbiterDut` |

## 工作入口

- 设计规格：[docs/spec/design/fp_rf_read_arbiter.md](../../docs/spec/design/fp_rf_read_arbiter.md)
- 验证合同与计划：[docs/spec/verification/fp_rf_read_arbiter.md](../../docs/spec/verification/fp_rf_read_arbiter.md)
- 公开环境：[testbenches/fp_rf_read_arbiter/env.py](env.py)
- 用例与自检：[testbenches/fp_rf_read_arbiter/tests](tests)
- 实现职责：[testbenches/fp_rf_read_arbiter/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info fp_region --dut fp_rf_read_arbiter
./scripts/ucv run fp_region --dut fp_rf_read_arbiter --collect-only --workers 1
./scripts/ucv run fp_region --dut fp_rf_read_arbiter --workers 1 -- testbenches/fp_rf_read_arbiter/tests/test_fp_rf_read_arbiter_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
