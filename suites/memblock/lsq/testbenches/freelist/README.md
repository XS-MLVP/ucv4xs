# freelist

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `freelist_rar` | `FreeList` | `FreeListRarDut` |
| `freelist_raw` | `FreeList_1` | `FreeListRawDut` |
| `freelist_replay` | `FreeList_2` | `FreeListReplayDut` |
| `freelist_uncache` | `FreeList_3` | `FreeListUncacheDut` |

这些 DUT 显式共用参数化实现；运行共享用例时选择其实际需要的全部 DUT。

## 工作入口

- 设计规格：[docs/spec/design/contracts/freelist.md](../../docs/spec/design/contracts/freelist.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/freelist/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/freelist/tests](tests) · [testbenches/freelist/tests/test_basic.py](tests/test_basic.py) · [testbenches/freelist/tests/test_returns.py](tests/test_returns.py)
- 实现职责：[testbenches/freelist/transactions.py](transactions.py) · [testbenches/freelist/model.py](model.py) · [testbenches/freelist/checker.py](checker.py) · [testbenches/freelist/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut freelist_rar --dut freelist_raw --dut freelist_replay --dut freelist_uncache
./scripts/ucv run lsq --dut freelist_rar --dut freelist_raw --dut freelist_replay --dut freelist_uncache --collect-only --workers 1
./scripts/ucv run lsq --dut freelist_rar --dut freelist_raw --dut freelist_replay --dut freelist_uncache --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
