# lsq_enq_ctrl

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `lsq_enq_ctrl` | `LsqEnqCtrl` | `LsqEnqCtrlDut` |

## 工作入口

- 设计规格：[docs/spec/design/lsq_enq_ctrl.md](../../docs/spec/design/lsq_enq_ctrl.md)
- 验证合同与计划：[docs/spec/verification/lsq_enq_ctrl.md](../../docs/spec/verification/lsq_enq_ctrl.md)
- 公开环境：[testbenches/lsq_enq_ctrl/env.py](env.py)
- 用例与自检：[testbenches/lsq_enq_ctrl/tests](tests)
- 实现职责：[testbenches/lsq_enq_ctrl/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut lsq_enq_ctrl
./scripts/ucv run ctrl --dut lsq_enq_ctrl --collect-only --workers 1
./scripts/ucv run ctrl --dut lsq_enq_ctrl --workers 1 -- testbenches/lsq_enq_ctrl/tests/test_lsq_enq_ctrl_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
