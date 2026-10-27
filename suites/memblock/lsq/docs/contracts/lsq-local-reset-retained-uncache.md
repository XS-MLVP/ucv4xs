# LSQ本地reset之后，旧Uncache响应仍须偿还（实现前合同）

这是既有reset/外部响应路由功能遗漏的**跨reset外部所有权关系**，不是再排列一个
reset bit。旧共同系统reset用例仍成立，但其external-reset-aborted不证明本合同。

## 边界和生产者假设

只reset本次真实LsqWrapper DUT；外部Uncache代理保留已经接受且已经ack的NC读。
旧SID必须保留到其真实响应，期间新请求不能占用该SID；LSQ结构MID、LQ槽和Replay
槽则随本地reset释放，可以由新UID使用。原请求和新请求用不同PA，不制造未声明的
外部NC合并。旧返回可带corrupt或denied，但遵循`Uncache.scala:99-105`：`error`
与`nderr`不同时为真。普通LD operation6/hyper0/nonleaf0，首次NC S3无Backend WB：
`updateAddrValid=0`；真实回包/原slot grant/bypass后，正常NC Replay S3才WB并释放LQ。

固定开源`MemBlock.scala:1299-1324`给LSQ分支reset树，Uncache由父MemBlock实例化；
`utility/ResetGen.scala:28-43,61-76`异步assert、同步deassert。这里没有原生MemBlock/
Uncache/TL DUT，**不能**凭独立本地reset刺激声称真实SoC会在运行中执行相同隔离
reset，亦不能仅凭同源reset断言在途TL一定安全。系统reset域/总线drain仍为集成边界。

`LoadQueueUncache.scala:65-71,94-110,437-440`表明本地reset清除req_valid、slaveAccept
与state，而SID数值本身可不reset；只有slaveAccept有效的当前SID才能路由响应。
这正是要用真实旧SID回包检查的关系，不读内部寄存器作为参考答案。

**本批不生成迟到旧ack**：旧MID的idResp先在reset前实际完成。迟到旧ack可能碰到
新MID，且原Uncache的e0/e1与skid时序限制其可达性，须另审；不能任意延迟ack后把
接口反例称真实上游正常程序，也不能把它排除成整个系统绝对不可达。

## LRESET-RETAIN：12例定向

三lane分别执行以下四个旧响应时点：reset后尚无新Load、新MID已复用但新响应未到、
新响应已到而bypass未消费、以及新bypass S1之后同拍返回旧数据。旧响应不能成为
新owner的完成条件，不能污染新数据或错误位，也不能冒出旧Replay/异常写回。

每例旧Load在LQ0分配并真实S0 Forward→S1 PA→S2 RAR/RAW→同lane S3，真实NC请求/
ack后只reset本地6拍。外部旧job不abort、不伪称完成。新UID必须实际复用LQ0和原MID，
由另一个仍空闲SID真实回包、原slot grant、NC bypass S0/S1/S2、RAR/RAW和S3、VLQ
deq正常完成。再由第三UID实际复用已归还的旧SID完成，不能把SID锁到旧Load数据消费。

旧UID终态是local-reset-aborted，外部job终态是actually-returned-and-discarded，
与年轻取消、普通完成、异常WB/精确trap都分列。所有本地reset旧槽须有新UID真实完成
见证。旧SID错误不得传播到两个新UID；旧job和全部新job终态都必须清零。

## 参考、检查与存储

只新增独立`tests/local_reset/`显式opt-in fixture：继承原WrapperModel全部输出比较、
knownness、物理字节安全、计数与时序，只在reset时保留已经ack的外部NC读job账本，
**不**保留本地仲裁state/本地Load，不改共享参考或现有用例。另一个在线checker仅
从公开输入/实际输出记原UID、reset、原req/ack/resp、grant、bypass、S3/deq与同槽
完成；不把控制器的终态计数当答案。独立fixture不是probe，不减少运行时检查。

默认0逐拍JSON/0wave，只输出有界每UID/外部job终态、少量关键事件和完整流SHA。
首轮后仍逐行分类自身原DA，再补case或缺失整关系并重跑；不借旧59595分子，不替代
原八类型随机、精确128/旧代、已保留SID污染普通FAIL或最终整体审计。
