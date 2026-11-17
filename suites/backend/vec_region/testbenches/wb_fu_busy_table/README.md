# wb_fu_busy_table

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `wb_fu_busy_table` | `WbFuBusyTable` | `WbFuBusyTableDut` |

## 工作入口

- 设计规格：[docs/spec/design/wb_fu_busy_table.md](../../docs/spec/design/wb_fu_busy_table.md)
- 验证合同与计划：[docs/spec/verification/wb_fu_busy_table.md](../../docs/spec/verification/wb_fu_busy_table.md)
- 公开环境：[testbenches/wb_fu_busy_table/env.py](env.py)
- 用例与自检：[testbenches/wb_fu_busy_table/tests](tests)
- 实现职责：[testbenches/wb_fu_busy_table/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vec_region --dut wb_fu_busy_table
./scripts/ucv run vec_region --dut wb_fu_busy_table --collect-only --workers 1
./scripts/ucv run vec_region --dut wb_fu_busy_table --workers 1 -- testbenches/wb_fu_busy_table/tests/test_wb_fu_busy_table_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
