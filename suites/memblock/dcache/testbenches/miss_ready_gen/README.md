# miss_ready_gen

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `miss_ready_gen` | `MissReadyGen` | `MissReadyGenDut` |

## 工作入口

- 设计规格：[docs/spec/design/functional-points-miss-ready-gen.md](../../docs/spec/design/functional-points-miss-ready-gen.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/miss-ready-gen-20261024.md](../../docs/spec/verification/evidence/miss-ready-gen-20261024.md)
- 公开环境：[testbenches/miss_ready_gen/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/miss_ready_gen/tests](tests)
- 实现职责：[testbenches/miss_ready_gen/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info dcache --dut miss_ready_gen
./scripts/ucv run dcache --dut miss_ready_gen --collect-only --workers 1
./scripts/ucv run dcache --dut miss_ready_gen --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
