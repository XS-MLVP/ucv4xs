# LLPTW 独立叶级闭环证据（2026-10-25）

最终完整 run：`results/llptw-final-04`（23 PASS + 1 strict XFAIL，
`state=committed`，`coverage_complete=true`）。

| 阶段 | run | 用例 | 行覆盖 | branch | toggle | 功能 |
|---|---|---:|---:|---:|---:|---:|
| 上一版 | `llptw-final-02` | 11 | 1275/1955 = 65.2% | 285/407 | 1913/20770 | 91.67% |
| 补 stage2/缓存/权限 | `llptw-tests-06` | 18 | 1329/1955 = 67.98% | 310/407 | 2228/20770 | 100% |
| 补每 slot 放置 | `llptw-tests-07` | 21 | 1656/1955 = 84.71% | 359/407 | 4300/20770 | 100% |
| 补多 allStage 边界 | `llptw-tests-14` | 23 PASS + 1 XFAIL | 1656/1955 = 84.706% | 359/407 | 4329/20770 | 100% |
| **最终** | **`llptw-final-04`** | **23 PASS + 1 XFAIL** | **1656/1955 = 84.706%** | **359/407** | **4329/20770** | **100%** |

关键修复：`io_hptw_req_valid` 是 `ready & arb_valid` 的组合信号，原 harness
在 `service()` 前不刷新组合值，会漏掉单拍 HPTW 请求。加入 `RefreshComb()` 后
stage2 请求/响应可稳定捕获；这是测试环境修复，不修改 RTL。

## 覆盖缺口分类

残余 299 行：

- 重复请求处于 `mem_waiting` / `last_hptw` 状态时的 `wait_id` fan-in mux；
- enqueue 时 `to_last_hptw_req` 的 per-entry 字段写入（需要重复请求恰好在最后
  HPTW 响应前到达）；
- 部分 `last_hptw`/`cache`/`bitmap` 状态转移和 reset/initial 结构。

均归为“已有重复合并/stage2 功能点的情况枚举缺失”，没有整体功能点缺失。
未闭合范围：多个 allStage 请求并发（见 `LLPTW-MULTI-STAGE2-UNVERIFIED`）。

## 文件

- `llptw-stage2-audit.json`：18 用例（stage2/cache/权限）compact 审计
- `llptw-slots-audit.json`：21 用例（每 slot）compact 审计
- `llptw-final-audit.json`：最终 compact 审计
- `llptw-final-functional.json`：最终功能覆盖原始 JSON
- 完整 audit/dat/lcov/html：`results/llptw-final-04/`

详见 [LLPTW 报告](../../llptw-20261025.md) 与
[功能点](../functional-points-l2-midblocks.md) §5。


## 第二阶段补充（2026-10-25）

`test_two_concurrent_all_stage` 将两个 allStage 请求放入不同 entry，DUT 发出两个
first-stage HPTW、entry 1 的 second-stage HPTW 和一次 PTE 读后停顿；另一个 entry 在 first-stage HPTW 响应后不再发
PTE 读；零间隔/stagger/slot 顺序均复现。该用例为 strict XFAIL，known-issue `LLPTW-MULTI-STAGE2-UNVERIFIED` 保留。
单 allStage 在 slot 1..5 全部通过。
