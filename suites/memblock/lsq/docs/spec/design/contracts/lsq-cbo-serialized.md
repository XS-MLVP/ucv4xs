# 正常CBO程序合同：包字段与NoSpec/BlockBack都必须满足

先定义行为，再新增串行生产者/测试；旧包字段正确的34例及全部FAIL保留，不能
追溯“升级”为正常程序。新源码门禁已经拒绝其716个已辨认CBO owner的BlockBack
违例，其中204个还在ROB非空时分配。724个STA包中有miss/retry，因此不把包数
与原owner数混为一谈。

## 真实生产者依据

- `Opcode.scala:676-680`四种CBO均`+ NoSpec + BlockBack`。
- `backend/vector/Decoder/DecodeStage.scala:160-161`将这两个属性送成
  `waitForward`、`blockBackward`。
- `Dispatch.scala:861-885`在ROB非空时阻止waitForward，且同拍不放过CBO之后的
  指令；`Rob.scala:198-205,512-524,623-625`的hasBlockBackward持续阻塞年轻分配，
  直到ROB清空/取消。不能只满足SQ/LQ容量、head单调及CBO STA字段便称为正常程序。
- 仍使用`NewStoreUnit.scala:98-102,433-438`规定的QB4/FFFF/wline1/16B对齐。

## 必需行为与新用例

1. **干净全槽完成**：ROB为空时单独分配一个CBO；真正的Cache req/resp（0..2）
   或16B零写（3）、WB fire之后才允许原CBO退休。其后才分配新的Load，并实际S3/
   VLQ完成。覆盖两个STA lane、64槽×4opcode、完整SQ四代及ROB回绕；不是同拍
   偷塞CBO和年轻Load。
2. **响应错误保持**：仍单独分配CBO，Cache denied/corrupt的三种原组合和0/3拍
   WB背压保留。协议探针在真实WB.fire核对原错误，若丢失必须普通FAIL；不用
   改RTL/参考或假装年轻Load先完成/错误已架构退休来绕过。
3. **不能额外限制“ROB空”等于“LSQ物理空”**：老普通Store在STA/STD执行完成后
   可以已从ROB退休但仍在Sbuffer背压中。此时ROB空，CBO可合法单独分配，并在
   ROB头获得真实preCommit。新strict/协议探针都保留这个条件；不得为了zero
   通过而添加`read==head`或要求先排空老Sbuffer。
4. **原zero身份**：上述老片段实际消费不能冒充年轻zero自己的写。strict参考
   捕获阶段失配，另明确protocol-only探针记录真实zero WB/SQ release前是否
   有自己的zero16。后者始终`checked=false`，不能冒充全输出比较。

## 不得虚标的边界

新全槽定向是必要条件，不代替全部8原固定种子、所有类型、完整随机/公平/恢复。
后续正常随机应保留计划中的CBO事务并等待真实串行许可，不能重抽/删除CBO；
全池联合的CBO不能在120个未退休Load之后提前分配。容量峰值和序列化CBO的
不同正常阶段须分别实际证明，而非要求一个真实上游不可能的CBO同场快照。
正常RAW exact128等尚缺情形仍继续，不把本合同或新定向当整体完成。
