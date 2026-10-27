# LSQ生产者域与满SQ端点复核：不能用绿色或包字段替代完整合法性

**目标active，整体NOT_PASS。** 本轮保留原1828例统一回归及全部真实失败，补充
了正常CBO字段、满128独占边界、SMF等待和CBO上游串行许可的实际证据。
“正常包字段”与“整个程序正常可达”明确分开。

## 1. 已结束并冻结的运行

| 运行 | 实际结果 | 启动/结束源 | 结论边界 |
|---|---|---:|---|
| `lsq-progress-regression-08` | 1828例，1658 PASS / 170 FAIL | 371 | 38DUT完整原范围，历史/失败/DA门禁完成；不是正常CBO准入证明 |
| `lsq-normal-cbo-01` | 14例，6 PASS / 8 FAIL | 380 | 197次CBO STA字段正确；其中一个失败是Forward exact128参考拒绝 |
| `lsq-sq-endpoint-01` | 12例，6 PASS / 6 FAIL | 388 | 保留旧Forward拒绝；其绿色对照后来发现ROB过早前进，不能验收 |
| `lsq-normal-cbo-02` | 28例，20 PASS / 8 FAIL | 388 | 709正确CBO包/512槽组合接口完成；12个绿色端点被独立生产者门禁拒绝 |
| `lsq-sq-endpoint-02` | 18例，15 PASS / 3 FAIL | 392 | 12纠正端点、3 SMF127完整完成；3 SMF128是Replay参考拒绝 |
| `lsq-normal-cbo-03` | 34例，26 PASS / 8 FAIL | 392 | 18个无CBO的合法端点完成；CBO相关流量仍受NoSpec/BlockBack拒绝 |

所有运行结束源一致；每轮独立目录，旧失败、错误工具和原件不覆盖。固定开源
`893e1580b705d81f113c30c7a05734e09a08050e`及原53份RTL/native再次复核，开源树干净，
没有改RTL/Chisel迎合参考。

## 2. 两个参考端点与一个真实用例错误，分别保留

### 2.1 满128独占SQ边界是生产者允许的端点

`Dispatch.scala:710-726`用Store end **>** SQ head判许可；多flag比较的差128为
full而不是第129个Store。Load记录这个exclusive tail，不代表可在第128物理槽
STA/STD。新[端点合同](../contracts/lsq-sq-endpoint.md)先于新用例建立。

Forward参考只将已锚定dequeue的`age<128`纠正成`age<=128`。AST门禁证明仅此一个
运算符改变：13824原输入配置完全相同、2304 exact128新配置准入、4608超界仍拒绝；
256个通用after半环拒绝不变，不改select/expected/PA安全/knownness/比较掩码。
见`results/static/sq-endpoint-reference-v1/report.json`。

SMF的blockSqIdx由原Load exclusive SQ保存，`Replay.scala:520-523,853-858`要求
真实dequeue到达才醒。另一个窄helper只用于SMF，full128继续阻塞。65280个非半环
配置不变、256个full端点正确等待，原/新通用sq_after的512次半环拒绝保持；
RAW及普通Store依赖没有无证扩大。见`results/static/sq-smf-reference-v1/report.json`。

### 2.2 不把用例自身非法的绿色当通过

独立审计发现旧12端点代理在只执行前64个Store时，把ROB直接移到最终Load，
越过尚未执行的后64个Store。保留这个拒绝，只改输入：先pending到Store64、
第一窗口实际消费/释放，再发第二窗口真实STA/STD，完成后才前进ROB。未将容量
减少为127，也没有放宽审计条件。

`sq-endpoint-audit-v2.json`在03轮核验**4701条公开记录、2313个原UID**：2295个
Store片段全部真实消费/释放，18个Load全部完成；6 strict+6 SMF共12次真实grant/
原slot反馈。15个旧合法完整历史逐bit不变，3个旧SMF128异常是新结果的实际前缀。
**旧normal02的12个绿色非法历史仍全部被同一退休检查拒绝。**

## 3. 正常CBO有两层准入，不能只修字段

### 3.1 包字段

真实StoreUnit CBO为QB4/FFFF/wline1/16B对齐。旧317例里747次STA均为size3/255/0，
已撤回正常包声明，见[第一轮复核](lsq-cbo-producer-review-20261019.md)。

03轮实际**724次STA包**与两张603实驱pin图一致；其中有miss/retry，独立识别为
**716个CBO原owner**。两个全槽例512个包字段正确的CBO及512个Load确实执行了
384 Cache req/resp、128次16B zero和512次WB；6联合例11766记录/22代满池/
18段fair/992同槽新UID完成也仍是实际接口事实。5个内存污染（含zero byte15、
CBO元信息与实驱pin同步污染）被独立原UID/包语义拒绝，原证据SHA不变。

### 3.2 NoSpec / BlockBack

新源码门禁连接了`Opcode.scala:676-680` → `DecodeStage.scala:160-161` →
`Dispatch.scala:861-885` → `Rob.scala:198-205,512-524,623-625`：CBO只在ROB空时
单独分配，且直到它退休/取消前不放更年轻指令。

`cbo-serialization-audit-v2.json`从03轮原dispatch/STA/ROB epoch证实：**716个
已识别CBO owner全部有BlockBack违例，204个还在ROB非空时分配。** 因此上述包
字段及生命周期通过不能升级为完整正常CBO程序证明；原6联合、混合及同拍年轻
Load的全槽CBO流量均明确保留为接口域。v1曾用opcode循环变量覆盖报告run标签，
v2只修这个元数据变量，716/204/716语义计数和原件不变。

新[串行合同](../contracts/lsq-cbo-serialized.md)和
[完整类型随机合同](../contracts/lsq-serialized-mixed.md)已经先于新代理定义：

- 真正空ROB单独发CBO，原WB/退休后才分配年轻Load，重做全部512槽×opcode×STA。
- **不要求LSQ物理空**：老普通Store可以已ROB退休却仍在Sbuffer背压，新strict/
  protocol-only zero例都保留这个合法故障域，不增加read==head限制。
- 新完整随机保留原八种子、全部八类型/权重、split/VA别名/SID复用/错误/恢复。
  CBO意图一旦抽中就sticky等待真实许可，不重抽/删掉；fair后未接受意图也单列
  真正分配/服务，不冒充已完成UID。

## 4. 03轮8个混合失败的精确范围

七个仍在实际逐拍失配处停止，原实际历史/失败签名与02相同。28934解除两个
参考端点后，首次实际执行完**600拍随机+5000拍fair服务**，5611条记录每拍严格
比较均一致，但最后**74个原UID未完成**，触发真实外层fair有界性FAIL，不能写成
RTL坏pin或公平成功；其CBO流量仍不满足上游串行合同。

独立7066条混合记录合计3004 UID=190完成+2178取消+636失败停留；231个原外部
接受=225真实响应+6待回，另60个已返回Load数据未消费。四个SID/Cache原效应终点
仍有具体身份见证；不把这些取消、停留或未消费量用新正例补成完成。

## 5. 本次自己的覆盖闭环，不借旧317/叶子命中

`normal-coverage-audit-v1.json`将01轮全部**2613条**未覆盖DA逐源/行/原文/上下文
映射既有可读功能的缺失情形，没有删行或悄悄移除整个功能。03轮自身实际覆盖
**56989→57394/59602，新增405，旧命中丢失0**：

| 实际RTL源 | 新动态命中 |
|---|---:|
| PhysicalStoreQueue | 108 |
| VirtualLoadQueue | 222 |
| LoadQueueReplay | 40 |
| LoadQueueRAW | 13 |
| FreeList_1 / FreeList_2 | 8 / 14 |

剩**2208行**仍逐项保留，Replay1509/VLQ469/Uncache114等不是本轮已排除行。
CBO相关命中受上述串行门禁限制，不能称为完整正常程序覆盖。旧全317例的
59595/59602是另一个冻结范围事实，不能拼过来变成本轮数字。18个无CBO端点的
合法完成证据单独保留，不受CBO准入错误牵连。

## 6. 下一步与未验收边界

新`lsq-serialized-cbo-01`已实际12例**7 PASS/5 FAIL**、404源一致；新
`lsq-serialized-mixed-01`原8种子仍**8 FAIL**、408源一致。522个定向CBO owner和
33个混合CBO owner均NoSpec/BlockBack零违例，字段也与实驱pin一致；512正常全槽
CBO及512年轻Load真实完成，3个实际WB错误、1个实际zero WB/释放错误和1个strict
phase错误全部保留。新混合430UID=214完成+166取消+50失败停留，28928实际600+
5000fair仍留18原UID。见[真正串行CBO与混合报告](lsq-serialized-cbo-20261019.md)。

完整正常混合公平/恢复、合法联合容量与CBO分阶段关系、RAW等剩余exact128情形、
扩大后的全38DUT统一回归及最终请求→实际产物/失败/未验证边界审计都仍必需。
整体目标保持active，三个STRESS总项不因原始行命中或必要条件正例而checked。
