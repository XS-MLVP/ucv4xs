# exu_block

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `exu_block` | `ExuBlock` | `ExuBlockDut` |

## 工作入口

- 设计规格：[docs/spec/design/exu_block.md](../../docs/spec/design/exu_block.md)
- 验证合同与计划：[docs/spec/verification/exu_block.md](../../docs/spec/verification/exu_block.md)
- 公开环境：[testbenches/exu_block/env.py](env.py)
- 用例与自检：[testbenches/exu_block/tests](tests)
- 实现职责：[testbenches/exu_block/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info int_region --dut exu_block
./scripts/ucv run int_region --dut exu_block --collect-only --workers 1
./scripts/ucv run int_region --dut exu_block --workers 1 -- testbenches/exu_block/tests/test_exu_block_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
