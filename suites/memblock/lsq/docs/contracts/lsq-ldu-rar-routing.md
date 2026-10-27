# LDU查询、RAR恢复与STA-nuke：正常生产者补充合同

**后续源准入限制**：旧18例默认S3 size/lastBeat/Replay更新违反源关系；旧15/3和
RAR行满只保留实际接口效应。已按[完整S3合同](lsq-ldu-s3-full-domain.md)仅修三字段
独立重跑相同18例，仍15/3、全公开输出相等，见[S3报告](../reports/lsq-ldu-s3-20261019.md)。

## 范围与先前证据的纠正

固定开源`893e1580b`，真实`LsqWrapper`及其全部下级，不改RTL/参考/比较掩码。
这里验证的是Wrapper外部LoadUnit生产者合同，不扩大为原生LoadUnit/MemBlock UT。
旧定向和混合运行原样保留；其中把RAR响应nuke转换为`C_NK`的流只能作为接口证据，
不能称为正常LoadUnit程序，更不能把这种驱动造成的fair超时认定为RTL活性缺陷。

## 人类可读功能点（实现前定义）

| 功能点 | 正常行为与实际检查 |
|---|---|
| LDU-RAR.stages | 一笔原Load依次发S0 Forward、下一拍S1 PA、再下一拍S2 RAR/RAW；同lane下一拍S3返回原UID。查询不能提前两拍后任意反馈，也不能把另lane的revoke撤掉无关查询。 |
| LDU-RAR.rollback | 有效的年轻同cacheline读者遇release后，较老读者的RAR nuke应产生以老Load原ROB为锚的`flushAfter`；它不是Replay cause11。老Load可正常完成，年轻原UID取消，并实际恢复LQ/SQ分配指针。 |
| LDU-RAR.reuse | 取消不是完成；恢复后必须在被取消的同物理LQ槽分配新UID，重新经过完整查询/反馈并真正dequeue。不能借reset或不相干Load完成宣称清理。 |
| LDU-RAR.release_window | 同拍release、前一拍release、无release分列，三个LDU lane轮换；需要保留真实RAR-REL失败，不能根据实际坏nuke改expected。 |
| LDU-RAR.revoke | S2投机查询在下一拍S3报告真实cache replay时，必须同时向RAR和RAW发同lane`revokeLastCycle`。撤销后的年轻原读者不得再使老Load nuke；Replay原slot握手后重新查询/反馈，两个原Load真正完成。 |
| LDU-RAR.STA_nuke | `C_NK`正例必须来自同一真实较老Store的STA、相同PA及重叠mask；STA同时进入真实StoreQueue/RAW。S3撤销自己的查询，等待真实Replay grant，再以原slot完成。Store原片段也须真正Sbuffer消费和SQ释放。 |
| LDU-RAR.full_pool | 一个真实最老Load阻塞VLQ头，后面96个不同UID依次完成正常查询与S3；没有取消、revoke或head释放，故真实占满96个RAR义务。此时最老Load的RAR查询无需新增记录，仍须接受并完成，随后全部97原Load真正dequeue。用这组正常源流补15例只到少量RAR槽的覆盖缺口，而非读取内部slot作答案。 |

## 固定开源生产者依据

`XiangShan/src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala`：

- 340–351、439–440、749–754、2123：S0 Forward请求、S1 PA/kill与真实连接。
- 1023–1031、1125：`C_NK`由本/前级实际STA-nuke产生，不由RAR响应产生。
- 1083–1097、1216–1219：RAR/RAW在S2发出；MMIO replay不发这两路查询。
- 1096：dataValid由fullForward、NC replay、实际DCache miss/bank-conflict决定，
  不能对所有查询常置1。本批对齐cached正例选择DCache hit或MSHR-nack无miss，
  因而dataValid=1；不冒称已覆盖cache-miss/NC/MMIO完整生产者枚举。
- 1481–1488：S3异常/Replay撤销上一拍的同lane投机查询；两拍older撤销属于S4
  unaligned-head合同，不用普通对齐Load伪造该路径。
- 1495–1504、1750–1759：RAR violation产生原Load的`flushAfter`；VA/PA
  matchInvalid另为`flush`，不是以普通Replay SMF替代。本批无别名负载不冒称覆盖后者。
- 1565–1615：真实S3报告one-hot Replay原因及原slot反馈；RAR nuke本身不是cause。

## 方法、合法性与未覆盖边界

每笔Load都有真实dispatch、完整ROB/LQ/SQ身份。仅在短小且不跨ROB回绕的定向
中复用`RecoveryOwners`，不扩大其raw ROB排序helper为长随机时间线。参考继续
比较所有已知公开输出，actor只读原事务和公开引脚，不读DUT/参考内部状态。
新目录保存启动/结束SHA、原始逐拍记录和普通FAIL；达到这些定向不等于完整STRESS。

仍须在独立完整随机生产者中实现并核验：单一绝对ROB时间线、原8种子及八类型/权重、
sticky CBO NoSpec/BlockBack、NC与MMIO的不同查询/异常合同、依赖重放优先级、
别名flush、split/S4撤销、恢复/取消同槽新UID、合法联合容量和CBO分阶段。
不因本批正常定向PASS追溯提升旧接口流，不删除旧8个随机FAIL，也不放宽半环年龄域。

## 首轮覆盖反馈（新增full_pool前）

`lsq-ldu-rar-routing-01`实际15例12 PASS/3 FAIL，415份源一致；闭包26902/59602，
RAR本体2283/3898。该小定向未遍历96个RAR槽，属于已有容量/生命周期功能的缺失情形，
不是整个RAR功能点遗漏。故增加上表`full_pool`正常源实例并在新目录重跑；
其余总线、CBO、split和大随机未运行缺口仍属于完整Wrapper既有功能的后续必需情形，
不能从这一个定向目录的低覆盖宣布不可达或缩小完整范围。

第二轮`lsq-ldu-rar-routing-02`实际16例13 PASS/3 FAIL，418份源一致，增加的97个
原Load全部完成、峰值96个公开RAR义务。闭包26902→29161/59602，RAR2283→2822/3898。
RAR剩余1076条逐槽ROB/LQ保存分支说明：只改变循环中lane随n变化还未证明每个
分配记录能从任一Load入口保存正确原身份。这仍是已有容量/身份功能的缺失情形，
因此第三轮保留原15例并对同一正常97-Load程序作三种入口轮换。每轮完整排空，
不只改变硬件组合计命中。已有82情形的reached/checked仅在原UID效应完成后
显式采样；先前01/02的自定义审计不追溯改写其0/82结果。
