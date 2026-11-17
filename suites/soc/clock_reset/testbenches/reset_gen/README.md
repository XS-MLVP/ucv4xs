# reset_gen

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `reset_gen` | `ResetGen` | `ResetGenDut` |

## 工作入口

- 设计规格：[docs/spec/design/reset_gen.md](../../docs/spec/design/reset_gen.md)
- 验证合同与计划：[docs/spec/verification/reset_gen.md](../../docs/spec/verification/reset_gen.md)
- 公开环境：[testbenches/reset_gen/env.py](env.py)
- 用例与自检：[testbenches/reset_gen/tests](tests)
- 实现职责：[testbenches/reset_gen/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info clock_reset --dut reset_gen
./scripts/ucv run clock_reset --dut reset_gen --collect-only --workers 1
./scripts/ucv run clock_reset --dut reset_gen --workers 1 -- testbenches/reset_gen/tests/test_reset_gen_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
