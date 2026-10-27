# SQ头许可取消的上游域：只排除IRQ，不作全面非法输入豁免

本轮沿固定开源`893e1580b705d81f113c30c7a05734e09a08050e`审计14份源文件，
工作区字节与对应Git对象全等，未读internal版本、未修改RTL/Chisel。
机器证据：`results/vsq-cancel-capacity-contributor-regression-01/sq-head-permit-domain-audit-v1.json`。
执行：`python3 -B tools/audit_sq_head_permit_domain_v1.py`。

## 已证实的窄控制域

- `CompressUnit.scala:94..96,233..235,296..307`的执行逻辑规定，含真实Store的
  entry有unsafe成员，因此interruptSafe为false。`Rename.scala:464`、Dispatch/
  EnqRob的connectSamePort、`RobBundles.scala:226,270`把该位传至ROB提交项。
- `Rob.scala:768`的intrEnable受interruptSafe约束。对8个Store lane和其余任意
  entry/unsafe mask共131072组、每组8种intr/wait/flushed组合检查，IRQ路径均
  关闭。这不是引用`Rob.scala:1688..1698`已注释历史代码来代替实际实现。
- **该证明仅限IRQ。** `Rob.scala:853,898`仍有exception/replay路径；
  `1224..1256`还明确处理head former/latter的flushSelf及pendingPtr恢复。
  非IRQ路径与执行异常、debug、single-step、压缩slot、pending延迟的组合域
  没有被该布尔mask证明覆盖，不能据此称原节点非法或豁免它。

## 与失败旧字节一致、但不能冒充逐拍重放的结构证据

- VSQ在ROB头相等时给preCommit，redirect只抑制当前valid；PSQ另有持久
  committed位和已接受的EnterSbufferQueue请求，二者不等价于VSQ当前许可。
- 固定导出的`rtl/store_queue/EnterSbufferQueue.sv` SHA为
  `35e3124ddb6624ff53c510e69e3c95f0bbdfd1f076dac42a292555297925e2ca`；
  其接口没有redirect/flush或ROB/SQ身份输入，分配状态由入队及实际Sbuffer fire
  更新。**已进入这个FIFO的请求不会因后来的redirect被该FIFO取消。**
- 这与tick932的公开输出属于旧UID315/SQ254/原PA有效字节相符，但没有保存完整
  逐拍trace，故不声称已离线重建该UID在哪一拍进入FIFO。实际失败瞬间见证及
  原public/actor/check流摘要是动态证据，静态控制锥只是补充解释。

## 仍然必保留的义务与下一动态目标

原SQ失败继续`OPEN_HEAD_PRECOMMIT_FLUSHSELF_BOUNDARY`、required=true、
waived=false。需要完整上游历史证明或真实动态反例，不以未许可正例替换它。
本次没有执行DUT，**动态覆盖增益为0**，不改分母、缺口库存或失败结果。

最新1177-node dat按精确build源路径统计（leaf为`VirtualStoreQueueDut.v`，父级
为`VirtualStoreQueue.sv`）：VSQ计数锥仍缺retire bit6双方向及启动bit9双方向；
SQ缺cancel bit7双方向、retire bit4下降及启动bit8双方向；Wrapper缺retire bit6
下降、bit7双方向及启动bit8双方向。不能只按`.sv`后缀漏掉leaf而误判已覆盖。

下一动态合同为[已知退休批宽](../contracts/vsq-retire-known-width.md)：真实
1→64→16→1flow退休批次及父级全部原字节/Load完成，三层独立native覆盖，不
用启动随机态、高位算术界或较易通过的叶子代替父级验收。
