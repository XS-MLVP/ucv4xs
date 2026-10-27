# 集成TAGE selector：合格训练、完整提交与真实预测消费

## 行缺口归因到事件需求

基线为已发布 `production-micro-ras-events-20261013-v1`：15252 PASS、7既有strict
XFAIL、0 SKIP，305功能点298 PASS；BPU33146/46541。十DUT原生零回退，
MicroRAS四格reached/checked完整，pytest446.21秒、完整657.36秒。

该基线的集成`Tage.sv`有71个缺失原生键，其中39个位于selector训练。它们不是
39项新功能，也不能用独立TAGE的4467/4587来豁免集成训练资格。
`Tage.scala:427–430`定义弱provider与alternate/base分歧时的训练资格；
`:433`限定conditional/owner；`:637–659`按selector聚合增减并在T3提交。

新增 **BPU-INT-072** 的稳定事件义务：

- 真实接纳的合格弱provider分歧，alternate正确则增、provider正确则减。
- 聚合净增量后五位饱和；强provider、方向一致不训练；其他selector隔离。
- 后续真实预测根据独立selector符号选择provider或alternate，且实际输出和最终
  BPU结果都必须符合，而不是仅检查metadata中的useProvider。

训练提交与预测消费是两个事件族，分别统计reached/checked。更新有六种规则，
消费有provider/alternate两种选择；各自要求两种alternate置信度条件实际出现。
不要求规则×置信度×物理bank/set的笛卡尔积，不以覆盖标签数代替功能点通过率。

## 输入与前置状态构造

只用一个固定零PHR predictor key、两条不同conditional及两个最高表provider。
复用已有真实provider-pair准备，初始计数4/5。训练只针对前一条，metadata均来自
不同实际预测来源；每笔反馈后等待既有pipeline/write完成条件，再取得新预测。
不改metadata，不写内部状态，不使用VPI、波形或逐周期JSON。

真实mispredict或alternate参与时会重读表，其他条件才可能使用原metadata。
因此checker检查T2模式并把训练read operands的provider/alternate投影与新鲜
公开预测关联；不假设所有反馈都采用原meta，也不拿实际selector寄存器给模型起算。

固定反馈序列建立强负alternate，令同一个高置信selector先15→0，再0→16→31，
两端都再施加合格票以证明饱和保持。116笔反馈是状态构造/功能刺激，不是116个
必要等待周期，也不是116个物理地址case。

第一次候选在上升过16后失败：恢复provider的taken反馈也训练了新选中的alternate，
置信度变弱导致后续票切到另一个寄存器。模型与硬件仍完全一致，但原先指定的
同一寄存器上界目标没有成立；没有删除这个断言或改成“任意寄存器到31即可”。
独立pair模型推导并验证新的置信度重建步骤，随后同一selector确实到0和31。
失败保留为 `integrated-tage-selector-candidate-20261013-v1`，不计正式覆盖、不新增XFAIL。

## 参考、monitor与比较边界

`model/tage/selector.py`独立生成owner/conditional/provider/弱值/方向分歧资格、
增减票、按索引聚合及饱和；八个selector从reset值16起算。
`monitor/tage/selector.py`用既有Bundle/CycleMonitor/@on读取memory-direct信号。
`checker/tage/selector.py`用既有Scoreboard关联实际公开payload、T2模式/输入、
T3全部八槽资格/投票及下一观察点完整八寄存器，不在case暴露边沿或内部延迟。

训练read operands是明确观察的输入，只用于新鲜源投影一致性检查；这不是完整
TAGE SRAM/allocator/LFSR/useful状态参考。零PHR由既有全52位/76fold参考持续检查，
当前四表MiniConfig标签几何也核对。不声称stale/overlap metadata或完整FTQ合法性，
既有TAGE stale-useful XFAIL和其他普通失败诊断不被豁免。

消费检查使用精确S2时刻的参考selector快照，匹配原public source与S3 metadata：
先比较同源TAGE输入/metadata，检查真实takenVec valid/taken，再根据独立选择与
已安装程序目标检查最终S3 PC/target/taken/position。输出损坏即使metadata自洽
也会失败。其他slot/selector状态和全部来源排空继续检查。
每笔新鲜回读另用既有纯provider转移规则检查被训练counter的饱和增减，并检查
未选provider的table/way/counter完整签名保持；不把这个局部算术检查外推为完整SRAM模型。
仅保留64帧诊断窗口和32条事件见证；成功输出累计计数与阶段summary。

## 独立资格与完整生产发布

[`v1资格`](../results/integrated-tage-selector-qualified-20261014-v1/exit.json)
1 PASS，19.23秒pytest，完整选测处理40.56秒；116个不同来源、125次总训练接纳、
2148个观察周期，最终selectors=`16,16,16,16,16,16,19,31`。
[`严格单场景原生差分`](../results/integrated-tage-selector-qualified-20261014-v1/functional-line-delta.json)
新增11个键，全部`Tage.sv`，也均未在旧全物理范围中命中：

| 位置 | 增量 | 解释 |
| --- | --- | --- |
| 3439及3524–3531中的原生键 | 8 | 合格selector7净减及五位寄存器更新/饱和；完整八寄存器已实际比较 |
| 1925、1982 | 2 | 伴随训练的分配候选组合；未据此宣称分配优先级需求独立关闭 |
| 9984 | 1 | 伴随有效预测的provider数据选择；不能单凭该行计数宣称完整预测模型 |

[`v2加强资格`](../results/integrated-tage-selector-qualified-20261014-v2/exit.json)
1 PASS，另加入真实TAGE输出及最终S3完整比较。随后增加发布门禁/负向纯契约；
[`v3最终源码资格`](../results/integrated-tage-selector-qualified-20261014-v3/exit.json)
1 PASS，19.41秒pytest、完整39.49秒；1772项源码哈希、JUnit及worker收据重新核验一致，
严格差分仍为11键。118项selector纯契约与54项发布门禁合计172 PASS；
全部BPU scoreboard兼容9766 PASS、167.13秒。随后仅补每笔provider转移/邻居签名
检查后，[`v4加强资格`](../results/integrated-tage-selector-qualified-20261014-v4/exit.json)
也已通过，1 PASS、完整40.04秒，1772项源码/收据/JUnit核验一致，严格差分仍为11键。
随后64进程完整生产回归
[`production-tage-selector-events-20261014-v1`](../results/production-tage-selector-events-20261014-v1/exit.json)
已退出0并正式发布：15387 PASS、7既有strict XFAIL、0 SKIP，306功能点299 PASS，
220功能组208满目标。pytest455.37秒，完整668.48秒。源码、计划、DUT和依赖
1772项哈希保持冻结；64收据、983功能输入、完整JUnit及根报告/profile/LCOV均独立复核。
十DUT零旧键回退；BPU精确新增上述11键，集合与v4资格完全相同，正式值33157/46541。
两个更新/消费事件族的reached与checked四组及置信度条件均通过完整发布门禁。
此前单场景历史并集不是正式值；本次正式值来自新的完整执行，不回填旧冻结证据。

发布后进一步复核采样次数，发现case在上一笔反馈后与下一笔反馈前重复调用
同一个预测的消费检查。v1覆盖格及11键集合仍真实，但selection的188次sample
不是188个不同硬件事件。当前改为初始预测检查一次，每笔新预测检查一次，
把已验证的metadata留给下一笔反馈使用；不改变刺激或比较规则。
[`v5唯一采样资格`](../results/integrated-tage-selector-qualified-20261014-v5/exit.json)
1 PASS，19.28秒pytest、完整39.87秒；116个更新事件和95个弱provider消费事件，
分别为46次alternate、49次provider，reached/checked完全对应且四组仍100%。
严格增量仍精确11键。新epoch的完整生产
[`v2`](../results/production-tage-selector-events-20261014-v2/exit.json)
现已退出0并发布：15387 PASS、7既有strict XFAIL、0 SKIP，306点299 PASS，
220组208满目标；pytest451.87秒、完整666.05秒。64收据/983功能输入/1772项
源码、JUnit、根报告/profile/LCOV再次独立核验一致，四组事件计数和覆盖格完整。
十DUT原生集合与v1完全相同，精确保留相对初始基线的11键增量；最终正式BPU
仍33157/46541。旧v1证据保留，不回写其计数。
这个问题说明：覆盖事件身份不能由重复assert调用次数决定；比较可重复，事件采样
必须由同源新预测/新更新驱动。

本需求只补闭合selector事件，不把剩余TAGE缺口全部叫物理复制项：
分配失败老化3键、其他selector/context、分配优先级及candidate useful仍需继续归因。
ITTAGE目录的序号式清单采样也仍待迁移；完整验证目标没有完成。

## 剩余缺口的下一步：不把复制位置变成新功能点

072完整发布时的`Tage.sv`还剩60个零计数原生键，与v4和前基线隔离并集一致。
以下是实现位置分类，不是60项需求：

| 实现位置族 | 剩余键 | 下一步必须证明的语义 |
| --- | --- | --- |
| selector更新上下文 | 31 | provider表身份和alternate置信度到共享selector的路由；不能只复制本例到所有bank |
| 预测provider/alternate来源 | 17 | 最长历史及次长历史选择，在同源实际valid/taken/target上比较，不仅看metadata |
| 分配候选优先级 | 3 | 空项优先于弱且无用，后者优先于其他无用项；有效写入及后续消费必须关联 |
| 分配失败老化 | 3 | 合格分配失败累计、饱和触发全表useful清理、清理结束后重新可分配 |
| provider useful候选 | 6 | 真实资格、有效write及后续保持；不能用候选算术命中代替提交检查 |

尤其不能把本例的最高表错误预测拿去累计老化：`Tage.scala:414–419`明确排除
最高表的`needAllocate`。需要真实建立候选表全部无可用way且仍需要更长历史的状态，
每次关联accepted feedback→T3 `needAllocate && !canAllocate`→8位计数器提交。
255是合格失败事件数，不是空等255周期。计数饱和后的下一次真实`t3_fire`触发
一次清理，即使这一笔不需要分配；此时清零计数，清理中不得重复累计/重启。
`TageTable.scala:177–199`按实际SRAM写
握手推进清理，完成边界应是所有表in-flight退出，再检查保留tag、清零useful及
新分配恢复。当前仅完成源码分析，尚未实现或给予覆盖信用。

集成构造还有两项不能从独立TAGE测试照搬的前提：

- 当前MiniConfig的MainBTB为两对齐bank各两way，只提供四个预测结果；TAGE却有
  四表×两way。独立模块的八position装满序列不能假定八个MainBTB owner同时存在。
  候选方案是少量不同source PC共享同一TAGE bank/set、使用不同tag，并通过真实
  MainBTB安装建立每个当前owner。必须实际验证index/tag关系、保留useful和
  owner容量影响，不能只在metadata中填`rawHit`。八个对象是容量压力前提，不是bank遍历。
- 独立模块可直接提供basePred=0；集成MainBTB会被反馈真实训练。固定重复taken=1
  最终会被base正确预测，便不再满足`needAllocate`。压力阶段应根据每个新鲜真实
  来源的最终方向构造相反结果，同时比较MainBTB/PHR/资格和未被驱逐的TAGE状态。
  255笔都必须是真正合格的分配失败，不是只让公开mispredict字段保持1。

这些是待实验验证的构造方案，不是已经可达或通过的结论。目标应是一次全局老化
生命周期及恢复，不复制多个bank的整套255笔序列刷行。

后续073已完成这项构造的真实DUT实验与最终双触发资格：合格累计、需要分配或
正确更新触发清理、正常useful写被维护覆盖、全地址握手和七项保留/新项consumer。
联合资格精确新增92键，随后完整生产已发布并精确重现、十DUT零回退，BPU至33249/46541；
集成Tage剩18键。上文“尚未实现”描述的是072阶段，不代表最新状态。
见 [073事件、oracle修正及完整发布](hardware-event-functional-points-20261013.md#tage-useful老化073的真实事件资格与完整发布)。

## 八个逻辑selector的输入路由：加强原072，不增加物理枚举

073发布后的18个集成Tage零键中，7键属于selector0提交。原因不是遗漏一种新的
计数器算术，而是容量准备总把MainBTB base重建到强正3；弱负provider与它分歧时
只训练了各表的高置信度路由。四表×两置信度是共享selector的八个逻辑对象，
不是bank/set/way物理坐标。因此在原072中明确
`TAGE.SELECTOR.PROVIDER_CONFIDENCE_ROUTING`，不新增同义功能点。

复用073已经必须建立的八个容量对象：每表第一个tag保留真实分配后的弱正base2，
第二个tag仍以正常反馈重建强正base3。表身份来自已独立验证的实际分配及新鲜
预测，不假定随机选择顺序，不写内部状态或改metadata，不复制新的255笔老化循环。
这还省去四个tag的强base重建；两个原老化触发case数保持不变，并同时归属072/073。

比较复用原selector参考及monitor，不另做调度/关联框架。独立票先确认同源公开
反馈、owner、条件分支、弱provider、方向分歧和置信度，reached再记录真实T3来源；
随后实际T3八槽资格、索引、增减票及下一观察点完整八寄存器必须一致，才给checked。
每场景八个对象各训练一次、最终八寄存器均为15。覆盖仅有index0..7，没有
phase、bank、way或笛卡尔积，且每笔保留prediction/meta/accepted/committed身份。

[`最终三用例资格`](../results/integrated-tage-selector-routing-qualified-20261015-v2/exit.json)
已退出0：原072饱和用例及两个073触发共3 PASS，pytest47.99秒、完整69.36秒；
1780项源码、完整JUnit及3个worker回执重新核验一致。两种老化贡献合并后，
routing reached/checked各16个样本、每个逻辑index各2次、两组均100%，原六组老化
和四组更新/消费检查继续保留。v1因命令的重复`--select`仅执行两项老化，不作为
三用例资格；v2使用单个`--select`列出两条路径并核对实际collection。

[`严格单场景差分`](../results/integrated-tage-selector-routing-candidate-20261015-v1/functional-line-delta.json)
与最终三用例联合原生集合相同，新增8键：`Tage.sv:3454,3455,3456,3457,3458,3460,3461`
直接对应完整比较过的selector0提交，`9973`是伴随预测来源路径，不单独关闭完整
provider来源要求。新增15项纯路由契约包含八输入、六故障和合并；selector/aging/
routing纯契约合计248 PASS，发布门禁78 PASS。纯fixture不计原生覆盖。
随后64进程完整生产
[`production-tage-selector-routing-20261015-v1`](../results/production-tage-selector-routing-20261015-v1/exit.json)
已退出0并正式发布：15543 PASS、7既有strict XFAIL、0 SKIP，307点全执行、300 PASS；
228功能组216满目标。pytest458.18秒、完整671.16秒；1780项源码保持冻结，
64收据、987功能输入、完整JUnit及所有根报告/profile/LCOV再次独立复核一致。
routing reached/checked各16次、每index2次，原更新/消费及维护门禁继续完整。
十DUT零旧键回退，精确新增上述8键，集合与单场景严格差分及最终三资格相同；
八键在固定旧全物理基线也均为零。正式BPU为33257/46541，集成Tage3011/3021，
剩10键；独立Tage4467/4587不变。旧范围7424命中损失和384新命中继续分开报告，
不把历史并集当当前执行。未解决动态需求和既有普通失败仍保留，完整目标未完成。
