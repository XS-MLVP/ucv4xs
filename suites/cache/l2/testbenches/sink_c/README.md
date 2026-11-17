# sink_c

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `sink_c` | `SinkC` | `SinkCDut` |

## 工作入口

- 设计规格：[docs/spec/design/sink_c.md](../../docs/spec/design/sink_c.md)
- 验证合同与计划：[docs/spec/verification/sink_c.md](../../docs/spec/verification/sink_c.md)
- 公开环境：[testbenches/sink_c/env.py](env.py)
- 用例与自检：[testbenches/sink_c/tests](tests)
- 实现职责：[testbenches/sink_c/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut sink_c
./scripts/ucv run l2 --dut sink_c --collect-only --workers 1
./scripts/ucv run l2 --dut sink_c --workers 1 -- testbenches/sink_c/tests/test_sink_c_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
