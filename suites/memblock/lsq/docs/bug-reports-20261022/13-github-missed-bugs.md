# GitHub额外问题：这套UT没有检出什么，为什么没有检出

## 1. 结论与口径

**有。GitHub上至少找到下面5组与LSQ相关、没有成为本套UT现有11个根因的公开问题线索。** 其中既有激励时序缺口，也有参考模型判断盲区，还有默认配置之外的参数边界。

这里的“5组”是5组公开报告/补丁线索，**不是已经在本地新复现的5个独立RTL bug**。本轮没有运行它们的整核附件，没有应用补丁，也没有证明其中所有外部现象互不重叠。因此不能直接把当前数量改成“11＋5＝16”。

后续关系核验见[14号文件](14-relationship-11-vs-5.md)：这5组与11个根因**没有重复**；其中4组是独立的RTL功能bug（`#6704`、`#6229/#6312`、`#6634`、`#6714`），1组是配置合法性问题（`#6688/#6697`）。`#6229`、`#6634`与`#6714`已用本地公开端口探针复现，`#6704`为固定源码＋上游复现、本轮未重跑。正确的RTL功能bug总数是 **11＋4＝15**，另有1个配置问题；不是16个默认配置功能bug。`#6634` 的本地复现还证明：同拍多个真实错误只报一个，正常完成可抢占真实故障。

本文件分别标注：

- **外部报告说了什么**：来自Issue/PR正文，不能当作本地运行结果。
- **固定版本源码是否有相关实现**：已对照`893e1580b705d81f113c30c7a05734e09a08050e`静态核验。
- **本地UT为什么可能漏掉**：给出现有驱动/参考/测试的具体代码依据。
- **还缺什么验证**：明确没有完成的工作，而不是用“已有覆盖率”顶替。

截至2026-10-22查询，下面列出的Issue/修复PR均为open。检索证据保存在[GitHub查询目录](../../results/github-duplicate-check-20261022/)，新增外部正文快照为[additional-public-bug-details-v1.json](../../results/github-duplicate-check-20261022/additional-public-bug-details-v1.json)。检索不是整个GitHub全部bug的穷尽证明。

## 2. 一览

| 公开线索 | 外部报告的问题 | 固定源码情况 | 主要漏检原因 |
|---|---|---|---|
| [Issue #6704](https://github.com/OpenXiangShan/XiangShan/issues/6704) | 跨16B Store首请求之后、尾请求之前执行的Load读到旧值 | 最后请求才设`addrValid`的实现仍在 | 定向驱动把首尾连续发完；未把半完成窗口作为独立检查目标 |
| [Issue #6229](https://github.com/OpenXiangShan/XiangShan/issues/6229) / [PR #6312](https://github.com/OpenXiangShan/XiangShan/pull/6312) | 部分前递被当完全覆盖，分裂Load的字节读到旧数据 | `s2FullOverlap`仍按起止范围判断 | 参考也按同样范围判断；独立字节检查主要查“已宣称前递的字节”，遗漏“应前递却没有前递”的路径 |
| [PR #6634](https://github.com/OpenXiangShan/XiangShan/pull/6634) | 多个Uncache完成/异常竞争时，选错异常及故障地址 | 仍按entry顺序优先选择，没有按程序年龄筛选 | 参考也取第一个entry；槽顺序与程序年龄没有刻意打乱 |
| [Issue #6688](https://github.com/OpenXiangShan/XiangShan/issues/6688) / [PR #6697](https://github.com/OpenXiangShan/XiangShan/pull/6697) | 冷却阈值0时Replay被禁用，参数断言没有拒绝0 | 只有上界断言；默认值12 | DUT清单、模型和测试只使用12，没有配置0边界测试 |
| [PR #6714](https://github.com/OpenXiangShan/XiangShan/pull/6714) | 等待目标已经退休，回绕比较却让Load继续等待 | `outOfRange`未排除`targetRetired` | 虽测了普通“已退休”，没有强制跨代旧目标同时被判越域的组合 |

## 3. #6704：跨16B Store的“首尾中间”窗口

### 外部现象

报告用`sd ...473(base)`与`lw ...470(base)`构造只重叠Store下半段的Load。Store的首请求已经出现，尾请求尚未出现，Load在两者之间执行，读到了前一轮旧Store的字节。

外部报告称在其整核DiffTest环境中复现；本轮未执行其附件，不能把其运行日志记为本地结果。

### 固定源码上的依据

`NewStoreQueue.scala:1683–1686`只允许最后一个地址请求置地址有效：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1683-1686 -->
```scala
    val staSetValid    = staValidSetVec.reduce(_ || _)
    val addrValidSet   = io.fromStoreUnit.storeAddrIn.zipWithIndex.map { case (port, j) =>
      port.bits.isLastRequest && !port.bits.tlbMiss && staValidSetVec(j)
    }.reduce(_ || _)
```

前递候选又要求`ctrlEntry.addrValid`（473–476行）。因此“首包地址已知，整个entry仍不参与前递”的代码机制确实存在。是否形成外部报告的完整后果，还要同时核对首尾nuke/RAW检查及LDU时序。

### 为什么本套定向UT没检出

现有`tests/lsq_wrapper/memory_owners.py:213–233`的`write()`发首包之后，在同一个辅助函数内继续发尾包；调用者通常`await write_all()`结束、再等5拍，才调用`forward()`。

如`tests/lsq_wrapper/test_forward_memory.py:85–88、121–125`，检查的是**两段地址都写完后的稳定状态**。这些测试可以发现本汇报包07/08的问题，却天然绕过“只完成首包”的危险窗口。

不能说所有随机流绝不经过该窗口：混合actor允许交错。但是没有针对该窗口的必达门禁，而且稳定bank字节检查会跳过正在变化的bank；随机测试可能在更早的其它FAIL处停止。仅有随机流存在，不能证明该边界被有效检查。

### 需要补的验证

显式分开首/尾地址驱动：首包→插入只命中低段的Load→延迟STD→尾包；按不可变的原PA字节账本检查Load能否接受旧值，并检查之后正确的回滚或重放。当前没有补跑，不把它计成已确认新根因。

## 4. #6229 / #6312：参考模型可能和RTL一起判断错“完全覆盖”

### 外部报告与补丁

#6229报告跨16B的未对齐Load下半段没有取得应有的新Store数据。#6312给出的解释和修复是用真实前递mask检查完整覆盖，而不是仅比较字节范围的起止值。

两者的关联来自PR的`Fixes #6229`。这不等于我们已在当前固定版独立证明其所有scalar/vector触发路径，也没有证明与其它跨16B时序缺陷完全无关。

### 固定源码与参考的共同点

固定`NewStoreQueue.scala:637–640`：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:637-640 -->
```scala
      val s2FullOverlap        = s2SelectDataEntry.byteStart <= s2LoadStart && s2SelectDataEntry.byteEnd >= s2LoadEnd
      // First condition: access extends beyond the lower log2Ceil(VLEN/8) bits.
      // Second condition: higher bits of the virtual address within the page offset are non-zero, indicating a potential cross-page access.
      val s2SafeForward        = !s2MultiMatch || s2FullOverlap
```

本地`lsqverify/forward/model.py:100–104`也按同样的范围语义判断：

<!-- source: memblock-hash/lsq/lsqverify/forward/model.py:100-104 -->
```python
            start = query.vaddr % 16
            end = start + byte_count(query.size) - 1
            full = store is not None and store.vaddr % 16 <= start and store.vaddr % 16 + store.length - 1 >= end
            safe = len(answer.virtual) <= 1 or full
            bad_cbo = store is not None and store.cache_operation and store.cbo != 3
```

### 为什么独立字节检查还不够

`ForwardModel.check_physical_safety()`确实独立检查了物理来源，也因此发现07/08。但它在130–147行：

- bank变化时跳过该独立检查；
- 有重放/依赖时不把数据当接受；
- `forwardMask[byte]=0`时直接跳过该字节。

这能抓“错误地前递了一个字节”，却不能单独证明“每一个**应当**由未完成Store提供的字节，都得到前递或被正确阻塞”。后者还要检查遗漏字节是否错误地落到了旧DCache数据。

真实父级`test_forward_memory.py:12–31`已有独立完整mask检查，但集中于选定场景，未覆盖外部报告的全部分裂Load、多候选和部分覆盖组合。因此不能说完全没有独立参考，准确结论是**详细参考存在同源判断盲区，独立性质的适用范围也不完整**。

### 与07的区别及需补验证

07检查“不该标为前递的字节却被标了”；本线索检查“实际覆盖不足却被当作安全接受，缺失字节可能读旧值”。不能因为都带mask就直接合并，也不能未消歧就算作两个已确认本地新bug。

应按真实PA逐字节定义期望：最年轻的未完成Store覆盖该字节时，Load必须取其值或被阻塞；不允许仅因RTL的mask为0就不检查。还需连接/建模DCache旧值和split结果合并，复现外部例并做必要条件对照。

## 5. #6634：异常仲裁验证把“物理槽顺序”误当“程序顺序”

### 外部指出的问题

PR要求只有真实总线错误才产生异常候选，并从同拍候选中按`robIdx/uopIdx`选最老项，而不是按FreeList分配的entry编号选第一个。否则正常完成或年轻项可能遮住真正故障项的地址，导致错误的tval信息。

### 固定源码上的依据

`LoadQueueUncache.scala:236–239`对每次消费都产生候选，而不先限制总线错误：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:236-239 -->
```scala
  io.exception.valid := RegNext(writeback)
  io.exception.bits := RegEnable(req, writeback)
  io.exception.bits.uop.exceptionVec(loadAccessFault) := RegEnable(nderr, writeback)
  io.exception.bits.uop.exceptionVec(hardwareError) := RegEnable(derr, writeback)
```

父级`467–470行`再按entry集合的优先顺序选择：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:467-470 -->
```scala
  val exceptionEntry = ParallelPriorityMux(entries.map(e =>
    (e.io.exception.valid, e.io.exception.bits)
  ))
  io.exceptionInfo.valid := Cat(entries.map(_.io.exception.valid)).orR
```

“正常完成时valid=1但异常位为0”本身不能直接等同ISA错误；关键是它参与同拍候选选择，可能挡掉真正需要报告的故障owner。

### 本地UT为什么会放过

- `lsqverify/uncache_entry/model.py:96–100`同样在每次消费时构造`FaultReport(True, ...)`，没有先按真实错误过滤。
- `lsqverify/load_uncache/model.py:165`使用`next((out.exception for out in outs if out.exception.valid), None)`，也是按物理entry顺序取第一个。
- `tests/load_uncache/test_full.py:105–131`虽有多lane消费和异常“priority”测试，但分配顺序通常与ROB年龄一致，断言也选择较低槽的候选。没有让低槽的年轻正常项与高槽的老故障项同拍竞争。

所以这里不是“根本没有测异常”，而是**仲裁oracle验证了与RTL相同的错误策略，刺激又没有打散槽号和年龄的关系**。这也是“参考没有读内部寄存器”仍不能保证语义完全独立的实例。

### 还缺的验证

先用真实释放/重分配制造槽号与ROB顺序相反，再同时消费“低槽正常、高槽故障”及“两故障年龄相反”组合；按不可变原事务的年龄和故障地址选期望。还需检查同ROB不同uop的情形。本轮未补跑，因此不计为新的本地复现结果。

## 6. #6688 / #6697：参数边界没有进入固定配置UT

### 固定源码能够直接看出的边界

`LoadQueueReplay.scala:656–663`：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:656-663 -->
```scala
  val ColdDownCycles = 16
  val coldCounter = RegInit(VecInit(List.fill(LoadPipelineWidth)(0.U(log2Up(ColdDownCycles).W))))
  val ColdDownThreshold = Wire(UInt(log2Up(ColdDownCycles).W))
  ColdDownThreshold := Constantin.createRecord(s"ColdDownThreshold_${p(XSCoreParamsKey).HartId}", initValue = 12)
  assert(ColdDownCycles.U > ColdDownThreshold, "ColdDownCycles must great than ColdDownThreshold!")

  def replayCanFire(i: Int) = coldCounter(i) >= 0.U && coldCounter(i) < ColdDownThreshold
  def coldDownNow(i: Int) = coldCounter(i) >= ColdDownThreshold
```

阈值为0时，`counter < 0`永远不成立，Replay不能按该条件前进；现有上界断言却允许0。这一点可以静态推导。Issue还报告了整核数据错误，但本轮没有复现那部分后果。PR #6697的处理是增加合法性断言，**不是支持阈值0正常运行**。

### 为什么本套UT没发现

- `manifest/duts.json:17`明确记录当前Replay DUT阈值12。
- `lsqverify/replay/model.py:228、240`把12写入模型判断。
- `tests/replay/test_timing.py:139–173`测试的是默认12下进入冷却和恢复，没有切换阈值。

因此默认配置即使所有冷却分支都命中，也不能证明其它配置合法。固定原生DUT的运行用例变化，不能替代参数变体或Constantin配置验证。

### 需要补的验证

单独划分参数域：0应被拒绝，1、12、15等合法边界应能前进；具体取值须与设计约束一致。应保留独立构建/配置证据，不跨变体回填覆盖率。本轮没有生成阈值0的新DUT。

## 7. #6714：已退休等待目标叠加指针回绕

### 公开补丁说了什么

MDP是内存依赖预测：Load可能记着“等某个Store”。该Store已经退休后，本来不该再等；但回绕后的范围比较可能又把旧目标看成在物理窗口之外，要求等待永远不会再次到来的地址完成。

固定`NewStoreQueue.scala:579–584`：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:579-584 -->
```scala
      val s2MdpTargetRetired   = s2LoadWaitBit && s2WaitSqIdx.isBefore(s2DeqPtr)
      val s2MdpHitOutOfRange   = s2LoadWaitBit && s2WaitSqIdx.isNotBefore(s2PhysicalQueueUpper)
      val s2MdpHitInPhysical   = s2LoadWaitBit && s2WaitSqIdx.isNotBefore(s2DeqPtr) &&
        s2WaitSqIdx.isBefore(s2PhysicalQueueUpper)
      val s2PreciseMdpWait     = s2MdpHitInPhysical && !io.ctrlEntriesIn(s2WaitSqIdx.value).addrValid
      val s2NeedPreciseMdpWait = s2PreciseMdpWait || s2MdpHitOutOfRange
```

可以看到`targetRetired`算出来了，但没有用于排除`outOfRange`。PR #6714的改动正是增加`!s2MdpTargetRetired`。

### 为什么“测过retired”仍不足

`tests/forward/test_semantics.py:87–90`的retired对照只用`deq=1、waitSq=0、upper=65`。这个普通情形不会同时触发远端范围比较的回绕边界。

随机流虽有不同代号，但没有为“真实已退休旧预测目标＋跨flag回绕＋仍保留该目标的Load查询”建立独立必达计数和持续前进检查。`ForwardModel.expected()`在110–111行会先排除已退休目标，具备发现某些不一致的能力；所以不应把本项也误说成“参考照抄错误”，主要缺口是**完整生命周期与边界组合没有被保证命中**。

### 和10不是同一个bug

- 10是有效`dataInvalid`输出带了错误Store代号。
- 本项是Load记着的旧预测目标已经退休，阻塞资格仍可能被错误保留。

本轮没有构造其跨代合法最小反例，也没有核验外部补丁的所有环形年龄前提。因此仅确认相关代码仍在和定向覆盖不足，不声称本地已复现该PR报告的停滞。

## 8. 这次复核对验证方法的结论

1. **高代码覆盖率不等于语义覆盖完整。** 默认配置、稳定状态可能把所有行跑到，却不触发错误的首尾时序或参数边界。
2. **参考独立不仅是不用DUT内部值。** 若参考也按错误的“范围等于完整覆盖”“低槽等于最老”判断，RTL和参考可以一起通过。
3. **单向性质不够。** “所有被前递字节都有正确来源”之外，还要查“所有需要未完成Store提供的字节都被前递或阻塞”。
4. **测试恢复与真实producer必须正确。** 否则新增压力既可能制造误报，也可能提前超时，遮住真正想检查的后续窗口。
5. **先分清证据等级再计数。** 本地11个根因仍是已确认集合；这里5组公开线索是新增的复核/补测清单，不是已完成的新增发现，也不是已修复项目。

这些是基于具体代码的漏检原因和改进方向。本轮仅交付分析与报告，没有修改参考来追随补丁，也没有把任何旧FAIL改成PASS。
