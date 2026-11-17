# vf_reg_file

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `vf_reg_file` | `VfRegFile` | `VfRegFileDut` |

## 工作入口

- 设计规格：[docs/spec/design/vf_reg_file.md](../../docs/spec/design/vf_reg_file.md)
- 验证合同与计划：[docs/spec/verification/vf_reg_file.md](../../docs/spec/verification/vf_reg_file.md)
- 公开环境：[testbenches/vf_reg_file/env.py](env.py)
- 用例与自检：[testbenches/vf_reg_file/tests](tests)
- 实现职责：[testbenches/vf_reg_file/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vec_region --dut vf_reg_file
./scripts/ucv run vec_region --dut vf_reg_file --collect-only --workers 1
./scripts/ucv run vec_region --dut vf_reg_file --workers 1 -- testbenches/vf_reg_file/tests/test_vf_reg_file_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
