# llc_bridge

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `llc_bridge` | `OpenNCB` | `OpenNCBDut` |

## 工作入口

- 设计规格：[docs/spec/design/llc_bridge.md](../../docs/spec/design/llc_bridge.md)
- 验证合同与计划：[docs/spec/verification/llc_bridge.md](../../docs/spec/verification/llc_bridge.md)
- 公开环境：[testbenches/llc_bridge/env.py](env.py)
- 用例与自检：[testbenches/llc_bridge/tests](tests)
- 实现职责：[testbenches/llc_bridge/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ncb --dut llc_bridge
./scripts/ucv run ncb --dut llc_bridge --collect-only --workers 1
./scripts/ucv run ncb --dut llc_bridge --workers 1 -- testbenches/llc_bridge/tests/test_llc_bridge_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
