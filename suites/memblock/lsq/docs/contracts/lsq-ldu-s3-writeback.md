# S3的地址更新不是Replay完成（补例前纠正合同）

固定开源`NewLoadUnit.scala:1145-1146,1450-1457,1516,1544,1596-1613`：

- `alignedType := in.size`，即本轮对齐8B scalar应为3；不能沿用Enqueue默认0。
- `last_beat := paddr(log2Up(refillBytes))`，本配置由公开PA bit6决定。
- `updateAddrValid := ldoutValid || vldoutValid`。无异常、无VA/PA matchInvalid、无软件
  prefetch的普通缓存请求，只有真正不再Replay才写回；cause10等Replay必须为0。
- 异常、matchInvalid、MMIO replay、S4 head/tail须根据各自真实shouldWriteback合并
  判断，不可把“不是needReplay”作为所有域的通用公式，也不能总设1。

这补既有LDU pipeline/反馈功能中遗漏的S3字段关系，不增加新ISA/原生LoadUnit范围。
原`ldu_mixed_pipeline_v1`误将`packet.update_address`总为真作为门禁，因此旧两种子
接口PASS及原UID/总线/Sbuffer效应仍真实，但**不足以证明完整正常LDU生产者**。旧审计、
轨迹、源/FAIL都保留；后续用独立源关系审计量化拒绝，不能因为旧门禁绿色跳过。

`lsq-raw-exclusive-04`六个Wrapper用例也沿用默认size/lastBeat/update字段；其RTL比较
与原效应仍保留，但正常生产者准入须先被拒绝，再只修这些字段的新目录重跑相同节点。
本轮只补对齐cached hit/cause10最小域，不能据此追溯提升全八类型随机。

定义此合同时回归10启动源保持冻结；现已实际结束1708/200、430源一致，见[10报告](../reports/lsq-progress-regression-10-20261019.md)。
它是1908个节点的精确重复性门禁，不替代修正后的生产者域。
所有后续正常容量/混合程序都需包括这个S3门禁；既有RTL失败不因字段纠正抵消。
