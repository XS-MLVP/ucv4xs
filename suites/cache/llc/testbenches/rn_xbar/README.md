# rn_xbar

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `rn_xbar` | `RNXbar` | `RnXbarDut` |

## 工作入口

- 设计规格：[docs/spec/design/rn_xbar.md](../../docs/spec/design/rn_xbar.md)
- 验证合同与计划：[docs/spec/verification/rn_xbar.md](../../docs/spec/verification/rn_xbar.md)
- 公开环境：[testbenches/rn_xbar/env.py](env.py)
- 用例与自检：[testbenches/rn_xbar/tests](tests)
- 实现职责：[testbenches/rn_xbar/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut rn_xbar
./scripts/ucv run llc --dut rn_xbar --collect-only --workers 1
./scripts/ucv run llc --dut rn_xbar --workers 1 -- testbenches/rn_xbar/tests/test_rn_xbar_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
