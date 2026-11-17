# mmio_bridge_entry

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `mmio_bridge_entry` | `MMIOBridgeEntry` | `MmioBridgeEntryDut` |

## 工作入口

- 设计规格：[docs/spec/design/mmio_bridge_entry.md](../../docs/spec/design/mmio_bridge_entry.md)
- 验证合同与计划：[docs/spec/verification/mmio_bridge_entry.md](../../docs/spec/verification/mmio_bridge_entry.md)
- 公开环境：[testbenches/mmio_bridge_entry/env.py](env.py)
- 用例与自检：[testbenches/mmio_bridge_entry/tests](tests)
- 实现职责：[testbenches/mmio_bridge_entry/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut mmio_bridge_entry
./scripts/ucv run l2 --dut mmio_bridge_entry --collect-only --workers 1
./scripts/ucv run l2 --dut mmio_bridge_entry --workers 1 -- testbenches/mmio_bridge_entry/tests/test_mmio_bridge_entry_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
