# rxdat

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `rxdat` | `RXDAT` | `RxdatDut` |

## 工作入口

- 设计规格：[docs/spec/design/rxdat.md](../../docs/spec/design/rxdat.md)
- 验证合同与计划：[docs/spec/verification/rxdat.md](../../docs/spec/verification/rxdat.md)
- 公开环境：[testbenches/rxdat/env.py](env.py)
- 用例与自检：[testbenches/rxdat/tests](tests)
- 实现职责：[testbenches/rxdat/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut rxdat
./scripts/ucv run l2 --dut rxdat --collect-only --workers 1
./scripts/ucv run l2 --dut rxdat --workers 1 -- testbenches/rxdat/tests/test_rxdat_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
