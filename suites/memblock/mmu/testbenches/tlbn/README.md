# tlbn

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `tlbn` | `TLBNonBlock` | `TlbNonBlockDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-tlbn.md](../../docs/spec/verification/functional-points/functional-points-tlbn.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/tlbn-20261025.md](../../docs/spec/verification/evidence/reports/tlbn-20261025.md)
- 公开环境：[testbenches/tlbn/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/tlbn/tests](tests) · [testbenches/tlbn/tests/test_tlbn.py](tests/test_tlbn.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut tlbn
./scripts/ucv run mmu --dut tlbn --collect-only --workers 1
./scripts/ucv run mmu --dut tlbn --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
