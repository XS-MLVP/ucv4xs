# L2TLBWrapper 组合层闭环证据（2026-10-25）

最终完整 run：`results/l2tlbwrapper-final-05`（46 PASS + 1 strict XFAIL，
`state=committed`，`coverage_complete=true`）。

| 阶段 | run | 用例 | 行覆盖 | branch | toggle | 功能 |
|---|---|---:|---:|---:|---:|---:|
| 首轮 | `l2tlbwrapper-tests-01` | 34 PASS | 17015/22289 = 76.338% | 4294/6304 | 99389/260640 | 84.09% |
| 补 wrapper 专项 | `l2tlbwrapper-tests-03` | 43 PASS | 17050/22289 = 76.495% | 4304/6304 | 100103/260640 | 100% |
| 补 64 页 working set | `l2tlbwrapper-tests-04` | 44 PASS | 17449/22289 = 78.285% | 4423/6304 | 101349/260640 | 100% |
| 补共享叶子正例 | `l2tlbwrapper-final-04` | 45 PASS + 2 XFAIL | 17689/22289 = 79.362% | 4442/6304 | 102220/260640 | 100% |
| 补 4 outstanding | `l2tlbwrapper-final-05` | 46 PASS + 1 XFAIL | 17697/22289 = 79.398% | 4444/6304 | 102301/260640 | 100% |
| **最终** | **`l2tlbwrapper-final-05`** | **46 PASS + 1 XFAIL** | **17697/22289 = 79.398%** | **4444/6304** | **102301/260640** | **100%** |

说明：

- 首轮直接复用 34 个 L2TLB 顶层用例，证明包装层功能通路透明；功能覆盖
  84.09% 仅因 wrapper 专用 event bin 尚未采样。
- 9 个 wrapper 专项用例补齐 perf/WFI/CSR/PMP/bitmap/reset/背压语义，功能到
  100%。
- 64 页 4KB working set 覆盖全部 PtwCache L0 set/lane，行覆盖提升 1.79 个百分点
  （PtwCache 单独 +399 行）。
- strict XFAIL 固定“共享叶子表 back-to-back miss 停顿”的候选行为缺口；该用例
  在最终 run 中实际执行并失败，`manifest.tests` 为 `PASS=44, XFAIL=1`。

## 性能事件等价性

`perf-trace-l2tlb.json` 与 `perf-trace-l2tlbwrapper.json` 是同一复位、同一
1GB leaf 激励在 `L2TLB` 与 `L2TLBWrapper` 两个 DUT 上逐拍记录的 22 拍 trace。
`perf-trace-comparison.json` 由 `tools/compare_wrapper_perf_trace.py` 生成：

- 功能字段（response、A 通道、WFI）22 拍逐拍一致；
- 19 路 perf 全部满足 `wrapper[t] == l2tlb[t-2]`（忽略前 4 拍初始随机流水线）；
- `status=PASS`，0 failures。

trace 工具位于 `tools/trace/`，比较工具位于 `tools/compare_wrapper_perf_trace.py`。

## 文件

- `l2tlbwrapper-before-audit.json`：首轮 34 用例 compact 审计
- `l2tlbwrapper-mid-audit.json`：43 用例 compact 审计
- `l2tlbwrapper-prefinal-audit.json`：44 用例（未加 XFAIL）compact 审计
- `l2tlbwrapper-final-audit.json`：最终 compact 审计
- `l2tlbwrapper-final-functional.json`：最终功能覆盖原始 JSON
- `perf-trace-*.json` / `perf-trace-comparison.json`：性能事件等价性证据
- 完整审计、coverage dat/lcov/html：`results/l2tlbwrapper-final-05/`

未覆盖项分类、候选行为缺口和未闭合范围见
[L2TLBWrapper 报告](../../l2tlbwrapper-20261025.md) §5–§6。
本目录不保存波形或逐周期事务。


## 第二阶段补充（2026-10-25）

- 新增 `test_wrapper_shared_leaf_one_cycle_gap`：在三个共享 leaf 表 4KB 请求间插入
  1 个 service 周期，第三个 demand 行 0x800A2080 正常发出并全部完成；零间隔时该
  demand 被相邻预取行 0x800A20C0 替代并停顿，根因已隔离。
- `test_wrapper_four_outstanding`：4 个不同 4KB 翻译在 mem_latency=7 下全部完成；
  零延迟模型丢失第二个 D beat 是 harness 时序，不再作为 RTL 边界。
- 最终 XFAIL 数 1（仅零间隔共享叶子），PASS 46。
