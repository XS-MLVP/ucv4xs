# uncache_entry

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `uncache_entry_0` | `UncacheEntry` | `UncacheEntry0Dut` |
| `uncache_entry_1` | `UncacheEntry_1` | `UncacheEntry1Dut` |
| `uncache_entry_2` | `UncacheEntry_2` | `UncacheEntry2Dut` |
| `uncache_entry_3` | `UncacheEntry_3` | `UncacheEntry3Dut` |
| `uncache_entry_4` | `UncacheEntry_4` | `UncacheEntry4Dut` |
| `uncache_entry_5` | `UncacheEntry_5` | `UncacheEntry5Dut` |
| `uncache_entry_6` | `UncacheEntry_6` | `UncacheEntry6Dut` |
| `uncache_entry_7` | `UncacheEntry_7` | `UncacheEntry7Dut` |
| `uncache_entry_8` | `UncacheEntry_8` | `UncacheEntry8Dut` |
| `uncache_entry_9` | `UncacheEntry_9` | `UncacheEntry9Dut` |
| `uncache_entry_10` | `UncacheEntry_10` | `UncacheEntry10Dut` |
| `uncache_entry_11` | `UncacheEntry_11` | `UncacheEntry11Dut` |
| `uncache_entry_12` | `UncacheEntry_12` | `UncacheEntry12Dut` |
| `uncache_entry_13` | `UncacheEntry_13` | `UncacheEntry13Dut` |
| `uncache_entry_14` | `UncacheEntry_14` | `UncacheEntry14Dut` |
| `uncache_entry_15` | `UncacheEntry_15` | `UncacheEntry15Dut` |

这些 DUT 显式共用参数化实现；运行共享用例时选择其实际需要的全部 DUT。

## 工作入口

- 设计规格：[docs/spec/design/contracts/uncache-entry.md](../../docs/spec/design/contracts/uncache-entry.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/uncache_entry/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/uncache_entry/tests](tests) · [testbenches/uncache_entry/tests/test_basic.py](tests/test_basic.py) · [testbenches/uncache_entry/tests/test_extended.py](tests/test_extended.py) · [testbenches/uncache_entry/tests/test_toggle_gap_closure.py](tests/test_toggle_gap_closure.py)
- 实现职责：[testbenches/uncache_entry/transactions.py](transactions.py) · [testbenches/uncache_entry/model.py](model.py) · [testbenches/uncache_entry/checker.py](checker.py) · [testbenches/uncache_entry/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut uncache_entry_0 --dut uncache_entry_1 --dut uncache_entry_2 --dut uncache_entry_3 --dut uncache_entry_4 --dut uncache_entry_5 --dut uncache_entry_6 --dut uncache_entry_7 --dut uncache_entry_8 --dut uncache_entry_9 --dut uncache_entry_10 --dut uncache_entry_11 --dut uncache_entry_12 --dut uncache_entry_13 --dut uncache_entry_14 --dut uncache_entry_15
./scripts/ucv run lsq --dut uncache_entry_0 --dut uncache_entry_1 --dut uncache_entry_2 --dut uncache_entry_3 --dut uncache_entry_4 --dut uncache_entry_5 --dut uncache_entry_6 --dut uncache_entry_7 --dut uncache_entry_8 --dut uncache_entry_9 --dut uncache_entry_10 --dut uncache_entry_11 --dut uncache_entry_12 --dut uncache_entry_13 --dut uncache_entry_14 --dut uncache_entry_15 --collect-only --workers 1
./scripts/ucv run lsq --dut uncache_entry_0 --dut uncache_entry_1 --dut uncache_entry_2 --dut uncache_entry_3 --dut uncache_entry_4 --dut uncache_entry_5 --dut uncache_entry_6 --dut uncache_entry_7 --dut uncache_entry_8 --dut uncache_entry_9 --dut uncache_entry_10 --dut uncache_entry_11 --dut uncache_entry_12 --dut uncache_entry_13 --dut uncache_entry_14 --dut uncache_entry_15 --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
