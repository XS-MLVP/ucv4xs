# TLBNonBlock 独立叶级覆盖证据（2026-10-25）

最终完整 run：`results/tlbn-tests-13`（30 PASS，committed，
coverage_complete=true）。

| 阶段 | run | 用例 | 行覆盖 | branch | toggle | 功能 |
|---|---|---:|---:|---:|---:|---:|
| 首轮 | `tlbn-tests-02` | 18 | 2148/4956 = 43.34% | 947/1568 | 15065/37422 | 83.93% |
| 补端口/lane/容量/失效 | `tlbn-tests-12` | 29 | 4695/4956 = 94.73% | 1328/1568 | 20325/37422 | 100% |
| **最终** | **`tlbn-tests-13`** | **30** | **4839/4956 = 97.639%** | **1424/1568** | **20486/37422** | **100%** |

残余 117 行：TLBFA_1 的 48 个 sfence/hfence per-way ternary arm，
TlbNonBlockDut 的 59 行 need_gpa robIdx/GPA 响应端口 1/3 状态。分类与证据见
[报告](../../tlbn-20261025.md) 和
[功能点](../../functional-points-tlbn.md)。

文件：

- `tlbn-before-audit.json`：首轮 compact 审计
- `tlbn-mid-audit.json`：中期 compact 审计
- `tlbn-final-audit.json`：最终 compact 审计
- `tlbn-final-functional.json`：最终功能覆盖原始 JSON
- 完整 audit/dat/lcov/html：`results/tlbn-tests-13/`
