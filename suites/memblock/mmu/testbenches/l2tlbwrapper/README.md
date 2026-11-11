# l2tlbwrapper

独立性能诊断在 `tests/perf_trace.py`，需设置 `MMU_PERF_TRACE` 并显式选择
该文件运行；保持不进入默认回归集合。

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `l2tlbwrapper` | `L2TLBWrapper` | `L2TlbWrapperDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2tlbwrapper.md](../../docs/spec/verification/functional-points/functional-points-l2tlbwrapper.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2tlbwrapper-20261025.md](../../docs/spec/verification/evidence/reports/l2tlbwrapper-20261025.md)
- 公开环境：[testbenches/l2tlbwrapper/env/l2tlbwrapper.py](env/l2tlbwrapper.py)
- 用例与自检：[testbenches/l2tlbwrapper/tests](tests) · [testbenches/l2tlbwrapper/tests/test_l2tlbwrapper.py](tests/test_l2tlbwrapper.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut l2tlbwrapper
./scripts/ucv run mmu --dut l2tlbwrapper --collect-only --workers 1
./scripts/ucv run mmu --dut l2tlbwrapper --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
