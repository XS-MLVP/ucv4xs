# axi4_id_indexer

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `axi4_id_indexer` | `AXI4IdIndexer` | `Axi4IdIndexerDut` |

## 工作入口

- 设计规格：[docs/spec/design/axi4_id_indexer.md](../../docs/spec/design/axi4_id_indexer.md)
- 验证合同与计划：[docs/spec/verification/axi4_id_indexer.md](../../docs/spec/verification/axi4_id_indexer.md)
- 公开环境：[testbenches/axi4_id_indexer/env.py](env.py)
- 用例与自检：[testbenches/axi4_id_indexer/tests](tests)
- 实现职责：[testbenches/axi4_id_indexer/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info peripheral --dut axi4_id_indexer
./scripts/ucv run peripheral --dut axi4_id_indexer --collect-only --workers 1
./scripts/ucv run peripheral --dut axi4_id_indexer --workers 1 -- testbenches/axi4_id_indexer/tests/test_axi4_id_indexer_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
