# ncb_upstream_rxdat

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ncb_upstream_rxdat` | `NCBUpstreamRXDAT` | `NcbUpstreamRxdatDut` |

## 工作入口

- 设计规格：[docs/spec/design/ncb_upstream_rxdat.md](../../docs/spec/design/ncb_upstream_rxdat.md)
- 验证合同与计划：[docs/spec/verification/ncb_upstream_rxdat.md](../../docs/spec/verification/ncb_upstream_rxdat.md)
- 公开环境：[testbenches/ncb_upstream_rxdat/env.py](env.py)
- 用例与自检：[testbenches/ncb_upstream_rxdat/tests](tests)
- 实现职责：[testbenches/ncb_upstream_rxdat/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ncb --dut ncb_upstream_rxdat
./scripts/ucv run ncb --dut ncb_upstream_rxdat --collect-only --workers 1
./scripts/ucv run ncb --dut ncb_upstream_rxdat --workers 1 -- testbenches/ncb_upstream_rxdat/tests/test_ncb_upstream_rxdat_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
