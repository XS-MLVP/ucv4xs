# llptw

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `llptw` | `LLPTW` | `LlptwDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-midblocks.md](../../docs/spec/verification/functional-points/functional-points-l2-midblocks.md) · [docs/spec/design/contracts/ptw-completion-contract.md](../../docs/spec/design/contracts/ptw-completion-contract.md) · [docs/spec/design/contracts/implicit-gstage-mxr-contract.md](../../docs/spec/design/contracts/implicit-gstage-mxr-contract.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/llptw-20261025.md](../../docs/spec/verification/evidence/reports/llptw-20261025.md)
- 公开环境：[testbenches/llptw/env/llptw.py](env/llptw.py)
- 用例与自检：[testbenches/llptw/tests](tests) · [testbenches/llptw/tests/test_llptw.py](tests/test_llptw.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut llptw
./scripts/ucv run mmu --dut llptw --collect-only --workers 1
./scripts/ucv run mmu --dut llptw --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
