# DEQ-SPLIT-WLINE-001：普通Store尾段带上了相邻CBO.zero的整行写标志

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。16个原失败节点属于此根因。

## 1. 用一句话理解

跨16B的普通Store拆成两路发送。第二路的数据、地址和mask正确地来自第一条Store，但它的`wline`控制位却来自旁边第二条CBO.zero。

好比货物和地址装对了，外包装却贴了下一单的“整箱替换”标签。

## 2. 为什么wline不是无关位

`wline`代表整缓存行写入控制，CBO.zero使用它完成整行清零。普通Store只应该修改mask指定的几个字节，因此必须`wline=0`。

接收端`mem/sbuffer/Sbuffer.scala:148–156`把`line_write_buffer_wline`作为各字节写使能的条件之一。即使普通字节mask很小，错误的`wline=1`仍会扩大写入范围，不能把它当作don't-care。

## 3. 有问题的Scala实现

文件：[NewStoreQueue.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala)，**1180–1188行**：split时第二路的内容切到head的尾段。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1180-1188 -->
```scala
        writeSbufferData(i)  := Mux(headCross16B, outData(0), outData(i))
        writeSbufferMask(i)  := Mux(headCross16B, outMask(0) & (~unalignMask(0)).asUInt, outMask(i))
        writeSbufferPaddr(i) := Mux(headCrossPage,
          io.fromUnalignQueue.bits.paddr,
          Mux(headCross16B, paddrHigh, Cat(dataEntries(i).paddr(dataEntries(i).paddr.getWidth - 1, 4), 0.U(4.W))))
        // if unalign cross Page, it is must cross 16Byte
        writeSbufferVaddr(i) := Mux(headCross16B,
          vaddrHigh,
          Cat(dataEntries(i).vaddr(dataEntries(i).vaddr.getWidth - 1, 4), 0.U(4.W)))
```

但**1262–1272行**没有给`wline`做同样的owner选择：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:1262-1272 -->
```scala
    for(i <- 0 until EnsbufferWidth) {
      val port      = writeSbufferWire(i)
      val dataEntry = dataEntries(i)
      val ctrlEntry = ctrlEntries(i)

      port.bits.data     := writeSbufferData(i)
      port.bits.mask     := writeSbufferMask(i)
      port.bits.addr     := writeSbufferPaddr(i)
      port.bits.vaddr    := writeSbufferVaddr(i)

      port.bits.wline    := ctrlEntry.isCbo && isCboZero(dataEntry.cboType)
```

当`i=1`时，前四个字段可能属于entry0，`wline`仍属于entry1。

## 4. 怎样激励

已有直接观察真实交接的用例：

1. entry0是普通8B Store A：`VA=0x9400c`，物理页`0xabcd`，数据`0x8877665544332211`，跨16B，且已获许可。
2. entry1保留相邻CBO.zero Z的元数据：`VA=0xa0000`，物理页`0xdead`，`cboType=3`；Z可以尚未committed。
3. 让A同时产生首、尾两个片段并进入FIFO；先背压，再打开两路Sbuffer的`ready`。
4. 只检查属于A的真实尾段`fire`，不要求Z自身被执行。

尾段正确内容应为：

| 字段 | 预期 | 实际 |
|---|---|---|
| VA | `0x94010` | 正确 |
| PA | `0xabcd010` | 正确 |
| mask | `0x000f` | 正确 |
| 有效低32bit数据 | `0x88776655` | 正确 |
| `wline` | **0，普通部分写** | **1，被相邻zero污染** |

因此这不是数据/地址算错导致的旁证，而是单独的控制归属错误。

## 5. 为什么相邻项没获许可也能污染

`NewStoreQueue.scala:1243–1248`的第二路有效条件有一个独立分支：`headCross16B && toSbufferValid(0)`。它允许第二路被head尾段占用，**本来这是正确的**。

问题是第二路被head占用后，`wline`还读邻居entry1。因此把邻居设为未提交，不能阻止这个错误，也不需要假设正常后端允许年轻CBO提前执行。

## 6. 后果和修复方向

- **已经观察到**：普通Store尾段在实际Sbuffer交接时`wline=1`，预期为0。
- **下游源码可确认的风险**：原本只应写4B的尾段被当作整行写，可能改动目标之外的字节。
- **证明边界**：现有该UT没有把真实Sbuffer和整核内存系统一起跑完；不能宣称已经观察了全部最终内存破坏。

修复必须让地址、数据、mask和所有有语义的控制位跟随同一owner，不是只改数据mux。

## 7. 复现和证据

- [test_split_control_consumption.py](../../tests/deq/test_split_control_consumption.py)，`test_actual_split_tail_fire_keeps_ordinary_store_wline[0-False]`。
- 实际首次失败：`io_writeToSbuffer_req_1_bits_wline` **实际1，预期0**；不是仅观察新排队但尚未传输的payload。
- 生成RTL：`rtl/deq_module/DeqModule.sv:490–510`，第二路wline仍来自`io_rdataCtrlEntries_1_isCbo`。
- [裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`DEQ-SPLIT-WLINE-001`。

## 8. GitHub：同场景有历史报告，不是当前代码的修复

[PR #4759](https://github.com/OpenXiangShan/XiangShan/pull/4759)于2025-05-31合并，明确描述过“misaligned Store邻接CBO.zero，两路都属于前一条Store”的相同场景。

但旧补丁修的是**接收后如何识别cbozero完成**：用已传输请求的wline替代相邻deqPtr的fuOpType。当前bug是**发送出去的wline本身就从邻居取错**。所以这是重要历史关联，不应直接算作当前根因已被提交修复，更不能抵扣当前失败。
