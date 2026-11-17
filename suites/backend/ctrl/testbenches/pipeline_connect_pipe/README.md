# pipeline_connect_pipe

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `pipeline_connect_pipe` | `PipelineConnectPipe` | `PipelineConnectPipeDut` |

## 工作入口

- 设计规格：[docs/spec/design/pipeline_connect_pipe.md](../../docs/spec/design/pipeline_connect_pipe.md)
- 验证合同与计划：[docs/spec/verification/pipeline_connect_pipe.md](../../docs/spec/verification/pipeline_connect_pipe.md)
- 公开环境：[testbenches/pipeline_connect_pipe/env.py](env.py)
- 用例与自检：[testbenches/pipeline_connect_pipe/tests](tests)
- 实现职责：[testbenches/pipeline_connect_pipe/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info ctrl --dut pipeline_connect_pipe
./scripts/ucv run ctrl --dut pipeline_connect_pipe --collect-only --workers 1
./scripts/ucv run ctrl --dut pipeline_connect_pipe --workers 1 -- testbenches/pipeline_connect_pipe/tests/test_pipeline_connect_pipe_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
