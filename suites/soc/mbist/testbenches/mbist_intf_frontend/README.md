# mbist_intf_frontend

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `mbist_intf_frontend` | `MbistIntfFrontend` | `MbistIntfFrontendDut` |

## 工作入口

- 设计规格：[docs/spec/design/mbist_intf_frontend.md](../../docs/spec/design/mbist_intf_frontend.md)
- 验证合同与计划：[docs/spec/verification/mbist_intf_frontend.md](../../docs/spec/verification/mbist_intf_frontend.md)
- 公开环境：[testbenches/mbist_intf_frontend/env.py](env.py)
- 用例与自检：[testbenches/mbist_intf_frontend/tests](tests)
- 实现职责：[testbenches/mbist_intf_frontend/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mbist --dut mbist_intf_frontend
./scripts/ucv run mbist --dut mbist_intf_frontend --collect-only --workers 1
./scripts/ucv run mbist --dut mbist_intf_frontend --workers 1 -- testbenches/mbist_intf_frontend/tests/test_mbist_intf_frontend_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
