# level_gateway

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `level_gateway` | `LevelGateway` | `LevelGatewayDut` |

## 工作入口

- 设计规格：[docs/spec/design/level_gateway.md](../../docs/spec/design/level_gateway.md)
- 验证合同与计划：[docs/spec/verification/level_gateway.md](../../docs/spec/verification/level_gateway.md)
- 公开环境：[testbenches/level_gateway/env.py](env.py)
- 用例与自检：[testbenches/level_gateway/tests](tests)
- 实现职责：[testbenches/level_gateway/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info plic --dut level_gateway
./scripts/ucv run plic --dut level_gateway --collect-only --workers 1
./scripts/ucv run plic --dut level_gateway --workers 1 -- testbenches/level_gateway/tests/test_level_gateway_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
