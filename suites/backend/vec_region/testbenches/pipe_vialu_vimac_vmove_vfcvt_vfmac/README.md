# pipe_vialu_vimac_vmove_vfcvt_vfmac

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `pipe_vialu_vimac_vmove_vfcvt_vfmac` | `IssuePipeVialuVimacVmoveVfcvtVfmac` | `IssuePipeVialuVimacVmoveVfcvtVfmacDut` |

## 工作入口

- 设计规格：[docs/spec/design/pipe_vialu_vimac_vmove_vfcvt_vfmac.md](../../docs/spec/design/pipe_vialu_vimac_vmove_vfcvt_vfmac.md)
- 验证合同与计划：[docs/spec/verification/pipe_vialu_vimac_vmove_vfcvt_vfmac.md](../../docs/spec/verification/pipe_vialu_vimac_vmove_vfcvt_vfmac.md)
- 公开环境：[testbenches/pipe_vialu_vimac_vmove_vfcvt_vfmac/env.py](env.py)
- 用例与自检：[testbenches/pipe_vialu_vimac_vmove_vfcvt_vfmac/tests](tests)
- 实现职责：[testbenches/pipe_vialu_vimac_vmove_vfcvt_vfmac/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vec_region --dut pipe_vialu_vimac_vmove_vfcvt_vfmac
./scripts/ucv run vec_region --dut pipe_vialu_vimac_vmove_vfcvt_vfmac --collect-only --workers 1
./scripts/ucv run vec_region --dut pipe_vialu_vimac_vmove_vfcvt_vfmac --workers 1 -- testbenches/pipe_vialu_vimac_vmove_vfcvt_vfmac/tests/test_pipe_vialu_vimac_vmove_vfcvt_vfmac_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
