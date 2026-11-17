# ptwfilter_entry

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ptwfilter_entry` | `PTWFilterEntry` | `PtwfilterEntryDut` |

## 工作入口

- 设计规格：[docs/spec/design/ptwfilter_entry.md](../../docs/spec/design/ptwfilter_entry.md)
- 验证合同与计划：[docs/spec/verification/ptwfilter_entry.md](../../docs/spec/verification/ptwfilter_entry.md)
- 公开环境：[testbenches/ptwfilter_entry/env.py](env.py)
- 用例与自检：[testbenches/ptwfilter_entry/tests](tests)
- 实现职责：[testbenches/ptwfilter_entry/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut ptwfilter_entry
./scripts/ucv run mmu --dut ptwfilter_entry --collect-only --workers 1
./scripts/ucv run mmu --dut ptwfilter_entry --workers 1 -- testbenches/ptwfilter_entry/tests/test_ptwfilter_entry_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
