# select_oldest

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `select_oldest` | `SelectOldest` | `SelectOldestDut` |

## 工作入口

- 设计规格：[docs/spec/design/select_oldest.md](../../docs/spec/design/select_oldest.md)
- 验证合同与计划：[docs/spec/verification/select_oldest.md](../../docs/spec/verification/select_oldest.md)
- 公开环境：[testbenches/select_oldest/env.py](env.py)
- 用例与自检：[testbenches/select_oldest/tests](tests)
- 实现职责：[testbenches/select_oldest/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsu --dut select_oldest
./scripts/ucv run lsu --dut select_oldest --collect-only --workers 1
./scripts/ucv run lsu --dut select_oldest --workers 1 -- testbenches/select_oldest/tests/test_select_oldest_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
