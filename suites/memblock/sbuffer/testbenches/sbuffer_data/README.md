# sbuffer_data

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `sbuffer_data` | `SbufferData` | `SbufferDataDut` |

## 工作入口

- 设计规格：[docs/spec/design/functional-points-sbuffer-data.md](../../docs/spec/design/functional-points-sbuffer-data.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/sbuffer-data-20261024.md](../../docs/spec/verification/evidence/sbuffer-data-20261024.md)
- 公开环境：[testbenches/sbuffer_data/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/sbuffer_data/tests](tests)
- 实现职责：[testbenches/sbuffer_data/transactions.py](transactions.py) · [testbenches/sbuffer_data/model.py](model.py) · [testbenches/sbuffer_data/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info sbuffer --dut sbuffer_data
./scripts/ucv run sbuffer --dut sbuffer_data --collect-only --workers 1
./scripts/ucv run sbuffer --dut sbuffer_data --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
