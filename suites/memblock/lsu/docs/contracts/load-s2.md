# `LoadUnitS2`：forward 合并、replay 原因与 fast replay

## 1. 模块职责

S2 判断一条已完成翻译的 load 能否被现有数据源满足，并决定是否重放：

- 合并 SQ / Sbuffer / uncache / MSHR / TLD 的 forward 响应（按字节）；
- 区分 NC / MMIO（`pbmt` + PMP）；
- 重算 AF/AM/HWE 异常；
- 产生 11 种 replay 原因 `cause_0..cause_11`；
- 判定 `shouldFastReplay`、`rrBankConflictFastReplay`；
- 发出 RAR/RAW nuke 查询（SQ 地址冲突/数据冲突）；
- 输出 wakeup / writeback / matchInvalid 状态；
- 训练预取器（`prefetchTrain`）。

**2026-10-26复核更正**：当前拍 redirect 会 kill；硬件预取是 `endPipe`，在S2完成而不继续到S3，不应与取消语义混同。性能事件的合法硬件预取miss反例见 `docs/bug-reports-20261026/01-LSU-HWPF-MISS-001.md`。
异常和 trigger 断点**不**抑制输出（它们要写回 ROB）。

## 2. forward 覆盖

```
mask = pipeIn.mask
fullForward = ( ( ~(sqMask|sbMask|uncMask) & mask ) == 0 & ~sqDataInvalid )
            | ( ( ~mshrMask & mask ) == 0 )
            | tldForwardResp.valid
needDCacheAccess = ~fullForward & ~isUncache & ~uncacheReplay
```

- `forwardMask_i` 是字节 i 的覆盖位；只有 load 的所有字节都被覆盖才算 complete。
- `sqDataInvalid = sqForwardResp.valid & dataInvalid_valid` 会让 SQ 覆盖失效。
- `mask == 0` 时覆盖判断恒真（零字节访问）。

## 3. NC/MMIO 分类

```
mmioBase = tlbAccessResult[1] & ~(exc5|exc13|exc21)     // 只在 TLB hit 且无 fault 时
isNC   = mmioBase & pbmt==1
isMMIO = mmioBase & (pbmt==2 | (pbmt==0 & pmp_mmio))
isUncache = isNC | isMMIO
```

## 4. 异常重算

```
pmpUnaccessable = pmp_ld & tlbAccessResult[1]
af  = exc5 | pmpUnaccessable
    | instrType[1] & isUncache          // 向量访问 uncache
    | ~align & isMMIO                   // MMIO 非对齐
    | mshrDenied | tldDenied | bypassNderr
am  = ~align & instrType[0] & isNC & ~pmpUnaccessable
hwe = exc19 | mshrCorrupt | tldCorrupt | bypassDerr
```

`*Corrupt` 只在 `~denied` 时有效。`af` 写 `exceptionVec_5`，`am` 写 `exceptionVec_4`，`hwe` 写
`exceptionVec_19`。

## 5. Replay 原因

`gen = {trigger==1, exc23, exc21, hwe, exc15, exc13, exc7, exc6, af, am, exc3}`，
`troubleMaker = ~instrType[2] & ~(gen.orR | isMMIOReplay)`。

| cause | 语义 |
|---|---|
| 0 | uncache 首次访问；NC replay 且数据仍无效/nack/nuke/forwardInvalid |
| 1 | `sqForwardResp.forwardInvalid` |
| 2 | `storeSetHit & sqForwardResp.addrInvalid_valid` |
| 3 | `tlbAccessResult[2]`（TLB miss）**或** `specialModeRequest`（不受 troubleMaker 门控） |
| 4 | `sqDataInvalid` |
| 5 | `needDCacheAccess & dcacheMSHRNack` |
| 6 | `needDCacheAccess & dcacheResp.miss` |
| 8 | `needDCacheAccess & dcacheBankConflict` 或 `unalignHead & pipeIn.shouldFastReplay` |
| 9 | RAR 查询 nack |
| 10 | RAW 查询 nack |
| 11 | nuke（store-load 冲突） |

`nuke = (nukeMatch & ~tlbAccessResult[2]) | pipeIn.cause_11`；nukeMatch 按
`matchType==2 ? paddr[47:6] : paddr[47:4]` 比较，robIdx 用 ring 年龄，mask 必须重叠。

RAR/RAW 查询 valid：

```
rawValid = ~isMMIOReplay & ~instrType[2] & ~pipeIn.cause_11 & pipeIn.valid
dataValid = fullForward | isNCReplay | (needDCacheAccess & ~miss & ~bankConflict)
```

## 6. Fast replay

```
fastEligible   = ~entrance[2] & ~(unalignHead | entrance[0])
               & ~tlbAccessResult[2] & ~specialModeRequest
bankConflict   = cause_8 & {cause_0..cause_6} == 0
shouldFastReplay = pipeIn.shouldFastReplay
  | (fastEligible & ( cause_5 且 cause_0..4 全 0
                    | bankConflict
                    | cause_11 且除 cause_2(被 nukeFirst 抵消) 外全 0
                    | cause_4 且 cause_0..3 全 0 且 stdDataWrite 与 dataInvalidSqIdx 匹配 )
     & ~gen.orR)
rrBankConflictFastReplay = ~kill & fastEligible & bankConflict & dcacheRRBankConflict
```

`nukeFirst = storeSetHit & (nuke0.sqIdx == waitSqIdx & nuke0.valid | nuke1...)`，与
`pipeIn.fastReplayNukeFirst` 一起解除 `cause_2` 对 fast replay 的阻止。

## 7. wakeup / writeback

```
shouldWakeup = ~(causeOrR | pipeIn.shouldFastReplay) & ~isUncache & ~gen.orR & ~isSwPrefetch
shouldWriteback = shouldWakeup | |{trigger==1, exc23, exc21, hwe, exc15, exc13,
                                  exc7, exc6, af, am, exc3}
                | matchInvalid | isSwPrefetch
```

`matchInvalid` 是 SQ/Sbuffer/uncache 三路 `matchInvalid` 的或；输出字段还额外与
`troubleMaker` 相与。

## 8. 输出寄存器

```
pipeOutValid <= ~(kill | isHwPrefetch) & pipeIn.valid
pipeOutBits  <= 合并后的 beat (pipeIn.valid 时，即使 kill 也写)
```

硬件预取 (`instrType[2] & ~pftType[1]`) 被消费但不写回/唤醒。

perf：

```
perf_0 = Reg2(valid)
perf_1 = Reg2(valid & ~kill & cause_6)
perf_2 = Reg2(valid & isHwPrefetch)
perf_3 = Reg2(valid & isHwPrefetch & ~kill & cause_6)   // 原RTL结构恒0，但这是已确认的性能事件缺陷，不是规范期望
```

`perf_3` 的 `isHwPrefetch = instrType[2] & ...` 与 `cause_6` 的 `troubleMaker = ~instrType[2] & ...`
互斥，因此该计数器永远为 0（保留为观察项，见 gap 文件）。

## 9. 组合输出

```
unalignTailValid = pipeIn.valid & entrance[0]
dcacheKill = |{kill, trigger==1, exc23, exc21, hwe, exc15, exc13, exc7, exc6, af, am, exc3}
           | isUncache | uncacheReplay | specialModeRequest
rrBankConflictFastReplayCandidate = pipeIn.valid & rrBankConflictFastReplay
prefetchTrain.valid = valid & tlbAccessResult[1] & ~gen.orR & ~isUncache
                    & ~uncacheReplay & (entrance[6]|entrance[5]) & ~instrType[1]
```

## 10. 语义功能点

| ID | 语义 |
|---|---|
| S2-KILL | 当前 redirect / 硬件预取的输出抑制 |
| S2-FWD | 五路 forward 的字节覆盖与 `sqDataInvalid` |
| S2-CLASS | NC/MMIO 分类（pbmt + PMP + hit） |
| S2-EXC | AF/AM/HWE 重算（PMP、向量 uncache、非对齐、denied/corrupt） |
| S2-CAUSE | C0..C11 每个 reason 的触发条件与集合互斥 |
| S2-FAST | fast replay 四条路径与 eligibility |
| S2-QUERY | RAR/RAW 查询 valid/dataValid/字段 |
| S2-STATUS | shouldWakeup/shouldWriteback/matchInvalid/causeOrR |
| S2-TRAIN | prefetchTrain 与 isHwPrefetch/isSwPrefetch |
| S2-REG | 输出寄存器、空拍保持、perf 计数 |

## 11. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:875-1360`（S2 逻辑）
- `soc-split/rtl/LoadUnitS2.sv`（本 DUT）
