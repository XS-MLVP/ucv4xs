# freelist_raw

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `freelist_raw` | `FreeList_1` | `FreeListRawDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/freelist.md](../../docs/spec/design/contracts/freelist.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/freelist_raw/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/freelist_raw/tests](tests) · [testbenches/freelist_raw/tests/test_basic.py](tests/test_basic.py) · [testbenches/freelist_raw/tests/test_returns.py](tests/test_returns.py)
- 实现职责：[testbenches/freelist_raw/transactions.py](transactions.py) · [testbenches/freelist_raw/model.py](model.py) · [testbenches/freelist_raw/checker.py](checker.py) · [testbenches/freelist_raw/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut freelist_raw
./scripts/ucv run lsq --dut freelist_raw --collect-only --workers 1
./scripts/ucv run lsq --dut freelist_raw --workers 1 -- 'testbenches/freelist_raw/tests/test_basic.py::test_initial_pool_and_single_allocations[freelist_raw]'
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
