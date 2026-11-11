# ptwrepeater

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `ptwrepeater` | `PTWRepeaterNB` | `PtwRepeaterNBDut` |
| `ptwfilter` | `PTWFilter` | `PtwFilterDut` |

这些 DUT 显式共用参数化实现；运行共享用例时选择其实际需要的全部 DUT。

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-l2-leaves.md](../../docs/spec/verification/functional-points/functional-points-l2-leaves.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/l2-filter-repeater-20261024.md](../../docs/spec/verification/evidence/reports/l2-filter-repeater-20261024.md)
- 公开环境：[testbenches/ptwrepeater/env/ptw.py](env/ptw.py)
- 用例与自检：[testbenches/ptwrepeater/tests](tests) · [testbenches/ptwrepeater/tests/test_ptwrepeater.py](tests/test_ptwrepeater.py) · [testbenches/ptwrepeater/tests/test_ptwfilter.py](tests/test_ptwfilter.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut ptwrepeater --dut ptwfilter
./scripts/ucv run mmu --dut ptwrepeater --dut ptwfilter --collect-only --workers 1
./scripts/ucv run mmu --dut ptwrepeater --dut ptwfilter --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
