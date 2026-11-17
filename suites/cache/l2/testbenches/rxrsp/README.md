# rxrsp

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `rxrsp` | `RXRSP` | `RxrspDut` |

## 工作入口

- 设计规格：[docs/spec/design/rxrsp.md](../../docs/spec/design/rxrsp.md)
- 验证合同与计划：[docs/spec/verification/rxrsp.md](../../docs/spec/verification/rxrsp.md)
- 公开环境：[testbenches/rxrsp/env.py](env.py)
- 用例与自检：[testbenches/rxrsp/tests](tests)
- 实现职责：[testbenches/rxrsp/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut rxrsp
./scripts/ucv run l2 --dut rxrsp --collect-only --workers 1
./scripts/ucv run l2 --dut rxrsp --workers 1 -- testbenches/rxrsp/tests/test_rxrsp_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
