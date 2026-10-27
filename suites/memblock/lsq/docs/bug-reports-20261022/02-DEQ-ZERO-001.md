# DEQ-ZERO-001：CBO.zero没有写出自己的零数据，却报告完成

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。原回归去重后15个失败节点属于这个根因。

## 1. 用一句话理解

旧的普通Store还堵在出口，后面的CBO.zero已经开始等待清零。旧Store一出门，状态机就以为“清零数据已经出门”，实际上出门的根本不是CBO.zero。

好比排队办理业务时，把前一个人的“办理成功”记到了自己的工单上。

## 2. 正常应该怎样工作

CBO.zero必须把**自己的零写请求**交给Sbuffer，再按协议排空、写回完成。旧普通Store先前已经得到写出许可，所以即使它在ROB中已退休，仍可能因Sbuffer背压而停留在`EnterSbufferQueue`中。

因此，“ROB已经空了”和“所有旧Store片段都已经从FIFO写出”不是一回事。这个反例不需要在CBO后面违规分派年轻指令。

## 3. 有问题的Scala实现

文件：[NewStoreQueue.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala)。

**975–983行**：退出零写状态只看外部第0路有没有一次交接，没有核对是谁的请求。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:975-983 -->
```scala
      is(CboState.writeZero) {
        when(io.writeToSbuffer.req.head.fire) {
          cboStateNext := CboState.flushSb
        }
      }
      is(CboState.flushSb) {
        when(io.sbufferCtrl.resp.empty && dataQueue.io.empty) { // Ensure there are no in-flight request.
          cboStateNext := Mux(isCboZero(headDataEntry.cboType), CboState.writeback, CboState.sendReq)
        }
```

**1212–1216行**：但CBO.zero进入FIFO又要求FIFO在本拍已经为空。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1212-1216 -->
```scala
      if(i == 0) {
        uncacheStall(i) := !isCacheable(dataEntry.memoryType)
        // sq need to write zero to sbuffer && dataQueue is empty => write zero
        cboStall(i)     := ctrlEntry.isCbo && !(cboState === CboState.writeZero && dataQueue.io.empty)
      }
```

**1289–1293行**说明对外的请求来自FIFO出口，不一定是当前读指针所指的CBO：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1289-1293 -->
```scala
    dataQueue.io.fromDeqModule.zip(writeSbufferWire).map{ case (sink, source) =>
      sink               <> source
    }

    io.writeToSbuffer    <> dataQueue.io.toSbuffer
```

## 4. 怎样激励

采用已有的**正常串行CBO**测试场景：

1. 普通Store A写`PA=0xABC000`，先获许可并进入FIFO。
2. 保持Sbuffer不接收，使A留在FIFO；A在ROB中可以已经退休。
3. 之后在正常许可下分派CBO.zero Z，目标`PA=0xDEF000`。CBO地址包使用真实生产者格式：16B对齐、`size=4`、`mask=0xffff`，不是错误的8B包。
4. 等Z的状态机进入`writeZero`。此时FIFO仍非空，Z还不能进入FIFO。
5. 打开Sbuffer的`ready`，让FIFO中的A实际交接。
6. 继续正常响应排空和写回，统计Z自己的零写次数。

| 关键周期 | FIFO里是谁 | Z能否入FIFO | 状态机实际做了什么 |
|---|---|---|---|
| 出口被堵 | A | 不能，FIFO非空 | 停在`writeZero` |
| A实际`fire`的本拍 | 交接的仍是A | 仍不能；本拍`empty=0` | 错把A的`fire`当Z完成，转`flushSb` |
| 下一拍 | FIFO空了 | `writeZero`已经退出，仍无法零写 | 继续走排空、写回和释放 |

正确结果是Z自己的零写至少按该接口要求实际交接一次；实际证据中这个次数是**0**，但Z已经写回并释放。

## 5. 根因

本设计把**当前SQ请求的状态机**与**FIFO出口的握手**直接连在一起，却没有保留足以区分事务身份的完成条件。

FIFO出口的`fire`只能说明“某个旧请求被Sbuffer接收”。它不能证明“当前CBO.zero被接收”。同时，`empty`是本拍状态，不会因为本拍即将出队就立即变成真，因而不能假设Z在同拍已经替换了A。

## 6. 后果和边界

- **已经观察到**：原CBO.zero的实际零写次数为0，却出现该owner的WB和SQ释放。
- **风险**：清零操作被遗漏，目标缓存行可能保留旧内容。报告完成不能替代内存副作用。
- **没有声称**：已经跑过整核软件并验证最终内存残留值；本证据是Sbuffer公开传输和原事务完成之间的矛盾。

修复必须关联本CBO的真实零写交接，或者为零写提供独立的身份/状态记录；不能只把“任何出口fire”加上一个更长延迟。

## 7. 现有复现和证据

- 测试：[test_serialized_cbo.py](../../tests/lsq_wrapper/test_serialized_cbo.py)，`test_serialized_zero_retired_old_sbuffer_actual_WB_and_release_protocol_only[True]`。
- 这是正常空ROB条件下分派的16B CBO包；没有年轻分派。其断言是 `own_zero16_fires == 1`，实际为**0**。
- 生成RTL：`rtl/deq_module/DeqModule.sv:324–329、385–390`。
- [全量源码裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`DEQ-ZERO-001`。历史随机用例先出现`flush=1/预期0`也属于同一提前退出根因，不能换算成另一个bug。

## 8. GitHub状态

未检索到明确报告这个“借用旧FIFO请求的fire”根因的Issue/PR。[PR #6228](https://github.com/OpenXiangShan/XiangShan/pull/6228)虽然也叫“fix write zero”，实际修改的是零写入队许可及释放计数，不能因标题相似就认定当前问题已报告或已修复。
