# dtlb_store

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `dtlb_store` | `TLB_2` | `TLB_2Dut` |

## 工作入口

- 设计规格：[docs/spec/design/dtlb_store.md](../../docs/spec/design/dtlb_store.md)
- 验证合同与计划：[docs/spec/verification/dtlb_store.md](../../docs/spec/verification/dtlb_store.md)
- 公开环境：[testbenches/dtlb_store/env.py](env.py)
- 用例与自检：[testbenches/dtlb_store/tests](tests)
- 实现职责：[testbenches/dtlb_store/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut dtlb_store
./scripts/ucv run mmu --dut dtlb_store --collect-only --workers 1
./scripts/ucv run mmu --dut dtlb_store --workers 1 -- testbenches/dtlb_store/tests/test_dtlb_store_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
