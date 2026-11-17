# open_llc

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `open_llc` | `OpenLLC` | `OpenLLCDut` |

## 工作入口

- 设计规格：[docs/spec/design/open_llc.md](../../docs/spec/design/open_llc.md)
- 验证合同与计划：[docs/spec/verification/open_llc.md](../../docs/spec/verification/open_llc.md)
- 公开环境：[testbenches/open_llc/env.py](env.py)
- 用例与自检：[testbenches/open_llc/tests](tests)
- 实现职责：[testbenches/open_llc/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut open_llc
./scripts/ucv run llc --dut open_llc --collect-only --workers 1
./scripts/ucv run llc --dut open_llc --workers 1 -- testbenches/open_llc/tests/test_open_llc_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
