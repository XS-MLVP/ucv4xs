# tlfifo_fixer

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `tlfifo_fixer` | `TLFIFOFixer` | `TlfifoFixerDut` |

## 工作入口

- 设计规格：[docs/spec/design/tlfifo_fixer.md](../../docs/spec/design/tlfifo_fixer.md)
- 验证合同与计划：[docs/spec/verification/tlfifo_fixer.md](../../docs/spec/verification/tlfifo_fixer.md)
- 公开环境：[testbenches/tlfifo_fixer/env.py](env.py)
- 用例与自检：[testbenches/tlfifo_fixer/tests](tests)
- 实现职责：[testbenches/tlfifo_fixer/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info peripheral --dut tlfifo_fixer
./scripts/ucv run peripheral --dut tlfifo_fixer --collect-only --workers 1
./scripts/ucv run peripheral --dut tlfifo_fixer --workers 1 -- testbenches/tlfifo_fixer/tests/test_tlfifo_fixer_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
