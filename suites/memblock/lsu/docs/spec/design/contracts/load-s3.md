# `LoadUnitS3`：写回、head/tail 合并、LQ 更新与 replay/revoke

## 1. 模块职责

S3 是 load 的提交级。它把 S2 的处理结果变成四类可观察动作：

1. **写回 ROB**：标量 load 走 `ldout`，向量 load 走 `vldout`；
2. **唤醒寄存器**：`shouldWakeup` 时按 `rfWen/fpWen/v0Wen/vecWen` 写对应 RF；
3. **写 LQ**：记录地址、异常向量、replay 原因 one-hot 与 replay 提示；
4. **重放/唤醒回滚**：`fastReplay` 回 S0、`revokeLastCycle`/`revokeLastLastCycle`
   通知 replay queue、`rollback` 触发前端回滚。

## 2. kill 与 head/tail 合并

```
kill   = redirect.valid & (level & same & isFormer 相等
                         | robIdx 环比较更新
                         | same & ~pipe.isFormer & redirect.isFormer)
cancel = pipe.unalignHead & unalignTailValid
```

- `kill` 只来自**当前拍** redirect（S3 没有延迟 redirect 流水）。
- `cancel` 表示"head 还在 S3、tail 已到达"：head 的写回被取消，改为输出合并 beat。
- `pipeOutValid = ~(kill | ~cancel) & pipeIn.valid`：
  **`pipeOut` 只在 tail 到达时有效**，即 S4 只接收"head+tail 合并"的 beat。

`unalignConcat`（S4 的 head beat）在 S3 内的用法：

| 情形 | 行为 |
|---|---|
| `concat.valid & hasException` | 用 **tail** 的异常向量/地址替换 head 的 |
| `concat.valid & causeOrR` | LQ 的 replay 原因、tlbId/tlbFull、specialModeRequest 取 **head(tail) 的** |
| `concat.valid` | LQ 的 vaddr/mask/paddr 取 tail 的 |

## 3. 写回与唤醒

```
s3Exception        = |{exc23,21,19,15,13,7,6,5,4,3} | (trigger == 1)
headAlwaysWriteback= s3Exception | s3MatchInvalid
writebackDependOnTail = shouldWriteback & ~s3Exception & ~s3MatchInvalid
shouldWakeup       = pipe.shouldWakeup & (~concat.valid | concat.shouldWakeup)

writebackArmed = concat.valid
                 ? (concat.headAlwaysWriteback
                    | concat.writebackDependOnTail & pipe.shouldWriteback)
                 : pipe.shouldWriteback

ldoutValid  = pipeIn.valid & writebackArmed & ~vecWen & ~cancel
vldoutValid = pipeIn.valid & writebackArmed &  vecWen & ~cancel
```

- 有异常的 head **不等待 tail**（`headAlwaysWriteback=1`），立即写回。
- 无异常的 head 只在 tail 允许时才写回（`writebackDependOnTail`，且用 head 自己的
  `shouldWriteback` 门控）。
- **RF 写只看 `shouldWakeup`，不看 `writebackArmed`**：
  `intRf/fpRf/v0Rf/vecRf = valid & ~cancel & wen & shouldWakeup`。

## 4. LQ 写

```
lqWriteValid = pipeIn.valid & ~(shouldFastReplay & fastReplay_ready & allowRR) & ~cancel
allowRR      = ~(shouldFastReplay & rrBankConflictFastReplay) | rrBankConflictFastReplayGrant
```

- 被接受的 fast replay 不写 LQ（同一 beat 直接回 S0）；被反压的 replay 仍写。
- RR bank-conflict replay 必须拿到 `rrBankConflictFastReplayGrant` 才算被接受。

LQ 字段：

| 字段 | 来源 |
|---|---|
| 异常向量 | 合并后的 `exceptionVec_*`（tail 有异常则用 tail 的） |
| `vaddr/mask/paddr` | tail（`concat.valid` 时）否者 head |
| `fullva/gpaddr/isForVSnonLeafPTE` | tail 有异常时用 tail，否则 head |
| `nc` | `head.nc | (uncacheReplay & ncReplay)` |
| `mmio` | head |
| `memBackTypeMM` | `~pmp_mmio` |
| `isvec` | `instrType[1]` |
| `alignedType` | `size` |
| `isLoadReplay` | `entrance[1] | entrance[3] | (tail.entrance[1] | tail.entrance[3]) & tail.valid` |
| `schedIndex` | `replayQueueIdx` |
| `updateAddrValid` | `ldoutValid | vldoutValid` |
| `specialModeEligible` | `concat.valid & (cause3|cause5|cause6)`（cause 取自 head 或 tail 的有效集） |
| `rep_info_need_rep` | `headReplay | causeOrR` |
| `rep_info_last_beat` | `paddr[5]` |
| `rep_info_cause_N` | 13 位 one-hot，见下 |

replay 原因 one-hot（最高优先级者胜）：

```
cause_0→bit0, 1→bit1, 2→bit2, 3→bit3, 4→bit4, 5→bit5, 6→bit6,
8→bit8, 9→bit9, 10→bit10, 11→bit11
bit7 与 bit12 恒 0（cause 7/12 不存在）
```

## 5. fast replay 与 revoke

```
fastReplayValid = pipeIn.valid & ~kill & shouldFastReplay & allowRR
s3Revoke        = s3Exception | causeOrR
s4HeadRevoke    = concat.hasException | concat.causeOrR
revokeLastCycle      = s3Revoke | concat.valid & s4HeadRevoke
revokeLastLastCycle  = concat.valid & ~s4HeadRevoke & s3Revoke
```

`revokeLastLastCycle` 表示"tail 自己干净，但前一个 head 需要 revoke"——replay queue
用这两个信号定位要撤销的 entry。

## 6. rollback

```
s3RarViolation = rarResp.valid & rarResp.nuke & csrCtrl.ldld_vio_check_enable & ~s3Exception
s3MatchInvalid = pipe.matchInvalid & ~s3Exception
matchInvalid   = s3MatchInvalid | concat.valid & concat.matchInvalid
rollbackValid  = pipeIn.valid & (s3RarViolation
                                | concat.valid & concat.shouldRarViolation
                                | matchInvalid) & ~cancel
rollback.level = matchInvalid
```

异常会屏蔽 RAR violation 与 match-invalid（异常优先）。

## 7. exceptionInfo

```
exceptionInfoValid = ldoutValid & ~(uncacheReplay & ~ncReplay)   // 排除 MMIO
```

字段：ROB 索引、合并后的异常向量、`vaddr = 合并后的 fullva`、`vaNeedExt`（tail 优先）、
`isHyper`、`gpaddr[49:0]`、`isForVSnonLeafPTE`。

## 8. 其它组合输出

```
io_cancel = pipeIn.valid & (cancel | (~shouldWakeup & instrType[0]))
io_vldS3WakeUp_wen    = vecWen & valid & ~cancel & shouldWakeup
io_vldS3WakeUp_pdest  = pdest[6:0]
io_vldout_pdest       = pdest[7:0]
io_ldout_toRob.debugInfo_isMMIO = uncacheReplay & ~ncReplay
io_ldout_toRob.debugInfo_isNCIO = uncacheReplay & ncReplay & pmp_mmio
```

## 9. 输出寄存器

```
pipeOutValid <= ~(kill | ~cancel) & pipeIn.valid      // reset 清 0
pipeOutBits  <= pipeIn 字段 (pipeIn.valid 时)
```

`pipeOut` 只带 head 的原样字段（不做 tail 合并），并附加：
`matchInvalid = s3MatchInvalid`、`hasException = s3Exception`、
`headAlwaysWriteback`、`writebackDependOnTail`、`shouldRarViolation`。

## 10. 语义功能点

| ID | 语义 |
|---|---|
| S3-KILL | 当前 redirect kill |
| S3-CANCEL | head/tail 取消、`pipeOut` 只在合并时有效 |
| S3-CONCAT | tail 异常/地址替换 head、tail-only 载荷 |
| S3-WB | 写回条件（异常优先、依赖 tail）与 ldout/vldout 分流 |
| S3-RFW | 四条 RF 写通路与 wakeup 门控 |
| S3-LQ | LQ 写入条件、字段合并、replay one-hot、specialMode |
| S3-REPLAY | fastReplay 与 RR grant |
| S3-REVOKE | 两级 revoke 的编码 |
| S3-ROLLBACK | RAR violation / matchInvalid 与异常屏蔽 |
| S3-EXCINFO | 标量非 MMIO 的异常记录 |
| S3-REG | pipeOut 寄存器与空拍保持 |

## 11. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:1359-1730`（S3）
- `soc-split/rtl/LoadUnitS3.sv`（本 DUT）
