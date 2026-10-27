# Upper slot1：返回可达，但后续训练触发 dirty 冲突

此前 slot1 只有局部输入模型反例，现在已有真实集成 DUT 的因果证据。
[`冻结失败运行`](../results/sparse-wrap-upper1-causal-failure-20261013-v3/exit.json)
正常退出1：1 FAIL，没有新增 XFAIL，没有发布报告，也不计功能或原生行增益。
[`有界诊断复核`](../results/sparse-wrap-upper1-causal-failure-20261013-v3/slot1-causal-analysis.json)
重新核验实际失败、返回事务、全部八槽 payload 和指针，以及唯一 status 差异。

## 真实输入形成的事件序列

| tick | 独立检查的事件 |
| --- | --- |
| 2644 | 部分回绕并排空后，old index265 的 hits=0x02、mask=0x01、enq=1、deq=0；slot1 在 priority 前缀之外 |
| 2660/2664 | 新的合格 A 预测及对应 metadata：upper provider，旧 payload 为 valid1/tag75/position6/counter0；公开预测选择真实 position10 fallback、target B |
| 2669 | 返回对应的真实训练写 slot1，index265/tag75/counter0；旧命中 owner 与新 enqueue 同槽，same-slot-retirement=1 |
| 2670 | 全八槽 payload、enq=2、deq=1 均一致；只有 slot1 dirty 期望1、实际0，随即漏掉 bank1/set66 的 SRAM 写回 |

返回资格来自更早 C→D 的 index 请求与 D→A 的 tag 历史，不通过实际 hit/provider
筛选输入。完整公开 ways、metadata、训练 folds 和后续状态检查均保留。
本次使用真实 negative 程序的 counter0，不再只是局部模型的 allocation counter4。

[`BypassShadowBuffer.scala:243`](../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/BypassShadowBuffer.scala:243)
之后依次执行 writeback 清 dirty、新 enqueue 置 dirty、旧命中 owner 清 dirty。
新旧 owner 同槽时，最后一项覆盖新项 dirty1。当前冻结 RTL 与真实状态差异吻合，
并让期望 write_valid1/packed84832 变成实际 write_valid0/array.enable0。
这属于既有 shadow 持久化问题在集成 slot1 边界的具体表现，不能称为新发现的独立缺陷。
本次训练前后 counter 均为0，证明的是 dirty/写回契约违例，**不单独证明这一笔已造成
公开 payload 数据变化丢失**；counter 真正改变后的持久化损失由既有 UTAGE-016 场景检查。

## 报告边界

slot1 的读响应已经动态到达，不能再说“当前 DUT 未证明可达”。但完整的
返回→训练→排空需求仍失败，因此正式 response-selection cross 保持 **29/30**，
不把断言之前的瞬时命中注册成 PASS，也不在返回之后提前结束测试。
显式诊断位于 `tests/bpu/diagnostics/sparse_slot1.py`，不自动混入默认回归；
原七项 strict XFAIL 和全部原生分母不变。

失败运行有自己的冻结 source epoch。case 与编译 RTL 的哈希仍一致；随后 warm
capture helper 有其他候选改动，不能把历史失败说成整个当前源码的复跑资格。
后续修复必须重新通过完整 consumer/state/SRAM/drain 检查，才能关闭这格。
没有 VPI、内部写入、bank 枚举、波形或默认逐周期 JSON。
