# coupled_l2

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `coupled_l2` | `CoupledL2` | `CoupledL2Dut` |

## 工作入口

- 设计规格：[docs/spec/design/coupled_l2.md](../../docs/spec/design/coupled_l2.md)
- 验证合同与计划：[docs/spec/verification/coupled_l2.md](../../docs/spec/verification/coupled_l2.md)
- 公开环境：[testbenches/coupled_l2/env.py](env.py)
- 用例与自检：[testbenches/coupled_l2/tests](tests)
- 实现职责：[testbenches/coupled_l2/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut coupled_l2
./scripts/ucv run l2 --dut coupled_l2 --collect-only --workers 1
./scripts/ucv run l2 --dut coupled_l2 --workers 1 -- testbenches/coupled_l2/tests/test_coupled_l2_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
