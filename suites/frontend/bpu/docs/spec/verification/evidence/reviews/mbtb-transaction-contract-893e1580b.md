# MainBTB 事务适配合同历史原文（public-893e1580b / 2026-11-02）

状态：**历史材料，仅适用于旧基线 `public-893e1580b` / DefaultConfig**。本文是 2026-11-02
MainBTB 事务合同在 2026-11-09 拆分前的旧版正文，保留原日期、基线、运行数字和失败结论，
供追溯旧统计与四路训练条款。当前 `public-a0c2a26cb` 合同见
[当前事务合同](../../contracts/mbtb-transaction-contract.md)；新旧条款不得拼成同一完整验收。

- 旧基线：`public-893e1580b`；当前默认 `public-a0c2a26cb` 的独立适配见
  [2026-11-03 适配记录](../runs/baseline-update-a0c2a26cb.md)。
- 下文“四路训练投影”“完整 cleanup v3 / 训练账本 v4”等数字只属于所列旧运行和选择；
  当前基线的第五槽训练、真实 rawHit/position 与 conditional NT 条款不在此文。
- 旧合同中的来源/UID/所有权/收尾承诺经新基线差分确认未变，当前合同继续维护；本文
  保留原措辞和旧证据链接，不重标当前判定。

## 原始正文

适用于完整香山 `public-893e1580b` / DefaultConfig 提取的 `MainBtb`，不使用旧
MinimalConfig 两路答案，不改 RTL、原生构建或硬件缺陷的 oracle。证据见
[机器记录](../../../../../../../../docs/history/transaction-goal-mbtb-transactions-20261102.json)。

## 输入、输出与快照

| 通道 | 合同 |
|---|---|
| lookup | 50-bit **半字** `GuardedPc.addr`，可带guard，允许真实offset，不当作字节地址 |
| training PC / target | 49-bit **半字** `Pc.addr`；后继对齐窗口在49位域回绕 |
| result | 两个align ×（四个Main way + 一个Victim），target为50-bit guarded半字 |
| prediction metadata | 每align五槽；Main槽完整属性/counter/position/rawHit，Victim无attribute |
| training metadata | 每align四个完整Main槽；五槽预测快照可输入，严格校验后投影实际四槽 |
| resolve vector | 最多八槽，显式`None`空槽保留；位置唯一，最多一个mispredict |

`transaction/types.py`在驱动前拒绝非法类型、超宽、未知/缺字段和错误形状；不会依赖
XData截断，也不把已DCE的Victim训练叶补零。`bundle/abi.py`独立固定逻辑schema，不能
只因生成metadata和live对象双方都缩成旧形状就通过。只读train-ready常量不归driver。

输入与输出metadata递归只读并脱离调用者的可变容器。**显式deepcopy**按现有独立profile
模型接口返回新的可变诊断/expected副本；修改副本不能改原观察，编辑后须构造新事务。
纯错误控制也从副本构造受损观察，不再修改原生采样对象。检查器仍只比较valid/rawHit
所定义的payload域；缺少schema不能被解释为inactive或新的DCE。

## owner与迁移程序

cleanup使用输入reset-LRU计划：original/displacer=3，changed/extra=2，keep2/clear3。
shared-service两行同bank，原半字基址改为`1<<31`、tag步长`1<<15`、行步长`0x80`，
真正实现tag0/1。旧`0x40000020+(tag<<11)`、neighbor+64及`row>>5&63`不是当前坐标，
物理激励变化明确保留，不声称字节不变。

current-owner对照提名/服务2；old-miss在声明的taken-original touch后提名1，但纠正
必须找回retained owner3。同拍clear3属于另一行，四个retained槽可容纳两项，仍须服务
两次。checker完整检查2 align×4 bank×4 way×4 retained slot、原feedback、两个请求/
服务的全部字段、前态和fresh消费者，不按DUT返回way重命名expected。

depth-owner从输入前史建立owner3、负peer2及stale nomination1。旧cold来源不得令第二
深度目标保持旧值或另创owner；不论来源都应更新同一retained记录并保护负peer。外层
semantic cleanup收据改为真实keep2/clear3，不能因旧常量1挡住非零合法控制。

## 时序、框架复用与收尾

lookup复用框架异步单周期Driver及固定延迟Scoreboard；独立S1/S2尾部来自真实S0提交。
DriveStable保存pre-edge ready，实际RisingEdge才采输入；下一DriveStable消费保存输入，
避免可撤回的沿前预览在取消后变成幻影接受。两个lossless订阅始终工作。

`checker/lookup_inputs.py`在SDK提交后、发射前保存原UID/PC/epoch；核对实际S0与SDK
launch时刻、逐UID的S1/S2及输出窗口frame owner。SDK仍负责响应句柄关联；custom
expected不能豁免输入/阶段检查。未发射cancel有独立终态，不需要伪造响应或失败tail。
显式cleanup scope的保留S2脉冲记录原frame UID；被显式扣住的S2记作**未offer**，不是已
消费。关闭scope与模型/原生自主排空检查仍必需，不用次数相等替代身份。

接受后reset、S0/S1之间disable与disabled admission现在由`MbtbLookupDisposition`
交付原UID/epoch/reason；它不是`MbtbPrediction`，其`.preview`只是无查询来源信用的
只读诊断。已在控制变化前产生的结果保留为真正响应，不能reset后追溯取消。SDK继续
负责关联，`completed`含终态交付，不能直接当硬件响应数；`lookup_deliveries`分列。

独立账本分别记录`sample_tick`和真正通过SDK比较的`delivery_tick`，过滤/取消的
`response_tick`保持None。自定义expected只增加有效响应检查，不能豁免错终态或损坏的
SDK样本；终态不会调用功能响应callback。长reset等待遇到协议错立即唤醒，经公开
Scoreboard drain传播同一错误，不改SDK私有计数、不清观察队列或继续到溢出。

框架没有MainBTB reset/enable的语义，所以工程的`MbtbPredictionScoreboard`仅扩展公开
比较hook；提交、接受事件、固定时窗关联、句柄状态和monitor消费仍由SDK实现。它不是
新的通用传输层，input-only入口也不补造response handle。该扩展须随真实相位/终态控制
验收，不能仅凭SDK类名或COMPLETED统计签核。

每沿只查当前due时窗和未产结果UID；历史行、metadata来源及旧tick查询索引完整保留。
不能每沿扫描全部已完成历史，也不能通过删除旧行取得速度。完整finish仍逐项对账。
旧全历史扫描令shadow长矩阵持续变慢，已保留未完成回归并定向中断；不将其中间结果
冒充完整验收。

训练继续复用SDK独占SyncDriver，在发射前为每beat分配UID并冻结完整期望。实际wire的
四路metadata、两个PC、八个稀疏resolve槽及全部字段都需与计划一致；disabled/reset/
初始化过滤、reset取消、Python未发射取消和local-drained分开。local-drained不等于FTQ退休。

`MetadataOrigin`随实际lookup响应提供UID/epoch/PC/offer/response来源；deepcopy保留该
非wire声明，同时仍返回可编辑诊断副本。新训练在分配UID前对账来源catalog、当前epoch、
49位PC投影和完整metadata，不能按相同payload寻找一个来源。刻意编辑的端口压力须用
`declared_metadata(reason=...)`，收据明确不是lookup/FTQ producer credit。原生来源验证
发现replacement场景曾将改写的expected counter3冒充原counter2快照，现每次正常touch
都先取真实lookup并用独立wanted profile检查；没有修改oracle或缩窄原反馈激励。

`finish(timeout_cycles=...)`只等待已提交的尾部和自主训练写回，使用显式cycle预算、SDK
Scoreboard finish及两个尾部观察，再核对模型entry/direction/snapshot/cleanup/offer债务。
不自动补reset、enable、training、metadata或S2来清债。关闭monitor、取消tail、清空视图
都是cleanup，不是事务完成。正常close先finish；失败保持粘滞。

根fixture读取真实setup/call报告：正文已FAIL/skip只cleanup，避免同错变第二个teardown
ERROR；正文PASS（包括吞错）或缺报告仍严格finish。各资源的独立cleanup错误传播。
该checked-close当前只启用于MainBTB及cleanup-reset派生agent，不签核其他九DUT。

## 证据与限制

- 完整cleanup v3：2539 PASS/12 FAIL，其中native113/12、pure2426；原2486项无删除，
  217项FAIL→PASS，新65项自检PASS。12个cleanup原生场景通过，不是整个MainBTB通过。
- 后续seed2定向2599 PASS/5 FAIL；seed1定向88 PASS/5 FAIL。后者随后增加真实训练
  target的高guard消费者，两个源码身份不同，不拼为同源码双seed。
- 19条域/快照red与吞错close原生red修后通过。固定schema、四路容量、全部请求/服务
  字段、closed-monitor、stuck-tail、相同payload不同SDK身份及guard查询有合法/错误控制。
- 训练账本完整v4为2780 PASS/9 FAIL；同源码seed1定向90 PASS，新增55自检PASS、两条
  排空适配FAIL→PASS，源码/产物/构建已核验。
- lookup阶段与metadata来源定向v2为2686 PASS/5 FAIL（native61/5、pure2625），新增42
  自检PASS；后续replacement来源修复定向23 PASS（1 native/22 pure）。二者源码不同，
  不拼为同源码完整验收。详见[lookup/来源机器记录](../../../../../../../../docs/history/transaction-goal-mbtb-lookup-source-20261102.json)。
- 上述终态/索引生产定向为2737 PASS/5既有FAIL（native75/5、pure2662），sourceff41f...，
  新73自检相对训练v4所选集合PASS，源码/产物/构建已核验。旧完整08a1a...因历史扫描
  原因中断，nativeexit130/manifest仍running，无完整信用。中断后十工程collection已审计
  48809项，原45883/48673无删除和顺序变化；该总数早于本次新控制，不能重标。
- 上述同源码完整为2853 PASS/9 FAIL（native159/9、pure2694），seed1选测124 PASS，
  原项/完整分区相对顺序保持、新73自检PASS，来源/构建/产物已审计。但诊断复核发现
  七处独立语义比较先失败后，后续SDK检查因缺sample见证报了次生错误；不能只因FAIL数
  相同就说归因完成。专门red确认原错误对象被替换，现先调用公开`reference.raise_failure`，
  无先错时全部UID/交付检查保持；纯11控制PASS。新source606640...完整回归正在验证。
- 新完整MainBTB仍在独立BPU源码冻结范围执行，其余API/控制所有权和其他工程仍必需，
  详见[生产终态/索引证据](../../../../../../../../docs/history/transaction-goal-mbtb-disposition-index-20261102.json)。

真实FAIL保留：shared retained-owner丢纠正、foreign-tag同位置计数污染、旧cold第二深度
方向污染、联合zero-key清错owner及四个满容量同位置计数反例。原对照、metadata来源和
完整payload要求不删，不加XFAIL、不把错行为改成期望。覆盖产物完备不等于覆盖闭环；
runner清理过的raw覆盖输入不能再被声称可逐份复查。
