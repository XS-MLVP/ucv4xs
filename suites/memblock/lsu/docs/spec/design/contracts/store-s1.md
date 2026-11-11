# `StoreUnitS1`：store 地址第 1 级（物理地址 / 异常 / SQ 写地址）

## 1. 模块职责

S1 接收 S0 的流水 beat，用 TLB 响应得到物理地址，判定这条 store 能否继续，并把地址
写入 SQ。除输出寄存器外**所有输出都是组合的**：TLB 请求 kill、RS 反馈、`toSqAddr`、
STA nuke 查询、非对齐尾段注入、非对齐队列请求全部与输入同拍产生。

## 2. Kill 关系（三条来源，注意第一条没有 valid 门控）

```
illegalIssue  = pipeIn.valid && pipeIn.illegalIssue
youngCrossHead= pipeIn.valid && instrType[0](scalar) && unalignHead
                && cross4KPage && !isAddrReadyHead
redirectKill  = RobPtr.needFlush(pipeIn.robIdx, redirect)      // 无 pipeIn.valid 门控
kill          = redirectKill || illegalIssue || youngCrossHead
fire          = pipeIn.valid && !kill
```

- **`redirectKill` 不带 `pipeIn.valid`**：这是实际 RTL 的行为（`RobPtr.needFlush`
  本身没有 valid 项）。因此空闲拍上若仍保留着比 redirect 更年轻的 robIdx 载荷，
  `tlbReqKill` 仍可能为 1。它无害（没有在途请求），但必须如实建模，否则会在随机
  测试里出现假失败。
- `illegalIssue` 与 `youngCrossHead` 自带 valid 门控。
- `tlbReqKill = kill`，所以一个非法发射或年轻跨页 head 也会撤销自己的 TLB 请求。

## 3. TLB 响应与反馈

```
tlbHit          = resp.valid && !resp.miss
bothHit         = tlbHit && unalignHeadTlbHit
forceReplay     = scalar && (illegalIssue || youngCrossHead)
feedBackValid   = fire && scalar && !unalignHead || forceReplay
feedBackHit     = (entrance[0] ? bothHit && (!cross4KPage || toUnalignQueue.ready)
                              : tlbHit) && !forceReplay
```

`feedBackSlow.bits.hit` 是"这条 store 可以继续"的语义；`needRSReplay` 在输出寄存器里
记 `feedBackValid && !feedBackHit`。

## 4. SQ 地址写（`toSqAddr`）

`valid = fire && !instrType[2]`（预取不写 SQ）。CBO 特殊化：

| 字段 | CBO | 其它 |
|---|---|---|
| `vaddr` | `{vaddr[49:4], 4'h0}` | `vaddr` |
| `paddr` | `{paddr[47:4], 4'h0}` | `paddr` |
| `size` | `3'h4`（QB） | `size` |
| `wlineflag` | 1 | 0 |

其余：`tlbMiss = !feedBackHit`、`isUnalign = !align`、
`cross16Byte = entrance[0] || unalignHead`、`isLastRequest = !unalignHead`、
`isHyper = resp.excp[0].isHyper`。

## 5. STA nuke 查询（`staNukeQueryReq`）

`valid = fire && tlbHit && !instrType[2]`。字段为 robIdx/sqIdx（来自 pipeIn）、
`paddr = resp.paddr_0`（**不做 CBO 对齐**）、`mask = pipeIn.mask`、
`matchType = {isCbo, 1'b0}`：CBO 为 2（cacheline 粒度），普通 store 为 0（16B 粒度）。

## 6. 非对齐尾段（`unalignTail`）与非对齐队列

```
unalignTail.valid = fire && unalignHead
unalignTail.vaddr = {vaddr[49:4] + 1, 4'h0}
unalignTail.fullva= {resp.fullva[63:4] + 1, 4'h0}
unalignTail.mask  = ((genVWmask(vaddr, size) << vaddr[3:0]) >> 16) & 0x7F
toUnalignQueue.valid = fire && entrance[0] && cross4KPage && bothHit
```

- 尾段掩码用的是 `genVWmask`（只按 `size[1:0]` 取 B/H/W/D 基值），**不是**
  `genVWmask128`。因此 16B store（size 4..7）在尾段掩码上退化为 B/H/W/D 的基值。
  这是固定生成 RTL 的行为，已由 `tail_mask` 与定向用例逐值确认。
- 尾段掩码只有低 7 位可能非零（生成宽度为 `{9'h0, mask[22:16]}`），
  `vaddr/fullva[3:0]` 恒为 0。这些是**结构常量**，不是漏测。
- `toUnalignQueue` 的 valid 不看 `ready`；`ready` 只影响 `feedBackHit`。

## 7. 异常位

| 输出位 | 来源 |
|---|---|
| `exceptionVec[23]` | `tlbHit && (gpf_st \| gpf_ld)`（guest page fault） |
| `exceptionVec[15]` | `tlbHit && (pf_st \| pf_ld)`（page fault） |
| `exceptionVec[7]` | `tlbHit && (af_st \| af_ld)`（access fault） |
| `exceptionVec[3]` | trigger action == 0（breakpoint） |
| `exceptionVec[19]` | 直通 pipeIn |
| `hasException` | 上述四类或 trigger action == 1（debug mode） |
| `tlbException_vaNeedExt/isHyper`、`isForVSnonLeafPTE`、`gpaddr` | 直通 TLB 响应 |

异常位要求 `tlbHit`：TLB miss 时不会因为响应里的 excp 位而报异常。

## 8. LFST 与 trigger

- `updateLFST.valid = fire && tlbHit && scalar && !entrance[0]`（只有缓存标量 store 更新）。
- store trigger：`isVectorUnitStride = instrType[1] && fuOpType[6:5] == 0`，
  `isCbo = accessType.isCbo`，`vaddr/mask` 来自 pipeIn；输出 action 进入
  `pipeOut.uop.trigger` 与 breakpoint 异常位。

## 9. 输入合法域与 don't-care

- `pipeIn`：S0 的输出。`illegalIssue/align/unalignHead/cross4KPage/isAddrReadyHead`
  是 S0 派生的限定符，S1 只消费不重算。
- `tlbResp`：`valid=0` 时字段 don't-care；`miss=1` 时 `pbmt` 被清零、异常位不生效。
- `csrTrigger`：4 路 trigger 配置，语义同 `MemTrigger_3` 合同。
- `entrance=0x4`（vectorIssue）在本配置没有生产者（S0 只产生 0x1/0x8），但它是一个
  普通输入端口；边界用例驱动它并记录实际行为（走非尾段路径），不把它当作正常流量。

## 10. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala:200-470`（S1 全部逻辑）
- `NewStoreUnit.scala:376`（尾段掩码用 `genVWmask >> DCacheVWordBytes`）
- `XiangShan/src/main/scala/xiangshan/mem/MemCommon.scala:46-57`（`genVWmask` 只看 `size.take(2)`）
- `soc-split/rtl/StoreUnitS1.sv`（本 DUT，含 `kill` 无 valid 门控与 CBO 对齐）
