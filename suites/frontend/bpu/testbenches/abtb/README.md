# abtb

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `abtb` | `AheadBtb` | `AbtbDut` |

## 工作入口

- 设计规格：[docs/spec/design/abtb.md](../../docs/spec/design/abtb.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md) · [docs/spec/design/module-behavior-matrix.md](../../docs/spec/design/module-behavior-matrix.md) · [docs/spec/design/scala-interactions-20261106.md](../../docs/spec/design/scala-interactions-20261106.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/coverage/behavior-coverage-design.json](../../docs/spec/verification/coverage/behavior-coverage-design.json) · [docs/spec/verification/evidence/module-reviews/abtb-module-review-20261030.md](../../docs/spec/verification/evidence/module-reviews/abtb-module-review-20261030.md)
- 公开环境：[testbenches/abtb/env/agent/main.py](env/agent/main.py)
- 用例与自检：[testbenches/abtb/tests](tests)
- 实现职责：[testbenches/abtb/transactions](transactions) · [testbenches/abtb/model](model) · [testbenches/abtb/checker](checker) · [testbenches/abtb/coverage](coverage)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info bpu --dut abtb
./scripts/ucv run bpu --dut abtb --collect-only --workers 1
./scripts/ucv run bpu --dut abtb --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
