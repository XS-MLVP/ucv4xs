# slice

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `slice` | `Slice_4` | `Slice_4Dut` |

## 工作入口

- 设计规格：[docs/spec/design/slice.md](../../docs/spec/design/slice.md)
- 验证合同与计划：[docs/spec/verification/slice.md](../../docs/spec/verification/slice.md)
- 公开环境：[testbenches/slice/env.py](env.py)
- 用例与自检：[testbenches/slice/tests](tests)
- 实现职责：[testbenches/slice/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info llc --dut slice
./scripts/ucv run llc --dut slice --collect-only --workers 1
./scripts/ucv run llc --dut slice --workers 1 -- testbenches/slice/tests/test_slice_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
