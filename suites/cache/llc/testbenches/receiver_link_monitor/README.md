# receiver_link_monitor

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `receiver_link_monitor` | `ReceiverLinkMonitor` | `ReceiverLinkMonitorDut` |

## 工作入口

- 设计规格：[docs/spec/design/receiver_link_monitor.md](../../docs/spec/design/receiver_link_monitor.md)
- 验证合同与计划：[docs/spec/verification/receiver_link_monitor.md](../../docs/spec/verification/receiver_link_monitor.md)
- 公开环境：[testbenches/receiver_link_monitor/env.py](env.py)
- 用例与自检：[testbenches/receiver_link_monitor/tests](tests)
- 实现职责：[testbenches/receiver_link_monitor/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut receiver_link_monitor
./scripts/ucv run llc --dut receiver_link_monitor --collect-only --workers 1
./scripts/ucv run llc --dut receiver_link_monitor --workers 1 -- testbenches/receiver_link_monitor/tests/test_receiver_link_monitor_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
