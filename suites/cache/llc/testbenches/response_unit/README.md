# response_unit

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `response_unit` | `ResponseUnit` | `ResponseUnitDut` |

## 工作入口

- 设计规格：[docs/spec/design/response_unit.md](../../docs/spec/design/response_unit.md)
- 验证合同与计划：[docs/spec/verification/response_unit.md](../../docs/spec/verification/response_unit.md)
- 公开环境：[testbenches/response_unit/env.py](env.py)
- 用例与自检：[testbenches/response_unit/tests](tests)
- 实现职责：[testbenches/response_unit/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut response_unit
./scripts/ucv run llc --dut response_unit --collect-only --workers 1
./scripts/ucv run llc --dut response_unit --workers 1 -- testbenches/response_unit/tests/test_response_unit_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
