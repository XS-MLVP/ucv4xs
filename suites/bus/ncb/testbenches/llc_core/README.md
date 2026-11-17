# llc_core

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `llc_core` | `NCB200` | `NCB200Dut` |

## 工作入口

- 设计规格：[docs/spec/design/llc_core.md](../../docs/spec/design/llc_core.md)
- 验证合同与计划：[docs/spec/verification/llc_core.md](../../docs/spec/verification/llc_core.md)
- 公开环境：[testbenches/llc_core/env.py](env.py)
- 用例与自检：[testbenches/llc_core/tests](tests)
- 实现职责：[testbenches/llc_core/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ncb --dut llc_core
./scripts/ucv run ncb --dut llc_core --collect-only --workers 1
./scripts/ucv run ncb --dut llc_core --workers 1 -- testbenches/llc_core/tests/test_llc_core_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
