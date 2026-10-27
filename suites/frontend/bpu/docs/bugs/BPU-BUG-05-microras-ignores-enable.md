# BPU-BUG-05：MicroRAS 禁用后仍把旧返回地址标为可用

MicroRAS 向前端快速提供返回地址。测试先在启用状态下准备好一个返回地址，再关闭模块。按照检查约定，地址可以继续保存在内部，但禁用期间不能声称它可用于预测。

实际观察是：关闭后，可用标志仍为 1。这里不要求把目标地址清零，也不以内部状态是否保留来判断失败。

状态：已确认 RTL 问题。2026-10-22 重跑禁用场景仍失败；启用期间普通调用及三个空闲周期的地址保持对照通过。输出未使用 enable 门控。尚未修改 RTL。

## 怎样触发

1. 复位，在启用状态下输入一次调用，确认 MicroRAS 已保存正确的返回地址。
2. 关闭模块，连续提供 3 个空闲周期。
3. 每个禁用周期检查输出不可用，即 `usable=0`。
4. 重新启用后，应能继续使用原来保留的地址；禁用不是清空。

步骤 4 是测试中的后续要求，不是对已失败运行的成功结论。

## 已观察到的结果

用例：`test_disabled_micro_ras_withholds_the_armed_return_target`。

| 检查项 | 预期 | 实际 |
|---|---|---|
| 返回目标可用标志 `usable` | 0 | 1 |
| 返回地址 `target` | 不参与禁用时的比较 | `0x40000804`（1073743876） |

错误在于“禁用时仍标为可用”，不是这个地址的数值本身。目标无效时，负载字段不必为零。

## 代码线索与待确认项

[MicroRas.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/MicroRas.scala) 直接输出内部状态：

```scala
io.specOut.isCanUse  := isCanUse
io.specOut.retTarget := topRetAddr
```

该文件没有消费 `io.enable` 来限定输出。`isCanUse` 会随其他操作变化，并非永远为 1；问题是已经为 1 时，关闭模块没有让公开输出变为不可用。

本用例只证明输出门控差异，没有证明完整 BPU 已因此跳到错误地址，也没有要求禁用时冻结所有内部更新。修复后的重点是“关闭时不可用、重新启用时保留有效内容”。

## 不应混在本条中的失败

早期报告关联了 4 个 FAIL：本条禁用门控 1 个，另有 3 个来自“返回并调用”的栈顶替换，分别涉及推测和纠正阶段。

后 3 个用例名为 `test_return_and_call_replaces_top_instead_of_becoming_neutral`。本次已全部重跑，并确认它们漏译码组合操作，现单列为 [10](BPU-BUG-10-return-and-call-treated-as-no-action.md)。它们不是禁用场景，不能归因于输出忘记检查 enable。

## 上游输入审核

完整 BPU DUT 在 RAS 关闭时也观察到 MicroRAS 的 `isCanUse=1`。父模块将 rasEnable 接入 MicroRAS enable，但 S1 返回目标选择仅检查“返回类型且 isCanUse”，没有再检查 enable。

所以不能用“上游已经屏蔽”排除本例。现有动态见证没有包含一次真实 RET 跳错目标；当前证明到 BPU 输入、输出资格与消费者连接为止。详见[输入契约](input-contracts.md)。

## 复现与回归检查

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-05 \
  --select 'tests/uras/testcase/test_enable_gate.py::test_disabled_micro_ras_withholds_the_armed_return_target'
```

[测试入口](../../tests/uras/testcase/test_enable_gate.py)。相关功能点：`BPU-URAS-017`。

证据版本见[目录说明](README.md)。历史定位线索：`8bc33bbbbb`。
