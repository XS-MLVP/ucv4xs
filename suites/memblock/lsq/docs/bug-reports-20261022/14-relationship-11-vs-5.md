# 11个已确认bug与5组GitHub线索的关系

本文只回答一个问题：**此前确认的11个RTL根因，与[13号文件](13-github-missed-bugs.md)列出的5组GitHub线索，是不是同一批问题？**

结论先给：

> **没有一组是11个根因的重复。**
>
> 5组线索实际是：
>
> - **4组独立RTL功能bug**：`#6704`、`#6229/#6312`、`#6634`、`#6714`；
> - **1组配置合法性问题**：`#6688/#6697`，只在非默认参数域出现，不是默认配置下的功能bug。
>
> 因此正确关系是 **11 + 4 = 15个RTL功能bug**，另有 **1个配置合法性问题**；不是“11 + 5 = 16个默认配置bug”。

这里的“独立”按**不同的根因代码位置和不同的错误机制**判断，不按失败现象是否相似判断。

## 1. 总表

| GitHub线索 | 与11个根因的关系 | 不同的代码门控 | 本地证据等级 | 计数 |
|---|---|---|---|---|
| `#6704` 跨16B Store首尾请求之间Load读旧值 | **独立新RTL bug** | `ctrlEntry.addrValid`可见性，不是VA域、mask旋转或SQ代号 | 固定源码确认；上游整核已复现；本轮未重跑 | +1 RTL功能bug |
| `#6229/#6312` 部分前递被当作完整覆盖 | **独立新RTL bug** | `s2FullOverlap`的`byteStart/byteEnd`范围判断，不是B2的旋转mask | **本轮3个lane均FAIL** | +1 RTL功能bug |
| `#6634` 多Uncache异常按物理槽序选择 | **独立新RTL bug** | `exception.valid`与`ParallelPriorityMux`，不是B4的SID数据覆盖或B11的总线解锁 | **本轮同拍双lane已FAIL**；真实故障可被正常完成抢占或丢弃 | +1 RTL功能bug |
| `#6688/#6697` `ColdDownThreshold=0`禁用Replay | **独立，但属配置合法性** | 参数断言与`counter < threshold`，不是11个默认配置功能路径 | 固定源码确认；当前DUT固定为12，未生成0配置DUT | +1配置问题，不计入15 |
| `#6714` 已退休MDP目标被误判越域 | **独立新RTL bug** | `s2MdpTargetRetired`未排除`s2MdpHitOutOfRange`，不是B3的依赖SQ身份 | **本轮3个lane均FAIL** | +1 RTL功能bug |

补充：`#6703`（mask旋转折回）**不在这5组里**，它是B2 `FWD-RANGE-001`的上游同根因记录，已经计入11个，不能再加一次。

## 2. 逐一说明

### 2.1 `#6704`：不是B1/B2/B3

**机制不同。** 固定`NewStoreQueue.scala:1683-1686`：

```scala
val addrValidSet = io.fromStoreUnit.storeAddrIn.zipWithIndex.map { case (port, j) =>
  port.bits.isLastRequest && !port.bits.tlbMiss && staValidSetVec(j)
}.reduce(_ || _)
```

跨16B Store的**首请求**已经写入`vaddr/paddr/byteMask`，但`addrValid`只由**尾请求**置位。前递候选又要求`ctrlEntry.addrValid`（`s1VaddrMatchVec`，`473-476`），因此首请求到尾请求之间，这个Store对Forward完全不可见。

- B1是`loadInNext16B`/VA页面标签把物理别名候选过滤掉（`489-505`）；
- B2是`s2OutMask`的4bit减法与`rotateByteRight`折回（`632-644`）；
- B3是低半区命中时`operation_flag`取了Load的SQ代号（`548-564`）；
- `#6704`是`addrValid`可见性窗口。

四者分别位于候选准入、mask生成、依赖身份和地址有效位，**修一个不能自动修另一个**。上游`#6704`的补丁本身也说明：它需要新增`unalignHeadValid`；另外还要配合`#6312`和旋转mask修复（即`#6703`，B2的上游同根因）才能覆盖更广的测试。

### 2.2 `#6229/#6312`：不是B2

**机制不同。** 固定`NewStoreQueue.scala:637-640`：

```scala
val s2FullOverlap = s2SelectDataEntry.byteStart <= s2LoadStart &&
  s2SelectDataEntry.byteEnd >= s2LoadEnd
val s2SafeForward = !s2MultiMatch || s2FullOverlap
```

`byteStart/byteEnd`只表示Store的16B**跨度**，不表示它实际持有的字节mask。一个16B跨度内只有低8B有效的Store（例如向量Store的部分mask），会被判成“完全覆盖”，于是`forwardInvalid=0`，缺失的高8B没有触发重放。

- B2的错误是`rotateByteRight`把没有写过的字节**多标**为可前递；
- `#6229`的错误是真实mask只覆盖一部分时，`s2FullOverlap`仍把它当作**完整覆盖**，缺失字节不被阻塞；
- 两者方向相反，代码行也不同。`#6312`把判断改成`s2OutMask === s2LoadMaskEnd`，并不是修`rotateByteRight`。

本地新探针`results/github-gap-relationship-01/`在3个lane上都复现了：

- 选中的年轻Store真实`forwardMask = 0x00ff`；
- `forwardInvalid/matchInvalid/addrInvalid/dataInvalid`均未置位；
- 响应被当作安全前递接受。

这组失败与B2的28个失败节点不同：B2的典型现象是`0xf00f`这类**多余位**；这里是`0x00ff`的**缺失位**。

### 2.3 `#6634`：不是B4，也不是B11

**机制不同。** 固定`LoadQueueUncache.scala:236-239`：

```scala
io.exception.valid := RegNext(writeback)
io.exception.bits := RegEnable(req, writeback)
io.exception.bits.uop.exceptionVec(loadAccessFault) := RegEnable(nderr, writeback)
io.exception.bits.uop.exceptionVec(hardwareError) := RegEnable(derr, writeback)
```

`writeback`是`ncOut.fire`或`mmioOut.fire`，**正常完成也会fire**。因此每个正常完成的entry也会产生`exception.valid=1`，只是异常位为0。父级`467-470`又用`ParallelPriorityMux(entries.map(...))`按**物理entry顺序**选第一个，而不是按`robIdx/uopIdx`的程序年龄选。

- B4是SID重用把**旧Load的数据/错误**覆盖；
- B11是旧NC响应把**后来串行owner的状态**错误解锁；
- `#6634`是异常候选的`valid`和仲裁顺序错误，导致正常完成项可能遮住真正的故障项，产生错误`robIdx/mtval`。

这三者可以同时存在于LQU，但错误对象、代码位置和后果都不同。上游PR `#6634`明确把它描述为“select the oldest bus exception by (robIdx, uopIdx)”。

### 2.4 `#6688/#6697`：是配置合法性问题，不是默认配置功能bug

固定`LoadQueueReplay.scala:656-663`：

```scala
val ColdDownThreshold = Wire(UInt(log2Up(ColdDownCycles).W))
ColdDownThreshold := Constantin.createRecord(..., initValue = 12)
assert(ColdDownCycles.U > ColdDownThreshold, "ColdDownCycles must great than ColdDownThreshold!")

def replayCanFire(i: Int) = coldCounter(i) >= 0.U && coldCounter(i) < ColdDownThreshold
```

阈值为0时，`counter < 0`永远不成立，Replay不能前进；而现有断言只禁止“大于等于16”，**没有禁止0**。上游`#6697`的处理是增加合法性断言，不是支持0正常运行。

但当前原生DUT的生成RTL已经把阈值固化为12（`LoadQueueReplay.sv:10594-10596`、`38143-38154`里的`4'hB`），所以：

- 这不是默认配置下11个功能bug之一；
- 它也不应该被说成“当前DUT已跑出的第15个功能bug”；
- 它是**参数域/断言缺陷**，需要单独生成0配置DUT才能做原生验证。

因此它单独计1个配置问题，但不并入15个RTL功能bug。

### 2.5 `#6714`：不是B3

**机制不同。** 固定`NewStoreQueue.scala:579-584`：

```scala
val s2MdpTargetRetired   = s2LoadWaitBit && s2WaitSqIdx.isBefore(s2DeqPtr)
val s2MdpHitOutOfRange   = s2LoadWaitBit && s2WaitSqIdx.isNotBefore(s2PhysicalQueueUpper)
val s2MdpHitInPhysical   = s2LoadWaitBit && s2WaitSqIdx.isNotBefore(s2DeqPtr) &&
  s2WaitSqIdx.isBefore(s2PhysicalQueueUpper)
val s2PreciseMdpWait     = s2MdpHitInPhysical && !io.ctrlEntriesIn(s2WaitSqIdx.value).addrValid
val s2NeedPreciseMdpWait = s2PreciseMdpWait || s2MdpHitOutOfRange
```

`s2MdpTargetRetired`已经算出，但**没有用于排除**`s2MdpHitOutOfRange`。当目标的flag/value在物理窗口上表现为“越域”、实际上已经退休时，Load会等待一个永远不会再来的STA。

- B3是`dataInvalid.bits`返回了错误的SQ代号（数据依赖身份）；
- `#6714`是`addrInvalid.valid`错误地保持等待（地址依赖资格）。

本地新探针用`deq=131`、`upper=195`、等待目标`66`，在3个lane上都得到：

```text
io_query_{0,1,2}_s2Resp_bits_addrInvalid_valid
  actual = 1
  expected = 0
```

这与B3的`dataInvalid`身份失败是不同输出、不同信号、不同根因。

## 3. 证据等级与计数

| 口径 | 数量 | 说明 |
|---|---:|---|
| 之前已确认的独立RTL根因 | **11** | 221个原回归失败节点归并；不重复计种子/lane/父子层 |
| 本轮关系核验新增的独立RTL功能bug | **+4** | `#6704`、`#6229/#6312`、`#6634`、`#6714` |
| 关系核验后的RTL功能bug总数 | **15** | 接受“固定源码+上游复现”作为确认依据 |
| 其中本轮本地DUT直接复现 | **+3** | `#6229`、`#6714`、`#6634`；`results/github-gap-relationship-01/` 与 `results/uncache-exception-property-05/` |
| 其中仅固定源码+上游复现、本轮未重跑 | **+1** | `#6704`；不冒充本地已跑 |
| 单独的配置合法性问题 | **1** | `#6688/#6697`；默认DUT阈值为12，未生成0配置 |

如果只接受“本轮本地DUT重跑”作为确认，则目前是 **11 + 2 = 13个本地已复现RTL功能bug**；另外2个是源码/上游确认、尚未本地重跑；1个是配置问题。无论采用哪个口径，**都不能把5组直接加成5个默认配置功能bug**。

## 4. 为什么之前没有发现这4个RTL问题

这不是“覆盖率不够”四个字能解释的，具体盲区如下：

| 线索 | 之前为什么没发现 |
|---|---|
| `#6704` | 现有`memory_owners.write()`把跨16B Store的首包和尾包连续发完，再等稳定状态检查；没有“首包后、尾包前插入Load”的必达窗口 |
| `#6229/#6312` | 旧`ForwardModel.expected()`的`full`也用`byteStart/byteEnd`范围（`forward/model.py:100-104`），和RTL同源；`check_physical_safety()`只检查“已宣称前递的字节”，不检查“应当前递却缺失的字节” |
| `#6634` | 旧`UncacheEntryModel`在每次消费时也构造`FaultReport(True, ...)`（`uncache_entry/model.py:96-100`），父级模型也按entry顺序取第一个（`load_uncache/model.py:165`）；参考与RTL同源，且旧测试的分配顺序与ROB年龄一致 |
| `#6714` | 旧`retired`对照只用`deq=1/upper=65/wait=0`，没有构造“目标已退休、同时在flag/value上表现为越域”的跨代组合 |

这四条的修正方向也分别不同：

1. `#6704`：首包后插入Load，检查它应被阻塞或前递，而不是稳定态；
2. `#6229`：按真实Post-rotation mask检查完整覆盖，并检查“缺失字节必须重放”；
3. `#6634`：按不可变`robIdx/uopIdx`年龄选异常，且正常完成不应产生异常候选；
4. `#6714`：构造跨flag的已退休等待目标，检查`addrInvalid.valid`必须为0。

### 4.1 是“没做完”还是“测试设计漏了”？

按证据分开判断，**不能统一归因于进度不足**：

| 线索 | 性质 | 判据 |
|---|---|---|
| `#6704` | **测试设计漏了** | `memory_owners.write()`在同一函数内连续发首尾包；调用者`await write_all()`后才`forward()`。即使把计划内全部用例跑完，这个窗口也不会被任何现有用例走到 |
| `#6229/#6312` | **测试设计漏了（参考同源）** | 模型`full`判断与RTL `byteStart/byteEnd`语义等价，RTL错、模型也错，期望值本身是错的，因此永远PASS |
| `#6634` | **测试设计漏了（参考同源＋刺激域）** | 模型同样在任何消费时产生`valid=True`异常，也按物理entry顺序取第一个；RTL与模型一起错 |
| `#6714` | **验证范围没做完** | 模型`precise_wait`已先排除已退休目标，具备发现能力；但定向用例只测`deq=1/upper=65/wait=0`，没有跨flag回绕组合。`ut-plan`里“年龄域/回绕”尚未操作化到这个组合 |
| `#6688/#6697` | **配置域未纳入验证范围** | 原生DUT阈值固定为12，测试清单没有0配置变体。这是验证范围的合理裁剪，不是参考错误 |

因此：

- **3个是“测试漏了”**：`#6704`、`#6229`、`#6634`。它们属于**结构性漏检**：不改变驱动或参考模型，继续增加随机种子、提高覆盖率、延长运行时间都不会发现。
- **1个是“没做完”**：`#6714`。参考模型有能力发现，缺的是那一个跨代组合的激励。
- **1个既不是漏了也不是没做完**：`#6688`是配置域问题。

### 4.2 方法论上的原因

之前的11个根因来自**对228个FAIL逐条归因**。这个方法有一个固有边界：

> 它只能发现“已经被激励暴露”的问题。不产生FAIL的语义缺口，不会进入归因池。

- `#6704`：驱动结构跳过了危险窗口 → 不产生FAIL；
- `#6229`：参考与RTL同源，双方都认为“安全” → 不产生FAIL；
- `#6634`：参考与RTL同源，双方都选第一个 → 不产生FAIL。

这三类问题在“FAIL归因”视角下是**不可见的**。它们不是被判定为PASS，而是根本没有被提问。

这也是为什么它们直到主动阅读上游Issue/PR、把外部语义与本地实现对照时才浮现：外部报告提供了“本地激励尚未覆盖的语义”这个新输入。

要把这类问题纳入常规验证，需要在FAIL归因之外增加**正向性质检查**：

- 对每个前递响应，独立问“所有应当由未完成Store提供的字节，是否都被前递或被阻塞”，而不只看“已前递的字节是否来源正确”；
- 对每个异常汇聚，独立问“正常完成是否产生了异常候选”“同拍多候选是否按程序年龄选最老”；
- 对每个跨16B Store，独立问“首请求到达后、尾请求到达前，这个Store是否已经对后来的Load可见”；
- 对MDP等待，独立问“目标已退休时，是否仍保持越域等待”。

单项性质检查不依赖随机命中，也不依赖参考模型与RTL是否同源。

### 4.3 “参考同源”是怎么发生的，以及怎么修

#### 为什么会同源

不是有人故意抄RTL，而是三个过程叠加：

1. **模型是按RTL字段写的。** 为了预测每个引脚，模型自然采用了RTL的分解方式。
   - `forward/model.py:100`：
     ```python
     full = store.vaddr % 16 <= start and store.vaddr % 16 + store.length - 1 >= end
     ```
     与RTL `NewStoreQueue.scala:637`的`byteStart <= s2LoadStart && byteEnd >= s2LoadEnd`是同一个谓词；`byteStart/byteEnd`本身又由同样的`vaddr/size`算出。两边都只看“跨度”，都不看真实byte mask。
   - `uncache_entry/model.py:96-100`在任何消费时都构造`FaultReport(True, ...)`，对应RTL `LoadQueueUncache.scala:236`的`io.exception.valid := RegNext(writeback)`；父级`load_uncache/model.py:165`又按entry顺序取第一个，对应RTL `ParallelPriorityMux(entries...)`。
2. **检查形式是“预测引脚值”，不是“断言性质”。** `expected()`返回一组期望值，比较方式是相等。RTL怎么决策，模型就怎么期望；**两方同时错时，相等仍然成立**。所以这种结构无法表达“这里必须阻塞”或“正常完成不得产生异常候选”。
3. **调试循环把模型拉向RTL。** 每当模型和RTL不一致，通常先怀疑模型并修正——本工程就发生过多次（`last_beat`从PA[6]改到PA[5]、RAR相位、Replay原因映射）。这些修正是必要的时序校准，但在缺少独立规格时，“模型与RTL一致”逐渐变成了验收标准。

结果不是“模型读了DUT内部寄存器”，而是**模型复制了RTL的决策结构**。它仍然没有读内部状态，仍然有独立实现，但在被复制的那个判断上是同源的。

#### 怎么修

**第一步：把角色拆开。**

| 角色 | 允许做什么 | 不允许做什么 |
|---|---|---|
| 时序预测器 | 复制RTL流水/握手，预测引脚值 | 单独作为“功能正确”的证据 |
| 性质oracle | 只读原始激励账本和公开输出，断言必须成立的性质 | 读取RTL中间字段（`byteStart/byteEnd`、`ctrlEntry`、内部mask） |

**第二步：性质必须来自不可变的生产者账本。**

新增`lsqverify/independent_properties.py`，已实现两个oracle：

- `forward_byte_violations()`：对Load需要的每个字节，按程序顺序找**真正写过该PA字节**的最年轻Store（用原始`paddr/size/mask/data`，不读RTL跨度）；若该字节既没被前递、响应也没阻塞，就是违约。
- `exception_candidate_violation()`：只有真实总线错误的entry才能成为候选；多候选时必须按`(robIdx,uopIdx)`程序年龄选最老，而不是物理槽号。

它们不做引脚预测，因此不会因为RTL写错而一起写错。

**第三步：给oracle做灵敏度门禁。**

一个只会“永远失败”的检查没有价值；一个只会“永远通过”的检查更危险。所以每个性质测试必须同时证明：

1. 在bug现场**失败**；
2. 在干净对照上**通过**；
3. 对干净trace注入一个“丢失字节”后**再次失败**（证明它确实检查了该字节）。

**第四步：实测。**

运行`independent-property-oracle-03`（7节点）：

| 测试 | 预期 | 实际 |
|---|---|---|
| 部分mask Store + 16B Load，3 lane | 失败（丢失8个字节） | **3/3 FAIL**，报出byte 8..15 “neither forwarded nor blocked” |
| 完整覆盖Store对照，3 lane | 通过 | **3/3 PASS** |
| 同一对照注入`forwardMask_8=0` | 必须报违约 | 通过（说明oracle不是恒真） |
| 已退休MDP目标，3 lane→1 lane | 必须不等待 | **FAIL**，`addrInvalid_valid=1` |

这一步证明：**不依赖引脚预测器，也能抓住`#6229`和`#6714`。**

**第五步：把性质检查变成独立门禁，而不是替代预测器。**

预测器仍保留，用于比对时序和背压；性质oracle作为**额外**门禁加入回归。两者任何一个失败都必须保留为失败。对`#6704`、`#6634`还需要补同类性质：

- `#6704`：首请求后、尾请求前插入Load，性质是“该Store的字节必须被前递或阻塞”；
- `#6634`：让物理槽号与ROB年龄反序，性质是“正常完成不得产生候选”“候选必须按程序年龄选最老”。

**第六步：修改语义判断时必须引入外部锚点。**

以后凡是要改模型里的“完整性/顺序/选择”判断，必须同时给出一个不来自RTL的依据：ISA规则、上游Issue的最小复现、或不可变账本推导。仅仅“改完与RTL一致”不再算通过。

代码与证据：

```text
lsqverify/independent_properties.py
tests/fail_review/test_independent_forward_property.py
results/independent-property-oracle-03/pytest.xml
```


## 5. 与旧报告的关系

- 本文不修改11份bug报告的任何结论；
- 本文不把5组线索回填到原有228个失败节点的统计；
- 本文新增的`github-gap-relationship-01`是独立探针，不与原回归计算通过率；
- 本文不修改RTL、旧参考、旧测试或历史JUnit；
- `#6703`已作为B2的上游同根因记录，**不再另计**。

新的本地探针产物：

```text
results/github-gap-relationship-01/execution/manifest.json
results/github-gap-relationship-01/pytest.xml
results/github-gap-relationship-01/relationship-v1.json
```

该运行共6个节点（2类×3 lane），**6 FAIL**；这不是修复后的回归，而是两个新增根因在当前固定DUT上仍然存在的证据。`relationship-v1.json`保存了关系表、计数、测试与本文SHA，`pytest.xml`保存了逐lane的实际失败点。
