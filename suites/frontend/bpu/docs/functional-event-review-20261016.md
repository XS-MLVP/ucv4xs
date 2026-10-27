# 从行缺口审查功能事件

最新完整诊断20035项，20000 PASS／32 FAIL／3 XFAIL。本批从不同身份部分
服务的缺证据处细化4项语义要求，再实现4个DUT程序与44项纯检查；622项专项
通过后只跑一次全量。48项配对义务闭合，423组／385满，旧415组比例保持。
BPU原生新增7个DA键，独立四DUT复验同样命中，其他九DUT集合不变，十DUT
无旧命中损失。17288零键／49职责组，集成写缓冲开放键144→137；仍不能由
关联替代全部原因证明，也不把生成分支复制当成新的功能点。见
[当前账本](../results/production-mixed-visibility-20261017-v1/gap-map.json)、
[完整诊断](../results/production-mixed-visibility-20261017-v1/README.md)及
[混合版本要求](tage-mixed-visibility-learning-20261017.md)。原硬件失败保持。

## 前一批次完整测量

最新完整测量19987项。本批先定义失驻旧身份重新学习和两路独立服务要求，
集中完成5个真实DUT场景、80项纯检查，再执行一次全量。BPU新增5个原生
行键，均由独立异序服务DUT复验；十DUT无旧命中损失，17295零键／49职责组，
集成写缓冲开放键149→144。不能把槽位上的五行称为五个独立功能。
415组／377满，41项新配对义务闭合。完整轮34 FAIL中两项为总数硬编码的纯
检查，随后291 PASS专项已修，原32 FAIL和3 XFAIL保留；当前源码不冒充再次
完整验收。见[最新账本](../results/production-residency-batch-20261017-v1/gap-map.json)、
[完整诊断及版本边界](../results/production-residency-batch-20261017-v1/README.md)和
[五场景语义](tage-partial-residency-cases-20261017.md)。

## 以下保留阶段历史

最新完整测量19902项，四种恢复程序完成24项实际配对义务：实际条件方向、
非条件不追加、已执行前缀，以及提交状态与新有效消费者。85纯检查和4DUT
程序PASS，旧19813判定、343点状态和397组比例保持；405组／367满。
十DUT原生键和命中集合无增无损，17300零键、49组及149个集成写缓冲开放键
保留。CommonHR三行已另有局部优先矛盾和全部原生producer匹配证据，不
将其说成三个缺失功能或删掉原生分母；本批自动分类器不变。见
[当前账本](../results/production-common-recovery-20261017-v1/gap-map.json)、
[完整诊断](../results/production-common-recovery-20261017-v1/README.md)和
[四种语义要求及局部归因](common-history-recovery-batch-20261017.md)。另有
[部分原身份已被替换时的模型边界](bpu-partial-residency-feedback-review-20261017.md)，
尚未决定允许结果和FTQ来源资格，不计作RTL错误或覆盖信用。下方保留历史测量。

最新完整测量19563项，补齐两条迁移分支的后继学习与前版两路服务同周期
发生的比较证据：8次实际完整服务、3次接纳／退休交叠和两个新历史消费者，
不能由最后0/7或两个单分支程序推断。66纯检查和1DUT程序PASS，旧19496
节点、343点判定及389组比例保持。十DUT原生集合无增无损，仍17330零键、
49职责组和179个集成写缓冲未闭合键。该组合补证不是新DA命中；邻居共存
前态另有纯模型正常事件推演，尚无DUT信用。见
[当前账本](../results/production-bpu-dual-retirement-20261017-v1/gap-map.json)、
[完整诊断](../results/production-bpu-dual-retirement-20261017-v1/README.md)及
[语义义务](bpu-dual-retirement-20261017.md)。下方保留历史测量。

最新完整测量19496项，两条迟到分支反馈在provider身份交换后仍独立累计，
补强已有INT-089而不按槽位新增功能点。24步正常准备、三份真实旧来源、
四次SDK完整服务和六个新消费者完成成对8项义务；旧19452判定及343点状态
保持。BPU原生DA新增7，均由独立通过的专项执行，其他九DUT集合不变，
十DUT无旧命中损失。总零键17337→17330，49职责组仍保留，TAGE写缓冲的
集成未闭合路径186→179；未把所有剩余行归为不可达或新的物理功能。
见[当前账本](../results/production-bpu-dual-migration-20261017-v1/gap-map.json)、
[完整诊断](../results/production-bpu-dual-migration-20261017-v1/README.md)和
[语义合同](bpu-dual-provider-migration-20261017.md)。下方为历史测量。

最新完整测量19452项，新增四个不同旧位置程序已证明MainBTB满组后的两向
年龄隔离：先检验邻居竞争，再让其合格访问，最后检验目标竞争，避免后续
同值更新掩盖串扰。原四个相同位置反例仍普通FAIL；MBTB-017未改判PASS。
两组扩为72项义务且保留原36个bin名称，reached48/72、checked36/72；全仓
387组／349满，其余385组比例保持。十DUT原生命中集合不变，17337零键及
全部物理副本仍保留，不把功能证据增加冒充行增长。见
[当前账本](../results/production-mbtb-full-capacity-age-20261017-v2/gap-map.json)与
[完整诊断](../results/production-mbtb-full-capacity-age-20261017-v2/README.md)。

当前最新完整测量为19429项、19394 PASS/32 FAIL/3 XFAIL，387组/349满。
MainBTB替换职责的50个缺行副本进一步关联满组连续学习义务：两份新分支
各保留独立方向，后续竞争保护较新者，独立邻居的内容和年龄保持。
四项新程序均在计数应2实1处普通FAIL；reached12/36、checked0/36，后续竞争
未获得硬件证据。MBTB-017由PASS转FAIL，其余342点不变，旧19390节点判定保持。
十DUT原生命中无增无损，17337零键仍保留；关联并不证明50个物理副本的因果
闭合。见[当前账本](../results/production-mbtb-full-capacity-learning-20261017-v1/gap-map.json)、
[完整诊断](../results/production-mbtb-full-capacity-learning-20261017-v1/README.md)和
[语义合同与真实首错](mbtb-full-capacity-learning-20261017.md)。下方为历史轮次。

当前最新完整测量为19390项、19359 PASS/28 FAIL/3 XFAIL，385组/349满。
MicroTAGE原生DA新增10，其他九DUT集合不变，无旧命中损失，总剩17337零键；
[当前账本](../results/production-utage-long-history-learning-20261017-v1/gap-map.json)
保留所有分母、语义关联与未决原因。333个硬件合同/0旧点待审查并不代表模型
完备。共享短历史的两个相反长路径补并发学习义务，新增成对20项全满，旧
19358节点和343点判定保持。增量包含正常建立记录及后续保护变化，不全部
归因于反馈重叠。完整来源和范围见
[最新诊断](../results/production-utage-long-history-learning-20261017-v1/README.md)。见
[新增来源/并发义务](bpu-microtage-functional-review-20261016.md)和
[SC/TAGE/RAS保留身份合同](retained-state-functional-review-20261016.md)及
[BPU来源合同](bpu-gap-owner-functional-review-20261016.md)。全部43个缺口关联
ID有合同，不代表全部功能规格或原因处置已完成。
最新[TAGE](tage-functional-definition-review-20261016.md)/[SC](sc-functional-definition-review-20261016.md)
审查还明确饱和资格、严格阈值和共享状态边界的证据缺口，不以旧满行或满组关闭。
后续[ITTAGE](ittage-functional-definition-review-20261016.md)、
[MicroRAS](micro-ras-functional-definition-review-20261016.md)、[RAS](ras-functional-definition-review-20261016.md)
进一步明确编码检查与硬件闭环、有限知识和调用版本信用，仍不增加测量PASS。
最新[MicroBTB](micro-btb-functional-definition-review-20261016.md)/[MainBTB](main-btb-functional-definition-review-20261016.md)
审查发现地址适配/模型单位和若干旧辅助期望的证据问题，原生行满也不能代替这些检查。
最新[AheadBTB审查](ahead-btb-functional-definition-review-20261016.md)完成其53点定义，
九UT的236点均有合同；保存年龄、分阶段旁带等仍有证据缺口。当前ABTB原生满行
不消除这些语义义务，也不把重复坐标配方计成不同功能。其后
[BPU剩余64点](bpu-integrated-functional-definition-review-20261016.md)也已定义完成；
接下来按[语义用例设计](semantic-gap-test-design-20261016.md)先修可信基线，再补
未闭合效果和消费者。所有旧点有合同不是所有零行原因已证，更不是覆盖率增长。
下方18项UTAGE“尚未采用”与17,377等均为原阶段历史，不是当前状态。

最新UTAGE事件补强已完成18852项全量诊断：18824 PASS/25 FAIL/3 XFAIL，
旧判定不变；四个新事件组全满，UTAGE新增3个原生DA键，总剩余**17,372**键。
见[最新账本](../results/production-utage-usefulness-events-20261016-v1/gap-map.json)与
[完整资格](../results/production-utage-usefulness-events-20261016-v1/qualification.json)。
另有[18项旧点审查提案](utage-functional-definition-review-20261016.md)，明确FastTrain
来自S3指导、不是提交执行真值，尚未改变合同计数或声明新的多错误输入要求。
下方17,377/17,375等均按原轮次理解。

后续已完成本批缺口的需求处置与测试，见
[定义先行的补全记录](coverage-gap-completion-20261016.md)。确认新增 MBTB-030、
INT-097 两项合同后，才实现 14 项 DUT 场景；最终 18,754 项全量诊断为
18,726 PASS / 25 FAIL / 3 XFAIL，旧判定保持。当前计划 343 项（333 硬件、
10 环境），14 类事件、29 项逐点合同，仍有 304 个旧硬件点待逐项审查。
MBTB 原生新增两键，当前未命中 17,375 键；
[最新账本](../results/production-main-latest-age-20261016-v2/gap-map.json)保留物理
副本和未决因果边界，不能把关联成功当作功能 PASS。**以下保留前一阶段记录**，
包括当时尚未登记/实现 MainBTB 集成合同的待办，不代表最新执行状态。

本轮先做功能定义，不改 RTL、不增加 bank 枚举，也不把分析结果登记为 PASS。
依据是最后一轮完整诊断 `production-feature-domains-20261016-v2`：
18,680 PASS、25 FAIL、3 XFAIL。以下是对保留测量的源码审查，不是新回归。

## 什么才算功能点

一个功能点应能说清：什么真实事件被接纳，义务属于谁，应产生什么效果，
谁能观察到效果，以及什么必须不变。信号、流水级和物理坐标可以作为定位或
资格证据，但不能代替上述要求。

例如“写到高地址 useful”不是要求；要求是“索引和 tag 来自不同流水线祖先时，
原 provider 接纳的合格反馈仍更新自身保护状态，其他身份保持，后续消费者
仍可找到原 provider”。高地址只是在检验地址截断风险的一组边界参数。

本轮在实际计划中修订了 29 项标题及描述，新增 8 项逐点事件合同；旧配方和
坐标保留在 `metadata.semantic_review.scenario_detail`，旧标题和文档来源也保留。
另有 55 项登记了与语义目录的多对多关系。341 个既有 ID、案例关联与判定不变。
这些计数有重叠，不能相加当作新增功能数。

[事件目录](functional-events.json)目前列出 13 类具体事件，均有事件、效果、
观察方法、相关功能 ID 和 Scala 源码位置。它不是完整规格。当前逐点合同为
27 项，其余 **304 个硬件点仍未完成逐项语义审查**；目录关联也不代表它们的
参考模型、断言或集成来源已闭合。

## 全部未命中行关联到了什么要求

逐行账本见
[gap-map.json](../results/semantic-event-review-20261016-v3/gap-map.json)。
使用每 DUT 的唯一 `(SF, DA)` 键，核对 LCOV 分母、零计数集合、冻结源码哈希及
源码原文，覆盖全部 17,377 个未命中键；没有用报告中重复的模块明细重复计数。
`groups[].lines` 是实际源文件行号，`events` 是语义要求，`related_features`
是现有计划关联，`cause_status` 保留原因审查的未决状态。

这里“未关联行数为零”只表示每行找到了实现职责，**不表示每行未命中的根因
已经证明，更不表示完整功能规格已完成**。一个控制行可同时关联多个事件，
不能把 `if (allocate)` 的覆盖锚点只算成分配效果，漏掉它的更新分支。

| DUT | 未命中 DA | 功能语义与当前结论 |
| --- | ---: | --- |
| UBTB / URAS / ABTB / ITTAGE | 0 | 行全覆盖仍有普通 FAIL，证明行覆盖不能代替正确性要求 |
| MBTB | 52 | 替换年龄的物理索引写入副本，关联 MBTB-024；默认代表索引不遍历所有副本，不新增 52 个功能点 |
| SC | 336 | 待写身份合并相关生成分支；复核局部 `hit && !hit` 矛盾及全部原生覆盖生产者，不新增功能要求 |
| TAGE | 120 | 待写身份更新的优先级排除副本；复核局部守卫及全部原生生产者，TAGE-026 的 FAIL 不因此豁免 |
| RAS | 16 | 提交调用/返回和重复组维护的生成分支；已有源码守卫审查，不是缺少 16 种栈操作 |
| UTAGE | 4,066 | 全部是 usefulness 分配、更新和饱和保持；不是 shadow 淘汰/持久化行缺口 |
| BPU | 12,787 | 分项如下；既有事件、来源闭合、物理副本、辅助比较逻辑和父级约束不能混作一种原因 |

## UTAGE：先把错误的层次拆开

源头是 [BypassShadowBuffer.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/BypassShadowBuffer.scala:197)，
不是“模块名称叫 shadow，就把所有缺口写成 shadow 功能”。

| 源码职责 | 低表未命中 | 高表未命中 | 对应的可读要求 |
| --- | ---: | ---: | --- |
| 分配/更新选择控制 | 381 | 371 | 一次合格反馈究竟建立新身份，还是更新原身份；控制锚点关联多个事件 |
| 分配初值写入 | 381 | 371 | 新身份建立自身保护等级，不继承旧身份 |
| 饱和选择控制 | 382 | 472 | 边界保持与正常变化按前态分开 |
| 饱和保持赋值 | 382 | 472 | 继续同向反馈不绕回，反向反馈仍能恢复 |
| 非饱和增减赋值 | 382 | 472 | 有效纠正获奖励，错误预测被削弱，无资格反馈不修改 |

具体入口例如 [低表](../rtl/utage/BypassShadowBuffer.sv:4084)、
[高表](../rtl/utage/BypassShadowBuffer_1.sv:3348)。这五种实现职责归到三个事件，
不是五种信号描述，更不是按地址复制的数千项需求。

相关点包括 UTAGE-020/021/023/024。020/021 仍为普通 FAIL；007 的 tag 身份、
016 的持久化、025 的指令类型资格也有失败，可能让后续场景提前终止。
不能把每个零计数都归因于这些失败，也不能绕过失败继续采样来恢复数字。
下一步要按事件建立有区分度的前态与实际来源，区分：资格没产生、产生后比较
失败、前一失败阻断后续、以及单纯未访问物理副本。

## BPU：12,787 行的职责拆分

| 实现位置 | 未命中 DA | 语义关联和行动 |
| --- | ---: | --- |
| AheadBtb | 4,926 | 原分支方向奖励、否定更早条件预测、新身份初始化；关联 INT-055/056/058/059，不按计数器地址新增需求 |
| 两个 BypassShadowBuffer | 4,778 | 同上三类 usefulness 事件；补真实来源/资格/效果关联，不盲目寻找更多 bank |
| AheadBtbReplacer | 739 | 用于策略一致性比较的 PLRU 镜像状态，不能全解释为未声明的新架构行为 |
| ReplacerState | 112 | AheadBTB 实际替换年龄副本；代表场景与所有物理副本的关系尚未证明 |
| ReplacerState_4 | 21 | MainBTB 替换年龄副本；缺少专门的集成替换合同与关联证据，不能借用 AheadBTB 的 INT-055 |
| WriteBuffer_4 | 116 | MainBTB 完整修正版本的保留/写回：74 个跨 owner 拷贝候选、42 个双入口仲裁候选；均不是已证明的缺陷归因 |
| WriteBuffer_8 | 306 | TAGE 待写身份：120 个局部守卫排除键，另 186 个仍需原始来源到真实消费者闭合 |
| WriteBuffer_30 / _38 | 336 | SC 局部守卫排除副本，跨 UT 的证明转移要求编译源码体完全相同，不靠模块后缀推断 |
| Phr | 1,417 | 13 个局部矛盾键；1,404 个需 reset 和同 epoch 真实检查点前提的游标余数约束，不是无限制输入不可达证明 |
| RasStack | 31 | 提交调用组维护，包含此前审查的守卫和物理副本；不按槽造功能点，完整输入/效果关系仍需维持 |
| CommonHR | 3 | 已选中恢复分支之后的重复恢复传播候选，按优先级源码继续审查，不新增“第二次恢复”功能 |
| MicroRas | 2 | 当前 BPU 父连接排除的 S2 停顿修正路径，已复核实际原生覆盖生产者，不是待补 BPU 场景 |

### 为什么 739 行不是 739 项新功能

[AheadBtbReplacer.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/abtb/AheadBtbReplacer.scala:60)
在 `EnableCommitGHistDiff` 下维护另一套 ReplacementPolicy 结果作一致性比较；
实际 victim 来自独立 `states` 的 `genReplaceWay`。
编译源码见 [镜像状态](../rtl/bpu/AheadBtbReplacer.sv:73) 与
[真正输出连接](../rtl/bpu/AheadBtbReplacer.sv:2449)。这仍是覆盖率范围内的
实现逻辑，分母不删除；事件要求应是“合格访问后的替换策略与独立模型一致”，
而不是“state_vec 某个物理下标被写过”。这里没有做全设计形式等价证明。

### 为什么不能为了 MicroRAS 两行硬造停顿

[Bpu.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala:254)
给出 `s3_ready = s3_fire || !s3_valid` 且 `s3_fire = s3_valid`，故 S2 有效就推进。
同时 S2 override 的定义要求 S2 有效。编译父连接
[Bpu.sv](../rtl/bpu/Bpu.sv:5034) 直接把 `s2_valid` 传给 MicroRAS 的 S2 fire。
因此 [MicroRas.sv:133](../rtl/bpu/MicroRas.sv:133) 要求的
`override && !fire && CALL` 与当前父连接矛盾。

本轮校验了完整 override 的顶层 AND、该实例的两条实际连线、子模块守卫、
负对照以及全部覆盖这些 DA 键的原生生产者。原生工具把这个源 IF 标作 ELSIF，
审查匹配实际 `arm/span`，没有因为源码写着 IF 就放宽校验。单独 MicroRAS
允许独立 stage 控制时，停顿 CALL 修正仍是有意义的单元要求；不能把那个
输入空间不加说明地移植到集成 BPU。

## 真正要补的要求与证据

### MainBTB 集成替换：待实现的明确合同，不是新 PASS

源头见 [MainBtbReplacer.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbReplacer.scala:54)。
这 21 个零计数自身主要是物理副本；从源码职责继续审查，集成层尚缺专门合同：

- 事件：带真实原始 metadata 的正常反馈改变 MainBTB 近期使用关系，紧随其后
  又有需要选择受害者的同替换索引请求。
- 所有权：以 MainBTB 策略索引及驻留分支身份为准，不能混用 AheadBTB PLRU，
  也不能把不同 SRAM set 自动视作不同替换状态。
- 效果：较新的合法 touch 必须影响后续 victim，不能读取旧年龄；不同替换
  索引不被污染。not-taken/仅查询的具体资格以 MainBTB 策略为准。
- 观察：独立 LRU 从原始事件计算受害者，用实际新分配及所有幸存分支的 fresh
  查询证明，而不是只检查 `stateBank` 被写。
- 最小区分场景：同策略索引相邻反馈、不同索引对照、共享策略索引的 SRAM
  别名、not-taken/仅查询对照；不需要遍历所有索引。
- 当前证据：MBTB-024 有单元级共享年龄/隔离检查，但不能自动当作集成来源、
  相邻反馈旁路和最终消费者的证明。现有 INT 场景是否已部分检查，需逐项追踪。

该合同先作为明确待办，不凭行数新增已执行功能 ID，也不声称 21 行都由缺少
这个场景引起。

### 其他优先事项

1. UTAGE usefulness：先核对真实资格、逻辑身份、边界前态和正确效果；将物理
   地址矩阵与事件覆盖分开。保留现有普通失败，不以覆盖率目标修改参考模型。
2. Main/TAGE 待写版本：现有 INT-093/095、086/087/088/091 等合同分别检查了
   特定行为，但不能自动关闭所有跨 owner 与命中/缺失组合。追踪每个未决
   分支的原始来源、预期版本、真实服务及脱离旁路后的消费者。
3. 继续逐 UT 审查其余 304 点。物理边界、同义配方和真正新增事件分别登记，
   保留旧 ID 和历史判定的映射，不把登记数量当作独立语义要求的总量。

## 复核与证据边界

```sh
python -B -m tools.review_semantic_gaps \
  --baseline results/production-feature-domains-20261016-v2 \
  --output results/新的审查目录/gap-map.json
```

源码对应关系、定义恢复来源和父连接负对照等 57 项针对性测试通过，并经
`xreactor run` 4 进程入口复验全通过；该纯框架检查没有产生 DUT 测量。没有运行
新的 DUT 测量，没有改刺激、计数分母、参考模型算法或普通失败处理；行/功能
覆盖率和功能点通过率均不因这次整理上涨。最后完整测量的 17 个 FAIL 硬件点
及 2 个 XFAIL 硬件点仍保留。

[逐点定义审查](../results/semantic-event-review-20261016-v3/definitions/README.md)
明确列出 27 项合同的证据缺项。文件路径存在仅证明可追踪，不证明模型独立或
场景完备；本轮新增合同中尚无 reached/checked 关联的地方仍如实为空。
