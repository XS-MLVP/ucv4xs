# flt_wb_data_path

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `flt_wb_data_path` | `FltWbDataPath` | `FltWbDataPathDut` |

## 工作入口

- 设计规格：[docs/spec/design/flt_wb_data_path.md](../../docs/spec/design/flt_wb_data_path.md)
- 验证合同与计划：[docs/spec/verification/flt_wb_data_path.md](../../docs/spec/verification/flt_wb_data_path.md)
- 公开环境：[testbenches/flt_wb_data_path/env.py](env.py)
- 用例与自检：[testbenches/flt_wb_data_path/tests](tests)
- 实现职责：[testbenches/flt_wb_data_path/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info fp_region --dut flt_wb_data_path
./scripts/ucv run fp_region --dut flt_wb_data_path --collect-only --workers 1
./scripts/ucv run fp_region --dut flt_wb_data_path --workers 1 -- testbenches/flt_wb_data_path/tests/test_flt_wb_data_path_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
