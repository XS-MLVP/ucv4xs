# prefetchpipe

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `prefetchpipe` | `ICachePrefetchPipe` | `PrefetchPipeDut` |

## 工作入口

- 设计规格：[docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/reports/baseline-update-a0c2a26cb.md](../../docs/spec/verification/reports/baseline-update-a0c2a26cb.md) · [docs/spec/verification/coverage/mainpipe-prefetchpipe-coverage-closure.md](../../docs/spec/verification/coverage/mainpipe-prefetchpipe-coverage-closure.md)
- 公开环境：[testbenches/prefetchpipe/env/agent/main.py](env/agent/main.py)
- 用例与自检：[testbenches/prefetchpipe/tests](tests)
- 实现职责：[testbenches/prefetchpipe/transactions](transactions) · [testbenches/prefetchpipe/model](model)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info icache --dut prefetchpipe
./scripts/ucv run icache --dut prefetchpipe --collect-only --workers 1
./scripts/ucv run icache --dut prefetchpipe --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
