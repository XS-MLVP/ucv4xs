# l2top

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `l2top` | `L2Top` | `L2TopDut` |

## 工作入口

- 设计规格：[docs/spec/design/l2top.md](../../docs/spec/design/l2top.md)
- 验证合同与计划：[docs/spec/verification/l2top.md](../../docs/spec/verification/l2top.md)
- 公开环境：[testbenches/l2top/env.py](env.py)
- 用例与自检：[testbenches/l2top/tests](tests)
- 实现职责：[testbenches/l2top/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info l2 --dut l2top
./scripts/ucv run l2 --dut l2top --collect-only --workers 1
./scripts/ucv run l2 --dut l2top --workers 1 -- testbenches/l2top/tests/test_l2top_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
