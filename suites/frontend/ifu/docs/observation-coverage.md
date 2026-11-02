# IFU 观察点与比较器对账

按 [checker 与运行时方法](../../../../skills/execution/checker-and-runtime.md) 建立
“需求 → 驱动字段 → 观测字段 → 比较器 → nodeid”表，并显式列出**不比较**的字段及
原因。缺字段必须报错，不用默认 0 掩盖；不比较项不能算已检查。

## 1. 顶层 `Ifu`（当前同一事务agent，2026-11-01）

下列比较均在`ifu/agent.py`的连续DriveStable/RisingEdge快照执行；功能用例只组织语义
事务。`ifu/checker.py::{check_enqueue,check_uncached_enqueue}`替代旧`check_beat`，后者
已删除。字段掩码来自独立输入答案，不从DUT的valid倒推。表中逐lane均指独立期望的
有效lane，padding另有常量合同。

驱动：`fromICache.req`（startVAddr/尺寸/数据/压缩图/范围/异常元数据/ftqIdx）、
`toIBuffer.ready`、`ibufferEmpty`、`backendEmpty`、`toUncache.req.ready`、
`fromUncache.resp`、`fromFtq.redirect`、`fromFtq.flushFromBpu.s3`、`frontendTrigger`。

| 观测字段 | 比较规则 | 比较器 | 不比较的理由 |
|---|---|---|---|
| `toIBuffer.bits.valid` | 逐lane位精确比较 | `check_enqueue/check_uncached_enqueue` | — |
| `toIBuffer.bits.enqEnable` | 逐lane位精确比较（预测截断后） | 同上 | — |
| `toIBuffer.bits.instrs[i]` | 逐lane精确（非法压缩保留原字） | 同上 | 无效lane数据不消费；lane35的instrs实际存在且按恒0额外比较，不是pruned端口 |
| `toIBuffer.bits.isRvc[i]` | 逐lane精确 | 同上 | — |
| `toIBuffer.bits.foldpc[i]` | 逐lane精确（50位虚拟字节PC去bit0后XORFold10） | 同上 | guard位不是虚拟地址的一部分；不能因此豁免redirect的R-08 |
| `toIBuffer.bits.ftqPtr[i]` | 逐lane精确（跨块/块1取第二块，carry完成槽按块0） | 同上 | — |
| `toIBuffer.bits.instrEndOffset[i].offset` | 逐lane精确（含5位回绕） | 同上 | — |
| `instrEndOffset[i].predTaken` | 逐lane精确 | 同上 | 只有lane35的predTaken叶被删除，显式证明恒0 |
| `toIBuffer.bits.prevInstrCount` | 当前/下一流水窗口按s1_moves选择；uncache为1 | `IfuAgent._check_phase` + 两enqueue比较器 | 不是无条件当前窗口计数 |
| `toIBuffer.bits.exceptionType/Mask/CrossPage` | 精确异常类别/bitmask/跨页，非异常值也比较 | 两enqueue比较器 | — |
| `isBackendException` / `hasSatpFlush` | 与输入icacheMeta(0)标记精确比较 | 两enqueue比较器及原三种组合功能用例 | 标记的消费在IBuffer/后端，不给跨DUT语义credit（R-11） |
| `toIBuffer.bits.triggered[i]` | 按旧/新配置与live门控、输入PC的逐lane动作 | `TriggerModel.lane_actions` + 两enqueue比较器 | 未配置时也比较动作15 |
| `toFtq.wbRedirect.*` | valid/ftq/pc/target/taken/offset/isRVC/attribute/canTrain | `IfuAgent._check_phase`、`expected_redirect/uncached_redirect` | pc的guard位受端口宽度限制（R-08） |
| `toBackend.gpAddrMem.*` | wen存在性总比较，有效时gpaddr/waddr/vs精确；ready0重复同址写合法 | `check_gpa` + agent | wen0的payload不消费，不比较 |
| `toUncache.req.*` | valid存在性总比较、有效时全部属性/字节PA；fire另按ready计数 | `UncacheModel` + agent Scoreboard | valid0时payload不消费 |
| `toIBuffer.bits.topdownInfo` | 全76位沿前/后持续比较 | `PerfModel.output` + agent | — |
| `io_perf[0..12].value` | 13个命名事件、实际fire和接受时cache metadata，公开两级寄存延迟 | `model/fetch_events.py` + agent两阶段Scoreboard；8种固定truth table、26个字段/阶段错误控制 | 两级无reset初值只在最初实际边沿填满前未知；非累计计数器 |

**不比较的字段（明确记录）**：

| 字段 | 原因 | 影响 |
|---|---|---|
| `toIBuffer.bits.pc[i]` | 该拍端口仅用于调试，`signals.json` 未导出（顶层裁剪） | PC 正确性通过 `foldpc` + 指令字 + 重定向 `pc` 间接覆盖；残余 R-12 |
| `toIBuffer.bits.isLastInFtqEntry[i]` | 端口未导出 | FTQ 边界标记未直接验证；残余 R-12 |
| `toIBuffer.bits.prevIBufEnqPtr` | 端口未导出 | 写指针初值未直接验证；通过后续对齐行为间接覆盖 |
| `toIBuffer.bits.debug_seqNum[i]` | 仅性能调试元数据 | 架构语义无关 |
| `toFtq.wbRedirect.bits.pc` 的 guard 位 | 本基线端口 50 位 | 见 `IFU-ENV-005` / R-08 |

## 2. 子模块观测

| DUT | 观测字段 | 比较规则 | 不比较 |
|---|---|---|---|
| `RvcExpander` | `io_out_bits`、`io_ill` | 定义编码逐位；hint 只比较合法性 | hint 的规范形式（允许规范化） |
| `InstrBoundary` | valid/isRvc/cross/end mask/start-end offset/blockSel/index/first&total half | valid/end mask/首尾half总比较；metadata按独立期望valid逐槽比较；carry cross仍受检 | 无效槽metadata不被compact消费；carry首槽endOffset被后级重写0；槽31 cross是已证明pruned0，不是缺省值（2026-11-01合同复核，R-14） |
| `PredChecker` | stage1 fixedInstrValid（35 lane）、stage2 重定向全字段 | 逐 lane/逐字段精确 | lane34 cross（端口删除，模型证明恒 0） |
| `IfuUncacheUnit` | 沿前/后req_ready、resp四字段、toUncache属性，完整9字段快照 | 三个ready/valid总比较，payload按独立expected valid逐值比较；reset另比固定零状态 | valid0总线/响应payload未被消费；不依DUT valid或override缩窄mask。pruned fromUncache.ready显式1 |
| `FrontendTrigger` | 沿前/后`io_triggered[i]`、`tdata2` 比较 | 两阶段全部36 lane；tdata2完整64位；旧/新配置与当前live门控独立 | RTL低50位截断是R-13两条FAIL，不是checker豁免；timing固定0无端口 |
| `IfuPerfAnalysis` | `io_topdownOut.topdown.reasons[*]` | 76 位全比较 | 无端口理由位恒 0（结构上限） |

## 3. 完成性 / 账本

| 对象 | 账本 | 检查 |
|---|---|---|
| `IfuUncacheUnit` | 输入UID/epoch，offered cycles、req_fire、flush-on-fire、accepted、issued、observed completed、cancelled、active | `fire=accepted+flush-on-fire`；`accepted=completed+cancelled+active`；700帧实际fire94/生效89/完成75/取消13/同拍flush5，最后1笔显式取消。reset保留历史；finish不自动清债 |
| `Ifu` 取指 | offer/physical fire/同拍取消/有效进入、stage1/2/writeback、beat/redirect/uncache子接受/issue/reply/resend/取消按输入UID记录 | `_audit`逐事件与记录守恒；高层API默认24拍预算，低层cycle不虚构进展；完成后4槽尾部，finish默认8槽且禁止补响应/flush/reset清债；未退休FTQ身份禁止重用，producer还检查半环内年龄 |
| `Ifu` carry | 原低半/PC/UID、输入与peer来源跨请求保留，完成或明确取消 | reset/cancel/backend redirect保留不可变取消原因/原身份；声明的高半必须匹配实际字节且低半与原输入历史一致，未完成不能finish |
| `Ifu` 冗余描述 | 驱动raw半字 → 新起始/完整字/PC/FTQ/预测/ISA/计数与half标志 | `ifu/input_contract.py`从字节步进，独立于generator/Boundary.predict及DUT输出；19字段/4计数/序列错误控制、1200窗口及手写固定答案 |
| `IfuUncacheUnit` 脉冲 | 每次完成恰好 1 拍 resp_valid | 完成用例逐拍检查“下一拍归零”；随机序列与模型逐拍对齐 |

## 4. 采样约定

七DUT均使用框架Driver/lossless Monitor。RVC/InstrBoundary无硬件时钟，native XClock
仅推进组合评估；PredChecker、Trigger、Uncache和Ifu按各自合同分别检查沿前/沿后；
PerfAnalysis检查三级理由传播。公开`Execution.paused`仅在调用间暂停仿真时间，不关闭
monitor。具体规则见[事务适配合同](transaction-adapters.md)。

- 同拍全部通道冻结采样后再统一更新账本，尾部也持续检查，不用`if/continue`漏通道。
- reset有固定零状态答案；原生寄存器随机化关闭不等于功能reset。取消在途义务必须给原因。
- 驱动槽完成不等于DUT接受。高层fetch/read/collect按实际事件完成，预算耗尽失败；
  finish不替caller回报完成，也不把停monitor当安静证明。
- 宽度断言用 schema 的 `High/Low`，不用 Picker 的 `mWidth`：1 位标量在
  `signals.json` 里记作 `High=-1, Low=0`，`mWidth` 返回 0，但端口存在且可正常读写
  （例如 `instrEndOffset[*].predTaken` 实测能读到 1）。把 `mWidth==0` 当作“端口不存在”
  会误判成pruned。绑定验证属性存在、方向、完整集合与`max(1,mWidth)`的实际宽度，
  自检使缺端口/错误宽度/额外端口/第二writer均失败。
- 判定不依赖 RTL 内嵌 assert：所有结论来自外部比较器；生成 RTL 中的 Chisel assert
  保留，但未作为证据来源（其启用与否随构建参数变化）。

## 5. 字段缺口（必须保留的残余）

按 [观察点精度方法](../../../../skills/design/observation-precision.md) 维护：内部宽于
端口的字段默认留下，关闭需消费者合同或结构证明。完整清单与关闭条件见
[退出与残余](exit-criteria.md) 的“观察点精度扫描”。

- **R-11**：`isBackendException` / `hasSatpFlush` 现在逐拍比较，并有三种取值的定向
  用例；仍不覆盖“后端异常 + 跨页异常同拍”的组合，且两个标记的语义消费在 IBuffer/
  后端（`satpFlushFirstFetchFault`），不在本 DUT 边界内。结论词为“转发已验证、消费未验证”。
- **R-12**：`toIBuffer.pc/isLastInFtqEntry/prevIBufEnqPtr` 在本基线未导出，未直接
  比较；PC 语义通过 foldpc、指令字与重定向间接覆盖，FTQ 边界标记通过 `ftqPtr`
  间接覆盖。若后续需要直接证据，需在配方中允许的导出方式下补充观察点，不能以
  间接覆盖声称已直接验证。
- **R-13**：`FrontendTrigger` 的 `tdata2` 比较只使用低 50 位。CSR 侧 `Tdata2Bundle`
  为 `RW(63,0)`，高 14 位可写且可读回，因此这是生产者/消费者宽度不一致的真实缺陷：
  EQ/GE 会把 `2^50+pc` 误判为 `pc`，LT 会把 `tdata2=2^50` 判成没有匹配。两条定向下
  文 `test_tdata2_above_the_address_space_*` 当前 FAIL；模型已从“复制 RTL 的 50 位
  掩码”改为全 64 位比较，避免 oracle 自证。

- **R-14（2026-11-01新增，已收紧范围）**：端口域carry高半槽被误标cross，完整指令
  会错用块1 FTQ身份；实际native端口历史与leaf对照已复现，但原短non-taken块不符合
  真实FTQ fall-through长度，撤回此前生产可达论证。严格producer尺寸/taken控制均正常。
  旧模型缺少“真实起始”条件，与RTL同错，
  原600随机有5个未检出反例。见[carry归属缺陷](bugs/instr-boundary-carry-ftq-owner.md)。
