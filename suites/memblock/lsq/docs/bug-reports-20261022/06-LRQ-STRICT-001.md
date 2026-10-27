# LRQ-STRICT-001：valid为0的输入也能解除Load的严格等待

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。11个原失败节点及3个独立补充探针失败属于同一根因。

## 1. 用一句话理解

一个Load本来必须严格等待更老的Store满足条件。另一个输入入口本拍没有有效事务，但它留在数据线上的槽号仍被使用，偷偷把这个Load的`strict`状态清掉了。

好比“本窗口不办理业务”的空白工单，仍然改掉了别人的审批条件。

## 2. 正常行为

`strict`表示不能只凭某一个Store地址ready位就提前放行。`valid=0`时，输入payload可以是旧值、任意合法位模式；接收方不能因此修改一个仍然活动的事务。

这里不是要求RTL的每一根无效数据线必须输出0，而是要求**无效输入不能改变将来的有效调度结果**。

## 3. 有问题的Scala实现

文件：[LoadQueueReplay.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala)，**825–829行**：即使`valid=0`，组合索引仍由payload或分配器输出决定。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:825-829 -->
```scala
    //  Allocated ready
    val offset = PopCount(newEnqueue.take(w))
    val enqIndex = Mux(enq.bits.isLoadReplay, enq.bits.schedIndex, freeList.io.allocateSlot(offset))
    enqIndexOH(w) := UIntToOH(enqIndex)
    enq.ready := true.B
```

**861–866行**：问题不在合法写入分支，而在没有握手门控的`otherwise`。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:861-866 -->
```scala
    // special case: data forward fail
    when (enqFireBase && isMA) {
      strict(enqIndex) := enq.bits.uop.loadWaitStrict
    }.otherwise{
      strict(enqIndex) := false.B
    }
```

其中`enqFireBase = enq.fire && !cancelEnq(w)`。没有有效握手时条件为假，恰好执行清零。

**393–395行**说明被清掉的状态有真实用途：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueReplay.scala:393-395 -->
```scala
    dataNotBlockVec(i) := io.stDataReadySqPtr.isAfter(blockSqIdx(i)) || stDataReadyVec(blockSqIdx(i).value) || io.sqEmpty // for better timing
    addrNotBlockVec(i) := io.stAddrReadySqPtr.isAfter(blockSqIdx(i)) ||
    !strict(i) && stAddrReadyVec(blockSqIdx(i).value) && blockSqIdx(i) < io.physicalUpperSqIdx || io.sqEmpty // for better timing
```

## 4. 怎样激励

已有独立公开端口探针使用以下场景：

1. 正常入队一个Load：`ROB=10、LQ=20、SQ=8`，地址依赖指向`SQ7`，`loadWaitStrict=1`，原因为`C_MA`。
2. 地址ready位图中仅`bit7=1`，但连续地址ready指针仍为0，没有匹配的实际Store执行唤醒，SQ也没有变空。
3. 先等若干拍，确认该Load确实被严格阻塞。
4. 在任一输入lane放`valid=0、isLoadReplay=1、schedIndex=0`。该槽号与活动项碰撞；测试枚举槽号和lane，没有读写内部DUT寄存器。
5. 继续等待，**仍然不发合法解除依赖的事件**，观察有效Replay输出。
6. 对照场景才将连续ready指针推进到8，正常放行原Load。

| 条件 | 正确结果 | 原RTL实际结果 |
|---|---|---|
| 只有单个地址ready位 | strict仍阻止放行 | 起初阻止 |
| 无效feedback碰到活动槽 | 什么也不应改变 | 活动槽`strict`被清零 |
| 随后只有原来的ready位 | 仍不应出现Replay.valid | 出现提前的有效Replay |

位图为0、或者无效payload没有碰到活动槽的对照不必失败；它们不否定这个明确的因果组合。

## 5. 根因和后果

代码把“本拍没有需要写strict的事件”写成了“本拍必须把某个strict清零”。每个lane都会执行这个分支；在池满时，分配器没有可用新槽的输出也可能命中旧活动项。

- **已经观察到**：没有合法唤醒时`io_replay_0_valid=1`，预期为0；独立探针在3个输入lane分别复现。
- **直接后果**：严格依赖约束被放松，Load提前重放。
- **边界**：提前重放不自动等于整核已经提交错误值。是否被后续检查纠正，需要更高层证据，不能据此夸大。

正确方向是只有真实owner更新事件才能写状态；没有更新事件时保持。不能要求所有`valid=0`的输入payload都清零来规避问题。

## 6. 复现和证据

- 原满池测试：[test_extended.py](../../tests/replay/test_extended.py)，`test_strict_full_pool_is_not_unblocked_by_only_ready_bits`。
- 独立探针：[test_public_contracts.py](../../tests/fail_review/test_public_contracts.py)，`test_invalid_feedback_must_not_relax_a_live_strict_owner[True-0-0-load_queue_replay]`；最后一个0为输入lane。
- 生成RTL：`rtl/load_queue_replay/LoadQueueReplay.sv:11212–11221、24112–24114、33683–33697`。
- [全量裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`LRQ-STRICT-001`及补充探针。

## 7. GitHub状态

未找到明确报告“未入队lane清除活动strict”根因的Issue/修复PR。[PR #6286](https://github.com/OpenXiangShan/XiangShan/pull/6286)调整StoreSet预测器中的strict刷新/过滤，不是Replay entry被无效入口写坏。[PR #5963](https://github.com/OpenXiangShan/XiangShan/pull/5963)的优化补丁中已经出现上述写法，但**代码曾在GitHub出现，不等于该缺陷已经作为bug被报告**。
