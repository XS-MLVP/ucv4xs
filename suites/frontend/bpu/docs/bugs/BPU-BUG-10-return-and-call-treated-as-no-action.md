# BPU-BUG-10：RAS 和 MicroRAS 漏掉“返回并调用”操作

一条“返回并调用”指令需要先结束当前调用，再为新调用保存返回地址。若原栈为 `[A, B]`，执行这条操作后应成为 `[A, C]`：下面的 A 保留，栈顶 B 被新返回地址 C 替换。

RAS 和 MicroRAS 的相关路径只识别纯调用、纯返回，没有把组合编码识别为有效操作，导致仍保留旧栈顶或旧返回目标。

状态：已确认 RTL 问题。原先混入 04、05 的 7 个归档失败已分别重新复现，不能归因于 enable 门控。

## 怎样触发

1. 用普通调用建立已知栈或可用返回地址，确认普通操作正常。
2. 保持模块启用，输入操作编码 3，即 `PopAndPush`。
3. 检查新栈顶是否为新调用的返回地址，而非旧栈顶。
4. 分别在推测、纠正、提交阶段检查同一组合语义。

提交阶段的用例通过真实调用提供返回地址和原始检查点，但其中部分是模块级属性纠正场景，不等于完整 FTQ 可达性证明。

## 已观察到的结果

| 模块与场景 | 复核结果 |
|---|---|
| RAS 普通调用、返回 | PASS |
| RAS 推测、恢复、提交及真实原预测提交中的返回并调用 | 4 个 FAIL |
| MicroRAS 普通调用与启用期间地址保持 | PASS |
| MicroRAS 推测、待纠正阶段、退出流水线阶段的返回并调用 | 3 个 FAIL |

例如 RAS 推测用例预期栈顶为 536877060，实际仍为旧值 536875012。MicroRAS 推测用例预期新目标为 1073745932，实际仍为旧值 1073743876。地址单位以各自测试接口为准，不能把不同接口的数字直接比较。

## 根因在哪里

[BranchAttribute](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bundles.scala) 区分了三个独立编码：

| 操作 | 编码 | `isCall` | `isReturn` | `isReturnAndCall` |
|---|---:|---:|---:|---:|
| 返回 Pop | 1 | 0 | 1 | 0 |
| 调用 Push | 2 | 1 | 0 | 0 |
| 返回并调用 PopAndPush | 3 | 0 | 0 | 1 |

[Ras.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/Ras.scala) 和 [MicroRas.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/MicroRas.scala) 的相关译码只使用 `isCall`、`isReturn`。因此输入编码 3 时，两者都为假，组合操作被遗漏。

这不是两个条件同时为真造成的优先级冲突，而是在译码入口就没有识别它。接口已提供 `isReturnAndCall`、`hasPush`、`hasPop`，使用方需要实现组合操作的完整状态变化。

不能仅把判定改成 hasPush/hasPop 就认为修好了：后续栈更新也必须正确实现“先返回，再调用”，避免两个独立更新互相覆盖。这里确认根因，不提供未经验证的 RTL 补丁。

## 上游输入审核

`jalr x1, 0(x5)` 等真实指令会由 IFU 译码成 PopAndPush。后端的 CoRoutineSwap 分类也同时设置 push、pop 位，经 CtrlBlock 和 FTQ CommitQueue 送入 BPU；CommitQueue 不会过滤这个非零编码。

因此组合编码不是测试自行发明、真实系统不会产生的操作。这里有完整的静态产生、传递路径，但尚未运行整核程序；部分单元提交场景直接纠正操作属性，也不能视为实际 FTQ 生命周期已验证。详见[输入契约](input-contracts.md)。

## 复现

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-10 \
  --select 'tests/ras/testcase/test_semantic_reference.py::test_speculative_return_and_call_replaces_only_the_youngest_frame'
```

相关入口：[RAS 推测、恢复、提交](../../tests/ras/testcase/test_semantic_reference.py)、[RAS 原始预测提交](../../tests/ras/testcase/test_commit_action.py)、[MicroRAS 三个阶段](../../tests/uras/testcase/test_semantic_reference.py)。

相关功能点：`BPU-RAS-017`、`BPU-URAS-016`。这 7 个 FAIL 已包含在原回归统计中，拆分报告不会新增失败数量，也不与 [04](BPU-BUG-04-ras-spec-pushpop-ignores-enable.md)、[05](BPU-BUG-05-microras-ignores-enable.md)重复计数。

复核方法与版本说明见[目录说明](README.md)。
