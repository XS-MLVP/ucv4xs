# gpa_mem

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `gpa_mem` | `GPAMem` | `GpaMemDut` |

## 工作入口

- 设计规格：[docs/spec/design/gpa_mem.md](../../docs/spec/design/gpa_mem.md)
- 验证合同与计划：[docs/spec/verification/gpa_mem.md](../../docs/spec/verification/gpa_mem.md)
- 公开环境：[testbenches/gpa_mem/env.py](env.py)
- 用例与自检：[testbenches/gpa_mem/tests](tests)
- 实现职责：[testbenches/gpa_mem/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut gpa_mem
./scripts/ucv run ctrl --dut gpa_mem --collect-only --workers 1
./scripts/ucv run ctrl --dut gpa_mem --workers 1 -- testbenches/gpa_mem/tests/test_gpa_mem_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
