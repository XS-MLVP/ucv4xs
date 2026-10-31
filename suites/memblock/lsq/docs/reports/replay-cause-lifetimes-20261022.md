# 同一原Load九次Replay：原因迁移与实际最终完成

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


当前状态：**01/02实际运行保留为LSQ接口证据；继续核对发现64B块误作refill拍宽，
固定源实为256bit总线→32B拍→PA[5]。已撤回02及此前PA[6]producer的固定上游
lastBeat声明，formal03三层定向已通过、完整03仍运行。整体ACTIVE_NOT_ACCEPTED。**

## 请求→功能点→实际检查→覆盖→剩余范围

| 要求 | 对应证据与本轮必须检查的内容 |
|---|---|
| 用例前定义功能点 | `docs/contracts/replay-cause-lifetimes.md`，owner、translation→cache、cache→translation、retry、ID_history、hold、finish，先于实现。 |
| 固定真实层次 | Replay叶子、真实LoadQueue、真实Wrapper，保留原参考/actor/子模块与固定RTL。 |
| 实际原UID生命周期 | `lsqverify/replay_cause_lifetimes.py`，复用只读原normal helper的公开检查/时钟适配，不修改它；刺激只由外部原UID及公开slot产生。 |
| 真实测试 | 三层`test_cause_lifetimes.py`，分别120条Load，每条九次真实grant、八次again反馈、最后一次成功反馈。 |
| 三类覆盖及前后集合 | `tools/audit_replay_cause_lifetimes_v1.py`，fresh各4→5节点前后、完整1762→1765节点，原三类全集和旧命中保持，不OR。 |
| 失败与原件保持 | 上轮61报告/933原件预保护，196旧失败全文与原节点结果必须精确保持，后续只增量接入新证据，不重跑基线或旧全链。 |
| 增益精确源归因 | `tools/audit_replay_cause_gain_attribution_v1.py`，完整新增toggle逐点均为四类cause的原缺失方向；LQ新增branch精确定位到两组有效again反馈谓词。 |
| 索引和终点保护 | `tools/audit_replay_cause_post_round_v1.py`，只增量审新证据和四受影响索引，四份旧字节SHA归档、其他旧报告保持；终点再生报告需幂等。 |

每个原Load只dispatch一次。原因轨迹是TM0→DM15→DR→BC→TM15→DR→DM0→TM0→BC，
最后实际执行成功。VA/指令/ROB/LQ/FTQ/checkpoint/pdest及公开slot不变，handled
为false时MSHR输入即使变化也不能改写保存身份。父级所有失败S3均update0且
准确revoke，最终才update1且等待真实LQ credit。叶子不借父级完成结论。

跨原因时先使旧通道相同数值ID绑定的另一活跃外部请求回应，再用当前通道的
错误ID回应，均不得放行；只有当前正确ID才能按精确边沿放行。C_DR/C_BC直接
重试也检查反馈后N+1首次valid，不将任意延迟“最终valid”当作通过。
每次valid背压3拍、真实grant/S0同拍、S1/S2/S3原bank同slot推进。

固定NewLoadUnit的C_DR由DCache miss+nack优先选择，C_BC拒绝fast消费者后进入
LQ S3；四类原因均有固定源投影。TLBmiss粗查询、Forward kill、DCache失败的
dataValid与最后成功query分开。正常LD、自然对齐与64B FTQ结束半字已声明。
无中途reset、无私有model控制、无跳pending捷径、无skip/xfail或放宽原比较。

## 已完成的小探测（不是正式或完整验收）

`replay-cause-lifetimes-probe-01`实际三层3/3 PASS，6个原UID完成，54个真实grant
与54次反馈；全保留原slot并在两父级实际释放LQ。独立`probe-audit-v1.json`
再次逐条核对原UID/FTQ、9原因序列、MSHR保存/更新、wrong-channel/ID→match
精确边沿、3拍hold和feedback→actual release。六段固定源表达式与旧163库文件、
202测试文件及pytest/README/manifest聚合已核验（明确排除本轮新增文件）。

## 正式及完整运行范围

正式每层fresh before只运行上轮四条normal metadata路径，after保持这四条并
加入新的120原UID节点；定向通过不替代完整目录。完整after已另开
`replay-cause-lifetimes-contributor-regression-01`，仍按原九build全部native贡献
选择（含48个Replay外目录endpoint及Wrapper主目录外贡献）。原1762真实基线
不重跑，实际1765节点/1569PASS/196原FAIL/0ERROR/SKIP；JUnit/manifest及失败
全文已核对。671个验证source聚合从启动到结束完全一致；性能缓存关闭、锁定
默认load调度24workers，实际耗时4651.088130772114秒。不因新例仅3个节点便缩短
旧回归等待预算，也不将不同轮运行时间当作同比性能改善。

### 实际定向结果（不是完整回归增益）

| DUT | 节点前→后 | toggle命中前→后 /总数 | 新toggle | 新branch/rawline |
|---|---:|---:|---:|---:|
| Replay | 4→5 PASS | 60188→60926 /79904 | 738 | 360/0 |
| LoadQueue | 4→5 PASS | 97163→97915 /204148 | 752 | 360/0 |
| Wrapper | 4→5 PASS | 134375→135137 /322010 | 762 | 360/0 |

每层120原UID覆盖全部公开slot0..119，每UID9次实际输出、8次需要再次重放反馈
和1次真正完成反馈；三层共360原UID/3240grant/3240feedback。每层cause位3/5/6/8
的120项×2方向共960点全命中，MSHR/TLB合法低4位也保持960/960。三对fresh
before/after source/build/三类点全集一致，4个旧节点结果与主stream精确相等，
旧native hit无丢失。独立witness逐字段核对所有原因/身份/精确tick与实际完成，
不以模型内部owner/slot生成刺激。完整九build分子需等该独立运行和审计，
上表不回填旧或新完整回归。

### 完整九build实际增益（独立完整上下文）

| DUT | toggle命中前→后 /总数 | 新toggle | branch命中前→后 /总数 | 新branch/rawline |
|---|---:|---:|---:|---:|
| Replay | 73467→73631 /79904 | 164 | 5444→5444 /5448 | 0/0 |
| LoadQueue | 160872→161437 /204148 | 565 | 16132→16372 /16440 | 240/0 |
| Wrapper | 289897→290195 /322010 | 298 | 18592→18592 /18670 | 0/0 |

完整新增toggle均精确等于此前缺失的cause存储位3/5/6/8方向点，已按位/方向、
源行、层次及点集合SHA归因；不是其他随机payload或startup变化。LQ240个branch
全部为原Replay源码中两组`valid && isLoadReplay && need_rep`（input1/input2）
谓词的`cond_then`，每组分发到120个scheduled-entry决定。这是分支求值覆盖，
不能冒称240个独立功能已完成或每个slot都从每个lane反馈。对应实际功能证据
是360原UID/3240grant/feedback的逐条witness。

六个未增加测试的build（Forward/PSQ/SQ/VSQ/LQU/UQ）原dat字节SHA全等；九build
原三类点全集、旧hit、全部旧primary journal贡献保持。完整节点1762→1765，
原结果与196份失败全文SHA精确相同：
`7762ca928cf073b58cfd3ae9e4b217f3fbee70332fea7481686e33a43de54cc0`。
三份完整witness逐字段等于定向原件，Wrapper旧2415份public/check/actor stream
全等，新3份只来自新Wrapper节点，不以叶子PASS掩盖父级失败。

native贡献Replay185→186、LQ261→262、Wrapper805→806，其余保持；所有1765节点
都能映射到实际native primary-journal贡献集合，数量与manifest input_files一致。
原163库/202测试/pytest/README/manifest聚合保持，只明确排除新增1helper/4test
计算旧集合，不声称新全source与旧全source相等。无逐拍JSON/波形/源码新副本。

LCOV闭包仍有原20行边界：LQ50513/50520、Wrapper59595/59602、LQU3169/3175。
native rawline点全命中并未删去这些行。最新完整toggle余Replay6273、LQ42711、
Wrapper31815、LQU12169、SQ6290、PSQ3300、Forward2380、VSQ823、UQ72，整体工作
显然未完成。最新缺点是上轮已分类缺点的子集，原统一235610toggle/563branch
分类库存不回填、不删减。

### 索引入口与保持策略

- 新专项三层与完整：`python3 -B tools/audit_replay_cause_lifetimes_v1.py --full`。
- 总入口：`python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15 --replay-cause-index-only`。
  首轮新证据/索引审计真实exit0/83.315773秒；新入口实测exit0/84.611192秒。
- 原`--normal-replay-index-only`入口在50报告图上明确拒绝exit2，四索引字节实测
  保持不变，防止回退到47报告，不误报为DUT功能FAIL。
- 终点：`python3 -B tools/audit_replay_cause_post_round_v1.py --capture`，再同脚本
  不带参数。重新审三层定向、新完整、下一NC选点及新增点源归因，核对SHA与
  `audit-history`幂等。不是第二次历史全链，不重跑任何DUT。

## 下一NC类型选点，而不是提前宣称新补例

`next-NC-type-lifetimes-selection-v1.json`位于本轮完整结果目录。固定MemBlock
LQ写入直连NewLoadUnit，isNC存储只有`nc && C_UNCACHE`时写1；简单给Cache/TLB
Load置nc不能补正例。最新isNC方向余叶子199/LQ161/Wrapper13，C_UNCACHE方向
余37/119/11，均按具体源/方向/点集合SHA保存。尚未创建下一合同、测试或DUT
运行。下一合同必须一起约束真实bus接受、ack绑定SID、响应/bypass、原bank同拍
grant/S0及实际S3/释放；合法SID“旧数据已消费后重用”正例不能代替原未消费
重用失败。当前选点动态增益0，不替代这些功能义务。

## 01后补查发现的PA/lastBeat关系错误与02必要纠正

上文01运行、前后覆盖和原UID接口检查均真实保留，但新helper在修改页内地址时，
沿用了normal helper profile0的last_beat0；60/120UID的实际PA[6]=1，违反固定
`NewLoadUnit.scala:1613`。只使用refill而非L2 beat的刺激使该错误未在既有参考
比较中暴露，**不能据此称源正确S3**。三份01定向、完整01报告及当前索引已标注
`UNIT_INTERFACE_S3_LAST_BEAT_UNPROVEN_PA_PROJECTION`，旧版本按SHA归档；原dat、
JUnit、witness及196份失败不动。

纠正只修改本轮新helper和新probe：last_beat=bool(PA&64)，每次S3有运行断言，
compact witness新增PA、首次与九次反馈last_beat；独立audit逐字段核对。新probe
从2UID扩到8UID以覆盖PA[6]的0/1，否则旧2UID都落在0域不能验证纠正；正式120UID
全slot不缩小。重建旧helper字节SHA与整个旧验证库/测试聚合，精确保存helper与
probe的sole diff，不保存完整新源码副本。源码纠正证据为完整01目录下
`PA-lastBeat-source-correction-v1.json`。

已启动的01终点审计与这次必要域标注窗口重叠，实际在关键报告SHA不一致断言
exit1/191.151762秒；原日志和receipt及其SHA保留，**没有幂等通过**，不能简单
忽略该错误或覆盖日志。纠正后另用corrected-input/post-index guard与新02目录
完成真实DUT、原失败保持、全部覆盖集合和幂等终点。当前50图明确保留01接口
限制；最终02接入时仍须可查01全部原件、域收回与首次审计失败。

### 已完成的02定向核验

probe02三层3PASS，各8UID涵盖PA[6]真假、共24UID/216grant/feedback。
正式02三层各4→5PASS且专项audit_pair均已通过；每层120UID分别60个PA[6]=0、
60个PA[6]=1，首次及九次反馈的last_beat均有运行断言与独立witness核验。
每层1080grant/feedback和完整120公开slot、原slot九次保持、精确唤醒/背压/S3/
最终实际释放检查全部通过。定向toggle新增738/752/762、branch各360、line0，
与01相同，但现在只有02满足已声明的PA/lastBeat源关系。源正确与覆盖计数相同
是两件事；原01不得因这次02通过而被回写为源正确。

`results/replay-cause-lifetimes-probe-02/formal02-PA-recheck-v1.json`保存三层报告和
witness指纹及60/60逐UID检查。完整02启动后再次冻结验证源码，待终态与完整
集合审计后才填写完整02增益/耗时，不重复1762基线、probe02或已完成正式02。

### 参数链的第二次发现与formal03

完整02实际1765节点1569PASS/196FAIL，4664.715184秒，674source聚合保持；三层和
完整检查与首02索引审计234.025877秒exit0仍是实际接口证据，未完成02终点幂等。
然而PA[6]修正本身仍缺参数链：固定`Parameters.scala:892`总线256bit，
`cache/L1Cache.scala:44`令refillBytes=256/8=32，`NewLoadUnit.scala:1613`应取PA[5]。
`DCacheWrapper.scala:54`的64是blockBytes，不是beat宽。03前已完整核对这四段
git对象及主Scala全部同名定义；02又有60/120UID的PA[5]与PA[6]相反，不能提升为
固定源正确轨迹。

相关14份normal metadata、RAW owners、response payload及cause02派生报告已显式
标记`UNIT_INTERFACE_PA_BIT6_NOT_FIXED32B_REFILL_LASTBEAT`并按旧SHA归档，当前
50补例/63源/38DUT图也公开这一限制。旧真实dat、JUnit、UID/功能检查和196/227
FAIL一律保留；不修改以前冻结helper/actor/参考，不据接口PASS恢复上游合法性。
此前lastBeat源声明须单独补强，不能因为本次cause03纠正就宣布那些旧例已合格。

03仅两行改本轮新helper为bool(PA&32)及逐S3断言，独立witness同样按PA[5]检查。
已重建原02helper字节与整个旧库聚合证明sole2line diff；8UIDprobe将涵盖PA[5]
真假和与PA[6]相反的交叉，120UID三层及独立完整after03仍完整不缩小，1762基线
不重跑，不合并01/02/03覆盖。参数链和纠正保存在完整02目录的
`refill-width-source-correction-v2.json`及`PA-bit5-producer-correction-v3.json`。
源audit首次仅有JSON list/tuple表示不一致断言，已JSON规范化续审，不重复DUT，
该工具错误与191.151762秒的首次幂等失败均如实保留。

probe03三层3PASS/24UID/216grant-feedback，8UID每层4个PA5!=PA6交叉。正式03三层
各4→5PASS且audit_pair均已通过，每层120UID/1080grant-feedback、全publicslot，
60PA5=0/60PA5=1及60PA5!=PA6，首次和所有反馈S3均按固定参数链独立核验。
`results/replay-cause-lifetimes-probe-03/formal03-PA5-recheck-v1.json`保存逐层报告/
witness指纹。source/build/三类全集与旧hit保持；定向toggle738/752/762、branch
各360、line0，没有将纠正输入本身冒作额外动态增益。完整03仍待终态，不回填
定向分子、不重跑1762基线、probe03或已完成正式03。

## 原域和剩余义务继续保留

NC/C_UNCACHE bus/bypass与SID未消费数据保持、Store地址/数据/多匹配依赖、真实
RAW/RAR容量nack、strict/disabled、vector/Hyper、取消/跨页异常、混合公平排空、
release-wait、头许可、完整核容量历史和全38DUT扩大回归仍开放。
本轮只针对四类合法原因之间的原owner迁移补例，不以更易通过的Cache/TLB序列
取消其余功能点，不把原始rawline命中满当作LCOV边界或功能验收。
Python验证代码自身代码覆盖率尚未采集，RTL三类指标不冒充Python覆盖。
