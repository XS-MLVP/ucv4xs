# chi_link_active_manager_rx

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `chi_link_active_manager_rx` | `CHILinkActiveManagerRX` | `ChiLinkActiveManagerRxDut` |

## 工作入口

- 设计规格：[docs/spec/design/chi_link_active_manager_rx.md](../../docs/spec/design/chi_link_active_manager_rx.md)
- 验证合同与计划：[docs/spec/verification/chi_link_active_manager_rx.md](../../docs/spec/verification/chi_link_active_manager_rx.md)
- 公开环境：[testbenches/chi_link_active_manager_rx/env.py](env.py)
- 用例与自检：[testbenches/chi_link_active_manager_rx/tests](tests)
- 实现职责：[testbenches/chi_link_active_manager_rx/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ncb --dut chi_link_active_manager_rx
./scripts/ucv run ncb --dut chi_link_active_manager_rx --collect-only --workers 1
./scripts/ucv run ncb --dut chi_link_active_manager_rx --workers 1 -- testbenches/chi_link_active_manager_rx/tests/test_chi_link_active_manager_rx_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
