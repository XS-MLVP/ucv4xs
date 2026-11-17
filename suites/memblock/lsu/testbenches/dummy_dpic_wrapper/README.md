# dummy_dpic_wrapper

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `dummy_dpic_wrapper` | `DummyDPICWrapper_LrScEvent` | `DummyDpicWrapperDut` |

## 工作入口

- 设计规格：[docs/spec/design/dummy_dpic_wrapper.md](../../docs/spec/design/dummy_dpic_wrapper.md)
- 验证合同与计划：[docs/spec/verification/dummy_dpic_wrapper.md](../../docs/spec/verification/dummy_dpic_wrapper.md)
- 公开环境：[testbenches/dummy_dpic_wrapper/env.py](env.py)
- 用例与自检：[testbenches/dummy_dpic_wrapper/tests](tests)
- 实现职责：[testbenches/dummy_dpic_wrapper/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsu --dut dummy_dpic_wrapper
./scripts/ucv run lsu --dut dummy_dpic_wrapper --collect-only --workers 1
./scripts/ucv run lsu --dut dummy_dpic_wrapper --workers 1 -- testbenches/dummy_dpic_wrapper/tests/test_dummy_dpic_wrapper_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
