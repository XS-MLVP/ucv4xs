# aplic

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `aplic` | `APLIC` | `AplicDut` |

## 工作入口

- 设计规格：[docs/spec/design/aplic.md](../../docs/spec/design/aplic.md)
- 验证合同与计划：[docs/spec/verification/aplic.md](../../docs/spec/verification/aplic.md)
- 公开环境：[testbenches/aplic/env.py](env.py)
- 用例与自检：[testbenches/aplic/tests](tests)
- 实现职责：[testbenches/aplic/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info aia --dut aplic
./scripts/ucv run aia --dut aplic --collect-only --workers 1
./scripts/ucv run aia --dut aplic --workers 1 -- testbenches/aplic/tests/test_aplic_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
