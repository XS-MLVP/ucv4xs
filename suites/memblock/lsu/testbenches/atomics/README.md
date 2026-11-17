# atomics

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `atomics` | `AtomicsUnit` | `AtomicsUnitDut` |

## 工作入口

- 设计规格：[docs/spec/design/atomics.md](../../docs/spec/design/atomics.md)
- 验证合同与计划：[docs/spec/verification/atomics.md](../../docs/spec/verification/atomics.md)
- 公开环境：[testbenches/atomics/env.py](env.py)
- 用例与自检：[testbenches/atomics/tests](tests)
- 实现职责：[testbenches/atomics/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsu --dut atomics
./scripts/ucv run lsu --dut atomics --collect-only --workers 1
./scripts/ucv run lsu --dut atomics --workers 1 -- testbenches/atomics/tests/test_atomics_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
