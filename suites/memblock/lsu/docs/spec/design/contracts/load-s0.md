# `LoadUnitS0`：load 请求合成、仲裁与发射

## 1. 模块职责

`LoadUnitS0` 是 `NewLoadUnit` 的第一级。它把四个请求 lane 归一化成 `LoadStageIO`
载荷、按固定优先级仲裁、派生对齐/跨 16B/128 位标记，然后向 TLB、DCache、SQ/Sbuffer
forward、MSHR/TLD forward 和 uncache 通路发出请求，并把选中 beat 打进单个输出寄存器。

**本模块没有 flush/kill 输入**：`pipeOutValid` 只由 `pipeIn_valid` 决定，重定向在 S1 处理。

## 2. 四条 lane

| lane | `entrance` | 说明 |
|---|---|---|
| `unalignTail` | `0x01`（arbiter 常量） | S1 的跨 16B 尾段注入 |
| `replay` 高优先级 | `0x02`（常量） | `replay.entrance[1]=1` |
| `fastReplay` | `entrance[7:3] \| (entrance[2:0] \| 0x04)` | S3 快重放，低 3 位强制带 `0x4` 标记 |
| `replay` 低优先级 | `0x08`（常量） | `replay.entrance[1]=0` 且 replay 比同拍 ldin **更老** |
| `ldin` | `0x40`（常量） | 由 `ExuInput` 合成的新 load |

低优先级 lane 的存在条件（`replayIsLoPrio`）：

```
replay.entrance[1] = 0
且 not (ldin.valid and replay.lqIdx >(ring) ldin.lqIdx)
```

`>(ring)` 是 `(flag_a ^ flag_b ^ (value_a > value_b))`。若 replay 比同拍新发射的 load
**更年轻**，该 replay 两个 lane 都不有效：本拍被丢弃、`replay_ready=0`，下拍重试。

## 3. 仲裁

固定优先级 `unalignTail(0) > replayHi(1) > fastReplay(2) > replayLo(3) > ldin(5)`，
由 `Arbiter7_LoadStageIO` 完成（该叶子已独立验证）。`out_ready = dcacheReq.ready`：

```
pipeIn_valid = arb.valid & dcacheReq.ready
```

`replay_ready = entrance[1] & in1_ready | replayIsLoPrio & in3_ready`
（注意：即使 `replay.valid=0`，该表达式仍可能为 1，是 don't-care 组合值）。

## 4. `ldin` 合成

```
vaddr  = (src_0 + sext(imm[11:0])) mod 2^50
fullva = (src_0 + sext(imm[11:0])) mod 2^64
size   = fuOpType[3:1]
mask   = fuOpType[0] ? 0 : genVWmask(size, vaddr)[15:0]
instrType = fuOpType[0] ? 4 (prefetch) : 1 (scalar)
pftType   = {1'b1, (fuOpType == 0x1)}
noQuery   = (fuOpType == 0x1)
```

`genVWmask`：byte 掩码 `(1<<size)-1` 再左移 `vaddr[3:0]` 后取低 16 位；`size>=4` 视为 16B。

## 5. 对齐、跨 16B 与 128 位

按仲裁优先级从 lane 自身载荷重算（不是从 arbiter 输出反推）：

```
upBound   = ((1<<size)-1) + vaddr[3:0]        // size>=4 时取 15
aligned   = size==0 | size==1&~vaddr[0] | size==2&vaddr[1:0]==0
          | size==3&vaddr[2:0]==0 | size[2]&vaddr[3:0]==0
crossBank = ~noAlignCheck & upBound[4]
is128Req  = unalignTail.valid | (~noAlignCheck & ~upBound[4] & ~vaddr[3] & upBound[3])
align     = ~alwaysUnalign & (noAlignCheck | aligned)
noAlignCheck   = alwaysUnalign | arb.accessType_instrType[2]   // 尾段或 prefetch
alwaysUnalign  = in0_ready & unalignTail.valid
```

`crossBank` 写入 `unalignHead`，同时**抑制 wakeup**：跨 16B 的 load 要等 S1 拆成
head/tail 两个请求后再唤醒。

## 6. TLB 请求

```
tlbReq.valid = (unalignTail.valid | replayHi.valid | replayLo.valid | ldin.valid)
               & dcacheReq.ready
tlbReq.vaddr = 优先级链的 lane vaddr（fastReplay 不在链中，落到 ldin 的 vaddr）
tlbReq.fullva = arb.fullva
tlbReq.checkfullva = firstIssue（= in5_ready & ldin.valid）
tlbReq.hyperinst  = fuOpType[6] & ~fuOpType[0]
tlbReq.hlvx       = fuOpType[6] & fuOpType[5] & ~fuOpType[0]
tlbReq.kill = noQuery
tlbReq.isPrefetch = instrType[2]
tlbReq.no_translate = noQuery
```

`fastReplay` 既不在 valid 项也不在地址链：它是 DCache 数据重放，不再发起翻译。

## 7. DCache 请求

```
dcacheReq.valid = arb.valid & ~(instrType[2] & pftType[0] | uncacheReplay)
dcacheReq.cmd   = {3'b0, instrType[2], 1'b0}        // bit1 = prefetch
dcacheReq.instrtype = {2'b0, {2{instrType[2]}}}     // 0 或 3
vaddr/vaddr_dup/mask/lqIdx 来自仲裁输出
```

- `prefetch_i`（`instrType=4, pftType[0]=1`）只查 TLB，不访问 DCache；
- `prefetch_r`（`pftType[0]=0`）正常访问；
- `uncacheReplay` 由 uncache 旁路通路处理，不发 DCache 请求。

## 8. Forward / bypass 请求

```
sqSbForwardReq = arb.valid, vaddr, sqIdx*, size, loadWait*, waitSqIdx*
uncacheForwardReq.valid = in1_ready & replayHi.valid & replay.uncacheReplay
mshrForwardReq.valid    = in1_ready & replayHi.valid & replay.forwardDChannel
tldForwardReq.valid     = 同上
uncacheBypassReq.valid  = uncacheForwardReq.valid
    lqIdx 取 replay 输入
    isNCReplay   = uncacheReplay & ncReplay
    isMMIOReplay = uncacheReplay & ~ncReplay
```

只有**高优先级 replay** lane 能发起 uncache / MSHR / TLD forward。

## 9. Wakeup

```
needX = lane_granted & lane.accessType_instrType[0]     // 仅 scalar 类
needScalar = firstIssue & ~ldin.fuOpType[0]
wakeup.valid = (need0|need1|need2|need3|needScalar) & ~crossBank
wakeup.rfWen/fpWen/pdest = 对应 lane 的 uop 字段（优先级 0/1 > 2 > 3 > scalar）
```

## 10. 输出寄存器与性能计数

```
pipeOutValid <= pipeIn_valid           // reset 清 0
pipeOutBits  <= arb bits (pipeIn_valid 时), align/unalignHead 用上面派生值
perf_0 = Reg2(pipeIn_valid)            // 发射计数
perf_1 = Reg2(arb.valid & ~dcacheReq.ready)   // 因 DCache 反压丢弃的请求数
```

空拍时载荷保持；没有 flush。

## 11. 语义功能点

| ID | 语义 |
|---|---|
| S0-LANE | 四 lane 的 entrance 重编码、载荷透传与 `ldin` 合成（地址/size/mask/pftType/noQuery） |
| S0-ORDER | hi/lo replay 拆分与 ring 年龄比较；更年轻的 replay 本拍丢弃 |
| S0-ARB | 五路固定优先级仲裁与 `dcacheReq.ready` 反压下的 ready 位图 |
| S0-ALIGN | 对齐判定、`align`/`unalignHead` 输出、跨 16B 抑制 wakeup |
| S0-128 | `is128Req`：尾段恒 1；其余源为"跨 8B 半字但未跨 16B" |
| S0-TLB | TLB 请求 valid/地址/checkfullva/hyperinst/hlvx/kill/isPrefetch |
| S0-DCACHE | DCache 请求抑制（prefetch_i、uncache replay）与 cmd/instrtype 编码 |
| S0-FWD | SQ/Sbuffer 常发；uncache/MSHR/TLD 仅高优先级 replay |
| S0-WAKEUP | wakeup 有效性（排除 prefetch 与 crossBank）与 pdest 选择 |
| S0-REG | 单深度输出寄存器、空拍保持、无 flush、perf 两拍延迟 |

## 12. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:94-380`（sources、entrance、align/crossBank、TLB/DCache/forward/wakeup）
- `XiangShan/src/main/scala/xiangshan/mem/pipeline/package.scala:61-88`（`LoadEntrance`）
- `soc-split/rtl/LoadUnitS0.sv`（本 DUT 全部 wire/assign/always）
- `soc-split/rtl/Arbiter7_LoadStageIO.sv`（下级仲裁器）
