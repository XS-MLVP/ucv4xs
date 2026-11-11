# dataarray

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `dataarray` | `ICacheDataArray` | `DataArrayDut` |

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/reports/baseline-update-a0c2a26cb.md](../../docs/spec/verification/reports/baseline-update-a0c2a26cb.md) · [docs/spec/verification/coverage/sram-dut-coverage-limitation.md](../../docs/spec/verification/coverage/sram-dut-coverage-limitation.md)
- 公开环境：[testbenches/dataarray/env/agent/main.py](env/agent/main.py)
- 用例与自检：[testbenches/dataarray/tests](tests)
- 实现职责：[testbenches/dataarray/transactions](transactions) · [testbenches/dataarray/model](model)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info icache --dut dataarray
./scripts/ucv run icache --dut dataarray --collect-only --workers 1
./scripts/ucv run icache --dut dataarray --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
