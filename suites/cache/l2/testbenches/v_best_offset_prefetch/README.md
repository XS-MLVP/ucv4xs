# v_best_offset_prefetch

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `v_best_offset_prefetch` | `VBestOffsetPrefetch` | `VBestOffsetPrefetchDut` |

## 工作入口

- 设计规格：[docs/spec/design/v_best_offset_prefetch.md](../../docs/spec/design/v_best_offset_prefetch.md)
- 验证合同与计划：[docs/spec/verification/v_best_offset_prefetch.md](../../docs/spec/verification/v_best_offset_prefetch.md)
- 公开环境：[testbenches/v_best_offset_prefetch/env.py](env.py)
- 用例与自检：[testbenches/v_best_offset_prefetch/tests](tests)
- 实现职责：[testbenches/v_best_offset_prefetch/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut v_best_offset_prefetch
./scripts/ucv run l2 --dut v_best_offset_prefetch --collect-only --workers 1
./scripts/ucv run l2 --dut v_best_offset_prefetch --workers 1 -- testbenches/v_best_offset_prefetch/tests/test_v_best_offset_prefetch_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
