# redirect_generator

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `redirect_generator` | `RedirectGenerator` | `RedirectGeneratorDut` |

## 工作入口

- 设计规格：[docs/spec/design/redirect_generator.md](../../docs/spec/design/redirect_generator.md)
- 验证合同与计划：[docs/spec/verification/redirect_generator.md](../../docs/spec/verification/redirect_generator.md)
- 公开环境：[testbenches/redirect_generator/env.py](env.py)
- 用例与自检：[testbenches/redirect_generator/tests](tests)
- 实现职责：[testbenches/redirect_generator/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut redirect_generator
./scripts/ucv run ctrl --dut redirect_generator --collect-only --workers 1
./scripts/ucv run ctrl --dut redirect_generator --workers 1 -- testbenches/redirect_generator/tests/test_redirect_generator_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
