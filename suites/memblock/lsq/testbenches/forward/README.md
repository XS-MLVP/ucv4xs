# forward

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `forward_module` | `ForwardModule` | `ForwardModuleDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/forward-module.md](../../docs/spec/design/contracts/forward-module.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](../lsq_wrapper/coverage/function_points.py)
- 公开环境：[testbenches/forward/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/forward/tests](tests) · [testbenches/forward/tests/test_alias_boundaries.py](tests/test_alias_boundaries.py) · [testbenches/forward/tests/test_basic.py](tests/test_basic.py) · [testbenches/forward/tests/test_github_gap_relationship.py](tests/test_github_gap_relationship.py) · [testbenches/forward/tests/test_pool_payload.py](tests/test_pool_payload.py) · [testbenches/forward/tests/test_prefix_byte_windows.py](tests/test_prefix_byte_windows.py) · [testbenches/forward/tests/test_semantics.py](tests/test_semantics.py) · [testbenches/forward/tests/test_independent_forward_property.py](tests/test_independent_forward_property.py)
- 实现职责：[testbenches/forward/transactions.py](transactions.py) · [testbenches/forward/model.py](model.py) · [testbenches/forward/checker.py](checker.py) · [testbenches/forward/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut forward_module
./scripts/ucv run lsq --dut forward_module --collect-only --workers 1
./scripts/ucv run lsq --dut forward_module --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
