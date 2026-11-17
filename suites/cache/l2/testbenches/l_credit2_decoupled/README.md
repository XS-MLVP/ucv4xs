# l_credit2_decoupled

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `l_credit2_decoupled` | `LCredit2Decoupled` | `LCredit2DecoupledDut` |

## 工作入口

- 设计规格：[docs/spec/design/l_credit2_decoupled.md](../../docs/spec/design/l_credit2_decoupled.md)
- 验证合同与计划：[docs/spec/verification/l_credit2_decoupled.md](../../docs/spec/verification/l_credit2_decoupled.md)
- 公开环境：[testbenches/l_credit2_decoupled/env.py](env.py)
- 用例与自检：[testbenches/l_credit2_decoupled/tests](tests)
- 实现职责：[testbenches/l_credit2_decoupled/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut l_credit2_decoupled
./scripts/ucv run l2 --dut l_credit2_decoupled --collect-only --workers 1
./scripts/ucv run l2 --dut l_credit2_decoupled --workers 1 -- testbenches/l_credit2_decoupled/tests/test_l_credit2_decoupled_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
