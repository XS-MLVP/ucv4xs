# `Arbiter7_LoadStageIO`：S0 load 请求源仲裁

## 1. 模块职责

`NewLoadUnit` 的 S0 把 7 个 load 请求源合并成一条流水线入口。固定优先级（源码注释
`NewLoadUnit.scala:94-102`）：

| 优先级 | 源码名 | `LoadEntrance` | 生成 RTL 端口 |
|---:|---|---|---|
| 0 | `unalignTail` | `unalignTail` = `0x01` | `io_in_0` |
| 1 | `replayHiPrio` | `replayHiPrio` = `0x02` | `io_in_1` |
| 2 | `fastReplay` | 自带（S3 透传） | `io_in_2` |
| 3 | `replayLoPrio` | `replayLoPrio` = `0x08` | `io_in_3` |
| 4 | `prefetchHiConf` | `prefetchHiConf` = `0x10` | **已消除** |
| 5 | `scalarIssue` | `scalarIssue` = `0x40` | `io_in_5` |
| 6 | `prefetchLoConf` | `prefetchLoConf` = `0x80` | **已消除** |

`Arbiter7` 的 7 个槽中有两个被整源消除：`prefetchHiConf`/`prefetchLoConf` 的
`valid` 依赖 `io.prefetchReq`，而父层在该生成配置下没有该端口，于是
`prefetchHiConf.valid` 恒 0、`prefetchLoConf.valid` 恒 0。它们的常量只剩：
- 槽 4 消失（无端口）；
- 槽 6 的 `entrance=0x80` 变成**无请求时的 bubble 默认值**。

因此本 DUT 有 **5 个输入槽 + 1 个 `out_ready`**，输出 43 个字段。

## 2. 优先级与握手

```
higher_valid(i) = OR over sources with index < i of in_*.valid
io_in_0_ready = out_ready                                 // 最高优先级，永远可接收
io_in_i_ready = ~higher_valid(i) & out_ready              // i ∈ {1,2,3,5}
io_out_valid  = OR of all 5 in_*.valid
```

- `in_0`（unalign tail）无优先级前缀，`ready` 直接等于 `out_ready`。
- 其余槽在任一更高优先级源有效时被反压。
- 输出 `valid` 与 `out_ready` 无关（纯组合 valid）。

## 3. `entrance` 输出

```
in_0 → 0x01
in_1 → 0x02
in_2 → in_2.bits.entrance            // fastReplay 自带 entrance（S3 的 entrance | 0x04）
in_3 → 0x08
in_5 → 0x40
默认 → 0x80                          // 被消除的 prefetchLoConf 常量
```

只有 `in_2` 是透传，其余都是常量重编码。

## 4. 逐字段规则（43 个字段分 6 类）

这类仲裁器的实际 RTL 不是统一的 6 路三元式：Chisel 对每一位按"该源的该字段是否为
常量/don't-care"做了不同折叠。必须按字段分类描述，否则测不出真实行为。

| 类别 | 字段 | 规则 |
|---|---|---|
| **A. 全通** | `accessType_instrType`(`3'h4`)、`uop_ftqPtr_value`(`6'h0`)、`uop_ftqOffset`(`5'h0`)、`uop_fuOpType`(`12'h0`)、`uop_pdest`(`8'h0`)、`uop_robIdx_value`(`8'h0`)、`uop_waitSqIdx_value`(`6'h0`)、`uop_lqIdx_value`(`7'h0`)、`uop_sqIdx_value`(`6'h0`)、`vaddr`(`50'h0`)、`fullva`(`64'h0`)、`mask`(`16'h0`) | 0/1/2/3/5 全透传，bubble 用括号内默认值 |
| **B. 全通 + 单 bit 门控** | `uop_isRVC`、`uop_ftqPtr_flag`、`uop_rfWen`、`uop_fpWen`、`uop_vecWen`、`uop_v0Wen`、`uop_robIdx_flag`、`uop_robIdx_isFormer`、`uop_storeSetHit`、`uop_waitSqIdx_first/second_flag`、`uop_loadWaitBit`、`uop_loadWaitStrict`、`uop_lqIdx_flag`、`uop_sqIdx_first/second_flag` | 0/1/2/3 透传，槽 5 的位写成 `in_5_valid & in_5_bit`（槽 5 被选中时等价透传），bubble 为 0 |
| **C. 缺槽 5** | `uop_exceptionVec_{23,19,15,7,6}`、`uncacheReplay`、`ncReplay` | 0/1/2 透传，槽 3 写成 `in_3_valid & bit`，**没有槽 5 分支**；槽 5 胜出意味着槽 3 无效，所以结果为 0 |
| **D. 缺槽 5 + 有默认** | `uop_perfDebugInfo_runahead_checkpoint_id`(`64'h0`)、`mshrId`(`4'h0`)、`replayQueueIdx`(`7'h0`) | 0/1/2/3 透传，bubble 用默认值 |
| **E. `paddr`（只有槽 2 有意义）** | `paddr` | `in_0 ? paddr0 : (in_1_valid \| ~in_2_valid) ? 48'h0 : paddr2`：只有 fastReplay 的 paddr 被保留，其余源或 bubble 都为 0 |
| **F. `size` 特化** | `size` | `in_0 → 3'h4`（unalign tail 恒为 Q），其余源透传，bubble 为 0 |
| **G. `pftType` 特化** | `accessType_pftType` | `in_0 → pft0`，`in_1 → 0`，`in_2 → pft2`，`in_3 → 0`，`in_5 → pft5`，bubble 0 |
| **H. `noQuery` 特化** | `noQuery` | `~in_0_valid & (in_1_valid ? nq1 : (in_2_valid \| (in_3_valid ? nq3 : (~in_5_valid \| nq5))))`：槽 2 恒为 1（该源本身常量 true），槽 5 在被选中时等于 nq5，bubble 为 1 |

`paddr`/`size`/`pftType`/`noQuery`/`exceptionVec*` 这些"字段只在某些源有意义"的
写法不是笔误，而是父层把对应源的这些字段设为 `DontCare*`/常量后 optimizer 折叠出的
结果（`NewLoadUnit.scala:117-220` 的 `DontCarePAddr()`、`DontCareVectorFields()`
等）。测试必须按字段实际规则，而不是按"统一 6 路 mux"的想象。

## 5. 输入合法域与 don't-care

- 各源 `valid` 可任意组合；本模块没有"必须互斥"的约束，优先级语义明确允许多源同拍有效。
- `bits` 在对应 `valid=0` 时架构上 don't-care，但 RTL 仍会读它们（见 H/E 类的
  `in_3_valid & bit`、`in_1_valid | ~in_2_valid`），所以测试驱动确定值以便检查
  未选中源是否泄漏。
- `out_ready` 由父层 `dcacheReq.ready` 门控；本 DUT 只看这一个 ready。
- 纯组合模块：无 clock、无 reset。

## 6. 语义功能点

| ID | 语义 | 可观察结果 |
|---|---|---|
| **ARB7-PRIORITY** | 5 源按 0>1>2>3>5 固定优先级 | 单源、两两、全有效共 32 种组合下 `out.valid` 与 `entrance` 正确 |
| **ARB7-READY** | `in_0.ready = out_ready`；其余 = `更高优先级全无效 & out_ready` | 32 种组合 × `out_ready∈{0,1}` 的 ready 位图 |
| **ARB7-ENTRANCE** | 常量重编码 + 槽 2 透传 + bubble `0x80` | 每源单独胜出与 bubble |
| **ARB7-FIELD-A..D** | 透传/门控/缺槽 5 三类字段保真 | 每源每字段逐位比较 |
| **ARB7-PADDR** | 只有槽 2 的 paddr 保留 | 槽 0/1/2/3/5 与 bubble 下 paddr 的期望值 |
| **ARB7-SIZEQ** | 槽 0 的 size 恒 `3'h4` | 驱动任意 size，检查被钳到 4 |
| **ARB7-PFT** | 槽 1/3 的 pftType 恒 0，其余透传 | 逐源 |
| **ARB7-NQ** | `noQuery` 的折叠加槽 5 门控 | 6 种情形 |
| **ARB7-NO-LEAK** | 未选中源的比特不得影响输出 | 翻转未选中源载荷，输出快照不变 |

## 7. 覆盖要求

- 5 个源的 32 种有效组合 × `out_ready` 两态（64 个 ready/valid 向量）。
- 每源单独胜出时 43 个字段的逐字段比较，含 A/B/C/D/E/F/G/H 全部类别。
- bubble 时 43 个字段等于各自的默认值（这是确定性可观测量，不是 don't-care）。
- 未选中源翻转的隔离检查（每源一次）。
- 合法随机（32 组合 × 随机载荷 × 随机 ready）。

## 8. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala:94-223`（7 源定义、优先级注释、`arbiter` 调用）
- `XiangShan/src/main/scala/xiangshan/mem/MemBlock.scala:85-96`（`arbiter` = `chisel3.util.Arbiter`）
- `XiangShan/src/main/scala/xiangshan/mem/pipeline/package.scala:61-88`（`LoadEntrance` one-hot 编码）
- `soc-split/rtl/LoadUnitS0.sv`（父块连线与 `prefetchHiConf`/`prefetchLoConf` 消除的旁证）
- `soc-split/rtl/Arbiter7_LoadStageIO.sv`（本 DUT 的全部 43 条 assign）
