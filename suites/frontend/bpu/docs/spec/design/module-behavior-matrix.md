# BPU 模块行为目录与场景设计入口（public-a0c2a26cb / DefaultConfig）

**行为类是验证的主轴**：先确定每个模块在合法前提下的责任，再把该行为拆成输入/历史等价类、
正确输出与**不允许出现的副作用**、实际接受与完成、边界和冲突。`BPU-XXX-NNN` 是
既有功能点文档和合同中的追溯标识，不能因同一编号下某条用例 PASS 而认为该类所有
组合都 checked。原始完整回归及本轮选择性运行属于**不同冻结源码和选择范围**；下表
的“待补交叉”是验证缺口/需要证据，不是新确认的 RTL 缺陷。

## 文档职责和阅读顺序

验证设计按 **模块责任 → 行为合同 → 场景等价类 → 检查义务 → 同轮证据** 推进，
不是先数测试、再把已存在的 ID 分组。各份资料只回答自己的问题：

| 层 | 权威入口 | 回答的问题 / 不得代替的结论 |
|---|---|---|
| 模块行为目录 | 本文的稳定 `behavior_id` 与合同入口 | 模块应该做哪些事；现有 ID 关联是反查，不证明应有行为没有遗漏 |
| 具体场景 | [覆盖设计](../verification/coverage/behavior-coverage-design.json)及[Scala审查](scala-interactions-20261106.md) | 33族78条代表分区、十模块八维入口与11个必须另建联合前态的交互；是待映射设计，不是全组合闭环 |
| 场景证据关联 | [场景记录](../verification/functional/behavior-scenarios.json)，仍保留 MainBTB 的3条示范 | 只引用真正审计过的原件/用例/运行；新设计未映射部分不自动获得旧PASS |
| 功能点与实现 | [验证规格](../verification/README.md)、[功能点辅助索引](../verification/functional/feature-classification.md)、相应 DUT 合同/模型/checker | 沿用原 ID、合同与实现关联，未证明范围维护在所属规格；`functional/pipeline/stress` 是标签，不是需求全集 |
| 执行矩阵 | `../coverage/io_matrix.py` 和实际用例 | 当前已落地的有限类别×结果域、nodeid 及到达/比较路径；不覆盖全部行为目录 |
| 冻结证据 | 原运行的 `run.json`、逐nodeid日志、覆盖产物与审计，见[交付记录](../verification/coverage/io-matrix-extension-20261103.md) | 该源码/基线/seed/选择中到底执行了什么；不覆盖其它选择或新源码 |
| 统计索引 | [功能点清单归类](../verification/functional/feature-classification.md) | 找 DUT、层级、旧结果入口；计数不充当功能验收 |

不在这些文档之间重复维护一份“最新全绿率”；历史报告保持原日期、基线与选择。
新增行为可以暂时没有旧功能 ID/用例，先留候选项和缺口，不为通过清单自检删掉需求。
工程根的旧计划已删除；下文 2026-11-06 检查点对旧计划的提及保留历史含义，当前开放
范围见[验证规格的完成条件与开放项](../verification/README.md#4-完成条件与开放项)。

## 当前目录的依据与审查状态

下方行为族先从现有合同/功能计划归纳，现已完成[固定Scala的逐族源码对照](scala-interactions-20261106.md)，
但**源码对照不等于独立规格确认**。覆盖设计把实现观察、既有模块合同性质、待确认预期
分开，保留动态启停及SC无效历史票两条无旧ID候选需求。仍必须从真实producer/独立
需求推出行为，再反查ID/端口/状态转移；机器门禁只检查这种分解的可追溯一致性，
不证明应有行为穷尽。

| 模块 | 当前稳定规格（可直接阅读的当前条款） | 合同/历史审查入口（不是当前版本全部已确认的声明） |
|---|---|---|
| Bpu | [bpu.md](bpu.md) | [当前流水合同](../verification/contracts/pipeline-transaction-contract.md)、[PHR合同](../verification/contracts/phr-transaction-contract.md)、[历史组合审查](../verification/evidence/reviews/bpu-integrated-functional-definition-review-20261016.md) |
| MainBTB | [mbtb.md](mbtb.md) | [当前事务合同](../verification/contracts/mbtb-transaction-contract.md)、[旧版合同原文](../verification/evidence/reviews/mbtb-transaction-contract-893e1580b.md)、[历史行为审查](../verification/evidence/reviews/main-btb-functional-definition-review-20261016.md) |
| Ras | [ras.md](ras.md) | [历史行为合同](../verification/evidence/reviews/ras-functional-definition-review-20261016.md)、[退休动作合同](../verification/contracts/ras-original-commit-action-contract.json)、[guard增补](../verification/evidence/runs/baseline-update-a0c2a26cb.md) |
| MicroBTB | [ubtb.md](ubtb.md) | [MicroBTB历史审查](../verification/evidence/reviews/micro-btb-functional-definition-review-20261016.md) |
| AheadBTB | [abtb.md](abtb.md) | [Ahead历史审查](../verification/evidence/reviews/ahead-btb-functional-definition-review-20261016.md) |
| MicroTAGE | [utage.md](utage.md) | [MicroTAGE历史审查](../verification/evidence/reviews/utage-functional-definition-review-20261016.md) |
| TAGE | [tage.md](tage.md) | [TAGE历史审查](../verification/evidence/reviews/tage-functional-definition-review-20261016.md) |
| SC | [sc.md](sc.md) | [SC历史审查](../verification/evidence/reviews/sc-functional-definition-review-20261016.md) |
| ITTAGE | [ittage.md](ittage.md) | [ITTAGE历史审查](../verification/evidence/reviews/ittage-functional-definition-review-20261016.md) |
| MicroRAS | [uras.md](uras.md) | [历史行为审查](../verification/evidence/reviews/micro-ras-functional-definition-review-20261016.md) |

各模块规格把当前可追溯条款与 `[待设计确认]` 分区分开；历史审查和旧版合同只保留
各自日期、基线与源码边界。旧 MinimalConfig/旧基线的尺寸、布局和行为结论不得直接
晋升为 DefaultConfig 合同。真实 producer 的完整可达性、接口合法性与叶子端口压力
分别记账。

## 统一提问方式

对每个下面的行为类，逐项写下：

1. **谁能产生输入**：条件分支、JAL、JALR、None 假命中、FTQ redirect/commit，或模块
   端口压力；合法编码、PC 单位、原 UID/epoch、分支位置和已执行前缀必须明确。
2. **需要什么原状态**：冷态/已学，原预测暴露/隐藏、仍驻留/已淘汰、计数强弱、资源
   空/满、原 metadata 与新状态分离。改变历史若会改变结果，就不是同一等价类。
3. **结果是什么**：有效位、方向、完整 target、属性、来源与当前容量；同时列出未执行
   分支/邻居/年轻已取消请求**不得改变**的字段。只有合法刺激而没有负输出对照，不算闭环。
4. **何时结清**：实际 fire/接受 UID、对应阶段响应或状态服务、fresh 消费者、有界 drain；
   背压、连续接纳、同拍优先级、reset/disable/取消、回绕分别标已检查或 gap。
5. **按本模块结果域判定**：预测器通常是 miss/hit、正确/纠正、拒绝/取消、替换/维护，
   并非总线 error/refill/翻译结果；后者移交 IFU/ICache/MMU，不能造一个常量零假响应。

每行是**行为族，不是一个可以整体标 PASS 的测试场景**；第一列代码为稳定标识，
中文名称可修订。范围号是关联 ID，不意味着范围内各点的前态/时序相同。
每行给的是**要求和关联功能点**，并不把未列的 ID 静默归为“其他”；按 ID 的唯一
责任 DUT/既有层级见[功能点清单归类](../verification/functional/feature-classification.md)。新增9×5有状态、nodeid
及自检的有限矩阵见[本轮 IO 矩阵](../verification/coverage/io-matrix-extension-20261103.md)；其余行目前只是
**需求分类，不是已经有全量机器可读场景到达/检查报告**。
`testbenches/bpu/tests/framework/test_module_behavior_taxonomy.py` 从下面的 ID 列解析各行为族，
拒绝漏DUT/行为/旧ID，并校验逐族Scala范围/锚点、设计分区、模块八维入口、关键交互、
候选缺口和证据状态；它仅防清单腐烂，不判断语义分区真的充分或ID归属正确，
**不提供硬件信用**。不安装Scala的可移植测试仍查资料结构，现场审计另核完整commit及文件哈希。

## MainBTB：多分支记录与第五槽（34点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `MBTB.lookup` 窗口查询与目标重建；001–003、007–009、012–013、018 | 冷/暖、两 align、起点跳过旧分支、跨页、低偏移同区/跨区；一次窗口多条 CFI | 完整有效位、顺序、位置、类型、方向和目标归原查询；过滤不删除后续居民，重叠响应不互换 | 起点×跨页×非首分支须以真实消费者核对；只按 bank/位置扫点不自动增语义 |
| `MBTB.learn` 条件方向与纠正；004–005、014–016、027–028、032–033 | taken/NT、原 conditional/indirect、明确类型纠正、None 假命中；原 rawHit/position 与顺序 NT target | 合格条件方向更新；NT 不创建、不改型或污染旧 target；None 可失效，邻居保持；foreign tag/未执行分支不能借资格学习 | `MBTB-033` 冷/暖/改型/None × align/位置/目标域已做 48 原生实例、40 去重语义类；容量满且同拍读/重置仍 gap |
| `MBTB.residency` Main/VBTB 暴露、驻留与替换；006、017、019、023–026、029–031、034 | 原第五槽已暴露/被前序分支遮住；反馈前 victim 仍在或经正常压力已淘汰；重复同位置/零 tag | 当前仍驻留的原暴露项就地改；隐藏或已淘汰按原身份分配 Main；清理旧副本、保持幸存者及原 UID，不从 fresh lookup 改写旧 metadata | `MBTB-034` 已验证两 align × 驻留/淘汰 4 原生实例；同拍 victim 替换×迟到反馈及零键清理旧普通 FAIL 不继承本次 PASS |
| `MBTB.service` 在途写服务与寿命；010–011、020–022、025–026、030 | enable/disable、读阻挡、多个不同分支补丁、同项较新完整版本、相邻反馈 | 接受的不同 owner 都结清；同一逻辑记录以最新完整版本服务；禁用不新学，恢复保留原已学；不丢其他未完成版本 | 持续读×满待写/取消/reset、同拍不同 owner 服务须独立断言；旧 6 个本 DUT 功能点在原完整回归 FAIL |

**一个行为类如何拆成真场景**（`BPU-MBTB-033`，仅本轮有限输入）：

| 原预测状态 → 执行结果 | 期望输出和不可改变的内容 | 本轮选定真实 DUT 证据 | 未闭合的交叉 |
|---|---|---|---|
| 冷表 → conditional NT | 不分配 taken payload；邻居不变 | 两 align × 首尾位置，12 参数仅 4 个去重类；逐类 checked | 满待写、同拍 reset |
| 已学 conditional → conditional NT | 方向 2→1，原目标/类型不动 | 12 实例 checked | 同拍读、disable/恢复 |
| 已学 indirect → 明确纠正为 conditional NT | **原 indirect 类型/目标保持，原身份方向 2→1**；不是把顺序 PC 写进 target | 12 实例 checked；旧“仅原 conditional 可学方向”规则被成对控制拒绝 | 完整 IFU/FTQ 产生该类型纠正的指令历史未证明 |
| 已学 indirect → None/NT 假命中 | 原假分支失效，不误删已学邻居 | 12 实例 checked | 与 victim 迁移/在途补丁的同拍组合 |

上述“checked”只表示同冻结源码的选定实例真的比较并完成；冷表三个 region 参数没有
旧 target，不能重复记三类。此例说明分类目标是**输入历史决定不同后果**，不是把
`MBTB-033` 改名成“学习”后便认为所有学习场景已通过。

## Ras：主调用栈（18点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `RAS.stack` 调用/返回与重复地址；001–005、017 | CALL/RETURN/return-and-call、空栈/多层、同返回地址连续调用、指令长度 | 按年龄/LIFO 消费，返回地址完整，重复组代表每一次逻辑调用；空栈不伪造有效地址 | CALL/RETURN 同拍与等待、压缩边界、错误年轻分支取消需分别比较 |
| `RAS.recovery` 检查点与 guarded 恢复；007、009、015、018 | 原 checkpoint、错误年轻路径、cfiPc 的 guard/sign 相同或不同、地址回绕 | 回滚年轻版本并重做原操作，字节 guarded PC +2（51 位回绕）返回；原 metadata 不变 | `RAS-018` 新增5例恢复→年轻 push→pop；端口非规范 guard 不等于完整 FTQ 可达性 |
| `RAS.retire` 提交/容量/禁止使用；006、008、010–014、016 | speculative/committed 分离、满版本、重复组上界、遗漏退休通知、disable | 只提交原调用一次，合法拒绝不冒充已接受；有界存储周转后保留原存活链；禁用不清空原栈 | 守护恢复 × 满栈/真实 commit/同拍退休仍 gap；旧 3 个本 DUT 功能点在原完整回归 FAIL |

## Bpu 顶层：选择、历史和生产者交接（114点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `BPU.select` 流水预测选择；001–004、006–019、032、075–079、101、109 | 冷/暖、早级候选冲突、S2/S3 修正、predictor 单独禁用、真实 ready 背压 | 各阶段选择按原请求及优先级，完整目标/类型/位置和原 metadata 配对；禁用候选不占优，旧被持有请求不被新窗口冒名 | DefaultConfig 已裁公开 target/perfMeta 的完整对外比较是阻塞残余；叶模块 PASS 不能代替顶层组合 |
| `BPU.learn` 实际反馈与跨预测器学习；020–031、039–051、055–062、066–074、083–093、106–107 | 稀疏多分支、taken/NT/None、原 provider/alternate/SC 使用资格、历史和提交年龄、读写冲突 | 各模块从**同一原 S3/FTQ 来源**学自己的方向/目标/useful；不合格或未执行后缀不训练，其他历史和居民不串用 | `INT-041` 旧 PHR 形状首先阻断 provider-role 后续验证；不能以同轮其他 PASS 掩盖 91 FAIL/4 ERROR |
| `BPU.history` 历史与恢复/返回；005、008、033–038、043、052–054、063–065、068–069、080–081、094、096、099、105、112–114 | 条件已执行前缀、循环迭代、guarded PC 与 sign、原 checkpoint 和年轻投机、CALL/RETURN | taken 更新正确前缀，NT 恢复不附加未执行后缀；guard 不取代虚拟地址；新请求获新 UID，年轻被取消路径无副作用 | `INT-114` 的 guard/sign×方向×空/非零历史 16 实例有 reached/checked；其他预测器全禁用，不证明活跃学习或完整 FTQ 寿命 |
| `BPU.arbitrate` 版本/容量与同拍仲裁；003、009–010、026–031、045–051、057、063–067、073–074、082–092、095、097–104、108、110–112 | 读写/反馈并发、满队列/替换、相邻修正、同拍 redirect+训练、缓冲版本迁移 | 保留全部有资格的原交易、唯一 owner 与服务；冲刷取消较年轻版本，不篡改其他存活来源，最终有界 drain | `INT-059` 等对齐/位置旧观察绑定先失败，不能向后续阶段补 checked 信用；S2/S3 高风险竞争需另核 |

上面 Bpu 行按**语义切面可重叠**，不像责任 DUT 那样互斥；例如 `INT-043` 同时是
反馈资格与历史前缀要求。原完整 113 点为 18 PASS / 91 FAIL / 4 ERROR；本轮
新增 `INT-114` 在选定子集 PASS，并未形成新版 114 点完整状态。

## MicroBTB：早级小表与可靠性（17点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `UBTB.lookup` 冷命中、taken 建立与完整 payload；001–004、013、016 | 冷/暖、不同分支类型、稀疏 resolve、同PC 不同原件 | 冷态 miss；合格 taken 建立完整 target/type/位置，冷 NT 不制造 taken，响应与原请求配对 | 本层早级预测不是最终 FTQ 目标；新旧来源不能以相同 PC 自动合并 |
| `UBTB.confidence` 可靠性削弱与恢复；005、009–012 | 原命中遇 NT、连续耗尽、紧邻新 taken、精确 taken 强化及 t0/t1 旁路 | 可靠性饱和保持而非绕回；耗尽变 miss，新 taken 按新身份建记录，旧失效版本不压住新学习 | 相邻训练×查询碰撞及连续更新要比较最后实际存活版本 |
| `UBTB.lifecycle` 容量、启停与竞争；006–008、014–015、017 | 冲突替换、tag/目标边界、disable、同拍 resolve/fastTrain | 只淘汰合法 victim；禁用不使用也不新学但保留已学；有资格 resolve 按优先级生效 | 旧完整 17 点均 PASS **不等于** reset×冲突×未完成查询每个交叉都已检查 |

## AheadBTB：超前窗口与方向归属（54点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `ABTB.lookup` 历史索引预测与纠正；001–009、012、016–018、022–025、032–033、054 | 取指 PC+历史、同 PC 不同上下文、相邻索引/回绕、S2/S3 保存的原窗口 | 冷 miss、目标/位置/强弱由原快照而非最新请求决定；跨局部地址域不虚构完整目标 | 早级 Ahead 和 MicroTAGE 共享上层选择，不把本层 target 命中当 S3 最终输出 |
| `ABTB.learn` 条件方向/类型与学习资格；010–014、036–042、047、049 | 前后序条件、taken/NT、同份多位置、条件与间接混合、不同历史窗口 | 只对合格原分支增减方向；较晚 taken 惩罚前序但不误伤后序；间接目标纠正不串入条件方向 | 不合格 NT、原类型改变、位置/历史组合要有区分性的合法对照 |
| `ABTB.residency` 容量/复制清理与受害者；005、015、019–021、026–030、034–035、043–046、048、050–053 | 高索引/进位、重复副本、四路周转、读阻挡/缓冲训练、同替换状态读写竞争 | 清理重复但不损失已发布预测；只动应淘汰居民，饱和与奖励各按合法身份；读优先待写最终服务 | 旧完整有 1 个 ABTB 功能点 FAIL；增加压力样本不能自动豁免旧重复身份/计数反例 |
| `ABTB.lifecycle` 生命周期；001、017、031、054 | reset、enable/disable、redirect 正在途的查询窗口 | 撤销新发布资格、已学居民保持/按 reset 清空；原窗口未到期前不套用年轻快照 | 新旧 epoch、连续 redirect 与反馈同拍由顶层 Bpu 另检查 |

## MicroTAGE：早级条件方向与保护（28点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `UTAGE.select` provider/tag/历史选择；001–002、005–010、013–014、018–019、023–025 | 冷/暖、短/长历史、原读索引与 tag 祖先、同低位不同高位、未执行条件与非条件 | 未学习不纠正；只用原资格的 tag/历史输出，别的分支不占用 provider；无合法条件结果不学方向 | 旧完整 28 点中 12 FAIL；相同低位≠完整 tag 来源，父级不能仅从叶 PASS 推回合法原件 |
| `UTAGE.learn` 方向/有用性与维护；003–004、011、017、020–021、028 | taken/NT、计数上下界、弱/强、初始保护、长期分配失败/整表老化 | 计数/有用性按真实合格结果升降、两端保持、反向可恢复；老化不删除方向 | 原错误 provider、弱来源错用及饱和交叉需区分性 mutant/独立答案 |
| `UTAGE.service` 在途服务与生命周期；006、008–009、012、015–016、022、026–027 | 保存的中/晚级快照、相邻反馈、缓冲强制写回、同 bank 查询、enable/redirect | 版本、原 owner 与新消费者一一对应，禁止年轻覆盖旧来源；禁用/取消只作用合同允许的寿命 | 有界背压×reset/取消×完整 SRAM 服务未逐类闭合；新 guard 高位不由 UTAGE 原件自证 |

## TAGE：长历史 provider、alternate 与保护（36点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `TAGE.select` 匹配与 provider/alternate 选择；001、005、007–008、011–013、019、029–030、036 | 无 provider/弱/强、最长/次长、基础预测强弱、向量非首位、不同历史/位置 | 合格 provider/alternate 参与正确选择，未命中不造历史；原请求的输出不跟随最新 PC | 选择结果和实际反馈资格分别检查；本层正确不证明上层 S3 选择正确 |
| `TAGE.learn` 方向、保护、维护与分配；002–004、006、009–010、014、017–018、020–021、032 | 条件 taken/NT、长表候选可/不可分配、合格弱来源、共享选择器同向/相反意见 | 方向升降边界不回绕；只有合格目标申请分配，失败维护释放保护但不损坏身份；同拍意见先净聚合 | `TAGE-032` 的原资格门禁有 PASS，但不替代其它来源资格或跨模块证明 |
| `TAGE.service` 独立/陈旧版本服务；015–016、022–028、031、033–035 | disable、非条件、连续相邻反馈、迁移后陈旧原端口、混合稀疏反馈、同拍分配 | 原逻辑 key 和当前 owner 决定服务，各分支方向/保护独立；禁用不新学；不串写邻居或退回旧计数 | `TAGE-026` 原迁移后旧 provider-way 的 XFAIL 保留；其它 35 点 PASS 不能关闭该义务 |

## SC：统计纠偏、资格与阈值（23点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `SC.select` 使用资格与纠偏决策；001–004、007–012 | 原 Main 命中、原 TAGE/provider 和历史有效性、条件/非条件、阈值内外、enable | 仅合格条件来源的权重越过阈值才纠正方向；无 Main/无 provider/非条件不得借强统计票给预测 | 顶层 `INT-041` 的旧 PHR 形状会先阻断 provider-role 验收；SC 叶子通过不能替代顶层归属 |
| `SC.weights` 权重/偏置和投票聚合；005–006、013–016、019–020 | 同拍两个合格分支、同向/相反票、不同 selector/way、弱/强及边界 | 按合格净票、正确特征和共享对象更新；饱和与邻居隔离，不吞第二分支或重置未选特征 | 需要把意见“已输入”与实际接受、下拍权重提交及新消费者区分 |
| `SC.threshold` 阈值更新与在途快照；017–018、021–023 | 连续反馈/交错历史、原快照资格、更新跨上下限、读写竞争 | 整步更新或整步拒绝；新旧权重及原来源配对，不把失败投票当干净提交 | 旧完整 SC 仍有 1 FAIL；顶层 SC 资格/历史错形不能借其它点 PASS 消去 |

## ITTAGE：间接目标与区域目录（20点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `ITTAGE.select` 间接来源/资格与目标选择；001–005、007、009–014、019–020 | 冷/已学、原已发布/未发布快照、taken 间接/返回或其它类型、不同 PC/历史、置信0/正 | 冷态不伪造 target；仅真实 taken 非返回原件能学；失信回退到合格次长，置信0 的原件纠正完整目标；未发布原件不能训练 | `ITTAGE-020` 的未发布资格保持旧 FAIL；软件构造合法形状不等于原件真实发布 |
| `ITTAGE.region` 区域压缩与目录替换；008、014–015、017–018 | PC 区域/外部区域、同低偏移不同高位、目录有空位/满、已有区域再用及指针受害 | 复用已有区域优先于新分配；满表只重解读受害指针，其他 target/居民不变；字节地址往返无损 | 旧 3 个本 DUT FAIL 仍在；区域目录 PASS 不能关闭置信0跨区改目标的普通反例 |
| `ITTAGE.service` 并发/启停；004、006、010–013、016、020 | 重叠查询、稀疏位置、enable 改变、读阻挡、迟到原件 | 响应、补丁按原 PC/历史/发布资格配对；禁用不新学，fresh 原件与无资格旧原件不可互换 | 并发×未发布原件×目录满尚须真实生产者与收尾对照 |

## MicroRAS：早级返回转发与年龄仲裁（17点）

| 行为类 / 代表 ID | 合法输入与必须区分的历史 | 预期输出与禁止副作用 | 高风险交叉 / 证据边界 |
|---|---|---|---|
| `URAS.stack` 返回来源和栈效果；001–002、007–008、010–014、016 | 已知/未知主 RAS top、S1 CALL/RETURN/return-and-call、等待中的老 CALL 与年轻 RETURN | 有已知可用来源才给返回目标；早级旁路按年龄 push/pop，未知深度不伪造有效 top；转发到期后退回正确老来源 | MicroRAS 的旁路 top 是模块输入，不是完整自主主栈或 FTQ 回归 |
| `URAS.recovery` 恢复优先级与取消；003–006、009、011–015 | S2/S3 纠正、redirect 与年轻操作同拍或连续、neutral 操作、未知来源 | 较老权威操作保留，年轻被取消效果不复活；主来源恢复前保持不可信，不因中性修正吞掉老 CALL | 旧 17 点中 2 FAIL；“两操作同时入端口”需实际推进后的存活对照 |
| `URAS.enable` 启停与所有权；006、008、015、017 | RAS enable 由开到关、老返回待决、主栈接管 | 禁用时 MicroRAS 不提供可用目标，恢复后只有合法存活来源继续；不把旧目标当新预测 | `URAS-017` 的关闭资格普通 FAIL 保留；旧消费者未清与 enable 后的新身份要分开 |

## 分类怎样变成验收

上述行为族是一份**需求分解**，不是 10 个 DUT × 全部交叉自动获得功能通过的报表。
逐族落成可机读的“行为类别 × 可用结果域”行：每格给合法前态/实例、原始
nodeid、实际 reached、实际 checked 的输出/禁止副作用和完成事件；没有证据就标
`gap` 并给下一实验，出域写承接层。功能点与行为类是多对多：一个 `PASS` 只证明
它实际检查到的那些格，**不能推定同一模块其它历史、结果域或交叉**。

### 场景记录的最小内容

`behavior-coverage-design.json` 保存**全模块有界设计**，不增加运行器或另一套PASS统计。
每个行为族有源码范围/锚点、独立合同、分区理由、准入、观察和完成义务；每条case有
原前态、事件、结果域、预期/待确认、禁止副作用、合法/错误规则对照及下一实验。
`module_axes` 给每个DUT八个维度的具体case入口，**不是八维笛卡尔积穷尽**；11个
`interactions` 必须另外构造联合前态，不能把各单case的旧结果相加当交叉通过。
所有新case继承明确的 `unmapped/none`，表示尚未审计完整设计到用例/控制/同轮结果的
一一绑定，**不是声称仓库没有相关测试**；两个无旧ID的候选需求仍为gap。

`behavior-scenarios.json` 专管**场景实现与证据关联**，目前保留 `MBTB.learn` 的一个
已执行串行样本及两个未实现交叉，并引用全模块设计。以下字段用于真正接通后的记录，
不把78条设计强行填成已实现或引用原PASS。

| 字段组 | 必填内容 |
|---|---|
| 标识与依据 | `scenario_id`、主 `behavior_id`、交叉行为/关联点、固定基线、合同来源与审查状态 |
| 准入与前态 | 谁产生输入、单位/编码、原身份、用合法序列建立的状态；完整 producer 未证须单列 |
| 事件与独立预期 | 触发事件、oracle 来源、输出结果、禁止副作用；待核时不凭实际输出填答案 |
| 观察与完成 | 必比较字段/对象、原 UID/epoch、真实接纳、状态服务/新消费者及有界收尾；具体时序无依据时记缺口，不随意加固定等待 |
| 实现与控制 | 实际用例/比较器、合法控制、错误规则及注错层；未实现就不填虚构 nodeid |
| 证据与残余 | 引用冻结运行、源码、seed、nodeid、到达/比较产物；缺什么、影响、承接人与下一实验 |

三个状态**分别填写**，不得合并成一个绿色状态：

| 轴 | 例子 | 不能推出什么 |
|---|---|---|
| 设计依据 | `pending-review` / `module-contract` | 合同已列出不代表激励到达、整机可达或 RTL 正确 |
| 实现接通 | `not-implemented` / `implemented` / `blocked` | 有模型和 nodeid 不代表必需字段真正比较完 |
| 执行证据 | `none` / `historical-selected`（引用实际运行，不另填静态 PASS） | 某次有限选择通过不覆盖别的场景或当前新源码 |

现有运行结果 PASS/FAIL/ERROR/XFAIL/SKIP 保持原义。场景收敛必须逐项核实合同、合法
前态、接受、reached、checked、禁止副作用、负对照与完成；第一处失败挡住后续比较时
后续义务不获得信用。新记录的 evidence 引用不接入生产报告聚合，仍以原 Toffee/ucv
报告和既有功能矩阵为执行事实；完整账本接入是后续必需工作，不在本次假称完成。

### 后续按什么顺序工作

| 顺序 | 具体产出 | 退出该步的条件 |
|---|---|---|
| 1. 独立确认待核合同 | 本轮33族源码对照已落盘；继续确认动态enable、FastTrain多错误、同拍线性化和SC无效历史占位票等 | 不是源码如此即为正确；未确认与出域各有承接，不靠ID总数通过 |
| 2. 将设计映射到实现/证据 | 从78条有界设计和11个交互逐格审计现有用例/缺项，优先MainBTB新规则 | 每格有真实接纳、必需比较、控制与完成，缺的新增用例；不能按测试名或旧PASS自动映射 |
| 3. 清除观察阻挡 | `INT-041` 旧 PHR 形状、`INT-059` 旧观察绑定；保存原失败 | 目标行为真的到达且后续比较执行，不能仅按 FAIL 数下降验收 |
| 4. 补有区分性的真实 DUT 场景 | MainBTB NT×读/复位/满容量、VBTB迟到×替换、活跃预测器guard×恢复竞争 | 同版本正负对照、真实接受/新消费者/排空和原件所有权检查齐备 |
| 5. 审计再选回归 | 新目录、同源选择、适用seed及同轮语义覆盖，按影响决定是否完整回归 | 场景证据与源码/RTL/工具对齐，历史非 PASS/新缺口分别报告 |

这不是恢复或重开旧已完成目标。`verification_plan.json` 的三个旧阻塞残余和
[先前矩阵的21个gap](../verification/coverage/io-matrix-extension-20261103.md)均不因本次整理关闭。
2026-11-06本轮仅改文档及其自检，未增加真实DUT场景或做新源码十DUT完整回归；
先前源码 `f22dc87a…` 的两轮 v4 仍仅是原选择的历史证据。
