# `NewLoadUnit`：load 执行流水线的整体组合

## 1. 模块边界

本 DUT 是真实的 `NewLoadUnit` 生成 RTL，内部保留：

```
s0 (LoadUnitS0)  ->  s1 (LoadUnitS1)  ->  s2 (LoadUnitS2)  ->  s3 (LoadUnitS3)  ->  s4 (LoadUnitS4)
                 <-  s1.unalignTail（尾段环回 S0 的 unalign 通道）
                 <-  s3.fastReplay（快速重放到 S0 的 fast 通道）
dataPath (LoadUnitDataPath) 由 s1.dataPathMeta 驱动，输出直接成为 ldout/vldout 的写回数据
s0 内部的 Arbiter7_LoadStageIO、s1 内部的 MemTrigger 也都是真实子模块
```

外部环境（LSQ 的 SQ/Sbuffer forward、DCache/Uncache、TLB、PMP、ROB 的 redirect/robHeadPtr、
RAR/RAW 查询响应、staNukeQuery、CSR trigger）由协议代理提供。这些代理只提供协议响应，
不作为相应子系统已验证的证据。

**没有跨模块联合 harness**：本 DUT 只验证 `NewLoadUnit` 自身及其真实子模块的组合。

## 2. 流水与时序（实测）

| 事件 | 时刻 |
|---|---|
| `ldin` 被 S0 接收 | t0（`ldin_ready=1`） |
| 同一拍的 S0 请求（TLB/DCache/SQ/Sbuffer/MSHR/TLD/uncache） | t0（组合） |
| beat 进入 S1（TLB 响应必须在**这一拍**给出） | t1 |
| beat 进入 S2（forward/DCache 响应在这一拍） | t2 |
| beat 进入 S3：`ldout`/`vldout`/`lqWrite`/`exceptionInfo` 组合可见 | t2（S3 的 pipeIn = S2 的 pipeOut） |
| 未对齐 head 的 tail 注入 | t1（S1 组合）→ t1 边沿进 S0 |
| head/tail 在 S3 合并（经 S4 环回） | t3 |

> 关键：S3 的写回组合输出在 beat 处于 S3 **pipeIn** 时就有效，因此从 S1 的
> `pipeOut` 起算只差一拍；整体从 `ldin` 到写回是 **3 个时钟沿**。

## 3. 跨级数据通路

```
S0 -> S1 : pipeOut 寄存器（含 align/unalignHead 派生位）
S1 -> S2 : pipeOut 寄存器（含 TLB 合并后的 paddr/fullva/pbmt/异常）
S2 -> S3 : pipeOut 寄存器（含 cause_0..cause_11、shouldWakeup/shouldWriteback）
S3 -> S4 : pipeOut 寄存器（head 的合并信息）
S4 -> S3 : unalignConcat（组合直通），供 S3 做 head/tail 合并与 LQ cause 覆盖
```

- **TLB 响应**：`io_tlb_resp_*` 在 beat 位于 S1 的拍被采样；miss 会在 S2 变成
  `cause_3`，并屏蔽 `ldout`（该 beat 走 replay）。
- **DCache 数据**：`io_dcache_resp_bits_data` 在 beat 位于 S2 的拍被数据通路合并；
  合并结果在 S3 拍成为 `io_ldout_toIntRf_bits_data` / `io_vldout_toVecRf_bits`。
- **head/tail 环回**：S1 在 t1 产生尾段（下一行地址、溢出字节掩码），同一沿进入 S0
  的 `unalignTail` 通道；尾段在 t2 进入 S1、t3 进入 S2、t3 进入 S3（与 head 的 S4
  环回相遇），S3 的 `cancel` 成立时把 head+tail 作为一条写回，数据通路的
  `s4ShiftHead | tail << 8*(16-offset)` 给出合并结果。
- **fast replay 环回**：S3 的 `fastReplay` 直接驱动 S0 的 fast 通道（entrance 带
  `0x04`）；被接受的 fast replay 不写 LQ（`lqWrite_valid=0`），随后重新走流水线。

## 4. 各阶段职责（详见各自合同）

| 阶段 | 合同 | 职责 |
|---|---|---|
| S0 | `load-s0.md` | 五 lane 仲裁、地址合成、对齐/跨 16B/128 位、TLB/DCache/forward 请求、wakeup |
| arbiter | `load-arbiter.md` | 五源固定优先级与逐字段 mux |
| S1 | `load-s1.md` | 三级 redirect kill、TLB 合并、异常、trigger、tail 注入、replay 判定 |
| S2 | `load-s2.md` | forward 覆盖、NC/MMIO、异常重算、C0..C11、fast replay、RAR/RAW 查询 |
| S3 | `load-s3.md` | head/tail 合并、写回/唤醒、LQ 写入、revoke、rollback、exceptionInfo |
| S4 | `load-s4.md` | head beat 的组合直通（供 S3 合并） |
| dataPath | `load-datapath.md` | 字节合并、移位、符号/零扩展与 NaN boxing |

## 5. 手摇与取消

- **S0**：`ldin_ready = ~更高优先级 lane 有效 & dcache_req_ready`；被反压的 beat
  不进入 S0 寄存器（上游自行保留）。
- **S1..S3**：没有 ready 端口，每拍都消费并前移；重定向通过 `redirect` 取消。
- **S3 的 `pipeOut`** 只在 head/tail 合并（`cancel`）时有效，其余写回走
  `ldout`/`vldout`。
- **S2 的硬件预取**（`instrType[2] & ~pftType[1]`）被消费但不写回，只训练预取器。

## 6. 输出合同（父块 273 个输出全部被检查）

| 组 | 语义 |
|---|---|
| `io_ldin_ready`/`io_replay_ready` | S0 的输入反压 |
| `io_tlb_req_*` | S0 发出的翻译请求 + S1 的 kill/no-translate 地址 |
| `io_dcache_req_*`/`io_dcache_is128Req` | S0 的 DCache 请求（prefetch_i/uncache 被抑制） |
| `io_sqForward_*`/`sbufferForward_*`/`uncacheForward_*`/`mshrForward_*`/`tldForward_*`/`uncacheBypass_*` | S0 请求 + S1 paddr/kill |
| `io_wakeup_*` | S0 的标量唤醒 |
| `io_dcache_s1_kill`/`io_dcache_s2_kill` | S1/S2 的取消 |
| `io_rarNukeQuery_*`/`io_rawNukeQuery_*` | S2 的查询与 S3 的 revoke |
| `io_ldout_toRob_*`/`io_vldout_toRob_*`/`io_ldout_to{Int,Fp}Rf_*`/`io_vldout_to{Vec,V0}Rf_*`/`io_vldS3WakeUp_*` | S3 写回与 RF 写 |
| `io_lqWrite_*` | S3 的 LQ 更新（含 13 位 one-hot cause） |
| `io_rollback_*`/`io_exceptionInfo_*`/`io_cancel` | 回滚、异常记录、取消 |
| `io_prefetchTrainHintS1/S2`/`io_prefetchTrain_*` | 预取提示与 S2 训练（父级再延一拍） |
| `io_swInstrPrefetch_*` | 软件预取分类 |
| `io_perf_0..7_value` | 各 stage 计数器再经父级两拍延迟 |

## 7. 语义功能点

| ID | 语义 |
|---|---|
| NLU-E2E | 一条 load 从 ldin 到 ldout/lqWrite/RF 写的跨级时序与字段 |
| NLU-TAIL | 跨 16B head 的尾段环回、合并写回与数据拼接 |
| NLU-REPLAY | 高/低优先级 replay 的通道选择、更年轻 replay 的丢弃 |
| NLU-FAST | fast replay 反馈（MSHR nack / bank conflict / nuke-first / data-invalid）与 LQ 抑制 |
| NLU-KILL | redirect 对在途 beat 的取消（S1/S2/S3） |
| NLU-TLB | TLB miss/fault/noQuery 在父块的可见结果 |
| NLU-UNCACHE | NC/MMIO 的 bypass 数据通路与 DCache 抑制 |
| NLU-VEC | 向量 load 的 vldout/v0 写与 128 位数据 |
| NLU-TRIG | trigger 断点/debug action 随 beat 传播 |
| NLU-NUKE | RAR/RAW 查询字段、revoke 与 rollback |
| NLU-PERF | 预取训练与 8 个性能计数器的延迟 |
| NLU-REG | 父级训练寄存器与计数器寄存器 |

## 8. 依据

- `soc-split/rtl/NewLoadUnit.sv`（4013 行，本 DUT）
- 子模块合同与 `docs/gaps/load_*.json`
- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala`
