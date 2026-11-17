# l2_slice2_pipeline

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `l2_slice2_pipeline` | `L2Slice_2` | `L2Slice_2Dut` |

## 工作入口

- 设计规格：[docs/spec/design/l2_slice2_pipeline.md](../../docs/spec/design/l2_slice2_pipeline.md)
- 验证合同与计划：[docs/spec/verification/l2_slice2_pipeline.md](../../docs/spec/verification/l2_slice2_pipeline.md)
- 公开环境：[testbenches/l2_slice2_pipeline/env.py](env.py)
- 用例与自检：[testbenches/l2_slice2_pipeline/tests](tests)
- 实现职责：[testbenches/l2_slice2_pipeline/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mbist --dut l2_slice2_pipeline
./scripts/ucv run mbist --dut l2_slice2_pipeline --collect-only --workers 1
./scripts/ucv run mbist --dut l2_slice2_pipeline --workers 1 -- testbenches/l2_slice2_pipeline/tests/test_l2_slice2_pipeline_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
