# NewStoreUnit 族完整 UT 报告（S0–S4 与集成）

本报告覆盖 `p1`–`p3` 阶段：NewStoreUnit 族的 9 个独立 DUT 全部完成 Picker 原生构建、
语义功能点、用例、覆盖率分析与缺口归因。

## 1. 汇总

| DUT | 用例 | 功能覆盖 | 行（DUT-only） | 分支 | Toggle（DUT-only） | 状态 |
|---|---:|---:|---:|---:|---:|---|
| `Arbiter3_StoreStageIO` | 22 | 100% | 32/32 | 62/62 | 1126/1128 | PASS |
| `MemTrigger_3` | 32 | 100% | 48/48 | 16/16 | 762/762 | PASS |
| `DelayPipeline` | 14 | 100% | 29/29 | 5/6 | 978/978 | PASS |
| `StoreUnitS0` | 57 | 100% | 83/83 | 67/68 | 3090/3100 | PASS |
| `StoreUnitS1` | 41 | 100% | 86/86 | 30/31 | 3836/3872 | PASS |
| `StoreUnitS2` | 22 | 100% | 32/32 | 5/6 | 1042/1042 | PASS |
| `StoreUnitS3` | 17 | 100% | 51/51 | 10/12 | 2502/2506 | PASS |
| `StoreUnitS4` | 6 | 100% | 0/0¹ | 0/0 | 572/572 | PASS |
| `NewStoreUnit` | 26 | 100% | 242/257² | 111/119 | 13231/13964 | PASS（缺口全部归类） |

¹ S4 全部是连续赋值，Verilator 的行覆盖只统计过程语句，因此分母为 0；13 个字段的
逐位透传由 toggle 572/572 与逐字段比较覆盖。
² 15 条未命中行全部是声明/连续赋值行，过程语句未覆盖为 **0**。

合计 **237 个用例，0 FAIL、0 xfail、0 skip**。

## 2. 各 DUT 的关键语义发现

### 2.1 固定延迟、无背压（S0/S1/S2/S3）

生成的 store 地址流水线**没有 ready 链**：`StoreUnitS0` 没有 `pipeOut_ready`，
`StoreUnitS1/S2` 没有 `pipeIn_ready`。`pipeOutValid <= ~kill & valid`，`stin_ready`
只是仲裁器的 `~in_0_valid`。因此每个 beat 在输出上只出现一拍，测试按"驱动一拍 →
立刻可见 → 下一拍消失"的约定建模，而不是 ready/valid 停滞协议。

### 2.2 `kill` 的 valid 门控不一致（S1/S2/S3）

`RobPtr.needFlush` 没有 valid 输入，而 `illegalIssue`/`youngCrossHead` 都自带宽
valid 门控。因此 S1/S2/S3 的 redirect-kill 项在**空闲拍**也可能成立：只要保留的
陈旧 robIdx 载荷比 redirect 更年轻，`tlbReqKill` 就会为 1。它无害（没有在途请求），
但随机测试若不带此语义会出现假失败。S0 的 kill 则带 `arb_valid` 门控。

### 2.3 载荷寄存器只被 valid 门控（S0/S1/S2/S3）

`pipeOutBits` 在 `pipeIn.valid=1` 时更新，**即使该 beat 被 kill 也更新**（只有 valid
清零）。后续周期会读这些陈旧载荷（S1 的 redirect 比较、S2 的 `isLastRequest` 等）。
集成模型必须保留陈旧载荷，否则跨级比较会在若干拍后发散——这正是父块模型最初失败的
根因。

### 2.4 head/tail 环回在同一拍抢走仲裁（集成）

S1 的 `unalignTail` 组合输出直接进 S0 的仲裁器。跨 16B 的 head 在 S0 寄存器里时，
尾段已经在同一拍赢得仲裁：`stin_ready` 当拍变 0，`tlb_req` 发出的是尾段地址
（下一个 16B 字）。这是 S0/S1 各自 UT 看不到的跨级效应，由
`test_tail_wins_the_arbiter_in_the_head_cycle` 固定。

### 2.5 延迟管的一拍是"进入后一拍"

`DelayPipeline` 的 `out.ready` 被父块接成 `true`，因此 beat 只驻留一拍；其输出寄存
器在下一个时钟沿就绪，表现为 `stout` 比 `stin` 晚 3 拍（S1 寄存器 + S2 寄存器 +
延迟管）。`feedBackSlow` 由父层 `RegNext` 再延一拍，且 `bits.hit` 在 valid=0 时保持
旧值（`RegEnable`）。

### 2.6 CBO 语义

S1 把 CBO 的 vaddr/paddr 对齐到 16B、`size` 置 4（QB）、`wlineflag=1`；S2 把访问
uncache 空间的 CBO（以及向量 store）判为 access fault；S3 中正常完成的 MMIO/CBO
store **不写 ROB**（只有带异常才写）。

### 2.7 跨页 head 需要地址就绪

`youngCrossHead = valid && scalar && unalignHead && cross4KPage && !isAddrReadyHead`
会杀掉年轻跨页 head 并强制重放。跨页定向用例必须让 `sqAddrReadyPtr` 指向该 store
的 SQ 槽——这是真实上游约束，不是测试取巧。

### 2.8 尾段掩码用 `genVWmask`（只看 size[1:0]）

`NewStoreUnit.scala:376` 用 `genVWmask(...) >> DCacheVWordBytes`，而 `genVWmask` 的
`LookupTree(sizeEncode.take(2), ...)` 只认 B/H/W/D，因此 16B store 的尾段掩码按
`size mod 4` 取基值，且结果只保留高半字低 7 位。S1 的 `tail_mask` 与
`test_tail_mask_walks_every_reachable_bit` 逐值固定了这一行为。

## 3. 覆盖闭环过程

| DUT | 首轮 | 缺口 | 处理 | 终轮 |
|---|---|---|---|---|
| store_arbiter | 88.72% 功能 | cross 含逻辑不可能的 bin | 重设计 4 个 beat_kind | 100% |
| store_trigger | toggle 650/762 | tdata2 高位未翻转；matchType 宽度误判 | 64 位 walking-one × 4 路；删除不可表达情形 | 762/762 |
| store_delay | 14 FAIL（模型相位错） | 采样约定 + 不可观测的出口 kill | 重定采样语义；差分实验证明出口不可观测 | 14 PASS |
| store_s0 | toggle 2888/3100 | imm/src_0 高位、Q size 未覆盖 | 模型扩展到 size 4..7；64 位 walking-one | 3090/3100 |
| store_s1 | toggle 3610/3872 | tdata2 高位、尾段地址/掩码 | 4×64 位 walking-one；掩码可达值枚举 | 3836/3872 |
| store_s2 | — | 无 | — | 1042/1042 |
| store_s3 | 10 FAIL（写回相位） | 延迟管采样相位 | 改为"进入即写回"语义 | 2502/2506 |
| store_s4 | toggle 570/572 | valid 下降沿 | 补 idle 收尾 | 572/572 |
| new_store_unit | 15 FAIL（组合模型） | 陈旧载荷保留、反馈寄存、priming | 修正三处模型语义后全绿 | 13231/13964 |

所有早期运行目录保留，不追溯改写。失败中有 39 个是**验证侧模型/相位错误**，不是 RTL
缺陷，已在各 gap 文件中如实记录。

## 4. 未覆盖点归因（仅结构性/工具边界）

| 类别 | 点 | 证据 |
|---|---|---|
| `initial` 块内 `if (reset)` | 5 分支（S0/S1/S2/S3/DelayPipeline） | Picker 的 InitClock 在测试能拉 reset 前执行 initial |
| `entrance[2]`、`matchType[0]`、`tail mask[15:7]`、`tail addr[3:0]`、`cmd[2:1]` | 若干 toggle | 生成 RTL 中为字面常量 |
| `io_prefetchTrain_bits_*` | 212 toggle | 父层恒接 0，本配置无预取训练器 |
| 向量 unit-stride trigger 分支 | 3 分支 | `instrType[1]` 在本单元恒 0，无向量生产者 |
| 延迟管 `instrType[2]` | 4 toggle | 预取不进写回管线 |

每条都在 `docs/gaps/*.json` 中有源码行号与理由。

## 5. 边界

- 9 个 DUT 通过**不**代表 LSQ、Sbuffer、DCache 或 MemBlock 通过。
- TLB/PMP/ROB/SQ 在本工程中是测试侧激励，不是它们已验证的证据。
- 父块 UT 保留真实 S0–S4；`pipeOut`/`prefetchTrain` 等未被父层消费的输出按实际端口
  检查或归因为结构常量。
- 未做向量 store、预取 store、原子操作；它们在本配置的 store 地址单元里没有生产者。
