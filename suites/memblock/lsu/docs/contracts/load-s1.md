# `LoadUnitS1`：TLB 合并、异常/trigger、tail 注入与 replay 判定

## 1. 模块职责

S1 接收 S0 的请求 beat，做四件事：

1. **翻译合并**：把 TLB 响应（paddr/fullva/pbmt/gpaddr/异常）合并进 beat；
2. **取消/异常判定**：三级 redirect 流水 kill、TLB miss、load 异常、special mode；
3. **拆分未对齐访问**：跨 16B 的 head 在 S1 发出下一行的 tail 注入；
4. **重放判定**：`shouldFastReplay`、`fastReplayNukeFirst`、`cause_11`（S1 只检测 nuke）。

本模块**没有 ready 端口**（父层把 S1 的 pipeIn/pipeOut ready 固定为 1），因此每拍都消费并前移；
输出 beat 的有效性只由 `~kill & pipeIn.valid` 决定。

## 2. redirect kill

```
kill = ~pipeIn.valid
     | redirect.valid      & match(redirect)
     | redirectNext.valid  & match(redirectNext)
     | redirectNextNext.valid & match(redirectNextNext) & pipeIn.entrance[0]

match(r) = r.level & same(r) & pipeIn.isFormer == r.isFormer
         | pipeIn.flag ^ r.flag ^ (pipeIn.value > r.value)
         | same(r) & ~pipeIn.isFormer & r.isFormer
```

- `level=1`：比较整个 ROB entry（允许 `isFormer` 不同则同样命中）。
- `level=0`：只比较 ROB index；“更年轻”（ring 比较）的 load 被 kill。
- 同 entry 的两个 uop 用 `isFormer` 排序：`isFormer=0` 是前半，被 `isFormer=1` 的 redirect kill。
- `redirectNext`/`redirectNextNext` 是各级 delay 1/2 拍的 redirect 寄存器；第 2 级只 kill
  **tail 注入**（`entrance[0]=1`）——因为 tail 是在 head 通过 S1 的下一拍才注入 S0 的。

**采样相位**：寄存器更新用的是"边沿前"的 kill；Picker 在 `Step` 后读到的组合输出
（`tlbReqKill`/`dcacheKill`/`dataPathMeta.valid`/`forward*Kill`）用的是"边沿后"的 redirect
流水与当拍输入。两者在 UVM 里分别是"本拍请求"与"下一拍请求"，参考模型分别计算。

## 3. TLB 合并

```
tlbHit  = tlbResp.valid & ~tlbResp.miss & ~pipeIn.noQuery
tlbMiss = tlbResp.valid & tlbResp.miss
paddr   = pipeIn.noQuery ? (bypass.valid ? bypass.paddr : pipeIn.paddr)
                         : tlbResp.paddr_0
noQueryPAddr = bypass.valid ? bypass.paddr : pipeIn.paddr
```

- `io_tlbPAddr = noQueryPAddr`（只用于 no-translate 路径）；
- `io_dcachePAddr = noQuery ? noQueryPAddr : tlbResp.paddr_1`（DCache 用 TLB 的第二个口）；
- 所有 forward 请求的 paddr 都用 `paddr`（第 0 口）。

输出寄存器字段：

| 字段 | 值 |
|---|---|
| `fullva` | `tlbResp.fullva` |
| `tlbAccessResult` | `noQuery ? 1 : tlbHit ? 2 : 4` |
| `tlbException_vaNeedExt/isHyper` | `tlbResp.excp_0_*` |
| `pbmt` | `tlbHit ? tlbResp.pbmt_0 : 0` |
| `gpaddr` | `tlbResp.gpaddr_0` |
| `isForVSnonLeafPTE` | `tlbResp.isForVSnonLeafPTE` |

## 4. 异常

```
pf  = tlbHit & excp_0_pf_ld
af  = tlbHit & excp_0_af_ld
gpf = tlbHit & excp_0_gpf_ld
tlbException = pf | af | gpf
bp  = (triggerAction == 0)
```

`exceptionVec_13/5/21/3` 分别写 pf/af/gpf/bp；其余 exception 位从 pipeIn 透传。
**fault 位只在 TLB hit 时置起**（miss 时不报异常）。breakpoint **不** kill DCache。

Trigger 是真实的 `MemTrigger` 子模块，参数为 load 变体：

```
is_vector_stride = pipeIn.instrType[1] & pipeIn.fuOpType[6:5] == 0
is_prf           = pipeIn.instrType[2]
```

## 5. kill 的下游差异

```
io_tlbReqKill          = kill | specialRequest
io_dcacheKill          = kill | tlbMiss | tlbException | specialRequest
sqForwardKill          = 同上（dcacheKill）
sbufferForwardKill     = 同上
uncacheForwardKill     = kill          // 不含 miss/异常/special
io_dataPathMeta.valid  = pipeIn.valid & ~kill
```

`specialRequest = specialMode & pipeIn.robIdx != robHeadPtr`（三字段比较）。

## 6. 未对齐 tail 注入

```
unalignTail.valid  = pipeIn.valid & pipeIn.unalignHead
unalignTail.vaddr  = ((vaddr[49:4] + 1) << 4)     // 下一行
unalignTail.fullva = ((fullva[63:4] + 1) << 4)
unalignTail.mask   = ((base << vaddr[3:0]) >> 16) & 0x7FFF
    base = (1<<size)-1 (size=fuOpType[3:1] < 4) 或 0xFFFF (fuOpType[3]=1)
```

注意：tail 的 mask 只保留**溢出到下一行**的字节（低 4 位恒 0、bit15 恒 0）。
tail **不**被 kill 门控：被 kill 的 head 仍会注入 tail，下一拍由 redirectNextNext 再 kill 它。

其余字段（uop、entrance、mask 之外的地址字段）透传 head；`paddr/mshrId/replayQueueIdx/ncReplay` 也透传
（tail 的地址由 S0 重新翻译）。

## 7. Replay 判定

```
shouldFastReplay = unalignTail.valid & ~unalignTail.ready & ~tlbMiss
                   & ~(tlbException | bp)
fastReplayNukeFirst = storeSetHit & (nuke0.sqIdx == waitSqIdx & nuke0.valid
                                   | nuke1.sqIdx == waitSqIdx & nuke1.valid)
```

`cause_11`（C_NK：nuke）对每个 `staNukeQueryReq`：

```
match = valid
      & (matchType==2 ? paddr[47:6]==req.paddr[47:6] : paddr[47:4]==req.paddr[47:4])
      & (pipe.robIdx >(ring) req.robIdx
         | 同 index & ~pipe.isFormer & req.isFormer)
      & |(req.mask & pipe.mask)
cause_11 = (match0 | match1) & (tlbHit | noQuery)
```

## 8. 其它组合输出

```
prefetchTrainHint    = pipeIn.valid & ~kill & (entrance[6] | entrance[5]) & ~isSwInstrPrefetch
swInstrPrefetch.valid= pipeIn.valid & isSwInstrPrefetch
    isSwInstrPrefetch = instrType[2] & pftType[1] & pftType[0]
```

## 9. 输出寄存器与 perf

```
pipeOutValid <= ~kill_reg & pipeIn.valid          // 无 reset 外其它清空
pipeOutBits  <= stageInfo (pipeIn.valid 时, 即使 kill 也写)
perf_0 = Reg2(pipeIn.valid)
perf_1 = Reg2(pipeIn.valid & tlbResp.miss)
```

## 10. 语义功能点

| ID | 语义 |
|---|---|
| S1-KILL | 当前/延迟 1 拍/延迟 2 拍（仅 tail）三级 redirect kill，level/isFormer/ring 年龄 |
| S1-TLB | hit/miss/noQuery 的 paddr 三选一、双端口、fullva/pbmt/gpaddr/excp 合并 |
| S1-EXC | pf/af/gpf 仅 hit 时置起；bp 来自 trigger 且不 kill DCache |
| S1-TRIG | load 变体 trigger（标量/向量 unit-stride/prf） |
| S1-KILLPATH | TLB/DCache/SQ/Sbuffer/uncache kill 的集合差异 |
| S1-TAIL | 下一行地址、溢出字节掩码、被 kill 仍注入 |
| S1-REPLAY | shouldFastReplay、fastReplayNukeFirst、cause_11 |
| S1-META | dataPathMeta 的 bankOffset/fuOpType/fpWen/NC/MMIO/unalignHead |
| S1-PREF | prefetchTrainHint 与 swInstrPrefetch |
| S1-REG | 输出寄存器（kill 也写 payload）、空拍保持、perf 两拍延迟 |

## 11. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:496-745`（S1 逻辑）
- `soc-split/rtl/LoadUnitS1.sv`（本 DUT）
- `soc-split/rtl/MemTrigger.sv`（child，load 变体）
- `docs/contracts/load-trigger.md`（child 的独立验证）
