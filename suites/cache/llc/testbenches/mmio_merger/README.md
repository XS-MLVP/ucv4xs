# mmio_merger

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `mmio_merger` | `MMIOMerger` | `MmioMergerDut` |

## 工作入口

- 设计规格：[docs/spec/design/mmio_merger.md](../../docs/spec/design/mmio_merger.md)
- 验证合同与计划：[docs/spec/verification/mmio_merger.md](../../docs/spec/verification/mmio_merger.md)
- 公开环境：[testbenches/mmio_merger/env.py](env.py)
- 用例与自检：[testbenches/mmio_merger/tests](tests)
- 实现职责：[testbenches/mmio_merger/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut mmio_merger
./scripts/ucv run llc --dut mmio_merger --collect-only --workers 1
./scripts/ucv run llc --dut mmio_merger --workers 1 -- testbenches/mmio_merger/tests/test_mmio_merger_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
