# l2tlb

独立性能诊断在 `tests/perf_trace.py`，需设置 `MMU_PERF_TRACE` 并显式选择
该文件运行；保持不进入默认回归集合。

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `l2tlb` | `L2TLB` | `L2TlbDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2tlb.md](../../docs/spec/verification/functional-points/functional-points-l2tlb.md) · [docs/spec/design/contracts/ptw-completion-contract.md](../../docs/spec/design/contracts/ptw-completion-contract.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2tlb-20261024.md](../../docs/spec/verification/evidence/reports/l2tlb-20261024.md)
- 公开环境：[testbenches/l2tlb/env/l2tlb.py](env/l2tlb.py)
- 用例与自检：[testbenches/l2tlb/tests](tests) · [testbenches/l2tlb/tests/test_l2tlb.py](tests/test_l2tlb.py)
- 实现职责：[testbenches/l2tlb/checker.py](checker.py) · [testbenches/l2tlb/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut l2tlb
./scripts/ucv run mmu --dut l2tlb --collect-only --workers 1
./scripts/ucv run mmu --dut l2tlb --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
