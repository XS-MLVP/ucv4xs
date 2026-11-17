# chi_logger

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `chi_logger` | `CHILogger` | `ChiLoggerDut` |

## 工作入口

- 设计规格：[docs/spec/design/chi_logger.md](../../docs/spec/design/chi_logger.md)
- 验证合同与计划：[docs/spec/verification/chi_logger.md](../../docs/spec/verification/chi_logger.md)
- 公开环境：[testbenches/chi_logger/env.py](env.py)
- 用例与自检：[testbenches/chi_logger/tests](tests)
- 实现职责：[testbenches/chi_logger/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut chi_logger
./scripts/ucv run llc --dut chi_logger --collect-only --workers 1
./scripts/ucv run llc --dut chi_logger --workers 1 -- testbenches/chi_logger/tests/test_chi_logger_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
