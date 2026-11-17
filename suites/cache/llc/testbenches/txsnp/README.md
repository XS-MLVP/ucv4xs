# txsnp

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `txsnp` | `TXSNP` | `TxsnpDut` |

## 工作入口

- 设计规格：[docs/spec/design/txsnp.md](../../docs/spec/design/txsnp.md)
- 验证合同与计划：[docs/spec/verification/txsnp.md](../../docs/spec/verification/txsnp.md)
- 公开环境：[testbenches/txsnp/env.py](env.py)
- 用例与自检：[testbenches/txsnp/tests](tests)
- 实现职责：[testbenches/txsnp/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut txsnp
./scripts/ucv run llc --dut txsnp --collect-only --workers 1
./scripts/ucv run llc --dut txsnp --workers 1 -- testbenches/txsnp/tests/test_txsnp_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
