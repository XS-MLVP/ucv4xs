# iq_alu_bku_vset

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `iq_alu_bku_vset` | `IssueQueueAluBkuVset` | `IssueQueueAluBkuVsetDut` |

## 工作入口

- 设计规格：[docs/spec/design/iq_alu_bku_vset.md](../../docs/spec/design/iq_alu_bku_vset.md)
- 验证合同与计划：[docs/spec/verification/iq_alu_bku_vset.md](../../docs/spec/verification/iq_alu_bku_vset.md)
- 公开环境：[testbenches/iq_alu_bku_vset/env.py](env.py)
- 用例与自检：[testbenches/iq_alu_bku_vset/tests](tests)
- 实现职责：[testbenches/iq_alu_bku_vset/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info int_region --dut iq_alu_bku_vset
./scripts/ucv run int_region --dut iq_alu_bku_vset --collect-only --workers 1
./scripts/ucv run int_region --dut iq_alu_bku_vset --workers 1 -- testbenches/iq_alu_bku_vset/tests/test_iq_alu_bku_vset_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
