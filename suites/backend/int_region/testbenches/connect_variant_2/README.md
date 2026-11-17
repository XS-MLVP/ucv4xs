# connect_variant_2

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `connect_variant_2` | `NewPipelineConnectPipe_2` | `NewPipelineConnectPipe_2Dut` |

## 工作入口

- 设计规格：[docs/spec/design/connect_variant_2.md](../../docs/spec/design/connect_variant_2.md)
- 验证合同与计划：[docs/spec/verification/connect_variant_2.md](../../docs/spec/verification/connect_variant_2.md)
- 公开环境：[testbenches/connect_variant_2/env.py](env.py)
- 用例与自检：[testbenches/connect_variant_2/tests](tests)
- 实现职责：[testbenches/connect_variant_2/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info int_region --dut connect_variant_2
./scripts/ucv run int_region --dut connect_variant_2 --collect-only --workers 1
./scripts/ucv run int_region --dut connect_variant_2 --workers 1 -- testbenches/connect_variant_2/tests/test_connect_variant_2_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
