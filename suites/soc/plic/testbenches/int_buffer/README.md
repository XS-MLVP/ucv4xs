# int_buffer

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `int_buffer` | `IntBuffer` | `IntBufferDut` |

## 工作入口

- 设计规格：[docs/spec/design/int_buffer.md](../../docs/spec/design/int_buffer.md)
- 验证合同与计划：[docs/spec/verification/int_buffer.md](../../docs/spec/verification/int_buffer.md)
- 公开环境：[testbenches/int_buffer/env.py](env.py)
- 用例与自检：[testbenches/int_buffer/tests](tests)
- 实现职责：[testbenches/int_buffer/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info plic --dut int_buffer
./scripts/ucv run plic --dut int_buffer --collect-only --workers 1
./scripts/ucv run plic --dut int_buffer --workers 1 -- testbenches/int_buffer/tests/test_int_buffer_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
