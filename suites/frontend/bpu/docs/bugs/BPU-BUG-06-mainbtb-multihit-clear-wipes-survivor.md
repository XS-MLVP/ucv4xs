# BPU-BUG-06：MainBTB 要求清理 way 1，写缓冲却从 way 0 写出了清零内容

MainBTB 的清理请求指定要删除哪一份重复记录。但当清理内容为全零、恰好与另一行缓冲中的地址标签和分支位置匹配时，写缓冲把它合并到了另一行。该行对应另一条固定的 SRAM 写入通路，最终清错了物理位置。

状态：模块错 way 写回已定位，直接证据是“请求进入 way 1，却从 way 0 写回”。但重复记录准备尚未闭环验证真实 FTQ 生命周期，SoC 可达性待证。

## 怎样触发

1. 通过正常训练，让同一分支的旧副本位于 way 1，新副本位于 way 0。
2. 让重复记录清理与另一条分支的训练重叠。
3. 清理请求应向 way 1 写入全零表项。
4. 观察清理请求从哪个缓冲端口进入、最终从哪个端口写回，再检查两份记录。

将被清理分支的 tag 和 position 都设为 0，会使全零清理内容与 way 0 的保留记录具有相同缓冲匹配键。对照仅把 tag、position 改为非零，其他流程相同。

## 直接观测

2026-10-22 的 memory-direct 复核：

| 检查项 | 非零对照 | tag=0、position=0 |
|---|---|---|
| 清理请求进入的端口 | way 1 | way 1 |
| 全零表项实际写回的端口 | way 1 | **way 0** |
| 原本应保留的 way 0 | 保留，测试通过 | 被清零，测试失败 |
| 原本应清理的 way 1 | 清理 | 仍有效 |

失败场景中，tick 222 观察到 way 1 的全零清理输入；tick 224 观察到它从 way 0 写出。tick 是仿真事件编号。

最终 `0.valid` 预期 1、实际 0；`1.valid` 预期 0、实际 1。请求本来只指向 way 1，不能把这次清错解释成合法的整组失效策略。

## 根因在哪里

[MainBtbInternalBank.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbInternalBank.scala) 把写缓冲的各输出端口与各 way 的 SRAM 一一连接。因此缓冲行及输出端口包含实际的写入目的地信息。

但 [WriteBuffer.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/WriteBuffer.scala) 的命中查找跨越所有缓冲行，只比较 `setIdx` 和请求的 `tag`。MainBTB 在 [Bundles.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/Bundles.scala) 中将这个键定义为 `Cat(entry.tag, entry.position)`。

清理请求的负载全零，正好命中另一行的保留记录。命中更新沿用被命中的行，没有保留原请求指定的 way，随后就从错误的固定 SRAM 通路写出了全零内容。

问题是**合并时丢失了写入目的地**。同一逻辑分支出现在不同 way，不代表对其中一份的清理可以被合并到另一份上。

## 与旧归因的区别

旧报告认为 `s2_multiHitMask` 包含所有命中 way，因此清理会把所有副本删除。实际 [Helpers.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/Helpers.scala) 的 `detectMultiHit` 已选择一个重复位置，返回独热掩码；本次观测的请求也只清理 way 1。旧根因解释不成立。

本例与 [09](BPU-BUG-09-aheadbtb-target-correction-wrong-destination.md) 都涉及通用 WriteBuffer，但具体约束不同：本条必须保留固定端口代表的 way，09 必须区分负载里的不同 way。不能未经验证就把所有使用者改成同一种合并键。

早期关联的 7 个 FAIL 中，本次确认的是这个零键最小场景；其他完整 BPU、共享写入资源场景不能自动关单。

## 上游输入审核

模块中错 way 写回的事实没有改变，但重复记录如何产生仍需 SoC 合法性证明。现有完整 BPU 准备保存多个冷原预测后再顺序训练，没有完整模拟误预测重定向对年轻 FTQ 原预测的清除。

例如较老原预测误预测后，被杀掉的年轻原预测不能继续训练。反过来，年轻反馈先到、较老反馈后到可能是另一条合法构造，不能据此认定所有重复记录都不可达。

因此现有 BPU 用例不能单独证明本条在正常 SoC 可达；需要含真实年龄、重定向与反馈顺序的复现。详见[输入契约](input-contracts.md)。

## 复现与对照

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-06 \
  --select 'tests/mbtb/testcase/test_semantic_reference.py::test_duplicate_clear_owns_destination_not_zero_payload_key[zero-tag-and-position]'
```

同一函数的 `[nonzero-control]` 已通过。[测试入口](../../tests/mbtb/testcase/test_semantic_reference.py)。

相关功能点：`BPU-MBTB-026`、`BPU-MBTB-029`。复核方法与版本说明见[目录说明](README.md)。
