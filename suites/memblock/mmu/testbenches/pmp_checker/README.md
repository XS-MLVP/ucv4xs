# pmp_checker

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `pmp_checker` | `PMPChecker` | `PmpCheckerDut` |

## 工作入口

- 设计规格：[docs/spec/design/pmp_checker.md](../../docs/spec/design/pmp_checker.md)
- 验证合同与计划：[docs/spec/verification/pmp_checker.md](../../docs/spec/verification/pmp_checker.md)
- 公开环境：[testbenches/pmp_checker/env.py](env.py)
- 用例与自检：[testbenches/pmp_checker/tests](tests)
- 实现职责：[testbenches/pmp_checker/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut pmp_checker
./scripts/ucv run mmu --dut pmp_checker --collect-only --workers 1
./scripts/ucv run mmu --dut pmp_checker --workers 1 -- testbenches/pmp_checker/tests/test_pmp_checker_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
