# mmio_diverger

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `mmio_diverger` | `MMIODiverger` | `MmioDivergerDut` |

## 工作入口

- 设计规格：[docs/spec/design/mmio_diverger.md](../../docs/spec/design/mmio_diverger.md)
- 验证合同与计划：[docs/spec/verification/mmio_diverger.md](../../docs/spec/verification/mmio_diverger.md)
- 公开环境：[testbenches/mmio_diverger/env.py](env.py)
- 用例与自检：[testbenches/mmio_diverger/tests](tests)
- 实现职责：[testbenches/mmio_diverger/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut mmio_diverger
./scripts/ucv run llc --dut mmio_diverger --collect-only --workers 1
./scripts/ucv run llc --dut mmio_diverger --workers 1 -- testbenches/mmio_diverger/tests/test_mmio_diverger_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
