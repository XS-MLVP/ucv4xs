# fusion_decoder

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `fusion_decoder` | `FusionDecoder` | `FusionDecoderDut` |

## 工作入口

- 设计规格：[docs/spec/design/fusion_decoder.md](../../docs/spec/design/fusion_decoder.md)
- 验证合同与计划：[docs/spec/verification/fusion_decoder.md](../../docs/spec/verification/fusion_decoder.md)
- 公开环境：[testbenches/fusion_decoder/env.py](env.py)
- 用例与自检：[testbenches/fusion_decoder/tests](tests)
- 实现职责：[testbenches/fusion_decoder/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut fusion_decoder
./scripts/ucv run ctrl --dut fusion_decoder --collect-only --workers 1
./scripts/ucv run ctrl --dut fusion_decoder --workers 1 -- testbenches/fusion_decoder/tests/test_fusion_decoder_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
