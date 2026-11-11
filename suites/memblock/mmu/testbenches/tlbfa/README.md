# tlbfa

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `tlbfa` | `TLBFA` | `TlbfaDut` |

## 工作入口

- 设计规格：[docs/spec/verification/functional-points/functional-points-tlbfa.md](../../docs/spec/verification/functional-points/functional-points-tlbfa.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/evidence/reports/tlbfa-20261024.md](../../docs/spec/verification/evidence/reports/tlbfa-20261024.md)
- 公开环境：[testbenches/tlbfa/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/tlbfa/tests](tests) · [testbenches/tlbfa/tests/test_tlbfa_basic.py](tests/test_tlbfa_basic.py) · [testbenches/tlbfa/tests/test_tlbfa_pages.py](tests/test_tlbfa_pages.py) · [testbenches/tlbfa/tests/test_tlbfa_refill.py](tests/test_tlbfa_refill.py) · [testbenches/tlbfa/tests/test_tlbfa_sfence.py](tests/test_tlbfa_sfence.py) · [testbenches/tlbfa/tests/test_tlbfa_toggle.py](tests/test_tlbfa_toggle.py)
- 实现职责：[testbenches/tlbfa/model.py](model.py) · [testbenches/tlbfa/coverage.py](coverage.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info mmu --dut tlbfa
./scripts/ucv run mmu --dut tlbfa --collect-only --workers 1
./scripts/ucv run mmu --dut tlbfa --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
