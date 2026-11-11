# load_s0

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `load_s0` | `LoadUnitS0` | `LoadS0Dut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/load-s0.md](../../docs/spec/design/contracts/load-s0.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/gaps/load_s0.json](../../docs/spec/verification/gaps/load_s0.json)
- 公开环境：[testbenches/load_s0/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/load_s0/tests](tests)
- 实现职责：[testbenches/load_s0/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsu --dut load_s0
./scripts/ucv run lsu --dut load_s0 --collect-only --workers 1
./scripts/ucv run lsu --dut load_s0 --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
