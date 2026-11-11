# manager

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `VAGQManager` | `VAGQManager` | `VAGQManagerDut` |

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/README.md](../../docs/spec/verification/evidence/README.md)
- 公开环境：[testbenches/manager/env/agent.py](env/agent.py)
- 用例与自检：[testbenches/manager/tests](tests)
- 实现职责：[testbenches/manager/transactions.py](transactions.py) · [testbenches/manager/model.py](model.py) · [testbenches/manager/checker.py](checker.py) · [testbenches/manager/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vagq --dut VAGQManager
./scripts/ucv run vagq --dut VAGQManager --collect-only --workers 1
./scripts/ucv run vagq --dut VAGQManager --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
