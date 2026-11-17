# rxsnp

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `rxsnp` | `RXSNP` | `RxsnpDut` |

## 工作入口

- 设计规格：[docs/spec/design/rxsnp.md](../../docs/spec/design/rxsnp.md)
- 验证合同与计划：[docs/spec/verification/rxsnp.md](../../docs/spec/verification/rxsnp.md)
- 公开环境：[testbenches/rxsnp/env.py](env.py)
- 用例与自检：[testbenches/rxsnp/tests](tests)
- 实现职责：[testbenches/rxsnp/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut rxsnp
./scripts/ucv run l2 --dut rxsnp --collect-only --workers 1
./scripts/ucv run l2 --dut rxsnp --workers 1 -- testbenches/rxsnp/tests/test_rxsnp_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
