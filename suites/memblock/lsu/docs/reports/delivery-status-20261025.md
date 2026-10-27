# LSU 独立 UT 交付状态（2026-10-25）

## 1. 结论

`memblock-hash/lsu/` 已建立独立验证工程，**19 个计划 DUT 中已完成 12 个**
（NewStoreUnit 全族 9 个 + StdExeUnit + LoadUnitS4 + MemTrigger(load)），
其余 7 个属于 NewLoadUnit 族，**尚未完成，目标仍为 ACTIVE，不构成整体验收**。

统一回归 `results/unified-regression-01`：**282 passed / 0 failed**，12 个原生构建。

| 指标（各 DUT 独立分母之和，仅用于展示） | 值 |
|---|---|
| 行覆盖 | 647 / 662（97.7%），过程语句未覆盖 **0** |
| 分支覆盖 | 328 / 342 |
| Toggle | 30127 / 30912（97.5%） |
| 功能覆盖 | 12 个 DUT 全部 100% |

剩余行/分支/toggle 缺口逐项归因为**结构常量**或**工具边界**（`initial` 块内的
`if (reset)`），每条在 `docs/gaps/*.json` 有源码行号与理由。

## 2. 已完成 DUT

| DUT | 用例 | 功能 | 行 | 分支 | Toggle |
|---|---:|---:|---:|---:|---:|
| `Arbiter3_StoreStageIO` | 22 | 100% | 32/32 | 62/62 | 1126/1128 |
| `MemTrigger_3` | 32 | 100% | 48/48 | 16/16 | 762/762 |
| `DelayPipeline` | 14 | 100% | 29/29 | 5/6 | 978/978 |
| `StoreUnitS0` | 57 | 100% | 83/83 | 67/68 | 3090/3100 |
| `StoreUnitS1` | 41 | 100% | 86/86 | 30/31 | 3836/3872 |
| `StoreUnitS2` | 22 | 100% | 32/32 | 5/6 | 1042/1042 |
| `StoreUnitS3` | 17 | 100% | 51/51 | 10/12 | 2502/2506 |
| `StoreUnitS4` | 6 | 100% | 0/0¹ | 0/0 | 572/572 |
| `NewStoreUnit` | 26 | 100% | 242/257² | 111/119 | 13231/13964 |
| `StdExeUnit` | 17 | 100% | 11/11 | 12/12 | 1058/1058 |
| `LoadUnitS4` | 7 | 100% | 0/0¹ | 0/0 | 1168/1168 |
| `MemTrigger`（load） | 21 | 100% | 33/33 | 10/10 | 762/762 |

¹ 纯连续赋值模块，Verilator 行覆盖只统计过程语句，因此分母为 0；字段保真由 toggle 与
逐字段比较覆盖。
² 15 条未命中行全部是声明/连续赋值行，过程语句未覆盖为 0。

## 3. 尚未完成（任务保持 pending）

| DUT | 状态 | 说明 |
|---|---|---|
| `Arbiter7_LoadStageIO` | 未开始 | 248 端口、5 源（0/1/2/3/5）固定优先级，逐字段 mux 风格不一致（部分字段用 `valid & bits`，部分用三元），需要逐字段建参考模型 |
| `LoadUnitDataPath` | 未开始 | 158 端口，S2/S3 的字节选择/对齐/前递合成 |
| `LoadUnitS0` | 未开始 | 255 端口，7 源仲裁 + forward/bypass 请求 |
| `LoadUnitS1` | 未开始 | 249 端口，PA/kill、RAR/RAW 查询发起 |
| `LoadUnitS2` | 未开始 | 330 端口，TLB/PMP/Cache 响应、Replay 原因生成 |
| `LoadUnitS3` | 未开始 | 376 端口，revoke、数据选择、LQ 写 |
| `NewLoadUnit` | 未开始 | 645 端口，需在上面 6 个完成后组合 |

这 7 个 DUT 已有：基线哈希、静态闭包、Picker 构建（`dut/` 下全部 19 个包均已构建
并通过 `NATIVE_SMOKE_PASS`），但**没有功能用例、没有覆盖审计、没有阶段报告**，
因此不计入已完成。

## 4. 本阶段的方法学产出

1. **采样相位约定**：Picker 在 `Step` 内先求值、再走时钟、再求值，因此读到的组合
   输出反映**本拍输入**，寄存器反映**本拍时钟沿的结果**。所有 DUT 的模型都按此
   约定书写，早期的相位错误已保留在历史 run 中。
2. **陈旧载荷必须建模**：`pipeOutBits` 只在 `pipeIn.valid=1` 时更新（即使被 kill
   也更新），后续周期会读这些陈旧值；集成模型最初忽略这一点，导致 100+ 拍后发散。
3. **`kill` 的 valid 门控不一致**：`RobPtr.needFlush` 没有 valid 项，`illegalIssue`
   与 `youngCrossHead` 有；因此空闲拍的 `tlbReqKill` 可以为 1。
4. **无 reset 的模块**：`StdExeUnit` 没有 reset 端口，反馈寄存器上电值随机，第一个
   比较周期必须跳过。
5. **组合环回**：store 的 S1→S0 尾段注入在同一拍抢走仲裁，只能由父块 UT 观察。

## 5. 工具与证据

| 项 | 值 |
|---|---|
| 源码 | `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` |
| RTL | `soc-split/rtl`，19 文件 SHA-256 清单 `manifest/lsu-rtl.sha256` |
| Picker | 2.0.0-HEAD-4dd442c |
| Verilator | 5.052 |
| toffee | 2.0.0.dev12+g3017293a7 |
| 运行策略 | 无波形、无逐周期 dump；`trace-policy.json` 全部 PASS |
| 统一回归 | `results/unified-regression-01`（282 passed） |
| 覆盖汇总 | `manifest/coverage-summary.json` |

## 6. 明确不声称

- 不声称 LSU、MemBlock 或整核已验收。
- 12 个 DUT 通过只覆盖 store 地址/数据通路与两个 load 叶子；load 的地址生成、
  前递、Replay 与整体 `NewLoadUnit` **未验证**。
- 外部 LSQ/DCache/TLB/PMP/ROB 均为测试侧激励，不是它们已验证的证据。
