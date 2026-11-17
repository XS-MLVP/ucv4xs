# mmio_core

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `mmio_core` | `NCB200_1` | `NCB200_1Dut` |

## 工作入口

- 设计规格：[docs/spec/design/mmio_core.md](../../docs/spec/design/mmio_core.md)
- 验证合同与计划：[docs/spec/verification/mmio_core.md](../../docs/spec/verification/mmio_core.md)
- 公开环境：[testbenches/mmio_core/env.py](env.py)
- 用例与自检：[testbenches/mmio_core/tests](tests)
- 实现职责：[testbenches/mmio_core/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ncb --dut mmio_core
./scripts/ucv run ncb --dut mmio_core --collect-only --workers 1
./scripts/ucv run ncb --dut mmio_core --workers 1 -- testbenches/mmio_core/tests/test_mmio_core_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
