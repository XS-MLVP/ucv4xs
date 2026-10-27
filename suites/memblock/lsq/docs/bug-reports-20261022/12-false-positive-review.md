# 误报复核：哪些失败不是RTL bug，为什么会误报

## 1. 先把数量说清楚

**有误报，但不是把本文件夹的11个RTL bug再减掉几个。** 此前已经完成的全量源码裁定，在228个原失败节点中区分出：

| 范围 | 是RTL问题的失败节点 | 不是RTL问题的失败节点 |
|---|---:|---:|
| 两次原回归的去重并集 | 221 | **7** |
| 加上独立补充探针后的并集 | 231 | **7** |

221/231个RTL问题节点归并为11个根因；7个非RTL节点归并为下面**5类验证侧原因**。这不是“发现了238个独立bug”，也不是“已经修好了7个RTL bug”。

本轮是对已有源码、测试和失败证据的文档复核，没有新跑DUT；目前未发现需要新增撤回上述11个根因的证据。这里保留并总结的是已有完整裁定的误报，不冒称本轮又新排除了7个bug。

权威入口：[全量源码裁定报告](../reports/all-fail-source-verdicts-20261022.md)及[逐节点JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)。旧JUnit中的FAIL保留，没有改成PASS或xfail。

## 2. 误报一览

| 类别 | 节点数 | 测试看到的现象 | 真正原因 |
|---|---:|---|---|
| VSQ同拍dispatch＋redirect | 2 | 像是取消后还有幽灵项 | 测试直接送入真实上游不会同时送达的两个信号 |
| 多MMIO selector | 1 | 多个MMIO选择/优先级不符合预期 | 测试把ROB pending越过了尚未完成的老MMIO |
| 混合流排空超时 | 2 | Load反复重放，5000拍不排空 | 测试把RAR回滚误接成C_NK反馈，没有取消冲突年轻Load |
| 伪8B CBO.zero前递 | 1 | Load没有得到检查器认为应有的zero字节 | 刺激包大小错了，参考却按整行zero推导字节来源 |
| 已获许可Store被人为自取消 | 1 | “取消后旧字节又出现”，owner查找失败 | 测试撤销了已不可撤回的副作用，并提前删了owner记录 |
| **合计** | **7** |  | **5类原因** |

## 3. 第一类：绕过真实上游的互斥关系

### 测试原来怎样想

同一拍既给VSQ新分派，又给redirect，要求它仍能正确恢复，不能留下未被取消的项。

### 为什么不是本路径的RTL bug

固定源码中：

- `LSQWrapper.scala:499–502`先用`!redirect`门控分派，再寄存送出。
- `MemBlock.scala:494`把同源redirect也延迟一拍。
- `MemBlock.scala:1055–1058`把这两路连接到LSQ。

因此VSQ正常看到的这两个输入互斥。直接对子模块施加一个没有该producer来源的组合，只能算接口压力，不能自动升格成正常路径bug。

### 对应失败

`tests/vsq/test_extended.py::test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost[0]`与`[7]`。

### 以后怎样避免

先把真实上游的互斥、延迟和握手写成刺激准入条件。压力测试可以保留，但必须标注为越域，不能与正常微架构缺陷混计。

## 4. 第二类：把ROB许可当作可以任意提前的输入

### 测试原来怎样想

推进`pendingPtr`，让多个MMIO都变成可发出，检查它们同时成为selector时的顺序。

### 错在哪里

`LoadQueueUncache.scala:122–126`用pending判断MMIO是否获得许可。真实`Rob.scala:1248–1258`的pending来自ROB队头；老MMIO还没完成，ROB不能先提交并越过它，再许可后面的MMIO。

测试却直接把pending推进到两个未完成MMIO之后。它制造的多selector不属于这里已经支持的正常历史，不能要求RTL满足一个生产者不会提出的前提。

对应节点：`tests/load_uncache/test_timing_boundaries.py::test_multiple_mmio_selectors_interface_priority_not_rob_legality_claim`。

### 教训

端口能编码一个值，不表示正常上游能在这个时刻发出该值。特别是ROB头、提交许可和回收指针，必须与原事务完成账本一起检查。

## 5. 第三类：把RAR回滚错接成Replay循环

### 看起来为什么像RTL死锁

同一个Load不断重放，最终超过公平排空期限。仅看超时，很容易认为Replay或RAR不能前进。

### 真正的因果链

1. RAR报告Load–Load顺序冲突。
2. 正常LDU应产生`rollback + RedirectLevel.flushAfter`，丢弃相关年轻结果。
3. `tests/lsq_wrapper/mixed_owners.py:316–328`却把RAR nuke转成`Cause.VIOLATION`，即C_NK。
4. `mixed_owners.py:224–231`又把原老Load送回Replay，未取消年轻已released的Load。
5. 年轻冲突项一直存在，每次重试都命中同一个冲突，形成验证环境制造的循环。

源码区分非常明确：`NewLoadUnit.scala:1118–1125`的C_NK来自STA nuke；RAR走`1496–1504`的flushAfter回滚。

### 不是仅凭代码猜测

[额外补证索引](../../results/fail-source-adjudication-01/extra-captures-index-v1.json)和`results/fail-source-timeout-cause-01/`实际公开窗口确认：RAR有效且nuke=1，后面同ROB被注入`causes=2048`，没有STA有效，也没有redirect。

两个节点：

- `tests/lsq_wrapper/test_normal_cbo_mixed.py::test_normal_cbo_full_domain_original_seed_all_kinds_and_fair_obligations[28934]`。
- `tests/lsq_wrapper/test_serialized_mixed.py::test_serialized_CBO_full_domain_original_kinds_seeds_and_original_fair_obligations[28928]`。

### 教训

“让原请求重试”和“回滚年轻请求”不是可互换的恢复方式。只有把冲突集合真正改变，才有资格检查公平前进。

## 6. 第四类：刺激是8B包，参考却把它当整行CBO.zero

### 首次失败是什么

旧混合seed28928的检查器认为slot6是最新的物理字节来源，Load应得到它的zero，但RTL没有选中它。

### 为什么这个首次失败不成立

slot6实际不是普通Store，而是CBO.zero。旧生成器沿用`size=3、mask=0xff`，只把offset0..7送进重叠判断；Load读取offset12..13。检查器却按“CBO.zero覆盖整line”认为它一定命中。

真实`NewStoreUnit.scala:430–438`为CBO固定产生16B对齐、`size=MemorySize.QB=4`的包。对应连续mask应为`0xffff`，覆盖offset0..15，offset12当然会命中。

非法8B大小正是首次失败的必要条件；不能拿它当作[08中的普通Store VA别名bug](08-FWD-ALIAS-001.md)。08另有合法的普通Store反例，不因这个旧混合例撤回。

节点：`tests/lsq_wrapper/test_seeded_mixed.py::test_one_global_rob_full_mixed_domain_original_obligations_and_fair_drain[28928]`。

### 教训

参考不能一半按输入字段、一半按指令宏观含义推导。需要先确认实际生产者给出的大小、对齐、mask，再判断字节来源。

## 7. 第五类：撤销了已经不可撤回的普通Store

### 测试原来怎样想

让无异常的普通Store位于ROB头，STA、STD、S2都完成，Sbuffer暂时背压。然后人为向该Store发`flushSelf`，删除owner，再检查旧字节是否完全消失。

### 为什么前提不合法

该项已经得到VSQ的precommit许可，PSQ也允许它进入`EnterSbufferQueue`；这个FIFO没有redirect撤回接口。

对这条**无异常scalar Store历史**：

- 老Store不会被后面的分支/Load回滚取消。
- Store自己的异常和trigger会在S2门控中阻止提交，不能同时假设“没有异常且S2已完成”。
- singleStep项不会进入IQ形成这段执行历史。
- 含Store的ROB entry不允许用IRQ自取消。

源码依据包括`VirtualStoreQueue.scala:282–284`、`NewStoreQueue.scala:1995–2007、727–735`、`NewStoreUnit.scala:476–478`、`Dispatch.scala:594–595`、`CompressUnit.scala:94–96、296–300`及`Rob.scala:768`。

因此旧FIFO字节仍是合法、尚未偿还的写出义务。`lsqverify/store_queue/actor.py:330–340`提前删除owner之后，才出现找不到原owner的`StopIteration`；不是RTL在合法取消后泄漏数据。

节点：`tests/store_queue/test_cancel_capacity.py::test_real_cancel_capacity_old_bytes_and_every_new_UID_normal_consumption[True]`。

### 教训和范围

“ROB还没retire”不能被简化成“任何副作用都仍可撤回”。必须明确不可撤回许可何时产生。这个结论仅解释该无异常scalar反例，不冒充对任意vector、压缩slot或异常重定向的完整证明。

## 8. 另有工具错误，但不能混进这7个语义误报

| 历史问题 | 正确处理 |
|---|---|
| 旧VSQ异步reset的采样误判 | 属于验证采样问题，不重复计入当前7个节点 |
| 曾用PA[6]推导lastBeat | 来源声明撤回；当前参数链为256bit总线→32B refill→`NewLoadUnit.scala:1613`取PA[5]，不能拿64B cacheline代替refill粒度 |
| 首批独立探针24次KeyError | 探针/字段处理错误，不是24个RTL bug；不能把工具异常当DUT语义失败 |
| 新诊断格式器对RAR结构化list做XOR，首轮exit3 | 保留175份有效有界见证，另补53个缺失节点；不得把这轮中断冒称完整回归 |
| 旧Deq随机种子曾按名称误归类 | 实际首次违约分别属于zero、finish-order等；属于根因归类纠正，不是把真实RTL缺陷变成误报 |

本轮没有改旧测试、替换参考预期、屏蔽断言或回写历史JUnit。保留失败不代表仍声称它们都是RTL bug。

## 9. 共同原因总结

五类语义误报主要来自三种问题：

1. **刺激越过真实producer约束**：互斥、ROB头、不可撤回许可没有被完整建模。
2. **参考使用了与实际输入不一致的语义**：错误的CBO包却套用整行zero范围。
3. **恢复协议接错**：用重试代替本来必须发生的回滚，制造永远不消失的冲突。

后续防误报应先做producer准入检查，再检查有效握手与原UID义务，最后才把失败上升为RTL结论。它们是改进建议，**不是本轮已经修改完这些测试的声明**。
