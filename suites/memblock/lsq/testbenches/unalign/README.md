# unalign

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `unalign_queue` | `UnalignQueue` | `UnalignQueueDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/unalign-queue.md](../../docs/spec/design/contracts/unalign-queue.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/unalign/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/unalign/tests](tests) · [testbenches/unalign/tests/test_basic.py](tests/test_basic.py) · [testbenches/unalign/tests/test_extended.py](tests/test_extended.py) · [testbenches/unalign/tests/test_page_pairs.py](tests/test_page_pairs.py)
- 实现职责：[testbenches/unalign/transactions.py](transactions.py) · [testbenches/unalign/model](model) · [testbenches/unalign/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut unalign_queue
./scripts/ucv run lsq --dut unalign_queue --collect-only --workers 1
./scripts/ucv run lsq --dut unalign_queue --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
