# uncache

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `uncache` | `Uncache` | `UncacheDut` |

## 工作入口

- 设计规格：[docs/spec/design/uncache.md](../../docs/spec/design/uncache.md)
- 验证合同与计划：[docs/spec/verification/uncache.md](../../docs/spec/verification/uncache.md)
- 公开环境：[testbenches/uncache/env.py](env.py)
- 用例与自检：[testbenches/uncache/tests](tests)
- 实现职责：[testbenches/uncache/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info dcache --dut uncache
./scripts/ucv run dcache --dut uncache --collect-only --workers 1
./scripts/ucv run dcache --dut uncache --workers 1 -- testbenches/uncache/tests/test_uncache_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
