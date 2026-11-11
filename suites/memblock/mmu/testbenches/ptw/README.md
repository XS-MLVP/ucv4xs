# ptw

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ptw` | `PTW` | `PtwDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-midblocks.md](../../docs/spec/verification/functional-points/functional-points-l2-midblocks.md) · [docs/spec/design/contracts/ptw-completion-contract.md](../../docs/spec/design/contracts/ptw-completion-contract.md) · [docs/spec/design/contracts/implicit-gstage-mxr-contract.md](../../docs/spec/design/contracts/implicit-gstage-mxr-contract.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2-midblocks-20261024.md](../../docs/spec/verification/evidence/reports/l2-midblocks-20261024.md)
- 公开环境：[testbenches/ptw/env/ptw_walker.py](env/ptw_walker.py)
- 用例与自检：[testbenches/ptw/tests](tests) · [testbenches/ptw/tests/test_ptw.py](tests/test_ptw.py) · [testbenches/ptw/tests/test_ptw_identity.py](tests/test_ptw_identity.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut ptw
./scripts/ucv run mmu --dut ptw --collect-only --workers 1
./scripts/ucv run mmu --dut ptw --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
