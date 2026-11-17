# ncb_downstream_r

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ncb_downstream_r` | `NCBDownstreamR` | `NcbDownstreamRDut` |

## 工作入口

- 设计规格：[docs/spec/design/ncb_downstream_r.md](../../docs/spec/design/ncb_downstream_r.md)
- 验证合同与计划：[docs/spec/verification/ncb_downstream_r.md](../../docs/spec/verification/ncb_downstream_r.md)
- 公开环境：[testbenches/ncb_downstream_r/env.py](env.py)
- 用例与自检：[testbenches/ncb_downstream_r/tests](tests)
- 实现职责：[testbenches/ncb_downstream_r/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ncb --dut ncb_downstream_r
./scripts/ucv run ncb --dut ncb_downstream_r --collect-only --workers 1
./scripts/ucv run ncb --dut ncb_downstream_r --workers 1 -- testbenches/ncb_downstream_r/tests/test_ncb_downstream_r_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
