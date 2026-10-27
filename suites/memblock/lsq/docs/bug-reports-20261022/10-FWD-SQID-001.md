# FWD-SQID-001：返回的依赖槽号正确，却指向错误的一代Store

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。15个原失败节点属于此根因。

## 1. 用一句话理解

SQ只有64个物理槽，槽号会重复使用。Load发现需要等待slot48中的Store数据时，RTL返回了正确的48，却拼上了错误的代际标志，于是把SQ112误报成SQ176。

像酒店房号反复使用：房间号相同，不代表住的是同一批客人。只核对房号，仍可能把通知发给下一批客人。

## 2. 为什么需要完整身份

当前配置物理SQ有64槽，虚拟顺序范围更大。完整指针由槽号和`first_flag/second_flag`共同表示，测试使用0..255的编码解释它。

- `deq`：当前物理窗口的最老边界。
- `physicalUpper`：物理窗口的上边界。
- Load的`sqIdx`：比Load老的Store范围边界，不一定仍在当前64槽窗口内。

Load超出物理窗口时，可以裁剪检查范围，但返回的依赖必须是**被选中Store的身份**，不能沿用Load的代号。

## 3. 有问题的Scala实现

文件：[NewStoreQueue.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala)，**390–395行**，选择范围已经按物理窗口裁剪：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:390-395 -->
```scala
      val s0DifferentFlag    = io.ctrlInfo.deqPtr.operation_flag =/= s0Req.bits.sqIdx.operation_flag //TODO: out of range load need to replay...?
      // The load's sqIdx out of physicalQueue's range.
      val s0LoadOutOfRange   = s0Req.bits.sqIdx > io.ctrlInfo.physicalQueueUpper
      // Decode both bounds in parallel so the range comparison is not in front of UIntToMask.
      val s0LoadMask          = UIntToMask(s0Req.bits.sqIdx.value, StoreQueuePhysicalSize)
      val s0ForwardMask       = Mux(s0LoadOutOfRange, s0PhysicalQueueUpperMask, s0LoadMask)
```

但**548–554行**在命中低编号段时，身份标志仍直接取Load：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:548-554 -->
```scala
      val s1DataInvalidSqIdx   = Wire(new SqPtr)

      s1DataInvalidSqIdx.value := OHToUInt(s1SelectOH)
      s1DataInvalidSqIdx.operation_flag  = Mux(s1SelectLowOH.orR,
        s1LoadSqIdx.operation_flag,
        io.ctrlInfo.deqPtr.operation_flag
      )
```

这里保留了源码中的属性赋值写法`=`，不是把它改写成另一个补丁。生成SV也确认最后确实选到了Load的两个flag。

## 4. 怎样激励

1. 通过正常Store消费，把SQ队头推进到序号60。
2. 当前物理窗口为`[60,124)`，共64个Store；虚拟分配可以继续向后。
3. 令Load的SQ边界为128，即它前面有68个当前Store flow，其中只有前64个在物理窗口。
4. 在SQ112放与Load地址匹配的Store，只给地址，不给数据。
5. 正常发送Load前递查询，检查`dataInvalid.valid=1`时返回的完整SQ身份。

这个场景不是往未分配的物理槽里硬塞第65个Store。已有父级测试先正常推进60项，再分配68个虚拟flow，只让当前物理窗口内的项执行。

## 5. 可手算的预期与实际

```text
当前窗口：[60, 124)
选中的物理槽：48
该槽在窗口内对应：60 + ((48 - 60) mod 64) = 112

应返回：SQ112 = (first_flag=0, second_flag=1, slot=48)
实际返回：SQ176 = (first_flag=1, second_flag=0, slot=48)
```

Load属于128之后的代号，RTL用它的flags与slot48拼接，得到176。**候选范围已经换成物理窗口，身份重建却没有一起换。**

## 6. 后果与边界

- **已经观察到**：有效`dataInvalid`依赖返回的flag错误；不是在`valid=0`时比较一个无意义索引。
- **直接影响**：Replay得到错误的“应该等哪条Store”信息。
- **潜在后果**：真Store数据就绪却无法正确唤醒，或者被以后同槽的另一代Store误唤醒。
- 本报告不把这些潜在路径直接算成已经复现的整核死锁或ISA错误。

修复应从选中Store和物理窗口推导完整身份，保持窗口裁剪、年龄比较和依赖返回的一致性。

## 7. 复现和证据

- [test_semantics.py](../../tests/forward/test_semantics.py)，`test_missing_data_dependency_keeps_original_sq_flags_beyond_window[128-0]`。
- 实际首次失败：`io_query_0_s2Resp_bits_dataInvalid_bits_first_flag` **实际1，预期0**。
- 真实父级：[test_forward_memory.py](../../tests/lsq_wrapper/test_forward_memory.py)，`test_real_nonzero_sq_head_keeps_data_dependency_full_sq_generation[clipped-virtual-dependency-0]`。
- 生成RTL：`rtl/forward_module/ForwardModule.sv:5158–5161`。
- [裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`FWD-SQID-001`和指针手算证据。

## 8. GitHub状态

未找到明确对应此“选中依赖的代际标志拼错”的报告。[PR #6714](https://github.com/OpenXiangShan/XiangShan/pull/6714)修的是预测等待目标已经退休时的越域判断，不是`dataInvalid`返回的Store身份；它是[额外漏检分析](13-github-missed-bugs.md)中的另一类问题，不能与本项混成一个bug。
