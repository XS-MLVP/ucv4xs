# BPU-BUG-07：ITTAGE 重启后接受了禁用期间那次预测的反馈

ITTAGE 负责学习间接跳转的目标。这里的时间顺序很重要：**做预测时组件关闭，执行反馈到达时组件已经重新开启**。归档中，这份反馈让之后的查询从不命中变成了命中。

现有参考模型要求忽略这份反馈，但设计也可能允许把它当作一次未命中的新训练。两者必须先有明确约定，不能仅由参考模型失败认定 RTL 错误。

状态：2026-10-22 重跑仍有相同差异，正常有效元数据的训练对照通过。但跨禁用、启用边界的训练策略尚未确认，因此本条仍不能定为已确认 RTL bug。

## 怎样触发

1. 先在启用状态下查询另一个地址，留下真实的预测元数据。
2. 关闭 ITTAGE，查询待测地址 A。这次 ITTAGE 元数据的 `valid=0`。
3. 重新启用，确认 A 仍未命中。
4. 提交 A 的执行反馈，携带第 2 步保存的原始元数据，而非新一次查询的元数据。
5. 再查询 A，检查它是否已经学到目标。

用例还用一份启用期间的有效预测元数据训练另一个地址，确认正常训练能够工作。这不是简单的“反馈到达时模块关闭”测试。

## 已观察到的结果

用例：`test_late_feedback_for_an_unpublished_original_does_not_create_a_target`。

| 检查项 | 当前参考模型要求 | 实际 |
|---|---|---|
| A 的查询是否命中，`hit` | 0 | 1 |
| 是否存在提供目标的表项，`provider_valid` | 0 | 1 |

这些结果证明这份反馈产生了可命中的学习结果，不证明学习本身违反设计约定。

旧标题里的“未发布”指 **ITTAGE 当时没有产生有效预测元数据**，不是整条前端预测未发布、指令未执行，也不是较老预测被较新预测覆盖。

## 代码线索与待确认项

[Ittage.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ittage/Ittage.scala) 的训练入口要求反馈到达时处于启用状态，并由 `hasTrainBranch` 与训练阶段使能产生 `updateValid`；这条判定没有同时要求原预测元数据的 `valid`。

需要设计方明确以下哪种约定成立：

- 原预测时组件禁用，后来的反馈必须忽略。
- 允许跨启用边界学习，但应按未命中重新确定分配信息，不能使用无效元数据的残留子字段。
- 上游保证这种反馈永远不会到达组件；那么首先要验证该上游约束。

如果约定是第一种，应检查反馈携带的**原预测有效性**，而非反馈到达周期的新预测有效性。在策略确定之前，保留当前普通 FAIL，不修改 RTL，也不把它改成 XFAIL 来消除差异。

## 不应混在本条中的失败

早期报告关联 4 个 FAIL。本条直接对应 2 个：一个 ITTAGE 单元用例、一个完整 BPU 用例。

另外 2 个属于“零置信度下纠正目标后，高位地址是否保留”，不是本条的禁用边界问题。原报告把其中的目标地址差异混入本条，现在不再用它们佐证“禁用期间预测不应训练”。

## 上游输入审核

FTQ 会保存 ITTAGE 原预测元数据，再与后续执行反馈一起返回；没有按 ITTAGE 原元数据 valid 直接过滤整个训练。CSR 可以独立切换 ITTAGE_ENABLE，也没有发现 SBPCTL 写入必定排空所有旧训练的专用保证。

这尚不是完整 CSR／FTQ 时序见证，但不能简单以“写 CSR 总会清空旧原预测”判输入非法。即使输入可达，应该忽略还是允许重新学习仍是另一项设计约定。详见[输入契约](input-contracts.md)。

## 复现与回归检查

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-07 \
  --select 'tests/ittage/testcase/test_late_source_qualification.py::test_late_feedback_for_an_unpublished_original_does_not_create_a_target'
```

[单元测试入口](../../tests/ittage/testcase/test_late_source_qualification.py)；[完整 BPU 对照入口](../../tests/bpu/testcase/test_late_source_qualification.py)。相关功能点：`BPU-ITTAGE-020`。

证据版本见[目录说明](README.md)。历史定位线索：`333f593539`。
