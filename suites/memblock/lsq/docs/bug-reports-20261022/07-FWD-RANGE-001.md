# FWD-RANGE-001：前递mask循环折回，把未写过的字节也当成Store数据

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。原回归28个失败节点归于此根因。

## 1. 用一句话理解

Store跨过16字节边界时，RTL旋转了数据和mask，却没有剪掉从另一端绕回来的部分。结果，前递声称能提供一些Store根本没有写过的物理地址。

“循环旋转”像把一条纸带首尾相接再移动；真实内存却不是首尾相接的，跨到下一块的字节不能绕回上一块。

## 2. 一个可以手算的例子

以16B对齐块的起点为0，Store从offset12开始连续写8B：

```text
第一块地址： 0 ........... 11  12 13 14 15
这个Store： - ............ -   S  S  S  S

第二块地址：16 17 18 19  20 ........... 31
这个Store： S  S  S  S   - ............ -
```

所以读第一块时，只允许前递mask=`0xf000`；读第二块时，只允许mask=`0x000f`。不能在任何一块内同时宣称`0xf00f`都来自这个Store。

## 3. 有问题的Scala实现

文件：[NewStoreQueue.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala)，其中`ForwardModule`的**606行**：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:606-606 -->
```scala
      val s2ByteSelectOffset    = s2LoadStart - s2SelectDataEntry.byteStart
```

**632–635行**直接循环旋转mask，最后只按Load大小裁剪：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/NewStoreQueue.scala:632-635 -->
```scala
      val s2SelectMask         = (0 until VLENB).map(j =>
        j.U -> rotateByteRight(s2SelectDataEntry.byteMask, j)
      )
      val s2OutMask            = ParallelLookUp(s2ByteSelectOffset, s2SelectMask) & s2LoadMaskEnd
```

缺少的是“当前物理16B块到底承载Store的哪一段”的边界裁剪，不是Load大小本身。

## 4. 怎样激励，以及为什么会算出错误mask

已有合法连续mask定向例：

1. 一个地址/数据已就绪的8B Store：`VA=0x1000c、PA=0xabc00c`，数据`0x8877665544332211`，保存的连续`byteMask=0x00ff`。
2. Load读取`VA=0x10000、PA=0xabc000`起始的16B，即第一块。
3. 正常经过s0请求、s1地址翻译、s2有效响应，检查每一个声明可前递字节的真实PA来源。
4. 将Load改为读取`0x10010 / 0xabc010`，检查第二块，作为同根因的另一段。

第一块的手算过程：

```text
Load块内起点 = 0
Store块内起点 = 12
4bit减法：0 - 12 = 4（模16）
rotateRight16(0x00ff, 4) = 0xf00f
Load要求整个16B，Load mask=0xffff
最终错误mask = 0xf00f & 0xffff = 0xf00f
正确第一块mask = 0xf000
```

多出来的低4位对应`PA=0xabc000..003`，这个Store实际只写`0xabc00c..013`。无论数据线恰好是什么值，都不能把这4个地址标成它写过。

这里不依赖孔洞mask。`MemCommon.scala:182–184`的`CalculateSelectMask`返回长度，SQ按长度生成连续mask；`NewStoreQueue.scala:1931–1949`有真实生产者依据。旧随机孔洞mask例只是同根因的压力证据，不冒充正常producer，也不计成新的独立bug。

## 5. 根因和后果

数据旋转可以用于总线对齐，但**对齐后的数据位置**不等于**真实内存的有效字节范围**。当前只保留了前者，没保留后者。

- **已经观察到**：有效且没有依赖/重放阻塞的响应中，mask包含“找不到物理Store producer”的字节。
- **直接风险**：Load可能使用来自另一段、另一地址的字节，覆盖本应由缓存或其它正确来源提供的数据。
- 本模块证据不是整核汇编已提交错误结果的证明；外部GitHub报告另有其整核证据，不与本地UT混称。

修复应结合Load/Store相对位置，剪掉循环绕回的低段或高段，同时保留Load大小约束。不能简单取消所有跨16B前递检查，或放宽“每个有效字节必须有来源”的断言。

## 6. 复现和证据

- [test_semantics.py](../../tests/forward/test_semantics.py)，`test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses[0-0]`。参数为word、lane。
- 实际首次失败：`forward-physical-byte-safety ... byte 0 ... no physical producer`。
- 父级真实Store写入：[test_forward_memory.py](../../tests/lsq_wrapper/test_forward_memory.py)，`test_cross_word_forward_never_invents_unwritten_physical_bytes`。
- 生成RTL：`rtl/forward_module/ForwardModule.sv:991`明确为4bit减法；`1450–1498`保留了循环mask。
- [裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`FWD-RANGE-001`和`independent_scalar_counterexamples`。

## 7. GitHub：已有明确对应报告和未合并修复

- [Issue #6703](https://github.com/OpenXiangShan/XiangShan/issues/6703)：跨16B前递收到本不重叠Store的字节，明确分析循环旋转折回。
- [PR #6718](https://github.com/OpenXiangShan/XiangShan/pull/6718)：增加旋转后的物理段边界mask。

截至2026-10-22查询，两者均open，PR未合并。这是11项中**明确对应当前根因**的公开记录。本文不声称已在本地应用该补丁或复测其全部边界。
