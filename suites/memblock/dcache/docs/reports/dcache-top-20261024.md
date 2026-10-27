# DCache 顶层 UT 报告（2026-10-24）

> **已被取代**：本报告的结论以 15 用例的早期版本为准，其中“store miss write-through
> 行数据来自 store 自身”与“dirty eviction 未产生 C 通道 Release”两项后续已被修正/闭合。
> 最新结论与数字请看 `dcache-top-20261025.md`（20 用例、7 个功能组 100%）。
> 本文件保留为历史记录，不再作为当前验收依据。

## 1. 结论

| 项 | 结果 |
|---|---|
| 运行 | `results/dc-final-05`（15 用例，固定 seed 1） |
| 功能覆盖 | **93.75%**（load 83.3 / miss 91.7 / store 100 / control 100） |
| DUT 行覆盖 | **67.92%**（34760 / 51179） |
| 分支覆盖 | **12155 / 20504 = 59.3%** |
| Toggle（DUT-only） | **116913 / 332370 = 35.18%** |

DCache 是可综合整块，包含大量本轮未驱动的旁路（atomics、CMO、WPU、L2 hint、
prefetch 标记、uncache、ECC 伪错误、probe 多条目合并）。功能点覆盖的是本轮定义的
端到端主路径；行/分支/toggle 的剩余量按“未纳入范围”和“结构/工具边界”分类记录。

## 2. 端到端验证结果

| 功能点 | 用例 | 结果 |
|---|---|---|
| DC-FP-001 复位/SRAM 清扫 | 所有用例的 300 拍预置 | PASS |
| DC-FP-002 load 命中 | `test_all_three_load_lanes`、`test_three_lanes_same_line` | PASS，3 lane 数据一致 |
| DC-FP-003 冷 miss + refill | `test_cold_miss_refill_then_hit` | PASS，AcquireBlock(6,size6) + 2×GrantData → 重放命中，数据逐字节一致 |
| DC-FP-004 双通道 | `test_dual_channel_selection` | PASS，paddr[6] 分别选 0/1 通道 |
| DC-FP-005 store | `test_store_masks_and_readback`、`test_store_miss_with_refill`、`test_store_mask_classes` | PASS，字节掩码合并、store miss write-through |
| DC-FP-006 MSHR 耗尽 | `test_mshr_full_yields_unhandled_miss` | PASS，出现 handled=0；仅 lane0 观测到 miss_unhandled |
| DC-FP-007 denied refill | `test_refill_denied_reports_error` | PASS，io_error.valid 拉高；paddr 观测为 0（记录） |
| DC-FP-008 probe | `test_probe_ack` | PASS，B→C ProbeAck，地址回显 |
| 掩码/坏数据 | `test_load_mask_shapes`、`test_partial_load_masks`、`test_corrupt_refill` | PASS |

## 3. 关键发现

1. **refill 前置条件**：tag/meta SRAM 复位后需要 256 拍清扫；清扫完成前 MainPipe 的
   tag/meta ready 为低。`test_*` 统一等待 300 拍。此前“refill 不命中”的阻塞由
   (a) 未等清扫、(b) GrantData size 用 5（单 beat）、(c) 未在 S2 采样响应三点共同造成，
   修正后冷 miss→refill→hit 全链路通过。
2. **GrantData 必须 size=6 + 2 beat**：size=5 时 `r_beats1=0`，MissEntry 把第一个 beat
   当作整行完成，后续不会形成完整行。
3. **store 的 64-bit mask 是逐字节掩码**；mask=0xFF 写 8 个字节。~~store miss 的 refill
   数据来自 store 自身（write-through），不是 L2 beat。~~
   **更正（2026-10-25）**：只有整行覆盖（`full_overwrite`）走 `AcquirePerm` 且行数据
   由 store 构成；部分掩码 store 走 `AcquireBlock`，refill 行 = L2 整行与 store 掩码
   字节的合并。证据：`results/w0-coverage-01` 的 `test_store_miss_with_refill`。
4. **denied refill 的错误地址字段为 0**：`io_error.valid=1` 但 `paddr=0`；与 ECC
   `read_error_delayed` 的异常行为一起记入 `manifest/known-issues.json`，需要上游确认
   是否是本配置的报错路径约定。
5. **dirty eviction 未产生 C 通道 Release**：对同一 set 填充 5 个 dirty 行（set 保持
   不变的地址构造）未观察到 C 释放。可能原因：store 命中未置 dirty、替换写回走
   WBQ 但需要更长的 miss_resp 收尾、或本轮地址构造没有真正落到同一 set。该场景保留为
   未关闭项（不声称写回已验证）。

## 4. 覆盖率归因

### 行（未覆盖 16419 / 51179）

按源文件集中在：
- `DCacheDut.v` 的 atomics/uncache/CMO/WPU/L2 hint/prefetch 标记/ECC 伪错误注入分支；
- `MissQueue` 的 release/CMO/spec-fabric/forward 路径；
- `MainPipe` 的 amo 运算、probe 数据回填、prefetch 统计；
- `WritebackQueue` 的多条目/delay_release/merge 路径；
- `ProbeQueue` 的多条目与响应完成路径（顶层只走单条 ProbeAck）。

这些属于**本轮未定义的功能点**（atomics、CMO、uncache、WPU、prefetch 标记），
不是已定义功能点的情形缺失。已在 `docs/hierarchy.md` 的范围说明中列出。

### 分支（未覆盖 8349 / 20504）

与行缺口一一对应；另有时间零 `initial` 的 else 与 DFT/时钟门控恒等条件。

### Toggle（未覆盖 215457 / 332370）

主要类别：未访问的 data/meta SRAM 行（256 set × 32 bank × 4 way 的大部分）、
未驱动的 uncache/atomic 端口、perf 计数与 DFT 控制。已覆盖的主路径（load/store/
refill/probe/miss）数据与握手位均双向翻转。

## 5. 证据

- `results/dc-final-05/manifest.json`、`functional-coverage.json`、`coverage-audit.json/.md`
- `manifest/rtl-sha256.json`（`dcache` 58 个 RTL 文件）
- `results/builds/20261024T115459476607Z-dcache/report.json`
- `tools/probe_dcache_refill.py`（TL/refill 握手探针，含 GrantData size/beat 修正）
