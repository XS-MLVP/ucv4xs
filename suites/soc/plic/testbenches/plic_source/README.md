# lazy_module

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `plic_source` | `LazyModule` | `LazyModuleDut` |

## 工作入口

- 设计规格：[docs/spec/design/plic_source.md](../../docs/spec/design/plic_source.md)
- 验证合同与计划：[docs/spec/verification/plic_source.md](../../docs/spec/verification/plic_source.md)
- 公开环境：[testbenches/plic_source/env.py](env.py)
- 用例与自检：[testbenches/plic_source/tests](tests)
- 实现职责：[testbenches/plic_source/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info plic --dut plic_source
./scripts/ucv run plic --dut plic_source --collect-only --workers 1
./scripts/ucv run plic --dut plic_source --workers 1 -- testbenches/plic_source/tests/test_lazy_module_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
