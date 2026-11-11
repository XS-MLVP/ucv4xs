# RAW与容量Replay的满128 exclusive端点（实现/用例前合同）

本合同补既有RAW分配/回收、Replay RAW_CAPACITY和Wrapper合法容量功能中的缺少情形，
不是新增第129个Store许可，也不把所有SQ半环比较变成可判年龄。固定开源893e1580b，
真实Picker原生DUT及xreactor持续采样不变，目标RTL/Chisel不改。

## 可读行为与实际检查

1. **记录所有尚有较老未决地址的Load。** Load的SQ是已分配较老Store之后的exclusive
   tail；当恰有128个老Store地址未就绪，它与address-ready相差128合法，RAW必须记录，
   不因first_flag翻转而拒绝、漏分配或立即回收。127是相邻对照；跨63/64、127/128、
   255/0保持完整flag/代。叶子外部前缀单调；Wrapper必须来自真实StoreQueue反馈。
2. **回收到边界而不是边界前一项。** address-ready还差一个老Store时，该原Load记录
   仍能被真实更老STA按PA/mask找到；前缀到达exclusive边界后，后续STA不再找到它，
   空闲池按原返回延迟恢复。满56原记录要逐个查询，不能只查一条或看full变0。
3. **容量Replay的两个独立唤醒条件。** 原Load cause10入LRQ后，rawFull且还有未决老
   Store时不能grant，包括恰好差128；rawFull真正解除，或地址前缀到达原tail，任一可
   解阻塞。解阻塞不被后来rawFull重新锁住；grant必须真实fire、保留原slot/ROB/LQ/SQ，
   再原slot S3反馈完成，不能把query.ready/队列空当Load完成。
4. **完整容量与新一代身份。** RAW满56不能接受第57条需要记录的Load；原记录释放
   后以新PA/ROB/checkpoint填满56并逐条产生恢复，原PA负查询不得命中新owner。
   正常回收与取消分开；若用取消/revoke须同物理槽新UID实际完成，不拿reset清空替代。
5. **真实Wrapper端点。** 分配128原Store及57原Load，绝对ROB槽活动跨度<320；正常
   S0 Forward→S1 PA→S2 RAR/RAW→同lane下一拍S3。前56原Load建立RAW记录，第57条
   真实ready拒绝后cause10、同lane revoke；由真实原Store地址/STD/Sbuffer/credit驱动
   唤醒。当前64物理窗口以外禁止STA/STD，ROB不得跳过尚未执行Store。
6. **分辨池credit与地址前缀。** 一条较老Load在第127个Store之后、末Store之前派发，
   其exclusive tail127；余Load为128。该原记录到127回收后可解除最后Load的容量等待，
   即使尚有末Store地址未知。全56记录tail128对照必须等地址前缀128。Load允许在第二
   窗口老Store仍未Sbuffer消费时完成，不添加“必须SQ空”的人为条件；最终全部原
   Store片段、SQ释放和原Load VLQ完成都须偿还。

## 固定源码依据及参考边界

- `LoadQueueRAW.scala:129-156,196-202`：address-ready `isBefore(load.sqIdx)`才需分配，
  `isNotBefore`才头回收；原Load保存exclusive SQ。`MultiFlagCircualQueuePtr.scala:106-121`
  在差128的完整flag上，前者为真、后者为假；相等时反过来。
- `LoadQueueReplay.scala:507-510,853-858`：cause10用原Load exclusive tail作blockSqIdx，
  `!rawFull || block.isNotAfter(addressReady)`解除。差128时后者为假；0时为真。
- `Dispatch.scala`真实full128许可、Load exclusive SQ和物理64裁剪，沿用
  [SQ端点合同](lsq-sq-endpoint.md)，不伪造父块就绪/容量输入。

原RAW参考`context`和Replay `sq_after`拒绝distance128的记录必须先原生运行保留普通FAIL。
回归10的启动文件仍冻结；新文件以**显式opt-in**的端点参考运行新例，非端点比较、
knownness、输出选择、mask、checker、安全检查和普通`sq_after`拒绝都保持。后续整合
共享参考前需核对旧轨迹和完整影响回归，不以本合同授权blanket半环放宽。

## 证据门禁

先保存legacy失败与127对照，再新目录重跑相同节点；逐周期raw公开日志独立重建
记录/slot/UID与原响应。每DUT保留自身原DA分母及缺口原文/功能映射；正常端点通过
不抵消既有RAR、strict disabled、SID、WB/zero/完成顺序FAIL，也不代替全域随机、
合法联合容量/CBO分阶段及最终全请求审计。
