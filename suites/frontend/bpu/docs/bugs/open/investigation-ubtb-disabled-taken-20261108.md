```ucv-bug
{
  "id": "BPU-INV-UBTB-DISABLED-TAKEN-20261108",
  "title": "关闭预测器后 Bpu 仍发布 taken",
  "kind": "investigation",
  "versions": [
    {"baseline": "public-a0c2a26cb", "status": "open", "evidence": ["docs/spec/verification/evidence/runs/closeout-20261108.md"], "note": "真实 seed1 FAIL 已复现；模块根因与完整生产者资格仍在核查，不计新整机 bug。"}
  ]
}
```

# 待核：关闭预测器后，Bpu仍发布taken（2026-11-08）

**状态：真实FAIL已复现，模块根因/生产者全程资格仍在核查。不是已修缺陷，也不计新整机bug。**
基线固定`public-a0c2a26cb` / `a0c2a26cbe3c862175174bad03a1a23c406315ed` /
`DefaultConfig`。没有修改RTL/Scala/参数/锁，没有上游提交或push。

## 实际复现，不放宽断言

入口：
`tests/bpu/testcase/test_parent_fallthrough.py::test_parent_fallthrough_extent_and_hold_keep_page_guard_and_fire_owner`。

1. 从agent公开API关闭全部七路CSR，等待传播到真实DelayN输出。
2. 物理地址`0x40000800`复位启动，取得真正prediction/metadata。
3. 保持FTQ背压，用原metadata和真实CFI发一次indirect恢复到`0x40001007`，再开启接受。
4. 要求公开预测为该新地址、`target is None`（DCE边界不造字段）且`taken=0`。

`results/bpu-closeout-parent-primitives-seed1-v1-20261108`和`...-v2-20261108`，
同nodeid、真实seed1都在第一种target失败：

```text
BpuPrediction(start_pc=1073745927, target=None, taken=1,
              position=0, s2_override=0, s3_override=0)
expected: target is None and taken == 0
```

原断言未删、未弱化，后续高guard/页末/保持用例没有因首错获得比较信用。v1同时包含
DelayN观察器误把待提交Rise-write缓存当作已消费输入的独立误报；v2换成真实输入别名
后DelayN用例PASS，**本公开taken失败仍在**，不能用采样器修正把它重标为PASS。

## 当前源码线索（不是独立golden）

- `ubtb/MicroBtb.scala:58,77-96`：s0/s1 fire用enable；`s1_hitOH`/`s1_hitT1Victim`
  是无reset的RegEnable。`prediction.valid := s1_hit && enable`，但
  `prediction.bits.taken := s1_hit`，关闭时可能保留旧命中或初始未定义命中。
- `Bpu.scala:325-329`：ABTB无有效entry时按`s1_ubtbPrediction.taken`选UBTB，而非其valid。
- 当前生成`MicroBtb.sv`已裁掉未被父级消费的prediction.valid，只保留bits；
  `io_prediction_bits_taken = s1_hit`。`Bpu.sv:5121-5122`也直接使用该bits。

独立合同来自[冷来源隔离](../../spec/verification/contracts/pipeline-transaction-contract.md)和已有CSR使用资格：
未启用来源不能覆盖合法fallthrough。不能把“源码正如此”改写为合法预期；也不能要求
预测器总是命中/总预测正确来泛化此义务。

## 必须继续的区分实验与结论边界

1. 保存真实七路DelayN输出、UBTB实际enable、s1_hit/bits.taken、父级S1选择和公开接受
   在同一事件的诊断证据，不能只看到测试调用了disable。
2. 从enable状态正常学习并消费**已知taken命中**后禁用，再恢复到新地址；与始终启用、
   正常无命中的情况成对。这样才能区分随机初值、旧命中保持和真正关闭消费错误。
3. FallThrough leaf的给定S0结果检查应另记，不能被公开门控首错遮住后仍称全检查，
   更不能用一个只检查leaf的PASS抵消本组合FAIL。
4. 完整CSR指令/FTQ寿命/新旧checkpoint的整核来路尚未证明。该UT使用公开模块端口，
   不是整机程序执行；当前影响只确认到公开预测taken错误，未确认架构状态破坏。

该问题不是[08](BPU-BUG-08-microbtb-fallthrough-revives-dead-entry.md)的NT重新分配问题，
也不是MicroRAS的[05](BPU-BUG-05-microras-ignores-enable.md)。修复决定交回用户；
本目标不会修改RTL或新增XFAIL/SKIP来消除此FAIL。
