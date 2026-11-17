# sync_data_module_template_backend_pc_64_entry

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `sync_data_module_template_backend_pc_64_entry` | `SyncDataModuleTemplate_BackendPC_64entry` | `SyncDataModuleTemplateBackendPc64EntryDut` |

## 工作入口

- 设计规格：[docs/spec/design/sync_data_module_template_backend_pc_64_entry.md](../../docs/spec/design/sync_data_module_template_backend_pc_64_entry.md)
- 验证合同与计划：[docs/spec/verification/sync_data_module_template_backend_pc_64_entry.md](../../docs/spec/verification/sync_data_module_template_backend_pc_64_entry.md)
- 公开环境：[testbenches/sync_data_module_template_backend_pc_64_entry/env.py](env.py)
- 用例与自检：[testbenches/sync_data_module_template_backend_pc_64_entry/tests](tests)
- 实现职责：[testbenches/sync_data_module_template_backend_pc_64_entry/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut sync_data_module_template_backend_pc_64_entry
./scripts/ucv run ctrl --dut sync_data_module_template_backend_pc_64_entry --collect-only --workers 1
./scripts/ucv run ctrl --dut sync_data_module_template_backend_pc_64_entry --workers 1 -- testbenches/sync_data_module_template_backend_pc_64_entry/tests/test_sync_data_module_template_backend_pc_64_entry_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
