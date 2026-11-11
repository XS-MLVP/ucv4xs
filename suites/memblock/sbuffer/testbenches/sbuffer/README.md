# sbuffer

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `sbuffer` | `Sbuffer` | `SbufferDut` |

## 工作入口

- 设计规格：[docs/spec/design/functional-points-sbuffer.md](../../docs/spec/design/functional-points-sbuffer.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/sbuffer-top-20261024.md](../../docs/spec/verification/evidence/sbuffer-top-20261024.md)
- 公开环境：[testbenches/sbuffer/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/sbuffer/tests](tests)
- 实现职责：[testbenches/sbuffer/transactions.py](transactions.py) · [testbenches/sbuffer/model.py](model.py) · [testbenches/sbuffer/checker.py](checker.py) · [testbenches/sbuffer/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info sbuffer --dut sbuffer
./scripts/ucv run sbuffer --dut sbuffer --collect-only --workers 1
./scripts/ucv run sbuffer --dut sbuffer --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
