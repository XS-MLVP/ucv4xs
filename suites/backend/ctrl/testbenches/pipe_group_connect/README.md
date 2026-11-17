# pipe_group_connect

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `pipe_group_connect` | `PipeGroupConnect` | `PipeGroupConnectDut` |

## 工作入口

- 设计规格：[docs/spec/design/pipe_group_connect.md](../../docs/spec/design/pipe_group_connect.md)
- 验证合同与计划：[docs/spec/verification/pipe_group_connect.md](../../docs/spec/verification/pipe_group_connect.md)
- 公开环境：[testbenches/pipe_group_connect/env.py](env.py)
- 用例与自检：[testbenches/pipe_group_connect/tests](tests)
- 实现职责：[testbenches/pipe_group_connect/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut pipe_group_connect
./scripts/ucv run ctrl --dut pipe_group_connect --collect-only --workers 1
./scripts/ucv run ctrl --dut pipe_group_connect --workers 1 -- testbenches/pipe_group_connect/tests/test_pipe_group_connect_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
