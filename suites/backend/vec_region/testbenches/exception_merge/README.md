# exception_merge

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `exception_merge` | `VecExcpDataMergeModule` | `VecExcpDataMergeModuleDut` |

## 工作入口

- 设计规格：[docs/spec/design/exception_merge.md](../../docs/spec/design/exception_merge.md)
- 验证合同与计划：[docs/spec/verification/exception_merge.md](../../docs/spec/verification/exception_merge.md)
- 公开环境：[testbenches/exception_merge/env.py](env.py)
- 用例与自检：[testbenches/exception_merge/tests](tests)
- 实现职责：[testbenches/exception_merge/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vec_region --dut exception_merge
./scripts/ucv run vec_region --dut exception_merge --collect-only --workers 1
./scripts/ucv run vec_region --dut exception_merge --workers 1 -- testbenches/exception_merge/tests/test_exception_merge_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
