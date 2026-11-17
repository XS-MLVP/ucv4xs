# txrsp

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `txrsp` | `TXRSP` | `TxrspDut` |

## 工作入口

- 设计规格：[docs/spec/design/txrsp.md](../../docs/spec/design/txrsp.md)
- 验证合同与计划：[docs/spec/verification/txrsp.md](../../docs/spec/verification/txrsp.md)
- 公开环境：[testbenches/txrsp/env.py](env.py)
- 用例与自检：[testbenches/txrsp/tests](tests)
- 实现职责：[testbenches/txrsp/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut txrsp
./scripts/ucv run l2 --dut txrsp --collect-only --workers 1
./scripts/ucv run l2 --dut txrsp --workers 1 -- testbenches/txrsp/tests/test_txrsp_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
