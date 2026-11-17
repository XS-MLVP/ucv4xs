# nf_mapped_elem_idx

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `nf_mapped_elem_idx` | `NfMappedElemIdx` | `NfMappedElemIdxDut` |

## 工作入口

- 设计规格：[docs/spec/design/nf_mapped_elem_idx.md](../../docs/spec/design/nf_mapped_elem_idx.md)
- 验证合同与计划：[docs/spec/verification/nf_mapped_elem_idx.md](../../docs/spec/verification/nf_mapped_elem_idx.md)
- 公开环境：[testbenches/nf_mapped_elem_idx/env.py](env.py)
- 用例与自检：[testbenches/nf_mapped_elem_idx/tests](tests)
- 实现职责：[testbenches/nf_mapped_elem_idx/transactions.py](transactions.py)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info vec_region --dut nf_mapped_elem_idx
./scripts/ucv run vec_region --dut nf_mapped_elem_idx --collect-only --workers 1
./scripts/ucv run vec_region --dut nf_mapped_elem_idx --workers 1 -- testbenches/nf_mapped_elem_idx/tests/test_nf_mapped_elem_idx_smoke.py::test_smoke
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
