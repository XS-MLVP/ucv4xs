# uras

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `uras` | `MicroRas` | `UrasDut` |

## 工作入口

- 设计规格：[docs/spec/design/uras.md](../../docs/spec/design/uras.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md) · [docs/spec/design/module-behavior-matrix.md](../../docs/spec/design/module-behavior-matrix.md) · [docs/spec/design/scala-interactions-20261106.md](../../docs/spec/design/scala-interactions-20261106.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/contracts/owned-return-stack-contract-20261020.json](../../docs/spec/verification/contracts/owned-return-stack-contract-20261020.json) · [docs/spec/verification/coverage/behavior-coverage-design.json](../../docs/spec/verification/coverage/behavior-coverage-design.json) · [docs/spec/verification/evidence/module-reviews/uras-module-review-20261029.md](../../docs/spec/verification/evidence/module-reviews/uras-module-review-20261029.md)
- 公开环境：[testbenches/uras/env/agent/main.py](env/agent/main.py)
- 用例与自检：[testbenches/uras/tests](tests)
- 实现职责：[testbenches/uras/transactions](transactions) · [testbenches/uras/model](model) · [testbenches/uras/checker](checker) · [testbenches/uras/coverage](coverage)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info bpu --dut uras
./scripts/ucv run bpu --dut uras --collect-only --workers 1
./scripts/ucv run bpu --dut uras --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
