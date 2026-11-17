# rxreq

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `rxreq` | `RXREQ` | `RxreqDut` |

## 工作入口

- 设计规格：[docs/spec/design/rxreq.md](../../docs/spec/design/rxreq.md)
- 验证合同与计划：[docs/spec/verification/rxreq.md](../../docs/spec/verification/rxreq.md)
- 公开环境：[testbenches/rxreq/env.py](env.py)
- 用例与自检：[testbenches/rxreq/tests](tests)
- 实现职责：[testbenches/rxreq/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut rxreq
./scripts/ucv run llc --dut rxreq --collect-only --workers 1
./scripts/ucv run llc --dut rxreq --workers 1 -- testbenches/rxreq/tests/test_rxreq_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
