# decode_stage

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `decode_stage` | `DecodeStage` | `DecodeStageDut` |

## 工作入口

- 设计规格：[docs/spec/design/decode_stage.md](../../docs/spec/design/decode_stage.md)
- 验证合同与计划：[docs/spec/verification/decode_stage.md](../../docs/spec/verification/decode_stage.md)
- 公开环境：[testbenches/decode_stage/env.py](env.py)
- 用例与自检：[testbenches/decode_stage/tests](tests)
- 实现职责：[testbenches/decode_stage/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut decode_stage
./scripts/ucv run ctrl --dut decode_stage --collect-only --workers 1
./scripts/ucv run ctrl --dut decode_stage --workers 1 -- testbenches/decode_stage/tests/test_decode_stage_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
