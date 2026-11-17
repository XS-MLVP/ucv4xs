# axi4_deinterleaver

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `axi4_deinterleaver` | `AXI4Deinterleaver` | `Axi4DeinterleaverDut` |

## 工作入口

- 设计规格：[docs/spec/design/axi4_deinterleaver.md](../../docs/spec/design/axi4_deinterleaver.md)
- 验证合同与计划：[docs/spec/verification/axi4_deinterleaver.md](../../docs/spec/verification/axi4_deinterleaver.md)
- 公开环境：[testbenches/axi4_deinterleaver/env.py](env.py)
- 用例与自检：[testbenches/axi4_deinterleaver/tests](tests)
- 实现职责：[testbenches/axi4_deinterleaver/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info peripheral --dut axi4_deinterleaver
./scripts/ucv run peripheral --dut axi4_deinterleaver --collect-only --workers 1
./scripts/ucv run peripheral --dut axi4_deinterleaver --workers 1 -- testbenches/axi4_deinterleaver/tests/test_axi4_deinterleaver_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
