# DEQ-FINISH-ORDER-001：年轻Store完成，未完成的老Store却被释放

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。20个原失败节点归于这个根因。

## 1. 用一句话理解

SQ必须从队头开始按顺序回收。现在RTL只数“完成了几个”，却没检查“从队头开始的这几个是否都完成”。所以第二个完成时，第一个即使没有完成也会被回收。

排队取号的类比：2号办好了，不代表可以把1号的记录删除。

## 2. 为什么会有两个不同的队头

- `rdataPtr`：接下来处理哪个Store，可在普通Store进入缓冲后前进。
- `deqPtr`：接下来真正回收哪个SQ项，普通Store要等实际Sbuffer消费对应义务后才能前进。

所以Sbuffer背压时，`rdataPtr`领先`deqPtr`是允许的，不是测试伪造了一个不可能的指针关系。

## 3. 有问题的Scala实现

文件：[NewStoreQueue.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala)，**1318–1324行**：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1318-1324 -->
```scala
    private val uncacheMove = VecInit(deqCtrlEntries.map(x => x.handleFinish && x.committed && !x.vecInactive)).asUInt

    // The credit vector needs one more cycle because storeQueue forwarding observes the entry for one additional cycle.
    val deqCount = Cat(deqPtrMoveFromSbuffer.asUInt, deqPtrVectorInactiveMove, uncacheMove) // timing is ok ?

    io.sqDeqCnt := PopCount(VecInit(deqCount).asUInt)
    io.deqPtrExtNext := io.deqPtrExt.map(_ + io.sqDeqCnt)
```

`PopCount`只统计1的个数，不区分是哪一个SQ项。

**1658–1659行**又表明特殊完成记在`rdataPtr`所指项，不必是旧`deqPtr`所指项：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1658-1659 -->
```scala
    val ncFinish = io.toUncacheBuffer.idResp.valid && !io.toUncacheBuffer.idResp.bits.is2lq && isPbmtNC(dataEntries(i).memoryType)
    val handleFinishSet = rdataPtrExt.head.value === i.U && (io.writeBack.fire || ncFinish)
```

## 4. 怎样激励

最小思路是让队列中按程序顺序存在A、B两项：

1. A是普通Store，地址和数据齐全，已获写出许可。
2. A进入`EnterSbufferQueue`，但把Sbuffer的`ready`保持为0，A还没有实际交接。此时`deqPtr`仍指A，`rdataPtr`可以前进到B。
3. B是NC Store，在允许的接口历史中取得自己的请求接收确认；于是B的`handleFinish=1`。
4. 保持A仍未被Sbuffer接收，检查SQ回收数量。

| 当前状态 | A（较老） | B（较年轻） |
|---|---|---|
| 对应义务是否完成 | 否，普通数据仍堵在FIFO | 是，已经取得该类型要求的完成 |
| 正确回收 | 不能越过A，回收数为0 | 暂时记住完成，等待A |
| 原RTL | `PopCount`数到B的完成，回收数为1 | 这1个名额却从A开始回收 |

现有测试也覆盖其他特殊项；**NC场景已经足以说明根因**，不需要用存在争议的CBO年轻分派许可来支撑结论。

## 5. 根因分析

SQ的合法回收条件应该是“从队头开始连续完成的前缀”。例如：

```text
完成状态 [0, 1]：应回收0项，不能回收1项。
完成状态 [1, 0]：应回收1项。
完成状态 [1, 1]：才可回收2项。
```

当前代码把来自Sbuffer、inactive跳过、特殊完成的位拼接后直接数数。它丢掉了“完成属于哪一项”和“队头有没有完成”这两个条件。

## 6. 后果和边界

- **已经观察到**：A未交接时`io.sqDeqCnt=1`，本应为0；`deqPtrExtNext`相应提前前进。
- **不是无害计数**：SQ回收逻辑会清掉相应entry的`addrValid/dataValid`；前递不查询FIFO中的完整Store来源，因此可能丢失仍应可见的Store。
- **潜在后果**：错误重用槽位、丢失依赖/前递来源，进一步造成数据错误或停滞。
- 尚未在本报告中把这些潜在后果分别提升为整核ISA复现。

正确方向是按完整Store身份记录完成，再只释放连续前缀，不能让年轻项的“完成票”支付老项的义务。

## 7. 现有复现和证据

- 测试：[test_special_order.py](../../tests/deq/test_special_order.py)，`test_completed_special_cannot_release_older_stalled_sbuffer_owner[1]`。
- 实际首次失败：`io_sqDeqCnt` **实际1，预期0**；队头下一值实际1，预期0。
- 回收清有效位的源码：`NewStoreQueue.scala:1698–1701`及相邻数据有效位清除逻辑。
- 生成RTL：`rtl/deq_module/DeqModule.sv:343–360`。
- [裁定及失败证据](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)，查`DEQ-FINISH-ORDER-001`。

## 8. GitHub已经有同根因历史记录

[PR #4641：strictly ensure deq moves in order](https://github.com/OpenXiangShan/XiangShan/pull/4641)在2025-04-29合并。它明确描述“老普通Store卡在dataBuffer，年轻NC完成导致deq越过老项”，并在旧`StoreQueue.scala`中用`completed`和连续完成前缀解决。

因此这不是全新的设计原则问题。但该PR修改的是旧实现，当前`NewStoreQueue.scala`仍存在上述无身份计数；**历史已修复不等于当前实现已修复**。本报告不把旧PR的通过结果当作当前复测证据。
