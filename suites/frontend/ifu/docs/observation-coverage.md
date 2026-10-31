# IFU 观察点与比较器对账

按 [checker 与运行时方法](../../../../skills/execution/checker-and-runtime.md) 建立
“需求 → 驱动字段 → 观测字段 → 比较器 → nodeid”表，并显式列出**不比较**的字段及
原因。缺字段必须报错，不用默认 0 掩盖；不比较项不能算已检查。

## 1. 顶层 `Ifu` 的入队拍（`tests/ifu/test_ifu_fetch.py`）

驱动：`fromICache.req`（startVAddr/尺寸/数据/压缩图/范围/异常元数据/ftqIdx）、
`toIBuffer.ready`、`ibufferEmpty`、`backendEmpty`、`toUncache.req.ready`、
`fromUncache.resp`、`fromFtq.redirect`、`fromFtq.flushFromBpu.s3`、`frontendTrigger`。

| 观测字段 | 比较规则 | 比较器 | 不比较的理由 |
|---|---|---|---|
| `toIBuffer.bits.valid` | 逐 lane 位精确比较 | `check_beat` valid mask | — |
| `toIBuffer.bits.enqEnable` | 逐 lane 位精确比较（预测截断后） | `check_beat` enq | — |
| `toIBuffer.bits.instrs[i]` | 逐 lane 精确（非法压缩保留原字） | `check_beat` instrs | lane 35 恒 0，端口叶子被删，按 pruned 常量声明 |
| `toIBuffer.bits.isRvc[i]` | 逐 lane 精确 | `check_beat` is_rvc | — |
| `toIBuffer.bits.foldpc[i]` | 逐 lane 精确（XORFold(pc>>1, 10)） | `check_beat` foldpc | — |
| `toIBuffer.bits.ftqPtr[i]` | 逐 lane 精确（跨块/块 1 取第二块） | `check_beat` ftq | — |
| `toIBuffer.bits.instrEndOffset[i].offset` | 逐 lane 精确（含 5 位回绕） | `check_beat` end_off | — |
| `instrEndOffset[i].predTaken` | 逐 lane 精确 | `check_beat` pred | lane35 的 `predTaken` 叶被删除（padding lane 恒 0） |
| `toIBuffer.bits.prevInstrCount` | 精确（异常窗口取 limit，否则 spec count） | `check_beat` prev_count | — |
| `toIBuffer.bits.exceptionType` | 精确（ICache 异常优先于 RVC 非法） | `check_beat` exception_type | — |
| `toIBuffer.bits.exceptionMask` | 精确 bitmask | `check_beat` exception_mask | — |
| `exceptionCrossPage` | 精确 | `check_beat` exception_cross | 仅在异常窗口构造，非异常窗口恒 0 也一并比较 |
| `isBackendException` / `hasSatpFlush` | 逐拍与输入 `icacheMeta(0)` 的两个标记比较（block-0 语义：挂到第一条指令） | `check_beat` 每拍比较 + `test_backend_exception_and_satp_flush_markers_reach_the_first_instruction` 三种组合 | 标记的语义消费（`satpFlushFirstFetchFault`）在 IBuffer/后端，本 DUT 不定义 → 残余 R-11 剩余部分 |
| `toIBuffer.bits.triggered[i]` | 逐 lane 动作精确 | `check_beat` trigger_actions | 未配置时全部为 15，也参与比较 |
| `toFtq.wbRedirect.*` | valid/ftq/pc/target/taken/offset/isRVC/attribute/canTrain | `check_redirect` | `pc` 的 guard 位受端口宽度限制（`IFU-ENV-005`） |
| `toBackend.gpAddrMem.*` | wen/gpaddr/waddr/vs 精确 | `check_beat` gp_* | 仅 GPF 场景比较 |
| `toUncache.req.*` | valid/addr/memBackTypeMM/memPageTypeNC | 非缓存用例内断言 | — |

**不比较的字段（明确记录）**：

| 字段 | 原因 | 影响 |
|---|---|---|
| `toIBuffer.bits.pc[i]` | 该拍端口仅用于调试，`signals.json` 未导出（顶层裁剪） | PC 正确性通过 `foldpc` + 指令字 + 重定向 `pc` 间接覆盖；残余 R-12 |
| `toIBuffer.bits.isLastInFtqEntry[i]` | 端口未导出 | FTQ 边界标记未直接验证；残余 R-12 |
| `toIBuffer.bits.prevIBufEnqPtr` | 端口未导出 | 写指针初值未直接验证；通过后续对齐行为间接覆盖 |
| `toIBuffer.bits.debug_seqNum[i]` | 仅性能调试元数据 | 架构语义无关 |
| `toIBuffer.bits.topdownInfo` | 由 PerfAnalysis 单独 DUT 验证 | 顶层不重复断言；理由位组合残余见 R-07 |
| `toFtq.wbRedirect.bits.pc` 的 guard 位 | 本基线端口 50 位 | 见 `IFU-ENV-005` / R-08 |

## 2. 子模块观测

| DUT | 观测字段 | 比较规则 | 不比较 |
|---|---|---|---|
| `RvcExpander` | `io_out_bits`、`io_ill` | 定义编码逐位；hint 只比较合法性 | hint 的规范形式（允许规范化） |
| `InstrBoundary` | valid/isRvc/cross/end mask/start-end offset/blockSel/index/first&total half | 逐槽精确比较 | 槽 31 cross（端口删除，模型证明恒 0） |
| `PredChecker` | stage1 fixedInstrValid（35 lane）、stage2 重定向全字段 | 逐 lane/逐字段精确 | lane34 cross（端口删除，模型证明恒 0） |
| `IfuUncacheUnit` | req_ready、resp 四字段、toUncache 属性 | 每拍全字段精确比较 | `toUncache` 属性在 `to_valid=0` 时不比较（合同只在其有效时定义） |
| `FrontendTrigger` | `io_triggered[i]`、`tdata2` 比较 | 36 lane 全比较；`tdata2` 是 64 位字段 | `tdata2` 比较只用低 50 位（R-13，两条 FAIL）；timing 无端口 |
| `IfuPerfAnalysis` | `io_topdownOut.topdown.reasons[*]` | 76 位全比较 | 无端口理由位恒 0（结构上限） |

## 3. 完成性 / 账本

| 对象 | 账本 | 检查 |
|---|---|---|
| `IfuUncacheUnit` | `accepted` / `completed` / `aborted` / in-flight | 随机 700 拍后断言 `accepted - completed - aborted == in_flight`（单槽，0 或 1）且 `completed + aborted <= accepted`；`test_random_sequences_match_the_model` |
| `Ifu` 取指 | accepted 请求 → 恰好一个 beat 或（被 flush 丢弃） | 每个用例在 `fetch()` 中断言请求被接受；beat/redirect 在有限拍内出现，否则失败（watchdog 30 拍） |
| `IfuUncacheUnit` 脉冲 | 每次完成恰好 1 拍 resp_valid | 完成用例逐拍检查“下一拍归零”；随机序列与模型逐拍对齐 |

## 4. 采样约定

- 写入/采样沿：DUT 输入为上升沿写入；`step()` 后采样为边沿后状态；组合 DUT 用
  `settle()`（无时钟单元推进一个时间步以记录 toggle）。
- 同拍多通道：`Ifu` 的 beat 与 redirect 在同一快照读取，各自独立比较，不用
  `if/continue` 串行分支。
- 复位：harness 先清所有输入再拉复位，避免释放沿接受残留请求；构造时关闭
  Verilator 寄存器随机化。
- 不做固定延迟假设：`fetch()` 只在“ready 且 valid”时推进，beat/redirect 用事件
  观察而非固定拍数；接受等待与 beat 等待各有上限，超限由用例的 `assert beat is not
  None` 失败，不能静默通过。
- 宽度断言用 schema 的 `High/Low`，不用 Picker 的 `mWidth`：1 位标量在
  `signals.json` 里记作 `High=-1, Low=0`，`mWidth` 返回 0，但端口存在且可正常读写
  （例如 `instrEndOffset[*].predTaken` 实测能读到 1）。把 `mWidth==0` 当作“端口不存在”
  会误判成 pruned；`read_pruned` 因此只用属性是否存在来判断，不用宽度。
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
