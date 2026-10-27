# 功能点定义与事件证据

最新完整测量20209项：20169 PASS／37 FAIL／3 XFAIL，2346文件哈希匹配。
原20156判定、345个ID、分域、六字段合同及功能点状态保持。INT-086保留
原十项细化要求，补当前置信度饱和保持、完整往返及原训练历史存活三项。
335硬件点仍311 PASS／22 FAIL／2 XFAIL，环境10 PASS。

47项新纯检查全PASS；六个DUT程序为4 PASS／2历史资格FAIL，不能将后者直接
称为RTL算术错误。114项新义务到达92、闭合76；459组／411满，旧447组比例
保持。65点成对关联、96点未分离关联、174点缺专属关联仍保留。BPU原生仅
新增1个既有Main替换副本行，非TAGE算术增长；17287零键和137个集成TAGE
缓冲键未据此重分类。见[最新定义审查](../results/production-confidence-boundary-20261017-v1/definitions/README.md)
与[完整结果](../results/production-confidence-boundary-20261017-v1/README.md)。

## 前一轮相反方向测量

最新完整测量20156项：20118 PASS／35 FAIL／3 XFAIL，2335文件哈希匹配。
INT-086原合同不变，补三条原来源与最新计数相反时的准入／累计要求；
原七条保留。三个非饱和对照PASS，三个原饱和场景少提案，因此086由PASS
转FAIL而原节点仍PASS。原20100测试判定、其余344点定义及判定映射保持。

335硬件点为311 PASS／22 FAIL／2 XFAIL，环境10 PASS。65点成对关联、
96点旧未分离关联、174点缺专属关联不变；447组／403满，旧435组比例保持。
新增90义务reached72、checked45，失败checked为0。原生集合不变，不把
新合同或旧行命中当成功证明。见[最新定义审查](../results/production-direction-turnaround-20261017-v1/definitions/README.md)
及[完整结果](../results/production-direction-turnaround-20261017-v1/README.md)。

## 前一轮循环迭代测量

最新完整测量20100项：20065 PASS／32 FAIL／3 XFAIL，2326文件哈希匹配。
新增INT-099明确循环迭代上下文属于准确预测来源，与已有GHR/BW合同分开。
原344点定义、合同、分域及节点判定映射保持；现在335硬件点为312 PASS／
21 FAIL／2 XFAIL，环境10点PASS。65点成对关联、96点旧未分离关联、174点
缺专属关联；335份合同齐备不表示全部要求已证明。

六个真实DUT程序和59项纯检查均PASS，只执行一次全量。45项新配对义务
包括年轻饱和后的准确恢复、注册状态、两个公开快照和真实S3修正发出的
准确消费者。435组／397满，旧423组比例保持；原生行集合不变，未把判据
补证称作行增长。见[最新定义审查](../results/production-loop-iteration-20261017-v1/definitions/README.md)
及[完整证据](../results/production-loop-iteration-20261017-v1/README.md)。

## 前一轮混合版本测量

最新完整测量20035项为20000 PASS／32 FAIL／3 XFAIL，当前源码2317文件哈希
匹配。全部344点身份、分域与原合同保持，INT-086保留原异序程序要求并追加
四条部分服务后的混合版本要求，不为物理复制新增ID。334份硬件合同仍为
311 PASS／21 FAIL／2 XFAIL，环境10点PASS；64点成对关联、96点旧未分离关联、
174点缺专属关联的状态不变，合同存在不代表所有子要求已被证明。

本批4个真实DUT程序、44项纯检查，48项配对义务已完成；两路不同数量的
实际服务、混合消费者和原快照闭合，不仅比较最终方向。前一轮两处纯断言
修复也纳入此次完整复验。见[最新定义审查](../results/production-mixed-visibility-20261017-v1/definitions/README.md)
及[完整证据](../results/production-mixed-visibility-20261017-v1/README.md)。

## 前一批次完整测量

当前344个ID包括334份硬件语义合同及10个环境合同。新增INT-098区分已失驻
原身份的重新学习，INT-086和089细化独立服务与部分驻留要求，不按物理槽位
增加功能点。64点有成对组关联、96点关联旧未分离组、174点缺专属关联；
334份合同齐备不表示全部模型或消费者证明闭合。

本批5个DUT场景完成41项配对义务；完整轮19987项，19950 PASS／34 FAIL／
3 XFAIL。硬件311 PASS／21 FAIL／2 XFAIL，原343点判定保持。两处旧纯检查
的全仓总数断言随后修复并通过291项专项，未重复全量或改写原测量；见
[最新定义审查](../results/production-residency-batch-20261017-v1/definitions/README.md)和
[完整版本边界](../results/production-residency-batch-20261017-v1/README.md)。

## 以下保留阶段历史

当前计划**333硬件合同/0旧硬件点待审**，343个ID保留。最后64项
[BPU集成审查](bpu-integrated-functional-definition-review-20261016.md)已采用，
不等于全部规格、模型或消费者证明闭合。当前63点有成对组关联、96点关联旧
未分离组、174点缺专属关联；关联存在也不证明每个新子义务已到达并比较成功。
最新MainBTB-017补满组学习合同后由PASS转FAIL；新程序reached12/36、checked0/36，
不能继承旧空组PASS。见[完整诊断](../results/production-mbtb-full-capacity-learning-20261017-v1/README.md)。
后续不同位置关系已补两向年龄隔离，仍保留原反例及FAIL判定；覆盖schema
扩为72项义务，原36个bin保留，当前reached48/72、checked36/72，不是整体功能
通过。见[最新完整诊断](../results/production-mbtb-full-capacity-age-20261017-v2/README.md)。
先按[后续设计](semantic-gap-test-design-20261016.md)修验证基线、再补判别用例。

此前计划**269合同/64待逐项审查**。九个独立UT的236点已有
合同；仅BPU64点仍待审查。最新[AheadBTB](ahead-btb-functional-definition-review-20261016.md)
区分保存年龄、分阶段旁带、方向和记录服务；旧同PC恢复、S2强弱profile不独立
证明正确快照选择和S1快速位置关联。旧物理变体保留追踪，不增加独立功能种类。
MicroBTB地址单位不一致是已确认的验证
实现问题，不是RTL缺陷结论；MainBTB请求way与保留owner的差异也不能被弱
计数初态或rawHit=0裸计数掩盖。见[MicroBTB](micro-btb-functional-definition-review-20261016.md)、
[MainBTB](main-btb-functional-definition-review-20261016.md)及
[静态来源证据](../results/btb-semantic-review-20261016-v1/static-findings.json)。
此阶段没有修复这些实现问题，也没有把新合同继承旧PASS。

此前178合同阶段，TAGE36项、SC23项、
MicroTAGE25项、ITTAGE19项、MicroRAS16项、RAS17项均有逐点合同。
新增45项定义明确目标身份和调用寿命：codec与整批拒绝不是硬件正向目标
消费者，空top保持不等于全部状态冻结，中性回收与真实退休动作不能共用
错误的“所有提交状态保持”断言。见[ITTAGE](ittage-functional-definition-review-20261016.md)、
[MicroRAS](micro-ras-functional-definition-review-20261016.md)及[RAS](ras-functional-definition-review-20261016.md)。

此前53项定义明确五类不同状态的语义，SC旧
“稳定方向”不等于权重边界，选择器同拍净聚合也不能用中间态PASS证明两端。
见[TAGE](tage-functional-definition-review-20261016.md)与
[SC](sc-functional-definition-review-20261016.md)。定义审查输出现在逐项呈现
semantic_requirements、evidence_limits及规格未决问题，不让这些被旧PASS掩盖。

此前80合同阶段新增33份合同及两个并发/
边界子要求先定义、暂不补DUT刺激；旧测量PASS只保留原证据范围，不自动证明
扩充义务。`metadata.semantic_requirements`登记同一功能下的正交子要求，
`semantic_review.evidence_limits`明确哪些未证明，不为每个表/槽增加同义ID。
见[MicroTAGE来源](bpu-microtage-functional-review-20261016.md)及
[保留学习/提交调用](retained-state-functional-review-20261016.md)和
[BPU剩余来源合同](bpu-gap-owner-functional-review-20261016.md)。全部43个缺口
关联ID已有合同，不意味着其事件到达、效果或消费者证据已经通过。

最新18983项完整诊断为18955 PASS/25 FAIL/3 XFAIL；365组/334满，十DUT原生
集合不变。MicroBTB地址域成套修复和六类真实消费者闭合，UBTB-011等普通FAIL
保留；冻结333合同及2163源码。以下47合同等按原阶段理解，不把定义采用
冒充效果证明。完整资格见
[当前基线](../results/production-byte-address-20261016-v1/qualification.json)。

## 以下保留阶段历史

最新采用18项审查定义后，当前计划47合同、286待审查，UTAGE25点均有六字段
合同。合同明确不等于证据完备：006/008/009补做了11项有区分度的DUT场景，
最终262项专项通过、六个新成对组全满；其余采用点仍保留证据限制，不把旧
PASS当作新增义务证明。定义阶段审查与场景设计见
[来源资格记录](../results/utage-source-ownership-20261016-v1/README.md)。当前全量
正在复验，以下29合同/304待审查等是各原测量冻结时的历史统计。

最新补强没有新建功能ID：既有UTAGE-020/021增加38项独立语义DUT场景和60项
纯检查，18852项完整诊断为18824 PASS/25 FAIL/3 XFAIL，旧判定保持。四个新
成对事件组全满；显式成对关联的合同由16增至18，两个旧物理组移至metadata
保留，不删除旧分母。原020/021整体仍FAIL，不能用新PASS冲抵旧反例。最新
[定义审查](../results/production-utage-usefulness-events-20261016-v1/definitions/README.md)
仍为29合同、304待审查；[另外18项审查提案](utage-functional-definition-review-20261016.md)
暂未写入冻结计划。以下是前期记录，不作为新增执行。

当前补全已先登记 MBTB-030、INT-097 两份合同，再设计/实现14项DUT场景。
计划343项：333硬件（314 PASS/17 FAIL/2 XFAIL）、10环境（全PASS）；29项
显式事件合同，仍有304个旧硬件点待逐项语义审查。18754项完整失败诊断及
覆盖差分见[缺口补全记录](coverage-gap-completion-20261016.md)，不替代RTL验收。
旧341个ID、判定、功能点测试关联保持；下文19/27合同、331硬件等是此前阶段
的历史审查统计，不是当前登记数量。

2026-10-16 后续工作见[从行缺口审查功能事件](functional-event-review-20261016.md)：
29 项名称/描述已从物理配方改为事件要求，逐点合同由 19 增至 27，仍有 304 个
硬件点待逐项审查；17,377 个未命中 DA 键已关联实现职责与事件，原因未决状态
继续保留。这是定义审查，不是新覆盖率测量。下文“首批19项”为此前阶段记录。

## 三种统计分别回答三个问题

| 统计 | 回答的问题 | 不代表什么 |
| --- | --- | --- |
| 硬件功能点判定 | 对声明的硬件要求，关联pytest检查是否通过？ | 不代表全部RTL行为已被声明 |
| 功能覆盖组/bin | 哪些已定义事件、效果或物理维度得到有效采样？ | 满组比例不是整体功能覆盖率，也不能替代正确性判定 |
| 原生DA源码行覆盖 | 哪些映射源码行被执行？ | 满行不代表行为正确；未命中行也不等于独立功能点 |

环境的绑定、driver、monitor和scoreboard契约独立统计，不进入硬件功能点分母。
341个原ID全部保留：331个hardware、10个environment。旧`ENV-IF-*`保留ID兼容，
component改为`Binding`，不引入Interface类或新的层次。

## 计划与报告

`verification_plan.json`版本2为每项明确记录`metadata.domain`和非空`description`。
此前缺少描述的152项从现有`functional-points.md`对应ID的要求列同步，并记录
`definition_source`，不是根据标题批量生成通用描述。恢复说明不等于完成语义审查。

新`feature-points.json`版本2中：

- `summary`及`summary_domain=hardware`：主要硬件判定；
- `summaries.hardware`：硬件功能点；
- `summaries.environment`：环境契约；
- `summaries.all`：完整计划，用于保证没有漏点，包括环境FAIL。

pytest串行证据、旧xdist兼容证据和xreactor托管证据共用同一统计函数。
SKIP/NOT_RUN不算执行，XFAIL算执行但不算PASS，FAIL/ERROR/XPASS不能被另一个
PASS覆盖。主统计分域不改变pytest退出状态，也不允许以此隐藏环境失败。
版本1历史报告继续读取，不修改原文件或将旧测量冒充当前执行。

## 一个事件合同的六个问题

`contract`直接放在功能点下，不再增加框架基类或测试调度抽象：

| 字段 | 要明确的语义 |
| --- | --- |
| event | 哪个真实事件、在什么接受资格下产生义务？ |
| owner | 义务属于哪个逻辑分支、上下文、版本或栈帧？ |
| effect | 必须发生什么状态变化，或者明确不发生什么变化？ |
| observation | 哪个实际服务、后续消费者或完整状态比较能证明效果？ |
| preservation | 哪些其他owner、状态和原始metadata必须保持？ |
| scope | 本合同证明到哪里，哪些集成/FTQ/其他预测器组合仍未证明？ |

例如`BPU-ITTAGE-019`不是“某个信号位取某个值”，而是：零置信度provider
接纳真实新目标反馈，即使不分配新预测表，也必须学习完整目标；旧PC/历史上下文
的后续真实provider或alternate消费者要看到正确地址，其他上下文必须保留。
bank/set、地址组合、固定等待周期是场景参数，不因此新增功能点。

`evidence`关联模型文件、检查文件、reached覆盖组和checked覆盖组。文件存在只
证明路径可追踪，不证明模型独立或完备；仍需审查输入来源、状态所有权与比较。
没有成对覆盖的地方使用空列表，不能映射一个旧满覆盖组就声称义务闭合。

## 当前审查边界

首批19项事件合同包含全部17个普通FAIL功能点，以及Main重分类093、RAS版本
复用096两个正向对照。12项已有显式reached/checked关联；5项只有旧的未分离
checked组，2项尚无专属关联。其余312个硬件点仍需逐项语义审查，不能因为已有
description或对应case就把它们全部标为“语义定义完备”。

首批审查时331/10是登记分域，不是逐项审查后的终局：`BPU-ITTAGE-017`现有证据主要
是地址codec和整批输入校验，需确认应归环境编码契约，还是补足硬件端到端证明。
该点仍在待审查集合，本轮不擅自更改其已有判定。反例是UBTB007等流水线测试：
虽在scoreboard目录，但实际使用DUT和agent，不能仅凭目录把它们当纯模型证明。
进一步归域应保留既有ID并明确审查依据，不能只按名称或文件夹推断功能性质。

分域/审查/兼容性的188项针对性检查通过；清理工具改成普通pytest参数化后，
正式managed入口4进程209项全部通过。首轮全量曾因新清理测试使用unittest
subTest触发项目“重复生命周期报告”校验而中断，该轮不作测量或验收。
现保留相同检查条件，以pytest参数化独立报告；没有禁用断言、放宽重复报告校验
或修改xreactor。通用subTest证据兼容仍是单独的待处理事项。

最终18708项/64进程完整复验：18680 PASS、25 FAIL、3 XFAIL，owner595.91秒。
旧18642节点、全部341点判定和所有349组比例保持；新增66普通测试全PASS。
10份最终DAT与前轮逐字节相等，原生分母与命中集合不变。这是分域与定义修正，
不是新的覆盖率增益或RTL验收。见
[复验资格](../results/production-feature-domains-20261016-v2/definition-qualification.json)。

优先补证据的7项：

| 功能点 | 缺口 |
| --- | --- |
| BPU-UBTB-011 | 相邻训练死亡entry的所有权/旁路义务没有专属reached/checked组 |
| BPU-UTAGE-007 | 同一完整tag的真实学习与后续消费者没有专属覆盖关联 |
| BPU-RAS-008 | disable组未分离事件接受与完整不变性检查 |
| BPU-TAGE-026 | 旧provider-way关联组未分离到达与逻辑owner保护检查 |
| BPU-UTAGE-016 | shadow持久性组未分离写入义务与离开旁路后的实际消费者 |
| BPU-UTAGE-020 | useful分配的物理地址矩阵不能代替独立语义事件覆盖 |
| BPU-UTAGE-021 | useful更新/饱和的物理矩阵不能代替独立语义事件覆盖 |

这些是关联与证据缺口，不等于缺少全部断言，也不授予任何新的PASS。

## 采样与行缺口归因

reached必须对应真实有资格的事件，不是仅驱动过输入；checked必须在该义务的
独立比较通过后采样。一个case之后因另一义务失败，不应抹掉先前真实检查样本，
但绝不能给失败或尚未完成的义务信用。功能点整体判定仍由关联pytest结果决定。

行缺口后续按“未声明的语义义务、已声明但未触发、已触发但比较失败、集成尚未
提供合法来源/消费者、物理副本、已证明的局部结构约束”等原因审查。分类必须
保留证据和未决状态，不扣除原生分母；不能把每行/每bank都定义成新功能。
本轮未重新分类所有行缺口，也没有通过枚举物理坐标提升覆盖率。

## 审查入口

```sh
python3 -m tools.audit_verification_plan \
  --measurement results/production-feature-domains-20261016-v2 \
  --output results/新的定义审查目录
```

输出`audit.json`和`README.md`，记录计划及所读测量的SHA256、分域统计、事件
定义和缺失关联。这是对既有测量的定义审查，不是新执行、覆盖率提升或RTL验收。
