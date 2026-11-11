# new_store_unit

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `new_store_unit` | `NewStoreUnit` | `NewStoreUnitDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/new-store-unit.md](../../docs/spec/design/contracts/new-store-unit.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/gaps/new_store_unit.json](../../docs/spec/verification/gaps/new_store_unit.json)
- 公开环境：[testbenches/new_store_unit/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/new_store_unit/tests](tests)
- 实现职责：[testbenches/new_store_unit/transactions.py](transactions.py) · [testbenches/new_store_unit/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsu --dut new_store_unit
./scripts/ucv run lsu --dut new_store_unit --collect-only --workers 1
./scripts/ucv run lsu --dut new_store_unit --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
