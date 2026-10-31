# Kunminghu-v3 BPU 验证策略

2026-10-10 目录已调整为 `suites/frontend/bpu/<dut>/<role>/`，详见
[目录与职责](repository-layout.md)。旧源码的全量回归已按用户要求中止，
不作为通过结果；新目录的生产验收进展见[并行迁移记录](pytest-parallel-migration-20261009.md)。
下方 2026-10-08 的完整回归数字是历史基线，不是新目录的验收结果。

状态：**2026-10-08 复核：固定 Verilator 种子并从首拍复位后，最新完整回归执行 255/255 个计划功能点；1911 PASS、6 strict XFAIL、0 SKIP。** 已覆盖场景与缺陷分别列在下文及[功能点清单](functional-points.md)；MainBTB 同位置双命中清理由公开预测和 metadata 先观察双命中、再观察清理，不再仅凭 RTL 行点判断。覆盖率报告 v3 统计生成 RTL 的 `.v/.sv`，排除 picker `*Dut_top.v/.sv`；源码行覆盖使用 `v_line`、`v_branch` 及 `S` 行段的原生 LCOV 汇总，而不是计数器点数。本文下方出现的 2/2、5/5、6/6 等“小分母满覆盖”是当时 `.v`-only 覆盖点子口径，不是当前全 RTL 状态。

本文规定本仓库后续验证活动的范围、证据标准和目录结构。它解决当前测试数量少、
单个 testcase 承担过多功能点，以及 bundle/driver/monitor/scoreboard 契约没有被
独立证明的问题。具体功能点清单见
[functional-points.md](functional-points.md)。

## 1. 当前基线与缺口

迁移前的 2026-09-18 基线为：

- BPU 仓库：15 个 pytest item，14 PASS，1 个 strict XFAIL；
- verification plan：11 个功能点；
- xreactor：128 个测试全部执行并通过，native xspcomm backend 不再 skip；
- BPU 用例已经不包含显式边沿等待、裸信号写入或用户可见的 asyncio.gather()。

完成迁移后的 2026-09-18 历史回归为：

- BPU 仓库：141 PASS，2 个已登记 strict XFAIL，0 SKIP；
- verification plan：82/82 executed，80 PASS，2 XFAIL，0 NOT_RUN；
- 功能点 execution 100.00%，completion 97.56%；
- 测试目录没有显式边沿等待、裸 Set() 或 asyncio.gather()。

当前完整回归为 1911 PASS、6 strict XFAIL、0 SKIP；
功能点 255/255 executed、249 PASS、6 XFAIL、0 NOT_RUN，计划完成率
97.65%。统一覆盖报告包含十份本次原生 LCOV 和 148 个功能 covergroup，
功能组聚合口径为 99.48%；四个未闭合组分别是 `kunminghu_v3.bpu.abtb_wrap` 的 4/5 bin
（`later_full_target`，对应 `BPU-INT-018` 的高位修正缺陷），以及
`kunminghu_v3.ras.enable_integrity` 的 1/2 bin（`metadata_preserved` 未命中，
对应 `BPU-RAS-008` 的 enable 门控缺陷），以及
`kunminghu_v3.utage.shadow_persistence` 的 cross 272/384 bin
（112 个 SRAM 保持失败格不采样，组内平均为 95.14%，对应 `BPU-UTAGE-016`），以及
`kunminghu_v3.tage.way_migration_captured` 的 cross 104/120 bin
（16 个无关 tag useful 保持失败格不采样，组内平均为 97.33%，对应 `BPU-TAGE-026`）。
功能 bin 覆盖率与计划功能点通过率不可互相替代。DUT 工厂为每个 Verilator 实例
传入固定随机种子，并在首个时钟前置位 reset；这使随机初始化不再随测试顺序
改变覆盖率。`results/summary.json` 保留的是 141 PASS／82 点的历史迁移快照，
不是当前回归摘要；当前功能点以 `results/feature-points.json` 为准。
此前未固定种子的 AheadBTB 2050/2050 是 `v_line` 锚点去重数，不是原生
源码行覆盖。版本 3 的旧 5.026 固定种子基线为 AheadBTB **10784/15929** 源码行，
TAGE **5336/5653**、SC **2732/3068**、集成 BPU **25691/44731**；
各自的 `v_line` 点数仍单独保留，不能相互替代。
本次原样 RTL 逐笔对照确认旧优化插桩漏计／错拍，十个 DUT 已用 5.052
重建、隔离验证并完成正式回归；新基线为 AheadBTB **12734/17854**、
TAGE **4467/4587**、SC **3145/3481**、MainBTB **1056/1056**、集成 BPU **28290/46541**、
MicroTAGE **6297/11053**。新旧工具的映射分母不同，不能按百分比差声称
新增功能覆盖。TAGE 共同映射的 3743 行命中 3426→3471；88 个已证明的
局部矛盾赋值仍未命中；追加 24 个 key 复制赋值的精确守卫复核后，
当前剩余 120 行恰为 112 个赋值行和八个块头局部分类，保留原始分母；先前
70 个未分类行已由下述 TAGE-035 正式关闭。SC 保留 336 个局部
矛盾赋值；首次刷新揭示的三个 threshold 候选已由下述正式场景关闭。见
[coverage-phase-audit.md](coverage-phase-audit.md) 与正式刷新审计
`results/coverage-toolchain-refresh-audit.json`，记录首次工具链刷新。
随后 MicroBTB 原生缺口揭示未封装的 resolve 通道和遗漏的连续 useful 转发：
新增完整八 slot 的 UbtbBatchTraining、同拍双源提交、RAS 属性 monitor，
三项架构场景关闭 34 行，760/794→794/794，分支 180/192→187/192；
其他九个 DUT 的行／点／分支计数不变。BPU-UBTB-016/017 均 PASS，
三个负对照均由断言检出；该轮完整报告刷新审计见
`results/coverage-ubtb-resolve-refresh-audit.json`。整体目标尚未完成，
满行覆盖不代表五个剩余分支或所有功能组合均已验证。
随后 ITTAGE 的满表 tree-PLRU 两行缺口促成 BPU-ITTAGE-018：真实 allocation
复用改变 touch 历史后插入两个新 region，由独立 heap-order 模型在结果返回前
预测指针，流水线检查 victim 旧 offset 重新解码及其余 resident 状态保持。
容量损失属于设计契约，不要求 17 个 region 无损驻留。八个 cross bin 在断言后
闭合，16 项纯模型测试通过，三项参考负对照都抛出异步 ScoreboardMismatch。
原生行 1396/1398→1398/1398、分支 650/658→651/658，其他九个 DUT 指标不变。
该轮完整清单及 LCOV／JSON／HTML 一致性见
`results/coverage-ittage-region-refresh-audit.json`；七个剩余分支仍需审查。
MicroRAS 再补中性 S2/S3 override：取消年轻 call、选当前主 RAS 地址、
redirect 优先及阶段专属恢复均以完整结果断言；十个 cross bin 闭合，
三个 encoder 负对照被检出。原生行 89/91→91/91，分支 20/24→21/24，
其他九个 DUT 指标不变。该轮正式刷新审计见
`results/coverage-uras-neutral-refresh-audit.json`；三个 MicroRAS 分支仍待检查。
只收集 pytest items 不再覆盖正式功能点及原始数据清单；三项独立框架测试
与真实全仓 collect-only 逐字保持检查都通过，正常执行仍生成本次证据。
独立 SC threshold 诊断先证明上下界可达，见
`results/coverage-sc-threshold-readonly.json`；其原始数据未计正式 PASS。
随后 BPU-SC-021/022 用独立模型、agent 内只读 Bundle／Monitor 及直接
Scoreboard 比较完整向量。四-way 的上下界、资格、混合贡献、邻项保持、
相邻反馈，以及 642−4／5038+4 整笔拒绝而非钳到边界，均进入正式 pytest。
88 个新 cross bin 闭合，40 项纯模型及三项能力错误测试通过，三负对照
均为带事务／周期／差异／状态的普通 ScoreboardMismatch。
当前 SC 正式行 3145/3481、分支 875/1038，其余九 DUT 及六项 XFAIL 不变；
该轮完整时效、一致性及原局部证明守卫复核见
`results/coverage-sc-threshold-refresh-audit.json`。336 个剩余 SC 原生行与
局部矛盾赋值一致，保留分母；其他功能和分支组合仍需审查。
四项 TAGE 后部 resolve 槽位诊断先在临时合并中关闭两行并增加十三个分支，
见 `results/coverage-tage-late-resolve-readonly.json`；其原始数据未计正式覆盖。
随后 BPU-TAGE-027/028 正式交叉八槽 × 双向 × 四深度 × 五 provider 阶段，
以及八槽 × 七资格／邻项原因；376 个 cross bin 均在精确状态断言后闭合。
输入期待独立冻结、不调用 encoder，被动 Bundle／Monitor 比较实际 sparse
placement、base counter 和真实 metadata；输出由既有异步 Scoreboard 流水线
回读并检查接受／完成时间。21 项纯语义测试通过；漏 slot7、压缩槽位、错
metadata、错 provider 参考四负对照均为带事务／周期／差异／状态的普通失败。
该 sparse 阶段 TAGE 为 4331/4587、分支 1411/1598，关闭 20 原生行、增加 92 个分支，
`v_line` 仍为 95/132；其余九 DUT 指标、六项 XFAIL 及映射分母不变。
该阶段完整时效、一致性及局部证明复核见
`results/coverage-tage-sparse-refresh-audit.json`；505-item collect-only 的
四份正式报告逐字保持见 `results/coverage-tage-sparse-collection-protection.json`。
当时仍不以 alternate 算术行命中证明实际写回对象和值。四个顶层
alternate-table2 mux 行先由正常分配／只读诊断证明可达，临时 4331→4335，
该 probe raw 不计正式主表，见 `results/coverage-tage-alternate-slots-readonly.json`。
随后 BPU-TAGE-029/030 将其正式化：独立 table2/table3 配对模型在提交前冻结
精确 counter、useful、table/way 身份及 selector 预期；原有 prediction monitor
在同一输出事件采样公开 metadata 与只读内部 Bundle，不另建错拍关联任务。
双向 × 四预测槽 × 两 baseConf × 十四阶段，以及相反方向 resident／alternate
混合槽的正反顺序重叠提交，共 236 个 cross bin 在完整状态检查后闭合。
27 项纯模型／能力／清理测试通过；保持错误 alternate、交换 way、使用上一拍
内部状态、漏 slot7 四负对照均正常失败，清理不产生重复 teardown 或悬空任务异常。
完整回归使 TAGE 4331→4335/4587、分支 1411→1421/1598，顶层 3021/3021；
其他九 DUT、六项 XFAIL、RTL／编译器／处理器及分母不变。该阶段完整时效和
LCOV／JSON／HTML 一致性见 `results/coverage-tage-alternate-refresh-audit.json`；
534-item collect-only 的四份正式报告逐字保持见
`results/coverage-tage-alternate-collection-protection.json`。
模型仅覆盖准备好的四表 MiniConfig 配对，不冒充完整分配／历史／aging／陈旧
metadata 或 FTQ 程序参考。再对 WriteBuffer 独立 key 复制块逐项核对 priority、
clean 条件、目标 row 和源 port：八块 24 个 set/valid/tag 赋值同样局部矛盾，
四个仅内存源码负对照均被拒绝。累计 112 个赋值行分类，仍保留原始
当时的 252 个行缺口，不声称覆盖率提升；见 `results/coverage-tage-key-copy-unreachable.json`。
该阶段 WriteBuffer 140 个未分类行及其他预测器缺口仍需审查。
单次混合 hit/allocation 诊断又证明 `WriteBuffer.sv:885,886,887,890` 可达，
临时 4335→4339、分支增加两点；目标 counter 必须 1→0，不能用饱和保持
冒充双端口写入。新 tag 分配、旧 victim 消失、六邻项保持均检查，probe raw
仍不计正式主表，见 `results/coverage-tage-mixed-hit-miss-readonly.json`。
随后 BPU-TAGE-031/032 正式化四上下文 × 双最高表 way × counter 1/2 双写，
以及饱和、无 MainBTB 命中、无效槽和全局关闭的单写／零写门控矩阵。
输入参考与完整写端口预期均在提交前独立冻结，被动 Bundle/CycleMonitor
核对同一事件的全 bank/way/set/tag/counter/outcome 和四周期延迟；输出继续
通过既有 prediction Scoreboard 正反顺序重叠回读全部 resident。
准备只用正常反馈；每上下文／way 准备一次、后续正常恢复，避免重复 aging。
144 个 cross bin 断言后闭合；23 项纯模型／能力／清理测试及四个普通失败
负对照通过。完整回归 TAGE 4335→4341/4587、分支 1421→1424/1598、
v_line 95→96/132；关闭 WriteBuffer 867/868/885/886/887/890，其他九 DUT、
六项 XFAIL、工具来源和分母不变。该阶段时效、一致性和局部守卫复核见
`results/coverage-tage-mixed-writes-refresh-audit.json`，559-item 收集保护见
`results/coverage-tage-mixed-writes-collection-protection.json`。
该阶段剩余 246 行中 112 行局部分类、134 行未分类；矩阵不是完整
shadow 槽位／容量／FTQ 参考，整体目标仍未完成。
随后 BPU-TAGE-033 交叉四上下文、两 way、counter 1/2 与相邻／间隔反馈，
96 个 phase cross bin 断言后闭合。两笔真实 metadata 均在反馈前捕获：
相邻请求看到同一旧 counter，buffer 必须转发递减并在 0 饱和；cold mispredict
强制 SRAM 读，所以间隔请求必须使用当前 counter，再递减或省掉饱和写入。
输入／逐事件写 payload 与延迟／完整输出／恢复阶段原始六邻项均独立检查。
26 项纯检查通过；漏第二分配、错误串行化、错最终 counter、漏第二写观察
四负对照均普通失败，没有额外 teardown 或悬空任务异常。
完整回归 TAGE 4341→4344/4587、分支 1424→1426/1598、v_line 不变；
恰关闭 WriteBuffer 844/845/888，没有新增行缺口；其他九 DUT、六项 XFAIL、
工具来源和分母不变。该阶段完整时效、325 raw、138 功能 JSON、139 组覆盖、
十份 LCOV/JSON/HTML 一致性见 `results/coverage-tage-overlapped-saturation-refresh-audit.json`；
586-item 收集保护见 `results/coverage-tage-overlapped-saturation-collection-protection.json`。
该阶段剩余 243 行中 112 行局部分类、131 行未分类；原始分母不扣除。

追加分析将 counter 请求 way 与 retained owner/depth 分开。四 bank、双向
owner、四 depth、pending/clean 共 64 组独立诊断全部通过；临时原生行
4344→4397/4587，恰关闭 53 行，112 个局部分类行仍保留，候选未分类为
78 行。这份隔离诊断自身不改变正式基线，见 `results/coverage-tage-retained-owner-readonly.json`。
新只读 shadow monitor、独立单写/drain/counter 转发模型和读压力驱动封装
有 115 项纯检查及四个逐周期硬件代表场景；现有 TAGE 全目录隔离回归为
258 PASS、1 个原有 strict XFAIL、0 SKIP，原生指标/缺口集合无退化，见
`results/coverage-tage-retained-owner-existing-suite-readonly.json`。
已登记 BPU-TAGE-034（计划现有 254 点），正式测试隔离 64 组合已通过，
192 个 cross bin 只在完整检查后采样，累计 3360 个 shadow 周期；最新
117 项纯检查和八个有 transfer/时刻上下文的普通 FAIL 负对照通过。负对照
发现嵌套直接检查会丢失外层异步上下文，回调改为纯 compare，由外层统一
包装失败；两项纯回归保护该行为。见
`results/coverage-progress-tage-retained-owner.json`。全仓刷新已完成并审计：
1401 PASS、6 strict XFAIL、0 SKIP，254/254 功能点执行、248 PASS。TAGE 正式
4397/4587，关闭同样 53 行，其他九 DUT 指标及缺口集合、六项 XFAIL 不变。
333 raw、146 功能 JSON、147 组和十份 LCOV/JSON/HTML 同源/时效一致，
刷新后 1407-item 收集保护通过。见 `results/coverage-tage-retained-owner-refresh-audit.json`
及 `results/coverage-tage-retained-owner-collection-protection.json`。当前 190 个缺口中
120 行局部分类、70 行未分类，原始分母不扣除。
taken base 用于隔离 useful 更新，不代表原 useful
缺陷修复，也不证明完整 FTQ、下界饱和或 full-miss/PLRU overwrite。

进一步的独立诊断用同批真实 NT/T metadata、正常 way 替换和独立双写
预期验证交叉 retained owner：32 组合通过，临时候选 4397→4418 行；普通
owner 的六个深层代表场景通过，候选再到 4442 行。它们不是已完成正式
刷新的一部分，也不是全 FTQ 资格证明。额外八个局部矛盾块头仅分类，
不扣分母；候选 145 个缺口中还有 25 行需用 companion hit/miss、
dirty/clean 组合检验。逐行证据及未执行的构造建议见
`results/coverage-tage-dual-write-gap-review-readonly.json`。十个混合 companion 代表
场景随后关闭其中 22 行至候选 4464/4587；三行仍需 port0 已饱和 × companion
首次 miss 的额外准备，见 `results/coverage-tage-mixed-companion-representatives-readonly.json`。
下一步应将这些
双写语义封入独立 bounded reference，补齐负对照后再登记正式功能点，
不能直接合并诊断 raw。

扩展的 companion 四状态全 bank 矩阵随后完成：68 组合、2148 个 shadow
周期、416 项双写见证和正反完整 profile 全通过，精确关闭该 25 行候选至
4467/4587；剩余 120 行与局部矛盾分类集合逐项一致且保留原始分母，见
`results/coverage-tage-mixed-companion-full-readonly.json`。新 BPU-TAGE-035
登记四 bank × 四 depth × 八模式的同拍独立双写需求；单独 bounded reference
拒绝碰撞/full-row PLRU，509 项纯检查和八个硬件代表通过。384 个断言后
cross bin 的完整隔离 pytest 已通过：128 组合、5336 个 shadow 周期、832 项
双写见证及完整输入/正反 profile 经独立重放核对；该测试 raw 相对冻结基线
精确关闭 70 行且无新增缺口。十个普通 FAIL 负对照均已通过，完整全仓刷新及
独立审计随后完成：1911 PASS/6 strict XFAIL/0 SKIP，255 点执行、249 PASS。
其他九 DUT、源码/工具/分母与六项缺陷不变，LCOV/JSON/HTML 同源一致。见
`results/coverage-tage-dual-shadow-refresh-audit.json`；新版四报告的1917-item
收集保护见 `results/coverage-tage-dual-shadow-collection-protection.json`。

RAS 当前 65 个未命中行也已源守卫复核：16 个赋值仅分类，不扣分母；其余 49 行
聚成 indexed committed repeat/wrap、非 push 有效提交的 bos 回收和 redirect-call/
return/bypass 三类待验证需求。现有 restore 没有驱动公开 cfiPc 字段，而实际
恢复返回地址由该字段而非 speculative startPc/position 计算；先补驱动/monitor，
再由真实 metadata 和独立模型检查。源码、九项源条件负对照及逐行证据见
`results/coverage-ras-commit-gap-review-readonly.json`。不把复制行数当功能点数，
不登记尚未运行的新 RAS PASS/XFAIL。
条件头 515 的旧不可达分类已撤回：虽然 true-arm 的赋值 516 不可达，false-arm
原生 counter=63 仍映射到该条件行。这不是 DUT 缺陷，也不能删原始行分母。
八 SSP × 普通/饱和共 16 组正常驱动诊断随后通过，独立有界模型及不同结构
物理格重放器检查 1063 次操作、5715 项比较，临时候选恰关闭 34 行至 554/585。
剩余 31 行为 16 个分类赋值、15 行待验证。见 `results/coverage-ras-indexed-commit-readonly.json`。
该首轮投影诊断不直接计功能 PASS 或正式覆盖；真实容量淘汰显式纳入期望，
而非要求无限栈。随后隔离原型补齐八槽完整 committed 存储、公开输入及父级
提交流水的静态 Bundle/@on 被动观测。56 项纯检查及 16 组合真实 pytest 通过；
1063 次操作、5315 个周期、33353 项比较由另一个物理表重放器独立核对，
八项负对照产生有上下文的普通 FAIL，包括漏提交。见
`results/coverage-ras-committed-cells-prototype-readonly.json`。原型不修改当前
冻结运行源码、不登记正式功能点；原生增量审计必须等待完整正式刷新审计通过，
不能将运行中的 raw 当作旧基线，也不拿首轮投影诊断的增量代替它的证据。

提交场景须从实际 FTQ 资格推导：CommitQueue 过滤 action=None，旧的
`neutral_commit_bos_reclamation` 只是历史分组标签，不代表可构造任意空操作
提交。bos 四行需要 Pop/PopAndPush 的真实退休 metadata 与距离条件；当前
既未证明可达也未证明不可达。沿实际源码的八项条件变异对照见
`results/coverage-ras-commit-qualification-source-readonly.json`；action=3 经 FTQ
进入后不满足当前 RAS 父级 `== Push/Pop`，还需单独动态验证 coroutine 预测
行为，不能把 UBTB 属性回传覆盖或预测提示未处理直接当架构缺陷。

串行 helper 的每次排空也不是相邻 beat 证据。既有 `PulseDriver.send_many()`
已支持连续周期，复用它完成相邻 RAS 场景，无须用例自行调边沿或 gather。
27 组 nested/alternate/turnaround 与饱和重复的真实隔离 pytest，经过独立
展开调用栈重放（198 次操作、225 周期、1431 项比较）及八项普通 FAIL 负对照；
检查完整输入、每拍公开 top/SSP/SCTR 和八槽 committed 邻项保持，47 次相邻
push→pop 使原生 `RasStack.sv:801` 计数为 47。见
`results/coverage-ras-adjacent-bypass-prototype-readonly.json`。不声称完整 speculative
queue/recovery metadata 模型或系统 FTQ 资格；原型不进入当前冻结源码，
不登记正式功能点或直接增加正式行覆盖，原生增量门禁等待当前正式刷新完成。

redirect 场景的隔离 agent 已补 cfiPc 裁剪驱动，24 组 inflight/committed ×
SCTR=0/3/7 × 同地址调用/不同正地址调用/不同负地址调用/返回重做经真实 pytest
通过。先发真实 wrong-path call、再恢复此前 genuine checkpoint 并逐步退栈；
独立展开调用栈/物理 committed 表重放核对 524 次操作、1160 周期、1528 项
比较和 24 次恢复，检查完整输入、metadata 来源、正负 signGuard、commit 与
redirect 延迟及全部 committed 邻项保持。八项负对照均普通 FAIL，十个原缺失
redirect 行在临时 raw 中实际命中。见
`results/coverage-ras-redirect-redo-prototype-readonly.json`；未登记正式功能点、
未合并正式原生增量，不声称完整 queue recovery reference 或 FTQ 系统资格。

整合候选将批量与观测能力放在 agent，而不是让用例直接使用 driver 细节：
`RasOperation` 描述操作，`act_many()` 返回逐笔状态，`observe_committed()` 管理
被动观测作用域，`restore(cfi_pc=...)` 兼容原 API 并隐藏编码/恢复延迟。三类
矩阵共 67 组，167 项纯模型/能力/缺格检查和三项硬件 pytest 共 170 PASS；
功能覆盖 16/24 个多轴 cross 与 27 个单轴 coverpoint bin 在检查后闭合。
25 项新 API 负对照均普通 FAIL，包括批量返回数组错配；完整记录的 6700
周期、36339 项比较与独立重放一致，raw 命中 45 个原缺失源行。见
`results/coverage-ras-integration-candidate-readonly.json`。另对字节相同的旧 RAS
测试实测兼容性：15 PASS、1 原 strict XFAIL、0 SKIP，见
`results/coverage-ras-candidate-legacy-readonly.json`。首次单点 cross schema 错误
保留失败证据并按 coverpoint 修正重跑；不得将封装错误混称为 DUT 缺陷。
候选仍在临时目录，不改变当次运行源码或正式功能计划。TAGE-035 完整刷新
审计通过后，候选用16份新鲜正式 RAS raw 加三份实际正向 pytest raw 通过
原生增量门禁：精确关闭45行至565/585，无新缺口；剩余16个分类赋值及4个
待FTQ资格的bos行，保留分母。这仍不计正式覆盖，须继续仓库迁入、正式
注册及完整回归。

随后 BPU-MBTB-020 将 counter queue 零计数对应的真实排队需求正式化：
四物理 bank × 双目标 way × 双向更新 × 阻塞/直通 × 两索引上下文，共 64 组合。
公开输入与全 bank queue 的静态 Bundle/Monitor 比较独立冻结的真实 metadata、
两笔相邻反馈、set/way-mask/counter、占用和写回时序。24 笔哨兵预测及正反顺序
全 resident 回读通过既有异步 prediction Scoreboard；训练 pulse 源仍是同步的，
不发布 XTransfer，故输入/队列活动用核心 Scoreboard 直接比较，不另造匹配器。
192 个 phase cross bin 断言后闭合，51 项纯检查通过，四个负对照均为有上下文
的普通失败且没有额外清理错误。完整回归 MainBTB 840→851/1056、分支
317→332/442、v_line 仍 29/38，其他九 DUT、六项 XFAIL、源码/工具及分母保持。
326 raw、139 功能 JSON、140 组和十份 LCOV/JSON/HTML 的时效与一致性见
`results/coverage-mbtb-counter-pending-refresh-audit.json`；638-item 收集保护见
`results/coverage-mbtb-counter-pending-collection-protection.json`。
随后 BPU-MBTB-021 正式覆盖同 key pending 间接目标改写：96 个上下文/bank/way/
阻塞/直通/carry 变化组合，288 个 phase cross bin 在独立输入、完整 entry 请求/
写回节拍和正反顺序完整 resident 断言后闭合。93 项纯模型/能力/清理检查与五个
普通 ScoreboardMismatch 负对照通过；共同输入检查封装没有使原 counter 场景退化。
完整回归 MainBTB 851→857/1056、v_line 29→31/38、分支 332→348/442。
327 raw、140 功能 JSON、141 组、十份 LCOV/JSON/HTML 的时效/一致性及其他
九 DUT 不变见 `results/coverage-mbtb-entry-retarget-refresh-audit.json`；732-item
收集保护见 `results/coverage-mbtb-entry-retarget-collection-protection.json`。
该阶段剩余 MainBTB entry WriteBuffer 146、ReplacerState 53 行。不同 key 的双
pending entry 32 组隔离候选，见 `results/coverage-mbtb-entry-two-keys-readonly.json`，
随后由 BPU-MBTB-022 正式化：低/高 set、四 bank、双 way、阻塞/直通、两种
反馈顺序与三种目标 region 配对，共 192 组合、576 个断言后 phase cross bin。
两个 PC 的目标配对不随提交顺序改变；阻塞后两 key 都按输入顺序写回。
145 项纯模型/输入约束检查和六个带身份/tick/status 的普通 FAIL 负对照通过，
没有超时、teardown 或未取回 task 异常。完整回归 MainBTB 857→877/1056，
v_line 31→32/38、分支 348→351/442，恰关闭第二槽 20 行，其他九 DUT 不变。
328 raw、141 功能 JSON、142 组、十份 LCOV/JSON/HTML 的时效与一致性见
`results/coverage-mbtb-entry-keys-refresh-audit.json`；878-item 收集保护见
`results/coverage-mbtb-entry-keys-collection-protection.json`。
该阶段剩余 WriteBuffer 126、ReplacerState 53 行。跨 way shadow 的 32 组隔离
探针关闭 44 行，见 `results/coverage-mbtb-crossway-shadow-readonly.json`，随后由
BPU-MBTB-023 正式化：独立两-way LRU 区分请求 victim 与 retained shadow owner，
192 个上下文/bank/owner/clean-dirty/mode/carry 组合，576 个 phase/status cross
在完整输入、全端口/节拍和正反顺序全状态回读后闭合。251 项纯检查通过，
漏正确 touch、误用 fresh metadata、写回误归请求 way、漏写回、错 carry 和
错误最终目标六负对照均普通失败且没有清理错误。正式 MainBTB 877→921/1056，
v_line 32→36/38、分支 351→365/442，恰关闭 44 行，其他九 DUT 不变。
329 raw、142 功能 JSON、143 组和十份 LCOV/JSON/HTML 时效与一致性见
`results/coverage-mbtb-shadow-refresh-audit.json`；1130-item 收集保护见
`results/coverage-mbtb-shadow-collection-protection.json`。
此矩阵只承诺初始 counter-2 居民，不能推广为任意邻项保持。独立有序模块
诊断以另一 tag 的条件邻项 counter=3 为前提，16 组均正确路由 entry/target，
却将邻项 counter 3→2；只有两处 metadata counter 字段不同。原始失败保留，
不计功能 PASS 或 blanket XFAIL；完整 FTQ epoch、redirect/flush 和训练资格
仍需审查，见 `results/coverage-mbtb-shadow-counter-side-effect-readonly.json`。
023 阶段剩余 WriteBuffer 82、ReplacerState 53 行。旧 128 组替换索引候选
见 `results/coverage-mbtb-replacer-index-readonly.json`，已由 BPU-MBTB-024 的
1024 个真实 conditional 组合替代：目标/set+32 alias 共享替换状态，邻接
索引/另一 align 独立；taken 2→3 且 touch、NT mispredict 2→1 不 touch、
读取不 touch、新分配 reset 到 2。独立 indexed LRU 选择 victim，完整
profile 正反异步 Scoreboard 回读通过后，6144 个 phase cross bin 闭合。
112 项纯检查和七个带上下文普通 FAIL 负对照通过，原 direct 试验刷新因
FTQ 资格审查停止并保留记录，修正后重新完整运行。正式 MainBTB
921→974/1056（92.23%）、分支 365→418/442，恰关闭 53 个 ReplacerState
行，v_line 36/38 不变，其他九 DUT 与六项 XFAIL 不变。330 raw、143 功能
JSON、144 组和十份 LCOV/JSON/HTML 审计见
`results/coverage-mbtb-replacement-refresh-audit.json`；1243-item 收集保护见
`results/coverage-mbtb-replacement-collection-protection.json`。
024 阶段剩余 82 个 WriteBuffer 行，025 已进一步关闭 42 行。

BPU-MBTB-025 用 24 笔同 bank 哨兵预测阻塞 SRAM 写回，正常送入两个不同
set 的 key，真实填充 depth 0/1；静态只读 Bundle/@on Monitor 证明第二个 key
确实驻留 depth 1。四物理 bank、双 owner、clean-first/pending-second 和
阻塞/直通共 32 组合；独立预期检查填充/改写的输入、请求、owner 写回及节拍。
entry 保留 shadow owner，而分配 counter 按 request way 初始化；空的未命中
way 也应从 0 到 2，不能把两种路由合并。23 项手算纯检查、六个带上下文的
普通 FAIL 负对照，以及双 key 完整 profile 正反流水线回读通过后，96 个
phase cross bin 闭合。正式 MainBTB 974→1016/1056（96.21%），v_line
36→38/38、分支 418→426/442，恰关闭 42 个 WriteBuffer 行。其他九 DUT、
源码/工具/分母及原有六项 XFAIL 不变。完整刷新为 1261 PASS、6 strict XFAIL、
0 SKIP；252/252 功能点执行、246 PASS；331 raw、144 功能 JSON、145 组聚合
99.47%，十份 LCOV/JSON/HTML 同源且时效一致。审计见
`results/coverage-mbtb-depth-one-refresh-audit.json`；1267-item 收集保护见
`results/coverage-mbtb-depth-one-collection-protection.json`。
这是有界 standalone 两 way/两 depth 场景，不证明任意饱和邻项、
full-miss overflow、多命中清理或完整 FTQ pointer/epoch/resolve 资格。

MainBTB 从 resolve 路径训练，redirect
过滤年轻训练；仅有 cold 捕获/反馈顺序不足以证明 FTQ epoch 资格，见
`results/coverage-mbtb-ftq-qualification-source-readonly.json`。训练 one-hot 不代表整个
write-buffer one-hot，flush 可以同时激活第二路，40 个复制赋值不因此分类为
不可达，见 `results/coverage-mbtb-flush-overlap-source-readonly.json`。不宣称全
entry-buffer、overflow、跨 row/flush 完整验证、完整 FTQ 或整个目标完成。
025 阶段正式剩余 40 个 WriteBuffer 双写复制行，不扣原生分母，也不划为不可达。
独立清理诊断覆盖四 bank、双 depth 和启动偏移，共 256 组合：192 例完整状态
通过，64 例 tag=0/position=0 清理请求 upper way 却经 retained lower owner
写回，清掉 lower 新目标、保留 upper 旧目标；这些是普通 Scoreboard FAIL，
未登记功能 PASS 或 strict XFAIL，也未证明完整 FTQ 轨迹可达。
64 例有真实同拍训练/flush 双写；只合并通过诊断的数据，可再命中 20 行至
1036/1056，但不进入正式主表，另 20 行仍需审查。fresh lookup 停止 cached
multi-hit 后排空，另一 set 的完整状态保持；首读旧值是 pending 写回，非更新丢失。
证据见 `results/coverage-mbtb-flush-key-expanded-readonly.json`。复现入口为
`python3 tests/mbtb/diagnostics/run_flush_key_probe.py`，默认不被 pytest 收集，
两类输出目录均隔离，四份正式报告逐字保持。整个覆盖率目标仍未完成。

随后 BPU-MBTB-026 正式覆盖四 bank、training depth 0/1、dirty/clean 清理
shadow 及三种非联合零 key，共 48 组合。agent 封装连续清理与单拍清理后
排空的区别；测试无边沿等待、内部写入或可见 gather/task。独立输入、两写
端口完整 payload/read 资格、全 shadow 前后状态和四周期延迟均比较，
两 set 完整 profile 正反异步回读通过后，144 个 phase cross bin 闭合。
21 项纯模型/scope 检查通过；八项负对照均为带上下文的普通 FAIL。
完整 MainBTB 1016→1056/1056，v_line 38/38、分支 426→434/442，恰关闭
最后 40 个映射行；其他九 DUT、原生分母、源码/工具及六项 XFAIL 不变。
332 raw、145 功能 JSON、146 组及十份 LCOV/JSON/HTML 审计见
`results/coverage-mbtb-cleanup-overlap-refresh-audit.json`；1289-item 收集保护见
`results/coverage-mbtb-cleanup-overlap-collection-protection.json`。
剩余八个分支由实际父模块常量连接分类，四项源码变异负对照检出，
见 `results/coverage-mbtb-branch-unreachable.json`；不删原生分母。
新的更早启动训练诊断在联合零 key 下还观察到另一 set 更新丢失，见
`results/coverage-mbtb-cleanup-routing-readonly.json`；这一偏移仅单 bank 复现，
不是旧 delay 0/1 的 pending 首读，也未证明完整 FTQ 资格。诊断不计正式
PASS/XFAIL，不能由 MainBTB 满映射行覆盖宣称整体目标完成。

下列场景增量描述均保留其原 5.026 基线语境。
MicroTAGE 在该旧基线为 **5728/10712（53.47%）**。此前 `BPU-UTAGE-015` 交叉两表、
四 bank、八索引的即时 bypass 和环形回绕，384 个 cross bin 在断言后闭合；
feedback monitor 验证真实拍数、PC／index 与相邻拍间距，readback 通过八笔
先提交后配对的 prediction transfer 完成。`BPU-UTAGE-016` 不把 shadow 中的
正确数据当成 SRAM 写回证据：另 bank 的八项新分配替换全部旧 shadow 后，
完整 16-case 矩阵中 112/128 个旧项 counter 退回（低表 7→5、高表 0→2）。
前提失败保持普通 FAIL，只有这项保持失败的异常触发 strict XFAIL；不删 bin。
独立 `--vpi` staging 构建确认 `cleanId == enqPtr` 时最后 dirty 清理覆盖新项
dirty 置位；诊断无内部写入、不替换正式 DUT、不改 RTL，不混入正式覆盖数据。
串行化相邻反馈、丢一索引、错误最终位置三负对照均被检出。该轮完整回归新增 189
原生行、无新增缺口，其他九个 DUT 行／分支计数不变；该阶段两 buffer 尚缺 5007 行。
证据见 `results/coverage-progress-utage-shadow.json`、
`results/coverage-utage-shadow-dirty.json` 和
`results/utage/shadow-persistence-known-fail.json`。新增必需缺陷使计划通过率和
组聚合覆盖略降，这是扩展证据范围，不是放宽预期或删除失败功能点。
随后 `BPU-UTAGE-017` 为四 bank 各准备三个不同索引，低表 useful 强度
1/2/3、高表 3，精确计入所有失败分配探测，跨过两次 128-failure aging。
独立校准项必须在两次高表错误后仍阻止 alias 分配、第三次才开放高表，
证明 useful 的资格更新，不能从 counter 正确反推 useful 正确。第一轮仅
低强度项开放低表，高表仍阻止升级；第二轮中等项先低后高，强项直接高表，
且原低表 counter 6 保留。每次操作后所有 alias／原位置均流水线回读，
检查 provider、counter、位置、索引／history 关联及邻项状态；无 hit 的 raw
takenVec 不具备 base fallback 语义，不作错误断言。60 个 cross bin 均在
断言后采样。少一拍失败反馈、少一次低表强化、只损坏高表 useful 更新资格
而保留 counter 更新三个负对照均普通 FAIL。本轮仅关闭 4 个原生源码行
（两 buffer 各两个训练回读 counter bypass 行），无新增缺口；其余九个 DUT
计数不变。该阶段两 buffer 仍缺 5003 行（2626／2377），没有宣布其全可达或全不可达。
增量与正式清单／时效审计见 `results/coverage-progress-utage-aging.json` 和
`results/coverage-utage-aging-refresh-audit.json`；原有持久化缺陷仍 strict XFAIL。
`BPU-UTAGE-018` 接着修正激励范围：不能为扩展旧四位 profile 而把更宽整数
原样写入每个 fold。共享编码器按当前 MinimalConfig 的 history／fold 长度
窗口做 XOR 折叠；MicroTAGE 与 ITTAGE 检查绑定位宽，旧低四位行为不变。
这不是从位宽推导任意配置的历史长度，而是当前固定 RTL 的布局契约。
四 bank × 较老 bit 6/7/8 在短六位窗口完全相同、长十二位窗口不同，须先
观察共享低表，再独立分配相反高表 provider。分别饱和至 0/7，每次选中
bank 更新后所有邻项／对侧历史仍保留；未训练 bit-11 高表上下文经 XOR
折到 index bit 2，并须返回共享低表 counter 4。正反顺序的重叠预测逐项
核对完整 history metadata、索引、位置、provider／counter 和接受／完成时间。
144 个 cross bin 断言后闭合；截历史位、A1 错用当前请求历史均普通 FAIL。
完整回归新增 14 行、没有新缺口；其他九个 DUT 汇总不变。该阶段仍有 4989 行
（低 2626／高 2363），不能把新 bin 全满当成全模块验证闭环。证据见
`results/coverage-progress-utage-long-history.json` 和
`results/coverage-utage-long-history-refresh-audit.json`。
`BPU-UTAGE-019` 再用 bit 对 (0,9)/(1,10)/(2,11) 构造高表 hash 同索引、
不同 tag 和低表索引的 A/B。真实错误反馈先证明 useful=2/1 时均不能替换，
第二次高表错误后 B 才可替换 A，A 须回退原低表。B 饱和至 7 后重放真正
捕获的 A counter-3 metadata，须重建 A=4；再重放 B counter-7 metadata，
须重建 B=6，不能用当前别的 tag 的 counter。四 bank／三 bit 对／相邻和
复位串行两模式，所有阶段流水线回读 A/B/邻项并核对完整 history、provider、
counter 和时间关联，720 个 cross bin 断言后闭合。错 snapshot counter、
错历史 tag、强制串行化三个负对照均普通 FAIL。仅新增 5 个高表 useful
源码行，无新缺口、其他 DUT 汇总不变；当前剩余 4984 行（2626／2358）。
八次低表写入未超过 resident shadow 容量，不把本场景当成替换后 SRAM
持久化证据。最新增量和报告时效审计见
`results/coverage-progress-utage-history-collision.json` 与
`results/coverage-utage-history-collision-refresh-audit.json`。
RAS 的原始 **457/563** 源码行进一步发现提交路径没有驱动，补充
`BPU-RAS-011/012`：提交的不同地址帧和正常／超上限重复帧都须经过
完整推测队列复用后再逐层返回。禁用提交／跳过重复提交的负对照均能检出，
不是只对 still-live speculative state 做 LIFO 检查。相关时序与 metadata
绑定封装在 agent 中，用例不处理边沿。完整回归关闭 RAS 46 个源码行缺口，
提升到 **503/563（89.34%）**，分支从 83/134 增至 107/134；剩余 60 个
源码行仍需按合法状态与复制栈槽分类，不能以新增功能 bin 已满代替分析。
新增 `BPU-TAGE-023` 和 `BPU-SC-017` 检查同 bank、四个不同索引在连续训练读
暂缓写回时的独立更新。TAGE 使用真实误预测 metadata 与最高 provider，检查
原 table/way、counter 0/7 与单项重训隔离；SC 检查相反方向学习和五类表的
公开索引关联。两者复位串行对照、均能检出丢弃一个 PC 反馈的负对照。
这关闭 TAGE 16 行、SC 516 行，逐行比较无新增缺口；其余八个 DUT 行计数不变。
24+12 个 cross bin 只在断言后采样；四项不超写缓冲容量，SC 不要求逐拍串行等效。
SC-017 完成时虽已 33/33 行点，仍有 500 个源码行缺口；TAGE 在该轮仍有 429 行。
随后 `BPU-TAGE-024` 用四个同 bank 索引、最高表两 way 的合法双分支反馈，
同时检查 counter 0/7、后分支 useful 增加、前分支 useful 保持、所有未选 tag
不变以及只重训第一项的隔离。四笔双分支 readback 先提交后由 driver/monitor
scoreboard 配对，复位串行比较 counter／方向，但不要求 useful 逐拍累积等效。
48 个 cross bin 断言后闭合；漏一个 way、漏第四索引、损坏 useful 的 base 条件
三负对照均在状态断言处失败。完整回归关闭 112 个源码行缺口、无新增，升至
**5336/5653（94.39%）**、分支 **301/442**，其他九个 DUT 行／分支计数不变。
该阶段剩余 317 行全部在 WriteBuffer，其中 32 个 counter-copy 分支的 40 个赋值行
要求局部 `hit && ~hit`（或 `hit_1 && ~hit_1`），另 277 行仍需审查；这些证明
不改变原生分母，也不证明其他行的可达性。逐行证据见
`results/coverage-progress-tage-dual.json` 与 `results/coverage-tage-unreachable.json`。
`BPU-TAGE-025/026` 再交叉四索引、最高表 way 0→1／1→0 的真实 tag 迁移。
先等待 useful reset 完成，再利用 weak/notUseful 分配优先级完成替换；
捕获 strong provider metadata 后不再 reset，只接受七笔真实反馈。被动
monitor 独立核对实际 valid／ready、PC、分支身份和原始 metadata；完整
邻项及重复正反顺序流水线回读检查保留状态、身份和接受／完成时间。
新鲜 metadata 对照的 120 个 cross bin 全通过；捕获 metadata 在八例中
使原 tag counter 4→5，却使无关 tag useful 3→1（counter 仍为 7），
其余六个 tag 全部保持。完整矩阵保留 16 项 useful 保持失败和未命中 bin，
只有特定异常触发 strict XFAIL，错发 metadata、丢反馈、串行化读回均普通 FAIL。
迟到 useful 更新允许丢弃或重定向，但不得改无关 tag；七拍计数不单独证明
集成 FTQ 的 resolve／redirect 调度可达。此轮原生行／分支／点计数均不变，
TAGE 仍为 5336/5653，不能用功能缺陷冒充覆盖率增量。最新 310 份正式
数据的隔离／新鲜度审计和场景证据见 `results/coverage-tage-way-migration-refresh-audit.json`
及 `results/coverage-progress-tage-way-migration.json`。
进一步复核优先级条件，另外 24 个生成 copy 分支的 48 个赋值行要求
`!(hit && selected) && hit && selected`，或等价的 clean-copy 反条件。
精确源码守卫／目标赋值核对和每块 16 个 Boolean 取值穷举证明局部矛盾；
去掉优先级前提后必须产生反例，三种内存源码破坏也被拒绝。结合前述 40 行，
该 5.026 阶段的 317 行中 **88 行已局部分类、229 行仍需审查**，原始分母保持不变；
当前 5.052 新场景后并追加 key-copy 证明的对应数字为 243／112／131，
证明摘要已按当前报告复核；追加的 24 个 key 赋值详见前文独立审计。
可重复审计为 `python3 suites/frontend/bpu/tage_coverage_audit.py`，证据见
`results/coverage-tage-priority-unreachable.json`；不据此宣称全 RTL 形式不可达。
随后 `BPU-SC-018` 把四索引 pending 与四 branch way／四 bias selector 组合：
counter 0/7/3/4 与 position 4/5/6/7 都由真实预测 metadata 核对。逐 way 连续
16 拍反馈后，每轮回读必须保持此前已学会的邻 way 和以后未选的冷态邻 way；
四笔 readback 一起提交，经 driver/monitor scoreboard 配对。全部阶段复位串行
作对照，漏 way、漏第四索引、错写邻 way 三个负对照均在输出状态断言处失败。
48+16 个 cross bin 断言后闭合，原生行关闭 74 个缺口且无新增，提升到
**2642/3068（86.11%）**，分支 **388/494**；其他九个 DUT 行／分支计数不变。
该阶段剩余 426 行中 336 个赋值行位于生成代码的 `hit && ~hit` 矛盾路径，已逐块
列出源码与 guard 定义；另外 90 行待审查。这些分类不改变原始 LCOV 分母，
不证明未分类行一定可达，也不以新增功能 bin 已满宣布全模块验证闭环。
`BPU-SC-019` 从这些 bias 赋值行发现另一维度：SC-018 的四 selector 分别
位于四个 PC，不能证明同一 PC 行内的四 selector 独立合并。新用例在每个
PC 交叉四个 counter profile／四 base way，先逐 selector 全部训练为负，
再只反转 row／selector 的棋盘格两 way。每次更新后检查全部 64 个 bias
方向状态，以及五类表索引、provider counter、selector、SC decision/meta
关联。使用公开 `debug.scBiasTakenVec`，不把共享的非 bias 总和当成 bias
状态证据；保持总方向 not-taken/used、但漏掉 selector-3 更新的负对照
仍在 bias 方向断言处失败。错 selector 和串行化由被动反馈 monitor 检出。
相邻与复位串行两模式共 1280 个 cross bin 断言后闭合；真实冷态和全负
metadata 的延迟反馈不做字段伪造，不承诺相邻拍累积速度等于串行。
该阶段完整回归新增 82 行（dirty 45、clean 37），SC 为 **2724/3068（88.79%）**、
branch **470/494**，`v_line` 仍 33/33；无新缺口，其他九个 DUT 汇总不变。
当时剩余 344 行仍包含原 336 个矛盾赋值和 8 个待审查 clean-shadow 赋值，
分母不排除。方向 metadata 不提供精确 signed counter，不宣称数值饱和验证。
增量与 307 份正式数据的时效审计见 `results/coverage-progress-sc-bias-selectors.json`
和 `results/coverage-sc-bias-selectors-refresh-audit.json`。
`BPU-SC-020` 再用合法的已排空行重激活关闭这八行：相邻／复位串行准备
先将四行的四个选中分支训练到真实 taken/used 全 1，捕获真实正向 metadata。
训练封装等待九周期更新／排空，完整回读后才发间隔式单 way 负向反馈；
每轮检查所有 64 个 bias 方向，未选 way 和 selector 不能变化。全负时捕获
真实 metadata，再只重训每行棋盘格两 way；最终 32 笔正反顺序流水线回读
核对完整 snapshot、身份及接受／完成时间。1024 个 cross bin 断言后闭合。
准备阶段强制串行化由 monitor 拍间距拒绝；漏第四行的重激活、错用捕获的
SC 预测使更新失去资格，均由明确行／slot／目标方向／实际状态的断言普通 FAIL。
后续重激活在两种准备模式下都使用间隔式反馈，不宣称该阶段的重叠／串行等效。
SC 当前为 **2732/3068（89.05%）**、branch **478/494**，`v_line` 仍 33/33；
无新增缺口、其他九个 DUT 汇总不变。八个 clean-shadow 赋值确实命中，
无需把缺口归咎于插桩相位。剩余 336 原始行与逐块复核的局部矛盾赋值
完全对应并保留分母，不以此宣称所有 SC 功能组合或精确 signed counter 饱和已验证。
该阶段增量与 308 份正式数据审计见 `results/coverage-progress-sc-clean-reactivation.json`
和 `results/coverage-sc-clean-reactivation-refresh-audit.json`。
ITTAGE 的 36/36 行点原先仍遗漏 69 个源码行，促成 `BPU-ITTAGE-015/016/017`。
先修正其 byte PC／target 与 `PrunedAddr.addr` 半字字段的编解码，包含两项
provider-target metadata；过去输入和输出均不转换，测试可自洽通过，却不满足
ITTAGE-014 宣称的实际同区／相邻 1 MiB 区边界。新容量场景检查 16 个不同
非 PC region、满表已有 region 复用与相邻 SRAM lane 隔离。新的 pending 场景
交叉两 bank 与首表／最高表两模式，八拍反馈只重复四个不同索引，使用真实旧
metadata；16 笔同 bank 预测保持旧状态，排空后回读，再逐项更新 clean shadow
并检查所有邻项。复位串行对照只比较最终 target/confidence 角色，不把重复旧
metadata 算作计数器累积；串行化、丢第四 PC 与 identity codec 的负对照均失败。
48+96 个 cross bin 在断言后采样。ITTAGE 原生源码行升至 **1285/1285**，
分支 **372/372**，其他九个 DUT 行／分支计数不变，逐行证据见
`results/coverage-progress-ittage.json`。这不证明超容量无损或所有功能组合；
其他 agent 仍有直接使用编码地址的旧约定，尚未完成全仓库字节地址契约审查。
统一报告复用 xreactor 的 `--line-coverage`，只引用新 RTL JSON 列出的十份
LCOV，所有 HTML/JSON/LCOV 命中数一致；不扫描可能残留的旧 `.info`。
新增的集成 BPU
`BPU-INT-010` 覆盖 prediction 背压与 redirect 同时作用时的 flush/恢复：
agent 在 ready 为低时记录旧/新 payload，并用 monitor 时间戳排除旧队列记录，
验证恢复后首个接受的预测来自 redirect PC。MainBTB 新增页边界和 fetch 起点
两种过滤场景、同位置属性改写、无误预测条件反馈、同笔多分支计数更新和 lookup/training 两种 enable 门控，说明 2/2 的 RTL 行覆盖
仍不能代替功能需求清单。`BPU-MBTB-019` 又用真实 stale metadata 与另 set
写入，在公开预测和 metadata 中观察同位置双 way，再验证 S2 清理和邻 set
保持；测试暂缓清理的时序由 agent 封装，不在用例中手写边沿。
SC 另补了 MBTB miss、非条件命中与全局 enable
三个独立门控；全局关闭时验证不使用已学会的校正、不接受反向训练，恢复后
原预测仍在且开启训练后可以改变方向。相关功能覆盖仅在输出断言后采样。
`BPU-SC-011` 又分别让训练反馈缺少 MBTB hit、属于非条件分支或携带无效
provider metadata，证明三者均不改变已学会的方向；合格条件反馈作为对照
可重新改变方向。训练 transaction 不再把 MBTB hit 和类型固定为真。
`BPU-SC-012` 把原 agent 固定只有效驱动／观察 slot 0 的 SC 预测扩展为
四路 S2 事务，monitor 对每路 S2 方向和 use 位与次周期注册 metadata
配对。已学成的条件分支依次放到 slot 1、2、3，较早直接分支和中间空槽
不得使用 SC；交错有效／无效 provider 的相邻请求继续逐笔检查 use、
`tagePredValid` 和方向。五格功能覆盖在输出断言后闭合，SC 仍为
2/2 RTL 行、16/16 分支。
`BPU-SC-013` 将 SC 训练绑定扩展至所有 resolved branch，并用一个 batch
反馈事务把 resolved slot 0/2 分别映射到预测 slot 1/3；相反方向的两路
SC 校正均需学成，证明同拍训练不是只处理第一路。六格覆盖在输出断言后闭合，
固定种子 RTL toggle 从 2968/4700 增至 3036/4700。
`BPU-SC-014` 再选取同一 SC way 的两个不同位置：较早条件分支 not-taken、
较晚条件分支 taken 的合格同拍反馈应按 way 抵消，而不是只更新某一个分支。
64 笔反馈保持两个预测槽冷态，随后的单分支反馈能学成校正并在两个槽共见，
用正对照排除训练整体关断的假通过。四格功能覆盖在断言后闭合，
固定种子 SC RTL toggle 从 3036/4700 增至 3048/4700。
`BPU-SC-015` 则让同 way 的两个条件位置都 not-taken；从两次匹配的
复位冷态出发，双分支反馈必须比单分支反馈用更少训练拍学成共享校正。
第三次复位还须复现单分支学习拍数，排除残留状态造成的伪加速。
这补齐同 way `PopCount=2` 的同向更新，对照断言后再采样四格覆盖。
固定种子 SC 原 `.v` 子口径的 RTL toggle 从 3048/4700 增至 3052/4700。
`BPU-SC-016` 进一步用 agent 连续驱动八拍、交替更新同一 fetch block 的
不同 SC way，随后断言两路最终学成；串行反馈在复位后作正对照。
这使更正后的 SC 全 RTL `v_line` 从 25/33 升为 27/33，仍余六个
WriteBuffer 复制槽位点（这是 SC-016 当次增量，不是当前剩余数）。两种时序的
收敛拍数不同，因此不声称逐拍等效。
`BPU-TAGE-022` 使用相同 agent 级连续反馈接口：先让 tagged provider
计数器到 5，再连续八拍反馈并等待写缓冲排空，公开 metadata 应显示原
table/way 的计数器饱和到 7。该场景使 TAGE 全 RTL 行点从 38/132
升为 55/132，当时剩余 77 点集中在 WriteBuffer 的其他状态和复制槽位。
正确 provider-only 反馈不读 SRAM，TAGE-022 只证明同项转发；不同索引的
pending 状态另由 TAGE-023 的真实误预测反馈检查。
`BPU-MBTB-016` 另让 MainBTB agent 绑定完整训练分支向量；同一反馈中的
较早正确 not-taken 与较晚唯一误预测 not-taken 同时把两个驻留计数器
从 1／2 更新为 0／1。重新布置计数器后，两分支均正确、没有误预测的
单笔反馈仍让两项分别从 1→0、2→3。这样较晚分支只在前者落空时
执行，符合真实 FTQ 控制流；每步核对方向、目标和 way，六格功能覆盖
仅在断言后采样。
`BPU-MBTB-017` 再用相邻接受周期的两笔 FTQ 反馈验证同物理 set 的替换状态
交接：driver 连续保持 valid，真实 cold metadata 对应两个不同 tag，正反顺序
都保留两项且各占一个 way。功能覆盖两格均在完整输出断言后采样；MainBTB
RTL 仍为 2/2 行、4/4 分支。独立的同位置 multi-hit 清理尚无通过用例，
不能从这项相邻反馈测试或已满的行覆盖率推断它已验证。
`BPU-MBTB-018` 从页内相邻 16 字节对齐起点分别训练直接分支，前一起点
同时看到位置 5／13 的两个 align-bank entry，后一起点只看到后者重映射到
位置 5；返回前一起点再确认两项目标仍正确。三个功能 bin 均在输出断言后
采样并于完整回归闭合。该场景检验地址轮转与位置高位映射，区别于页边界
过滤和同一起点的多 entry 共存；MainBTB 原始 RTL 仍为 2/2 行、4/4 分支。
`BPU-INT-020` 把同样的多分支反馈检查推进到集成 BPU：训练端口绑定完整 FTQ
向量，不再仅送 slot 0。slot 0 的条件分支正确落空、slot 1 无效、slot 2 的
较晚条件分支 taken 且误预测时，公开 MainBTB metadata 应显示前者计数递减和
后者分配；S2 必须返回较晚分支目标。随后无误预测的同笔反馈应同时更新两路
计数器。功能覆盖只在这些结果断言后采样，不把 ready/valid 握手当作充分证据。
`BPU-INT-021` 将同一问题推进到集成 TAGE：先建立 MainBTB 两条条件分支，
再用 agent 的有界无预测读取训练窗口避免 tagged SRAM 的预测读与训练读争用。
公开 MainBTB raw-hit 位置与 TAGE metadata slot 配对后，先读回两个不同的
provider table/way 和计数 2/3；同笔 FTQ 反馈的 slot 0/2 均正确落空、slot 1
无效，重新查询原 table/way 的计数须为 1/2，MainBTB 两项同时变为 0/0。
`BPU-INT-022` 再检查集成 SC：两路 TAGE provider 有效且初始均未使用 SC，
从同样复位状态分别施加单分支和 slot 0/2 同笔反馈。前者只让第一 SC way
学成 not-taken，后者使两个不同 way 都学成；训练时暂时关闭 TAGE 更新，
恢复查询后其 provider table/way/counter 必须不变，避免把 TAGE 变化误判成
SC 更新。`BPU-INT-023` 再以位置 1/4 的共享 SC way 检验同向聚合：
两路 TAGE provider 分属不同 cell、计数均为 2，SC bias 选择相同；
第一分支单独反馈 4 笔尚未使 SC 生效，累计 8 笔才生效，而包含两分支
的同笔反馈 4 笔即越过使用阈值。训练前后两个 provider 状态不变，
因此速度差来自集成 SC 的同 way 更新聚合，不外推到反向抵消。
`BPU-INT-024` 用相同资格和位置做反向票对照：较早分支 not-taken 后
较晚分支 taken，同笔 slot 0/2 反馈累计 64 笔仍保持 SC 冷态；随后
单分支 8 笔可学成 not-taken。再次复位并复现抵消后，只把较晚分支
改为 not-taken，同槽位双分支 4 笔便越过 SC 阈值，排除训练向量被
整体忽略的伪通过。各段 TAGE provider 状态都必须保持不变。
`BPU-INT-025` 解除这种隔离，让 TAGE 与 SC 同时使能。每笔双分支
not-taken 反馈使用上一笔新接受并由 agent 精确配对的 S3 resolve metadata；
两路 TAGE provider 计数从 2 经 1 到 0 后饱和，SC metadata 持续显示
有效 provider，至第 7 笔两槽共同启用 not-taken 校正并在第 8 笔保持。
逐笔检查 transfer tick、MainBTB 位置及原 provider table/way，证明串行
新 metadata 闭环。`BPU-INT-026` 则在相同 PC/历史下从两次分别配对的
S1/S3 快照产生不同位置的 FTQ 反馈，经 xreactor 异步训练 driver 连续
提交；driver 返回的两个接受事件相隔一个完整周期，后续回读同时验证
两个 TAGE provider 和 MainBTB counter 的独立变化。测试不直接操作 pin、
时钟相位或 `asyncio.gather()`。`BPU-INT-027` 再从两个不同 PC 的配对
metadata 连续提交相反方向的反馈，预测 monitor 在两笔训练接受窗口中
实际观察到预测事件；原 MainBTB 条目计数各自从 2 变为 1／3。这证明
跨 PC 的连续反馈与活跃预测并发。`BPU-INT-028` 再用两条真实 redirect
路径给同一 PC／条件位置构造不同的 PHR metadata：新历史先 miss 原 TAGE
provider，随后独立分配。两份 S1/S3 快照相邻反馈后，两个 provider
各自保留原 table/way，计数分别 2→1 和 4→3，MainBTB 仍共享同一条目。
TAGE 的候选表经运行中的 LFSR 筛选，因此不把第二 provider 的绝对表号
当作功能不变量。
本项训练暂缓预测读取以隔离单端口 SRAM。`BPU-INT-029` 在相同
两历史 provider 前提下，让另一个 TAGE bank 的非条件自循环持续预测；
prediction monitor 在两笔训练接受的同两拍均观察到该 PC，两个 provider
计数仍独立降为 1／3。这是跨 bank 的并发证据。`BPU-INT-030` 改让
非条件自循环持续读取反馈目标的同一 TAGE bank：监视器在 8 周期窗口
持续观察预测接受，训练 transfer 保持 pending；暂停预测读取后才接受，
随后 MainBTB 计数及更长历史 provider 均显示这笔反馈生效。这个用例
覆盖 `trainReady` 同 bank 仲裁，也暴露并修复了 Rise-mode 写入下 driver
过早报告接受的问题。
`BPU-INT-031` 把两份不同 PHR 的反馈同时排在同 bank 预测读取之后：
两笔在持续预测的窗口均为 pending，释放后接受 tick 相差一个周期。
第一历史出现更长表的新 provider，第二历史原 provider 计数 4→5；
这种分历史回读排除了队列第二笔丢失或两笔错误关联。MainBTB 的
两份 resolve 快照均携带旧计数，因此最终 MainBTB 值不作为笔数证据。
`BPU-INT-032` 通过集成 BPU 的真实 FTQ 反馈，为间接分支建立 ITTAGE
provider；关闭 ITTAGE 后只把 MainBTB 改为另一目标，确认 S2 返回新目标。
在相同 redirect／历史上下文重新开启 ITTAGE 后，公开 metadata 必须重新显示
provider，S2 仍返回 MainBTB 新目标，而与该请求配对的 S3 correction 必须选择
ITTAGE 保留的旧目标。四阶段覆盖仅在行为断言后采样；这验证了目标选择的
集成连通和优先级，不能由独立 ITTAGE 的满行覆盖率代替。
`BPU-INT-033` 再把独立 RAS 的栈行为延伸到顶层两层调用：四个不同地址的
MainBTB 条目预先训练，两次 return 的静态目标故意错误；运行时 S2
分别暴露静态目标，配对的 S3 必须按 LIFO 顺序覆盖成内层和外层两个
不同返回地址。两次 call 与两次 return 的接受 tick 递增，六格功能覆盖
只在逐笔断言之后采样。它补的是 `BPU-INT-008` 单层 call／return 未证明的
跨帧关联，而不是追逐已经命中的 BPU／RAS 行点。
其余 RTL 行/分支缺口以及
下一轮场景见 [RTL 覆盖率分析](rtl-coverage-analysis.md)。
ITTAGE 与 MicroTAGE 还新增了同 PC、不同折叠历史的独立训练及交错流水线
查询；由此纠正了测试 agent 对 S0/A0 与 S1/A1 上下文字段的同拍驱动，
并把 scoreboard 采样点分别校准为接受事件后 3／2 个周期。
ITTAGE 训练事务还支持选择唯一有效分支所在的 slot；非 0 slot 的目标
写入和回读由独立功能点检查，而不是通过 testcase 直接写裸 IO。
ITTAGE 的全局 enable 现由独立控制驱动持有；`BPU-ITTAGE-011` 以
同一训练事务对照禁用时不分配、启用时可分配，并检查禁用查询与重新
启用后目标状态保留，补足单纯“关闭时不命中”未覆盖的训练语义。
`BPU-ITTAGE-012` 再将 valid、taken、branch type 和 RAS action 作为训练事务输入，
验证 invalid、未 taken、条件／直接分支和带 pop 的 return／return-and-call 在空表不分配、
在已有 provider 时不改写目标或 confidence；普通间接跳转和间接调用可分配。
八格资格覆盖在输出断言后采样；ITTAGE 原始 5/5 行点、34/34 分支没有因该
功能点变化，说明满行覆盖率不等于训练门控充分验证。
`BPU-ITTAGE-013` 进一步让 agent 发送同一拍的完整分支向量：前四个有效条件
分支均落空时，后面的 taken 间接跳转仍应被选中；两个条件分支落空后的
间接调用 taken 也应分配。条件分支后若只剩 return，则仍保持 cold，
再送合格向量才能分配。
两类非法向量（多个误预测或多个 ITTAGE 候选）在 agent 层先被拒绝，
不把不合法的 FTQ 输入交给 RTL assertion。四格功能覆盖均在输出断言后采样。
AheadBTB 同样需要 S0/S1 上下文错拍对齐：新用例逐笔比较异质 PC
或折叠历史流的 bank、position、type、target，并校准接受事件后两周期的
scoreboard 采样。此前仅断言“存在有效 entry”的背靠背用例不足以证明关联。
AheadBTB 全局 enable 现由独立持久控制驱动持有；`BPU-ABTB-031`
对照关闭／开启时相同 fastTrain 的分配及间接目标更新，并分别检查关闭
查询隐藏命中、恢复后旧条目可读。六阶段功能 bin 均在断言后采样；
不能用 bank/set/way 复制行覆盖率代替门控行为判断。
MainBTB 新增异质 PC 的背靠背 payload 检查，把 scoreboard 采样点校准为接受后
两周期；TAGE 新增已训练／冷位置交错检查，将 S1 的 MainBTB 位置与上一拍 S0
请求对齐，也在接受后两周期采样。SC 的 S0 PC／历史、S1 推进和 S2 MBTB/TAGE
资格信息改由 xreactor 多阶段 driver 重叠驱动；S2 组合判定与次周期寄存 metadata
由 monitor 合成同一响应，在最后一个输入阶段接受后一周期检查。三类新用例都逐笔
检查不同请求的结果，而不以重复查询同一事务代替关联验证。
SC 还单独收集四类相邻资格切换的功能 bin；只有整段输出、metadata 和每周期接受
的断言通过后才采样，避免把“送入了组合”误记为“组合行为正确”。
MicroBTB 也新增条件／直接／间接三种不同 PC 的连续交错查询，逐笔比较完整
预测 payload 和接受间隔，补足旧契约测试只重复同一 PC 的盲点。
其全局 enable 现在由独立持久控制驱动持有；`BPU-UBTB-014` 对照禁用／
启用时相同 fastTrain 的分配和已有条目更新，检查禁用查询隐藏命中但不
擦除 payload，恢复后旧条目仍可读。六个功能 bin 都在行为断言后采样；
MicroBTB 的 RTL 行点仍为 4/4，不能代替这些门控语义的验证。汇总覆盖用例的
`trained`×`miss` bin 原先只查询冷 PC、并未发送 not-taken 训练；现复用
`BPU-UBTB-004` 的训练事务封装，在训练后再次断言 miss 才采样。完整回归
仍为 4/4 RTL 行、82/84 分支；改变的是该功能 bin 的证据，不是功能点计数。
AheadBTB 根据未命中的生成 RTL 计数器实例，选择 bank 3 的内部 set 16：四个
way 均分别验证负向饱和、正向恢复及其他 way 的方向／目标隔离，补齐对应四个
`v_line` arm，并新增八个在断言后采样的功能 bin。
随后又验证同 PC／同 bank 的四个 hash 选中 set，以及内部 set 1 四路老化后
逐路替换；MicroRAS 补上 pending S3 pop 与中性 S1/S2、较新 S2 push 的优先级，
并以相邻周期的 S1 pop／中性 × S2 pending push／pop 四格矩阵逐拍检查输出。
`BPU-ABTB-039` 把历史哈希选 set 与同 PC 四位置方向更新交叉：path hash
3/7 对同一 PC 分别选择 bank 3/set 0/1，前者保存条件／直接／间接混合
profile，后者的四个条件项先共同老化，再逐位置恢复。每次训练后同时回读
两个 set 的方向、类型、target、way 与路由，七个功能 bin 只在断言后采样。
`BPU-ABTB-040` 对相同两种 history-selected set 再检查四路 MicroTAGE
S2 旁路：弱正混合类型与饱和强负条件配置相邻周期交错，逐路对照主预测
与旁路的 valid、位置、类型、RAS action、taken、strong bias。五格覆盖
在行为断言后闭合。`fastPositions` 属于实时 S1，而 `result` 属于 S2，
agent 的原始旁路结构不能被误读为同一阶段快照。全量 AheadBTB 行点
当时保持 1585/3074，说明这是满布尔路径之外的输出关联检查。
`BPU-ABTB-041` 再把历史选 bank 与四路方向计数更新交叉：同一 PC 的
四套不同 target 条件分支分别放进 bank 0/1/2/3 的物理 set 1。
逐 bank 一拍老化全部四路，再按位置恢复四个物理 way；每次都核对
所有 bank 的路由、方向、target 和 way，证明未选中的 bank 没有被训练污染。
20 个功能 bin 均在四 bank 输出断言后采样。
AheadBTB 另在物理 set 31/32 × 四个 bank 的四路矩阵中对计数器做负饱和与
正向恢复，并逐次检查其余 31 个 resident。最初 bank 0/2 的固定种子回归
新增 24 个行点、36 个分支；随后 bank 1/3 的扩展又使完整回归净增
25 个行点、35 个分支；后续把 set 63→0 回绕扩至 bank 1/2 同时驻留，
又净增 7 个行点、9 个分支。`BPU-ABTB-043` 在四个 bank 同时驻留
物理 set 2/3/4，以 set 2 和 set 4 的 not-taken 哨兵夹住 set 3 四路；
逐路老化和恢复并回读全部 24 项，使 set 3 的 16 个正向臂与 11 个
减向选择臂全部命中。`BPU-ABTB-044` 再把老化满组替换与双侧邻 set
以及四个历史 bank 交叉，按 bank 替换一个物理 way 后回读全部 24 项；
set 4 新命中 10 个减向选择臂，16 个正向更新臂仍未命中。
`BPU-ABTB-045` 在该已替换状态下逐路恢复幸存项，并先将四个新项
再次老化为 not-taken 才恢复，全部 24 项的物理 way、target、方向
与路由持续核对；补齐 set 4 的 16 个正向更新臂，避免仅凭新项初始
taken 误认计数器已增加。`BPU-ABTB-046` 用同一 PC 的折叠历史交叉高 set
48–51 与四 bank，逐格老化／恢复并回读全部 16 格的路由、way、目标和方向；
新增 24 个计数器复制行点。`BPU-ABTB-047` 再让每格同时驻留四路，
逐路恢复并持续核对全部 16 格，使高 set 网格的 64 个计数器格子无行点缺口。
`BPU-ABTB-048` 继续在全部 16 格逐格训练第五个更后位置，检查唯一 victim、
幸存项方向变化与其他 15 格完整保持；行/分支计数没有增加，说明这项
行为交叉不能用复制点增量衡量。当前 AheadBTB 为 1810/3074 行点、
2062/4112 分支。
剩余复制点仍按几何和状态分类，不逐格增设功能点。
另用真实 cold 查询 metadata 重复训练同一 PC/position，在 bank 0/2 分别
观察到不同 way 双命中；停止单端口 bank 的连续读取并排空写缓冲后恢复
唯一命中。该场景命中此前唯一非复制的 AheadBTB multi-hit 清理分支，
覆盖从 1721/4112 增至 1722/4112，行点不变。
同 bank 不同 set 的两笔 fastTrain 还在连续读压下分别保持待写状态；
释放读端后各自写回并命中。这补上写缓冲不丢事务的行为对照，尽管它没有
增加 RTL 行/分支计数。
同一 `BPU-ABTB-024` 功能点又扩展到 bank 1／set 34 四路，进一步命中此前
全回归未触及的 8 个行点；两组 resident 最终都回读。随后同一功能点再
补 bank 1／set 34/35 同 bank 相邻 set 隔离：保持 set 34 四路 not-taken，
逐路翻转 set 35，并在每次转换后回读八项状态。当时 AheadBTB 为
1628/3074 行点、1812/4112 分支。`BPU-ABTB-035` 把同 PC 位置优先级
与四个替换 victim way 逐一交叉，四格均经方向、target、way 断言后采样；
新增行为覆盖但没有改变 RTL 行/分支总数。`BPU-ABTB-042` 又把四个历史
bank 的满组替换与位置优先级、四路计数器恢复交叉，set 2 的 23 个缺口
行点由此命中。剩余复制点不直接等于缺失的独立需求。
`BPU-ABTB-036` 在 bank 0/set 0 验证四路同 PC 条件命中后的 not-taken
全体降低与 taken 位置选择性恢复，逐次检查方向、target、way；完整回归
使该格子的五个剩余行点全部命中，唯一行和分支分别净增 2、5。
`BPU-ABTB-037` 在 bank 3/set 0 放入两个条件、一个直接和一个间接位置，
验证共享 not-taken 反馈只老化条件项，以及间接目标修正只改自身 target、
同时按位置抑制更早条件项；该场景净增 4 个行点、2 条唯一行和 4 个分支。
`BPU-ABTB-038` 在该满组上再交叉替换历史与旧分支类型：四个 victim way
和条件／直接／间接三类旧项均被新条件项替换。新项一次 not-taken 后失去
taken 预测、一次 taken 后恢复，幸存项的类型、目标、way 保持；固定种子
全量回归又增加 4 个行点、2 条唯一行和 2 个分支，bank 3/set 0 的剩余
两个物理 way 计数器行点全部命中。
`BPU-ABTB-030` 进一步在该 cell 逐路老化并替换，检查新项方向、旧 tag
淘汰、幸存项与另一 cell 哨兵隔离。功能覆盖四个 victim-way bin 均命中；
Verilator 的 `needReset` 原始分支检查早于同拍条件赋值和 counter reset，故
此场景不增加原始行/分支数字，不能将行为通过写成 RTL 覆盖命中。
MainBTB 的部分目标保存另以同一区域、上溢和下溢三格回读验证；集成 BPU
关闭早级预测器后，上下两个跨界方向都由 S2 的 MainBTB 返回完整目标。
但仅开启 MicroBTB 作为早级来源时，跨界目标高位丢失后 S2/S3 均未修正，已登记为
`BPU-INT-013` strict XFAIL。它说明集成 BPU 的 6/6 行点并不能证明
跨级目标一致性。`BPU-INT-014` 则在保持 MicroBTB 旧目标、仅更新 MainBTB
间接目标后，验证 S1 旧目标与 S3 新目标的低位差异纠正；通过与失败场景的
对照，明确缺陷范围是高位差异无法触发后级覆盖，而非 S3 覆盖路径全然失效。
另以 `BPU-INT-015` 验证 AheadBTB 的集成学习闭环：关闭两个早级来源时
MainBTB 在 S2 修正自循环分支，单独开启 AheadBTB 并让 S3 fastTrain 写回后
同一分支升为 S1 命中；再次关闭则恢复 S2 修正。预测 monitor 的接受时间
过滤掉重定向前的同 PC 历史结果，三格功能覆盖都在断言后采样。两个早级
来源同时有效且彼此目标不同的优先级由独立的 `BPU-INT-017` 验证。
`BPU-INT-016` 先后验证 MicroBTB 目标 A、AheadBTB 目标 B，并在关闭
AheadBTB/MainBTB 后回读 MicroBTB 仍为 A，证明禁用期间的 B 向训练没有
覆盖旧条目。BPU metadata monitor 现一并捕获公开的 S3 perf echo：
`BPU-INT-007` 核对同笔 S1 的 PC／target／方向／位置，`BPU-INT-016`
核对三阶段的来源依次为 MicroBTB／AheadBTB／MicroBTB。
`BPU-INT-017` 在不再次重定向的历史上下文中确认 AheadBTB 条目有效；
先背压，再开启 MicroBTB 并等待延迟控制生效，随后短暂恢复接受以触发
新的 S0 读取。再次背压保持 S1 时选择 AheadBTB 的目标 B；不接受下一笔
请求，仅关闭 AheadBTB/MainBTB 后同一 S1 改显 MicroBTB 原目标 A。
这同时断言 A/B 不同、PC/位置/方向保持一致。agent 封装了控制延迟、
短恢复和背压取样，避免测试用例接触时钟边沿或底层 IO。
`BPU-ABTB-032` 进一步界定 AheadBTB 单模块的 4 MiB 目标区域拼接：
fit 完整返回，跨区上溢／下溢按配置 wrap。`BPU-INT-018` 现用跨区往返
双分支形成自然重复路径，先在关闭 ABTB 时检查 MainBTB 双向完整目标，
再让 ABTB 学会返回分支。该笔 S1 输出局部 wrap `0x40bfffe0`，同笔
metadata 的来源为 ABTB，完整目标应为 `0x407fffe0`；两者低 22 位相同，
后级没有修正。只有缺少修正这一判定触发 strict XFAIL，前提缺失仍按
普通失败处理；对应功能覆盖的修正结果 bin 未命中。
`BPU-INT-019` 在真实 ABTB 自循环 S1 命中后背压，停止 S0 读占用再
更新 MainBTB 间接目标到跨区地址。恢复时，agent 将 S3 override 与同拍
metadata 关联，断言完整新 target 和 ABTB 的旧 S1 target/来源回显。
此例旧／新目标的低位不同，只证明 S3 这条路径对 ABTB 来源可用；
`BPU-INT-018` 则隔离了高位独有差异，并复现其失败。
上述已实现功能点的输出断言通过，并非声称所有生成计数器复制点都已命中。
TAGE agent 现可分别驱动预测侧 baseConf 和训练侧 MainBTB counter；新用例验证
弱 provider 在高/低 base 置信度下的 metadata 与 fallback。随后同 selector
桶的双 tag 场景验证未训练分支的 counter/way 保持、选择却从 base 转为
provider；同 set、多深度反馈场景使奇数索引 1/3/5 的逐用例 RTL 更新
arm 分别命中 7/5/1 次，TAGE 完整回归分支达到 30/30。
TAGE 的全局 enable 也改由独立控制驱动持有；新增 `BPU-TAGE-015` 以
相同 cold metadata 证明关闭时训练被挡、开启后训练可分配，并在再次
关闭／恢复时验证预测门控与原 provider 的 table/way 保留。
`BPU-TAGE-016` 再把分支类型贯通 lookup、MainBTB metadata 与训练事务，
验证直接／间接跳转的目标误预测不分配 TAGE provider，也不改动已学会
的条件 provider table、way、counter；合格条件反馈仍可推进计数器。
六格功能覆盖在输出断言后采样。`BPU-TAGE-017` 则把完整训练分支向量和
TAGE metadata 向量绑定到同一个 pulse：较早正确 not-taken 与较晚正确
taken 条件分支之间留一个空 resolve slot，两路 MainBTB hit 分别选取
metadata，并使两个已加强的驻留 provider counter 在同拍 2→1、5→6；下一笔
继续分别变为 0、7。三个阶段的功能 bin 都在结果断言后采样。单分支训练
接口仍沿用同一向量编码，不在 testcase 中构造裸信号或时序。
`BPU-TAGE-018` 补上 RTL `TrainInfo.valid = isCond && mbtbHit` 的另一半：
训练事务可声明有效条件分支在 MainBTB metadata 中未命中，agent 不再总是
伪造 `rawHit=1`。冷态 miss 不分配，已有 provider 遇到 miss 不更新；
同一向量里较早 miss、较晚 hit 时，后者仍可更新 provider。四个功能 bin
均在预测结果断言后采样，说明 5/5 RTL 行不能代替训练资格功能点矩阵。
`BPU-TAGE-019` 再补原 agent 仅有效驱动、观察 MainBTB slot 0 的预测盲区：
S1 位置和 S2 的 `result/baseConf` 分别由独立驱动阶段持有，monitor 返回
完整四路 provider／方向／metadata／SC counter valid，并保留旧的标量
slot 0 API。slot 1、2、3 的较晚条件分支分别分配并强化 provider；
相邻周期交错的两种向量再检验非 0 slot 的 provider 与 `altConf` 不被后续
请求覆盖。五格功能覆盖在真实结果断言后闭合，TAGE RTL 仍为 5/5 行、
30/30 分支。
集成 BPU agent 可单独关闭 MicroBTB/AheadBTB；新场景检查 S1 miss 后由
MainBTB 在 S2 修正 target，并命中此前未覆盖的 `BpuDut.v:1880`。
MicroTAGE 已用真实 metadata 建立两表有用度均阻塞的状态：同索引新分支
aging 前仍 miss，130 次高表误预测受阻后低表重新可分配，原高表 provider
仍命中；`UtageDut.v:1054` 的逐用例行点命中 1 次。
MicroTAGE 的全局 enable 也改由独立控制驱动持有；`BPU-UTAGE-012` 分别
证明禁用期间延迟 fastTrain 不分配、恢复后相同事务可分配，以及关闭查询
时预测级保持旧输出而非强制 miss。对不同折叠历史的恢复查询验证状态
确实未被关闭期间的请求改变。
`BPU-UTAGE-013` 进一步把 fastTrain 的最终分支类型从 agent 常量变成
事务字段；同位置 stale 条件 metadata 遇到实际直接／间接跳转时不得
错误分配。若较晚跳转已执行，较早条件分支的 base 为 not-taken 时不需
校正，base 错误预测 taken 时则应学得较早位置的 not-taken 修正。两类
跳转的六格行为均在真实预测结果断言后采样，不能由满行覆盖推断。
`BPU-UTAGE-014` 再把 AheadBTB 四路输入与 MicroTAGE 的 hit/taken 向量
封装成单笔 agent 事务，保留旧的第 0 路标量 API。第 0 路为正确落空的
条件分支，另一路依次放在 slot 1、2、3（中间允许无效空槽）；逐项检查
metadata 位置／有效位，训练实际 taken 的后续分支，再要求只有对应 slot
得到 taken 校正。异质向量与折叠历史还在相邻周期重叠提交，按 transfer
核对有效位、位置和预测向量。该场景发现旧 agent 把 A1 的
`fastPositions` 与 A2 的 `result` 同拍发送，导致后续请求覆盖较早请求的
metadata；现由独立驱动阶段按接受事件对齐。slot 三格与串行／重叠两格均在输出断言
之后记录功能覆盖，避免 6/6 的 RTL 行覆盖掩盖非 0 slot 与关联问题。
RAS 单模块另把三层调用、重定向回滚至中间层、再连续返回两层串成独立
`BPU-RAS-009`：每一级返回地址不同，六个阶段先断言输出再采样功能覆盖。
其 RTL 仍为 2/2 行、6/6 分支，说明满行覆盖率没有表达恢复后的 LIFO
链条是否正确。`BPU-RAS-010` 再交叉 near-overflow 门控与回滚：连续被门控的
push/pop 不得改变栈顶或完整 redirect metadata，回滚到较早调用帧释放容量后
新的 push/pop 须恢复工作且原帧可返回；五个阶段断言后采样均闭合，RTL
仍为 2/2 行、6/6 分支。RAS 汇总操作组过去在没有断言的情况下把 disabled
采样为已覆盖；现在先核对每步输出和重复计数，且只把通过的
`disabled_top_held` 记入汇总组。完整门控由 `BPU-RAS-008` 独立记录：
栈顶保持 bin 命中，指针 metadata 保持 bin 因 strict XFAIL 留空，不能
再用汇总组的 100% 误称 enable 功能已通过。
原系统版 picker 和 xcomm 缺少 xreactor 所需的模板及 native coverage ABI。
系统安装匹配的 picker 2.0 xreactor 产物和 xcomm ABI v3 后，重新构建了全部
10 个 DUT；`XTriggerEngine.CoverageVersion() == 3`，xreactor 全套自测为
**881 PASS**。重建和校验流程见 [DUT 重建](dut-rebuild.md)。
这些框架自测与 BPU 的 pytest 功能点 verdict 及 Verilator RTL 覆盖率
仍是不同的验证层次。

以下是本轮迁移针对并已关闭的原始结构性缺口；六个 strict XFAIL 对应 RTL 缺陷，
不属于验证环境缺口：

1. 一个 feature ID 聚合多个独立需求，无法给出逐需求 verdict；
2. 大多数 DUT 只有一个测试函数，reset、miss、train、update、pipeline 和 gate
   相互耦合；
3. BPU 自己的 interface、driver、monitor、scoreboard 缺少独立契约测试；
4. collision、replacement、counter saturation、backpressure、overflow、cancel、
   unmatched response 等边界覆盖不足；
5. 功能点通过率与 coverage bin 完成率都偏粗，100% bin coverage 不能代表功能点
   全部通过；
6. definitions.py 同时开始承担常量、编码辅助函数和检查逻辑，需要继续按职责拆分。

## 2. 验证证据的四个层次

每一层回答不同问题，不允许用较低层证据替代较高层证据。

| 层次 | 回答的问题 | 主要证据 |
| --- | --- | --- |
| 组件契约 | 验证环境是否正确驱动和采样 | interface/driver/monitor/scoreboard UT |
| DUT 功能点 | RTL 是否满足单项功能需求 | 一个主要不变量对应的 pytest testcase |
| 功能覆盖 | 激励空间中的重要分类是否被命中 | coverpoint/cross 的 bin 报告 |
| 回归结论 | 计划中的功能点是否都执行且通过 | pytest verdict + feature report |

功能点通过率和功能覆盖率是正交的：

- feature PASS 表示至少一个映射 testcase 完整通过；
- coverage 表示运行过程中观察到哪些输入、状态和交叉组合；
- feature 未执行时，即使别的测试碰巧命中过相关 coverage bin，也仍为 NOT_RUN；
- feature 失败时，coverage 命中不能把 verdict 改成通过。

## 3. 最小 UT 的定义

这里的“最小”不是每个 test 只能有一个 assert，而是每个 test 只有一个主要失败原因和
一个清晰的功能点边界。

一个合格的最小 UT 应满足：

1. 名称描述一个行为，例如 test_not_taken_miss_does_not_allocate；
2. fixture 只创建本测试需要的 DUT 和组件；
3. 激励数据与检查逻辑不在 test 内临时拼装；
4. reset、训练收敛等前置动作可复用，但不与被验证行为共用 feature verdict；
5. 失败信息指出 request、accepted/observed event、expected/actual 和状态；
6. 一个 test 可以映射多个真正不可分割的 feature，但不得用一个 feature 概括整条
   回归路径；
7. 随机测试必须有固定 seed、可打印/保存的失败向量和明确的停止条件。

## 4. 验证组件职责

### 4.1 Bundle 与静态绑定

不设置独立 Interface 层。Bundle 与 `PortBinding`/`PulseBinding` 描述结构、方向与绑定：

- 从 picker signal_tree 绑定层次化端口；
- 建立 Bundle/ReadyValid/pulse 视图；
- 声明输入写入模式，普通输入应为 AsRiseWrite，clock 保持 immediate；
- 不包含协议等待、reference model 或 DUT 功能判断。

Bundle UT 验证路径、字段宽度、读写方向、别名映射和 write mode。它不运行完整训练
场景。

### 4.2 Driver

Driver 只负责主动协议：

- 独占被驱动的 DUT 输入；
- 将 transaction 编码到绑定的信号（标量或 Bundle）；
- 在协议接受点发布 accepted event；
- 支持 back-to-back 请求、容量限制、cancel、close 和 idle 恢复；
- 不读取预测结果，不决定功能正确性。

Driver UT 使用最小 backend/fake binding 验证周期、脉冲宽度、队列和生命周期；只有
编码确实依赖真实 picker 层次时才启动 native DUT。

### 4.3 Monitor

Monitor 只负责被动观察：

- 在声明的采样相位捕获不可变快照；
- 保留 XEvent 时间；
- 明确 start/close/rearm；
- lossless 队列溢出必须失败，不能丢 observation；
- 不驱动 DUT，不生成 expected，不比较。

### 4.4 Scoreboard

Scoreboard 负责检查工作流：

- direct 模式比较已知的 expected/actual；
- async 模式绑定 accepted driver 和 observed monitor；
- association 只完成 request/response 对齐；
- expected source 只生成期望；
- compare 只比较；
- mismatch、association error、incomplete 必须到达 pytest；
- 批量流水线用 drain()，测试侧不出现 asyncio.gather()。

通用 Scoreboard 语义由 xreactor 测试证明；本仓库仍需证明每个 predictor 声明的 latency、
decoder 和 transaction encoder 与 Scoreboard 契约一致。

### 4.5 Testcase

Testcase 只表达架构场景：

- 调用 agent transaction API；
- 声明 expected、reference model 或局部 assertion；
- 采样覆盖率；
- 不操作裸信号，不等待显式边沿，不负责后台 task 生命周期。

### 4.6 Agent 与 Env

Agent 组合 Driver、Monitor、Bundle 和 Checker，开放事务级 API；Env 负责
DUT／Execution／Agent 的 fixture 和观察作用域生命周期。测试不承担这些底层职责。

## 5. 当前目录结构

实现按 DUT 再按职责组织，pytest 测试仍按最小 UT 和职责组织：

~~~text
suites/frontend/bpu/
├── common/{bundle,driver,monitor,env,checker,model,transaction,coverage,pytest}/
└── <dut>/{agent,bundle,driver,monitor,env,case,model,checker,transaction,coverage}/
tests/
├── conftest.py
├── framework/{bundle,drivers,monitors,scoreboard,transfers}/
└── <dut>/{conftest.py,bundle/,drivers/,monitors/,scoreboard/,testcase/test_*.py}
~~~

并非每个 DUT 都必须复制所有通用 UT。规则是：

- 通用行为只在 tests/framework/<responsibility>/ 验证一次；
- DUT 目录只验证该 DUT 的 binding、encoding、decoding、latency 和功能；
- 无内容的层次不创建占位文件；
- conftest.py 只注册 env 中的 fixture，不保存环境实现、向量或断言；
- 可复用场景／向量属于对应 DUT 的 case，领域检查器属于 checker，参考模型属于 model；
- 集成 BPU 内部 ABTB／SC／bypass 等位于 `suites/frontend/bpu/bpu/<role>/<component>/`；
- test 文件不定义可复用组件。

## 6. 功能点设计规则

功能点 ID 使用以下命名：

~~~text
ENV-<RESPONSIBILITY>-NNN
BPU-<DUT>-NNN
~~~

每个定义至少包含：

- component；
- title；
- description；
- priority：P0/P1/P2；
- verification level：contract/functional/stress/integration；
- planned testcase 路径。

优先级含义：

- **P0**：复位、基本协议、基本预测/训练、失败传播；任何发布都必须通过；
- **P1**：更新、冲突、counter、gate、redirect、流水线压力；
- **P2**：容量边界、replacement 长序列、alias、随机/压力和性能相关场景。

旧的聚合 feature ID 在新 testcase 全部建立后删除，不再让一个 PASS 同时代表多个未被
独立定位的需求。

## 7. 覆盖模型要求

每个 DUT 的 coverage 至少包含：

1. 输入分类：branch type、taken、position、enable、redirect/action；
2. 状态分类：cold/hit/miss/provider/alternate、counter 区间、stack shape；
3. 操作分类：allocate/update/replace/bypass/flush；
4. 边界分类：最小/最大 position、index/tag 边界、queue depth；
5. 必要的 cross：不能把无关 bin 做笛卡尔积，也不能只用单点命中代替组合验证。

Coverage model 位于 DUT 的 coverage.py，testcase 只调用领域化的 sample 方法，避免
在每个测试中手写字符串字典。

## 8. 回归门禁

完成迁移后的必需门禁：

~~~bash
# xreactor 自身，native backend 不允许 skip
python3 -m pytest -q --require-xspcomm

# BPU 全量功能回归
python3 -m pytest -q

# 计划完整性
python3 tests/run_all.py
~~~

并检查：

- 收集到的 testcase 数量不低于 verification plan 中已实现 feature 的数量；
- P0/P1 无 NOT_RUN、SKIP、ERROR 或非预期 XPASS；
- strict XFAIL 必须关联明确缺陷和独立 testcase；
- test 目录无 FallingEdge、RisingEdge、裸 Set() 和 asyncio.gather()；
- 每个 async Scoreboard 在 fixture teardown 中关闭；
- functional-point report 与 functional coverage report 分开生成；
- 随机失败保存 seed 和 transaction 序列。

## 9. 实施顺序

1. 建立本文与完整功能点清单；
2. 先拆并补齐 framework contract UT，证明验证环境本身可信；
3. 按 DUT 将旧的大测试拆成 reset/lookup/training/pipeline 等最小 testcase；
4. 增加 P1 边界与冲突场景；
5. 引入领域 coverage helper 和必要 reference model；
6. 增加 P2 容量、alias 和有 seed 的压力回归；
7. 删除旧聚合 feature ID，要求计划中除登记的 RTL defect 外全部执行。

在第 7 步完成前，报告必须如实显示 NOT_RUN，不能把迁移中的缺口解释为通过。
