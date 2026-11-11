# LSQ全部FAIL的源码裁定

固定对象：开源`kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`。
判定对象是**支持的模块接口内是否存在RTL逻辑缺陷**，不是整核ISA失败数。
所有引用的Scala均逐字节对照该Git对象；SV对照原导出`source.json`指纹。
不使用`XiangShan-internal`，不修改RTL、旧测试、参考模型或历史FAIL。

## 一、最终结论：全部228个失败节点均有二元裁定

| 原范围 | 原FAIL | 是RTL bug | 不是RTL bug |
|---|---:|---:|---:|
| 统一`lsq-progress-regression-15` | 227 | 221 | 6 |
| 最新`replay-cause-lifetimes-contributor-regression-03` | 196 | 189 | 7 |
| 两范围去重并集 | **228** | **221** | **7** |

**221个失败节点归并为11个RTL根因，不是221个独立bug。7个非RTL失败归并为5种
验证侧/刺激域错误。未裁定数量为0。** 原227/196条FAIL仍然原样存在，以上是
分析裁定，不是修复后仿真通过数；两个原范围的数量也不能相减当修复量。

此前独立复核另增的32个探针也未遗漏：其当前22PASS、10FAIL；10条FAIL全部
归入B4/B5/B6/B7的相同根因。连同这10个新节点，**全部现有语义失败证据并集为
238个节点：231个指向上述11个RTL bug，7个不是RTL bug，未裁定0**。下表各根因
的节点数只统计228个原回归节点，避免把补充探针与原回归混作同一运行计数。

逐节点清单：

- `results/fail-source-adjudication-01/all-fail-verdicts-v1.json`
- `results/fail-source-adjudication-01/all-fail-verdicts-v1.csv`

每个节点包含明确布尔`is_RTL_bug`、根因、错误描述、原失败详情SHA、该节点的
实际首次失败边界及代码证据索引。旧报告中“候选”“未提名”等状态由本报告
取代，旧文件不回写。特别纠正：不能把Deq随机用例按旧问题名称全部归到split；
也不能把一个错误CBO包造成的前递断言冒称成新的普通Store别名bug。
CSV包含228个原节点及10个新增独立探针，使用`scope`列区分，不跨运行计算通过率。

## 二、11个“是RTL bug”的根因

源码简称：`SQ = XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala`；
以下SV均位于`memblock-hash/lsq/rtl/`。

### B1. FWD-ALIAS-001：PA别名的年轻Store被重叠域漏掉（12个FAIL）

**是bug。** 对真实写入字节的年轻Store，VA标签不相同不意味着PA不重叠。
当前RTL把VA计算出来的“是否下一16B段”同时用于限制物理候选，造成检查盲区。

```scala
val loadInNext16B = s1Next16BMatchVec(j) // 其中要求VA page tag相同
val loadRangeStart = Mux(loadInNext16B, s1LoadStart + 16.U, s1LoadStart)
val s1OverlapCandidateVec = (s1AgeMaskLow | s1AgeMaskHigh) & s1OverlapMask & addrValidVec.asUInt
// PA CAM最后仍然只检查上述候选
... .asUInt & s2OverlapCandidateVec
```

代码：SQ **462–511、606–625**；`forward_module/ForwardModule.sv`
**3118–3123、11323–11330**。

反例中旧Store在`PA 0xabc010..13`写`0x11`；年轻8B Store从`PA 0xabc00c`跨到
`..13`写`0x22`，但VA为另一别名页。Load读`0xabc010`，应取得年轻字节或重放，
实际却无依赖/重放标志地接受旧`0x11`。VA/PA比较也漏报，因为年轻候选已先被删。

### B2. FWD-RANGE-001：mask循环旋转把另一段折回未写字节（28个FAIL）

**是bug。** 旋转不是具有物理字节边界的移位/裁剪。

```scala
val s2ByteSelectOffset = s2LoadStart - s2SelectDataEntry.byteStart
val s2SelectMask = (0 until VLENB).map(j => j.U -> rotateByteRight(s2SelectDataEntry.byteMask, j))
val s2OutMask = ParallelLookUp(s2ByteSelectOffset, s2SelectMask) & s2LoadMaskEnd
```

代码：SQ **606、632–644**；`ForwardModule.sv` **991、1450–1498**明确保留4bit减法
与旋转mask。合法producer依据是SQ **1931–1949**的连续size mask，不依赖孔洞mask。

8B Store起始offset12、mask`0x00ff`。Load从word起点读16B，4bit减法得到4，旋转
结果为`0xf00f`。首段实际只写过`0xf000`，尾段只写过`0x000f`；额外字节没有PA
producer，却被标成可接受前递。两个历史孔洞mask压力例也归此根因，但不冒充
正常producer历史：将其mask改为连续size mask，出错折回位仍为1，且合法最小例
已证明同一缺陷。它们不是另两个独立bug。

### B3. FWD-SQID-001：裁剪窗口后仍用Load的SQ代号（15个FAIL）

**是bug。** slot编号正确不等于完整Store身份正确。

```scala
val s0ForwardMask = Mux(s0LoadOutOfRange, s0PhysicalQueueUpperMask, s0LoadMask)
s1DataInvalidSqIdx.operation_flag := Mux(s1SelectLowOH.orR,
  s1LoadSqIdx.operation_flag, io.ctrlInfo.deqPtr.operation_flag)
```

代码：SQ **390–395、548–564**；`ForwardModule.sv` **5158–5161**直接在低半区命中时
拼接`s1LoadSqIdx_first_flag/second_flag`。

deq=60、physicalUpper=124、Load SQ=128时，slot48属于**SQ112**。RTL已把候选裁到
60..123，却返回Load代号下的**SQ176**。依赖醒错Store，不是无效输出payload。
父级/随机用例的其它位置同属这个代号选择错误，已逐节点归入本根因。

### B4. LQU-SID-001：已返回响应的SID仍能覆盖旧Load（29个FAIL）

**是bug。** 外部SID生命周期和LQU驻留生命周期被错误混用。

```scala
// LoadQueueUncache.scala
}.elsewhen(slaveAck) { slaveAccept := true.B ... }
}.elsewhen(writeback) { slaveAccept := false.B ... }
when(io.uncache.resp.fire) { uncacheData := io.uncache.resp.bits.data ... }
// 父级按slaveId.valid与sid相等分发resp，未限制entry仍在等原响应
```

代码：`LoadQueueUncache.scala` **94–109、190–197、438–439**；
`UncacheEntry.sv` **247–252、325–330**。
`cache/dcache/Uncache.scala` **493–499**则在`resp.fire`调用`updateReturn()`归还SID，
没有等待LDU最终消费的接口。因此响应后重用SID是合法的。

A尚未消费，B重用已归还SID并返回后，A的有效bypass返回B的数据/错误。缺少的是
原响应完成后撤销SID接收资格或限制更新的门控；不是参考模型不该比较s2数据。

### B5. LRQ-STRICT-001：未入队lane可清除活动strict（11个FAIL）

**是bug。** `valid=0`只使payload不被接收，不授权其改变其它有效事务状态。

```scala
val enqIndex = Mux(enq.bits.isLoadReplay, enq.bits.schedIndex, freeList.io.allocateSlot(offset))
when(enqFireBase && isMA) { strict(enqIndex) := enq.bits.uop.loadWaitStrict }
  .otherwise { strict(enqIndex) := false.B }
```

代码：`LoadQueueReplay.scala` **825–837、861–865**；
`LoadQueueReplay.sv` **11212–11221、24112–24114、33683–33697**。
后续`LoadQueueReplay.scala` **393–402**允许非strict owner被单个地址ready位放行。

没有真实enq，仍会根据无效schedIndex或不可用allocateSlot清活动strict，从而
提前Replay.valid。正确修复方向是状态写必须由真实owner更新事件授权，而不是
要求所有无效输入payload必须清零。检查的是受影响后的有效输出。

### B6. RAR-REL-001：release有效位比地址多一级（19个FAIL）

**是bug。** 不是RAR模型自行规定了一个与源码无关的时序。

```scala
val release2Cycle = RegEnable(io.release, io.release.valid)
release2Cycle.valid := RegNext(io.release.valid)
```

`release2Cycle`本身是寄存器；对其valid赋值是在指定该寄存器D端，又接入一个
RegNext的Q，因而valid变两级，地址仍在原release有效时保持。

代码：`LoadQueueRAR.scala` **130–138、181–189**；原SV **11865–11868**直接给出：

```systemverilog
release2Cycle_valid <= release2Cycle_valid_REG;
if (io_release_valid) release2Cycle_bits_paddr <= io_release_bits_paddr;
release2Cycle_valid_REG <= io_release_valid;
```

孤立脉冲实际捕获当前/前两拍，而不是所需当前/前拍：前拍冲突漏报，过期窗口
额外nuke。前者是正确性缺陷；后者是同一错拍的过度重放，不单独夸大为ISA破坏。

### B7. DEQ-WB-001：WB背压期间清除响应错误（50个FAIL）

**是bug。** 这50条含定向、父级及混合种子，第一次违约都是有效WB/异常信息中
已接受错误丢失，不是50个独立bug。

```scala
}.elsewhen(uncacheState === UncacheState.writeback || cboState === CboState.writeback) {
  hasHardwareError := false.B
}
// hasAccessFault有相同问题；FSM退出却要等io.writeBack.fire
```

代码：SQ **1082–1117**；`DeqModule.sv` **373–378、406–415**。
错误清除条件没有`writeBack.fire`，所以ready=0也清0，而valid保持1；最终fire
也消费错误0。`MemBlock.scala` **1028–1034**存在流水及STA仲裁，ready不是接口
常量1。不是只对无效payload检查过严，也不能靠参考跟随RTL清错使其通过。

### B8. DEQ-SPLIT-WLINE-001：split尾段继承相邻CBO.zero的wline（16个FAIL）

**是bug。** 地址/数据/mask和控制位来自不同owner。

```scala
writeSbufferData(1) := Mux(headCross16B, outData(0), outData(1))
writeSbufferMask(1) := Mux(headCross16B, outMask(0) & ~unalignMask(0), outMask(1))
// 但通用循环中wline仍取entry(i)，lane1即相邻entry1
port.bits.wline := ctrlEntry.isCbo && isCboZero(dataEntry.cboType)
```

代码：SQ **1180–1188、1243–1248、1262–1272**；`DeqModule.sv` **490–510**。
普通Store尾段地址/mask/data正确，唯独wline被相邻zero污染为1。
`sbuffer/Sbuffer.scala` **148–156**的`... || line_write_buffer_wline`使整line字节
写使能，证明wline不是don't-care。相邻zero未committed也能污染，因为split分支
会越过lane1普通有效条件，wline又未随数据owner一起mux。

### B9. DEQ-ZERO-001：用旧FIFO请求的fire完成CBO.zero（15个FAIL）

**是bug。** 不能把“总线有一次消费”当成“本owner的副作用完成”。

```scala
is(CboState.writeZero) {
  when(io.writeToSbuffer.req.head.fire) { cboStateNext := CboState.flushSb }
}
cboStall(0) := ctrlEntry.isCbo && !(cboState === CboState.writeZero && dataQueue.io.empty)
io.writeToSbuffer <> dataQueue.io.toSbuffer
```

代码：SQ **975–983、1212–1219、1289–1294**；`DeqModule.sv` **324–329、385–390**。
当旧普通Store仍驻留FIFO时，zero不能入FIFO；旧Store消费的同一拍却令zero FSM
退出writeZero。随后flush/WB/释放发生，zero自身的零写从未传输。
混合用例最先出现的`flush=1/expected0`也是这一根因，不能因为未等到WB就误归
为split，或把flush比较直接静音。

### B10. DEQ-FINISH-ORDER-001：晚完成项无身份增加SQ释放数（20个FAIL）

**是bug。** rdata领先deq是实际允许的，因此不能把源码注释的两者相等当约束。

```scala
val uncacheMove = VecInit(deqCtrlEntries.map(x => x.handleFinish && x.committed && !x.vecInactive)).asUInt
val deqCount = Cat(deqPtrMoveFromSbuffer.asUInt, deqPtrVectorInactiveMove, uncacheMove)
io.sqDeqCnt := PopCount(VecInit(deqCount).asUInt)
io.deqPtrExtNext := io.deqPtrExt.map(_ + io.sqDeqCnt)
```

代码：SQ **1296–1324、1658–1659**；`DeqModule.sv` **343–360**。
旧普通项尚在Sbuffer背压，年轻NC ack/IO WB已将第二项handleFinish置1，PopCount
仍释放从head开始的一项，把年轻完成错误地记给旧head。SQ **1698–1701**等逻辑
据deqCancel清除老entry，Forward又不查EnterSbufferQueue，故不是纯内部无害计数。
需要连续完成前缀/身份对齐，而非对每种完成信号各自计数后直接相加。

### B11. LSQ-BUS-OWNERSHIP-001：旧NC响应解锁后来串行owner（6个FAIL）

**是bug。** outstanding允许NC不占串行状态，不意味着它们之后的响应属于后来
进入的串行事务。

```scala
// NC在outstanding开启时不占pendingstate
Mux(io.uncacheOutstanding && io.uncache.req.bits.nc, s_idle, ...)
// s_load与s_store却都在任意共享响应上退出
when(io.uncache.resp.fire) { pendingstate := s_idle }
```

代码：`LSQWrapper.scala` **282–300、311–325**；`LsqWrapper.sv` **1499–1508**。
旧NC Load返回时，后来IO Store仍欠自己的响应，Wrapper却重新暴露下一请求。
响应按is2lq路由与是否完成串行owner是两个问题；当前清状态没有核对方向/身份。
`Uncache.scala` **365–384**的e0拒绝条件也没有保证接受另一block IO前必须先排空
所有旧NC。因此不能依赖一个不存在的外围互斥来判为误报。

## 三、7个“不是RTL bug”的失败：逐类说明原因

### N1. VSQ同拍dispatch+redirect（2个）

**不是RTL bug：刺激违反固定上游互斥。**
`LSQWrapper.scala:499–502`先`!redirect`门控后寄存dispatch，`MemBlock.scala:494`
把同源redirect延迟一拍，`1055–1058`直连两者。VSQ看到的正常dispatch与redirect
严格互斥。这两个测试直接绕过producer同时送入两者，所报ghost不构成该路径bug。

节点：`tests.vsq.test_extended::test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost[0/7]`。

### N2. 多MMIO selector（1个）

**不是RTL bug：pending非法越过未完成MMIO。**
`LoadQueueUncache.scala:122–126`用pending授权MMIO；真实`Rob.scala:1248–1258`
的pending源自ROB deq头。用例却把它推进到两个未完成MMIO之后，人为制造多个
selector。正常ROB不能先越过仍未完成的前一条MMIO，再要求低优先selector保持。

节点：`tests.load_uncache.test_timing_boundaries::test_multiple_mmio_selectors_interface_priority_not_rob_legality_claim`。

### N3. 两个混合排空超时（2个）

**不是RTL bug：验证producer把RAR回滚错接成C_NK循环。**
`tests/lsq_wrapper/mixed_owners.py:316–328`把RAR nuke变成`Cause.VIOLATION`；
`224–231`将同一老Load反馈到Replay，没有取消年轻已released的Load，RAR条件
始终存在。实际失败窗口直接确认：没有STA有效，RAR.valid/nuke=1，之后同ROB
被注入`causes=2048`，没有redirect，反复循环。不是RTL拒绝执行公平流量。

正确源合同：`NewLoadUnit.scala:1118–1125`的C_NK来自STA nuke；
**1496–1504**的RAR违约走`rollback + RedirectLevel.flushAfter`。两者不能混用。

节点：
- `tests.lsq_wrapper.test_normal_cbo_mixed::test_normal_cbo_full_domain_original_seed_all_kinds_and_fair_obligations[28934]`
- `tests.lsq_wrapper.test_serialized_mixed::test_serialized_CBO_full_domain_original_kinds_seeds_and_original_fair_obligations[28928]`

### N4. 原混合seed28928的前递物理producer断言（1个）

**不是RTL bug：该首次失败依赖伪造的8B CBO.zero包，不是普通Store别名反例。**

逐源检查后，断言中的“newest physical slot6”实际是CBO.zero，size=3、mask=0xff、
起始offset0；Load读offset12，检查器仍把该zero当作整line producer。旧actor的
`mixed_owners.py:83、118–119`给CBO沿用8B大小，`SpecialStore.address()`未覆盖size。

但固定`NewStoreUnit.scala:430–438`明确：

```scala
toSqAddr.paddr := Mux(isCbo, alignVWordAddr(paddr), paddr)
toSqAddr.vaddr := Mux(isCbo, alignVWordAddr(vaddr), vaddr)
toSqAddr.size := Mux(isCbo, MemorySize.QB.U, size)
```

实际应为16B包；SQ又按size生成连续mask，故应为0xffff。旧包的范围0..7不命中
12..13，真实包0..15会命中；这个失败依赖的关键条件因此消失。不能把它与B1
的12个普通跨VA Store反例合并。后来的normal-CBO同seed首次FAIL是另一SID问题，
对应节点另有B4裁定，不用它替换或删除旧FAIL。

节点：`tests.lsq_wrapper.test_seeded_mixed::test_one_global_rob_full_mixed_domain_original_obligations_and_fair_drain[28928]`。

### N5. head预许可后自取消容量用例（1个）

**不是RTL bug：用例撤销已获不可撤回许可的无异常普通Store，并提前删除owner。**

`vsq_cancel_capacity.py:115–126`让ROB头停在本Store、STA/STD/S2全完成、Sbuffer
背压，之后直接对同一head发flushSelf。`VirtualStoreQueue.scala:282–284`已经
给出precommit；SQ **1995–2007**允许无异常、S2完成项提交，**727–735**的真实
EnterSbufferQueue没有redirect撤回接口。`actor.py:330–340`仍删除旧owner，随后
真实旧FIFO字节出现，`next(live owner)`抛StopIteration。

对**该无异常scalar历史**，不能凭“ROB还没有retire”就认为Store尚可撤回：
- 正常分支/Load回滚不撤销更老的ROB头Store；
- STA异常/debug trigger在`NewStoreUnit.scala:476–478`进入hasException，阻止PSQ提交；
- singleStep项由`Dispatch.scala:594–595`阻止进入IQ，不会形成该STA/STD全完成历史；
- 含Store的entry经`CompressUnit.scala:94–96、296–300`得到interruptSafe=false，
  `Rob.scala:768`因此不给IRQ自取消。

因此旧FIFO字节并非“取消后泄漏的新RTL bug”，而是仍欠消费的合法不可撤回副
作用；错误在测试取消许可/owner账本。此裁定不扩大成任意vector、压缩slot或
异常重定向均已证明的定理，但该失败节点已能明确判定，不再列“待定”。

节点：`tests.store_queue.test_cancel_capacity::test_real_cancel_capacity_old_bytes_and_every_new_UID_normal_consumption[True]`。

## 四、范围、保持及可复核性

1. 本报告覆盖原两范围并集全部228节点；不把新诊断工具错误、历史reset误报混入
   当前7个非RTL失败，也不扣减历史JUnit的FAIL数。
2. “是bug”按模块支持域裁定，不冒充完整核ISA后果；legacy上游字段错误若不在
   当前违约的因果锥，不可拿来掩盖已有合法反例的同一RTL根因。N4则相反，非法
   size正是首次失败必要条件，故明确判为不是RTL bug。
3. 原已确认PA[6]来源错误继续保留，不恢复任何旧上游合法性声明。没有修改目标
   RTL、全局静音断言、skip/xfail或将旧失败变为PASS。
4. 对缺失的首次违约信息仅保留有界失败窗口，原字节无损gzip归档；无完整逐拍
   trace、全量波形或源码副本。源审计脚本是`tools/audit_fail_source_verdicts_v1.py`。
5. 新诊断第一次运行因格式器处理结构化RAR响应失败而中断，该exit3原件仍保留，
   不冒称完整回归。此事实记录在机器报告附录，不参与RTL二元裁定。原141产物
   指纹、全部旧测试/参考/fixture/manifest及四原索引保持。

最终交付是源码裁定及逐FAIL索引，不以仿真执行过程作为结果，也不代表RTL已经
修复或LSQ整体功能/覆盖率验收完成。

交付核验：`results/fail-source-adjudication-01/binary-source-final-receipt-v1.json`
实际exit0；JSON/CSV的238个唯一节点、231/7二元结果及11个RTL根因一致，连续两次
源码/证据审计幂等，旧141原件及旧验证源码保持。没有留下待裁定节点。
