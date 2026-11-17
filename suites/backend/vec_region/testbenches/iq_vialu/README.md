# iq_vialu

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `iq_vialu` | `IssueQueueVialu` | `IssueQueueVialuDut` |

## 工作入口

- 设计规格：[docs/spec/design/iq_vialu.md](../../docs/spec/design/iq_vialu.md)
- 验证合同与计划：[docs/spec/verification/iq_vialu.md](../../docs/spec/verification/iq_vialu.md)
- 公开环境：[testbenches/iq_vialu/env.py](env.py)
- 用例与自检：[testbenches/iq_vialu/tests](tests)
- 实现职责：[testbenches/iq_vialu/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vec_region --dut iq_vialu
./scripts/ucv run vec_region --dut iq_vialu --collect-only --workers 1
./scripts/ucv run vec_region --dut iq_vialu --workers 1 -- testbenches/iq_vialu/tests/test_iq_vialu_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
