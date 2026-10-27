# FWD-ALIAS-001：虚拟地址不同，漏掉了写到同一物理地址的年轻Store

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。12个原失败节点属于这个根因。

## 1. 用一句话理解

两个虚拟地址可以指向同一物理内存。年轻Store通过另一个VA跨16B写入时，RTL先用VA判断重叠范围，把它错误排除了。后面的PA检查已经看不到它，于是放心地把老值交给Load。

同一房子可以有两个入口；不能因为从不同入口进来，就认为写的是两个不同房间。

## 2. 触发场景

按程序顺序存在下面三条操作，两个Store都在Load之前，且地址/数据就绪：

| 操作 | VA | PA及实际覆盖 | 每个字节的值 |
|---|---|---|---|
| 老Store S0，4B | `0x10010` | `0xabc010..013` | `0x11` |
| 年轻Store S1，8B | `0x2000c` | `0xabc00c..013`，跨16B | `0x22` |
| 更年轻的Load，4B | `0x10010` | `0xabc010..013` | 应读S1的`0x22` |

页内偏移在VA→PA翻译中保持一致。S1覆盖的尾4B就是Load要读的4B，这不是捏造错误地址翻译。

## 3. 有问题的Scala实现

文件：[NewStoreQueue.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala)。

**462–467行**：是否为Store的下一16B块，要求VA页标签相同。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:462-467 -->
```scala
      val s1Next16BMatchVec = WireInit(VecInit(io.dataEntriesIn.zip(io.ctrlEntriesIn).map { case (dataEntry, ctrlEntry) =>
        val storePageOffset = dataEntry.vaddrPageOffset
        ctrlEntry.cross16Byte &&
          dataEntry.vaddrPageTag === s1LoadVaddrTag &&
          (storePageOffset +& 1.U) === Cat(0.U(1.W), s1LoadPageOffset)
      }))
```

**489–501行**又把这个VA判断拿来决定物理候选使用的坐标：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:489-501 -->
```scala
        val loadInNext16B   = s1Next16BMatchVec(j)
        val loadRangeStart  = Mux(loadInNext16B,
          s1LoadStart.pad(byteRangeWidth) + VLENB.U(byteRangeWidth.W), // mapping load to next 16B segment if cross 16B
          s1LoadStart.pad(byteRangeWidth)
        )
        val loadRangeEnd    = Mux(loadInNext16B,
          s1LoadEnd.pad(byteRangeWidth) + VLENB.U(byteRangeWidth.W), // mapping load to next 16B segment if cross 16B
          s1LoadEnd.pad(byteRangeWidth)
        )
        val storeRangeStart = dataEntry.byteStart.pad(byteRangeWidth)
        val storeRangeEnd   = dataEntry.byteEnd.pad(byteRangeWidth)

        storeRangeStart <= loadRangeEnd && storeRangeEnd >= loadRangeStart
```

**510–511行**将这个重叠mask用于物理候选：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:510-511 -->
```scala
      val s1OverlapCandidateVec = (s1AgeMaskLow | s1AgeMaskHigh) &
        s1OverlapMask & addrValidVec.asUInt
```

最后**617–618行**，PA匹配结果还要被这个候选mask裁掉：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:617-618 -->
```scala
        same16BMatch || next16BMatch || (storeIsCbo && sameLineMatch)
      }).asUInt & s2OverlapCandidateVec
```

## 4. 根因可以怎样手算

1. 对S1而言，Store范围应是相对起始16B块的`12..19`。
2. Load读取其下一块的前4B，正确相对范围应是`16..19`，两者重叠。
3. 但S1与Load的VA页标签不同，`s1Next16BMatchVec=0`。
4. RTL没给Load范围加16，把Load错误地当成`0..3`。
5. `12..19`与`0..3`不重叠，S1从候选集合被删除。
6. PA CAM本可命中S1，但结果再与候选mask相与，命中消失。
7. VA与PA候选表看起来一致，漏报别名冲突，最后选中S0的老值。

这不是PA比较器本身不会比较地址，而是**真正需要比较的项被更早的错误条件排除了**。

## 5. 激励与预期/实际

把上表三条操作送入已有ForwardModule定向测试，SQ年龄边界放在两条Store之后，按真实流水分别发送Load请求和PA翻译。

- **预期**：Load得到年轻S1的`0x22222222`；若当前实现不能安全前递，应明确报依赖或要求重放。
- **实际**：有效响应接受S0的`0x11111111`，没有相应重放/依赖标志。
- **必要条件对照**：把S1的VA改成同一页的`0x1000c`，该候选不再因页标签消失；允许保守重放，不要求一定立即前递。

## 6. 后果和边界

已经观察到**同一物理字节的最新Store未被选中，Load无阻塞地接收旧值**。这属于数据来源正确性问题，不是“无效payload恰好不好看”。

模块级证据和真实父级测试均存在；但本报告不把它冒充已完成整核汇编提交验证。修复方向是物理重叠候选不能依赖VA别名是否相同，应正确保留跨16B的物理尾段。

## 7. 复现和证据

- [test_basic.py](../../tests/forward/test_basic.py)，`test_cross_word_physical_alias_never_accepts_older_word_value[0]`。
- 实际首次失败：物理字节检查显示`selected=0`，`newest physical=1`。
- 父级：[test_forward_memory.py](../../tests/lsq_wrapper/test_forward_memory.py)，`test_cross_word_youngest_pa_alias_must_not_return_old_store_bytes[different-va-alias-0]`。
- 生成RTL：`rtl/forward_module/ForwardModule.sv:3118–3123、11323–11330`。
- [裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`FWD-ALIAS-001`。

## 8. GitHub：有历史别名修复，但不能认为覆盖了这个变体

[Issue #6690](https://github.com/OpenXiangShan/XiangShan/issues/6690)已经关闭，[PR #6693](https://github.com/OpenXiangShan/XiangShan/pull/6693)于2026-10-13合并，修复了VA别名造成的老Store前递。该修复**已经包含在本报告的固定版本中**。

当前反例是它仍未覆盖的“跨16B＋不同VA页标签＋物理尾段重叠”组合。不能把“曾修过VA别名”说成“当前12个反例已经修好”。是否作为原Issue补充或另建残留问题，需要在真正对外提交时说明区别；本轮没有提交。
