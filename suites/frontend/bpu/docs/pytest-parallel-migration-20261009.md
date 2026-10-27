# pytest 多进程并行迁移

## 2026-10-16：生产入口切换 xreactor managed runner

默认入口已切换，不是独立试点：通用 worker 生命周期、功能/原生覆盖合并、
manifest 提交及已消费输入回收都交给 xreactor。项目只保留功能点与原生源行归因；
纯模型/schema 测试通过公开标记排除自动功能测量，实际 DUT 发现不受影响。
原逐 case 功能导出在生产关闭，显式 serializer 单元测试仍可验证 JSON 合同。
最终14851门禁、71真实兼容及单场景通过，同2117文件epoch；全量18642项/
64进程完成：18614PASS/25普通FAIL/3strict XFAIL，旧判定及十DUT原生集合保持。
最终10份DAT约61.1MiB，worker输入已回收；功能349组/318满，新增可见4个
未满旧组与两项UTAGE样本恢复不是新功能。owner605.62秒含后处理，仍非RTL通过。
版本、保留策略和最终资格见[本次迁移](xreactor-managed-runner-20261016.md)。

以下各节是早期普通 pytest/项目 collector 的历史记录，不代表当前依赖分支或入口。

## 2026-10-11 16:41：旧全量发布完成，运行时优化切入生产

旧组合版本完整全量已实际退出0并发布：15156 PASS、7 strict XFAIL、0 SKIP，
293功能点全部执行（286 PASS、7 XFAIL），204功能覆盖组中194组满覆盖。
十DUT原生 source-line 集合与既有 hit 无回退；BPU为40297/46541。
pytest阶段14587秒，完整 owner 17875秒，约55分钟花在后处理，不能只报pytest时长。
终态见[旧全量回执](../results/full-native-parallel32-combined-repair-20261011-v1/exit.json)。

在确认旧owner退出、旧纪元哈希不变后，已迁入28个生产源码/测试文件：
xreactor静态采样、成功比较快路径和精确值bin重叠索引；BPU独立流式覆盖、
紧凑关联历史及阶段计时。xreactor保持main分支，原有文档修改未覆盖。
不修改RTL、DUT、picker/xcomm，不改变AsRiseWrite，不引入VPI或internal访问。

三个真实场景等价对照：789.17秒→440.49秒（约1.79倍），功能覆盖与全部原生
覆盖计数一致。缩短观察窗口的候选因54个映射行hit丢失未合入。相同6份FC输入
的合并从9.69秒降到4.22秒，整份报告SHA一致；这不是全量合并耗时保证。

实际安装路径下xreactor全部927项通过；新版本完整收集15176项，保留原用例并
新增13项边界/失败契约。相同64个原生场景的32/64worker对照各64PASS：
275.03秒→153.68秒；128份FC、132900个原生点的key与全部计数一致。
默认上限仍为32，本轮全量显式使用64，待完整资格后再考虑改变日常默认值。
生产路径组件/四个跨bank-set场景资格已整体退出0：9599 PASS、0 SKIP，
pytest783.04秒、完整owner833.10秒。两轮worker证据链重新核验通过后，
新纪元15176项完整回归已使用64worker启动；完整新纪元回归仍须再次验收，
不把隔离资格或旧全量成绩写成新版本全量通过。
终态分别见[生产资格](../results/case-runtime-preflight-20261011-v1/exit.json)、
[覆盖等价与worker资格](../results/case-runtime-optimization-20261011-v1/qualification.json)
和[新全量owner](../results/full-native-case-runtime-20261011-v1/owner.json)。
详见[迁入记录](../results/case-runtime-optimization-20261011-v1/promotion.json)和
[产物/内存策略](artifact-policy.md)。

## 2026-10-11：组合修复已迁入生产，原生资格回归运行中

上一轮11794项已于北京时间01:38结束：11786 PASS、7 strict XFAIL、1 FAIL、
0 SKIP，未发布。失败是第三个ABTB场景加入后旧AST契约仍要求两个调用；
现已修复为检查三个精确场景身份、kind和单一await，不放宽底层IO封装要求。

已合入双对齐训练PC修复及独立字节几何参考、SC接受边沿响应关联修复，
并按DUT/role迁入200组合训练几何和48组合SC-used场景，登记BPU-INT-059/060/061。
当前293点、完整收集15163项，旧DUT testcase全部保留；旧相位实现和离线
诊断执行器没有迁入生产。新增2000/24/48-bin矩阵纳入完整发布门禁，缺一bin拒绝。

同一1657文件版本上框架/模型/组件9582项已通过完整生产选跑收尾，退出0；
32worker原生547项正在验证200几何、48used及299个既有SC场景。普通串行pytest
现在自动隔离到新run，不再覆盖正式报告；成功/失败/collect-only负对照均通过。
本次误覆盖的两份报告已经按发布SHA逐字节恢复，其他正式文件未变。

单次协调器等待547项实际成功，再重新核对worker收据、源码、完整新矩阵和
正式报告哈希，随后启动正常32worker全量；任何资格失败则停止，不发布部分结果。
终态以对应exit.json为准，不把本段启动状态当作已通过。

- [精确迁移与归档](../results/coverage-repair-20261011-promotion-v1/promotion.json)
- [9582项组合资格终态](../results/coverage-repair-20261011-contracts-v2/exit.json)
- [547项原生运行](../results/coverage-repair-20261011-native-v1/owner.json)
- [衔接任务](../results/coverage-repair-20261011-promotion-v1/coordinator-owner.json)

下方各节为历史记录。正式BPU仍40039/46541，未提前计入候选增益；
reset优先级12288-bin、完整FTQ和既有缺陷目标均保留。

## 2026-10-10 13:43 UTC：正式报告已刷新，永久修复已落地并重跑新全量

上一版完整11269项的恢复后处理实际退出0。独立发布审计重新验证32份
worker收据、84条累计快照支配链、1477份独立FC输入、73397个bin计数及
provenance，逐项核对HTML/JSON/十DUT LCOV与零命中行位置后发布正式报告。
本轮11262 PASS、7 strict XFAIL、0 SKIP，289点全部执行（282 PASS、7 XFAIL），
201个功能覆盖组、190个达到100%；BPU为40039/46541，增加4305行，十模块
均未丢失旧命中。原owner退出1、恢复退出0、发布退出0分别保留，不篡改失败。
见[独立发布审计](../results/full-native-parallel32-role-layout-20261010-v1/recovery-publication-audit.json)。

冻结解除后，四份SC测试改为每次执行创建新的Coverage对象；没有放宽框架
重复身份守卫。隔离候选和生产目录各实际331项契约PASS，新增缺一条路径即
失败的完整12288-bin发布门禁，并把全256个cell的later-taken真实场景迁入
统一Case API与功能点BPU-INT-058。模型／场景职责保持当前DUT→role分层。
见[精确迁移记录](../results/coverage-production-candidate-v1/promotion.json)。

新正式回归已实际启动，完整收集11794项、290点、32个CPU-active独立worker；
1634文件ledger为`1a3476ee6ee12c909d9fcf9550d937f4d40a0cccbe4639f3473899ece02cb12a`。
此前所有DUT testcase节点均保留；五个便携契约节点因增加later-taken维度与
加强全量门禁改名，精确清单在迁移记录中。新增525项不包括删除任何DUT场景。
源代码再次冻结，未完成新全量不能算BPU-INT-058正式通过。已发布报告属于
上一版289点测量，summary明确标记当前源码已变、等待新全量，未提前增加数字。
见[当前状态](../results/production-parallel-migration-v7.json)和
[新全量owner](../results/full-native-parallel32-coverage-repair-20261010-v2/owner.json)。

以下13:09及更早各节为历史状态，不代表恢复仍在运行或修复尚未落地。

## 2026-10-10 13:09 UTC：全量 pytest 已通过，FC 发布恢复中

新布局完整11269项已实际结束：11262 PASS、7 strict XFAIL、0 SKIP，
32worker、9243.12秒。完整生命周期和原生无退步门禁已通过；BPU原生
实测40039/46541，相对已发布35734新增4305行，但正式报告尚未刷新。

owner在FC合并阶段退出1，原[失败终态](../results/full-native-parallel32-role-layout-20261010-v1/exit.json)
保留。根因是四份SC参数化测试复用模块全局可变Coverage对象，每worker
多次导出同一origin的累计快照。全部1715文件的SHA检查后发现84组重复身份，
其中238份被后续快照完整支配。所有计数、schema、origin、sampling contract及
first-provenance均逐项核对单调性，不修改身份或放宽xreactor重叠守卫。

`functional-recovery-v2`仅重做后处理，不重跑硬件、不自动发布。恢复前重新
验证完整收集、七个strict XFAIL、原worker收据、十DUT分母及零命中损失，
再由原框架严格合并1477份独立导出。旧结果与恢复终态分开，不能拿pytest
通过冒充完整发布验收。见[最新状态](../results/production-parallel-migration-v6.json)。
每用例新建Coverage对象的永久修复在隔离目录通过6项便携契约，生产源码
继续冻结，尚未安装该修复。完整原目标和原功能覆盖分母均不缩减。

## 2026-10-10 10:13 UTC：目录已切换，32 进程迁移验收通过

用户明确要求停止本轮全量回归并立即调整目录。旧全量已 SIGINT 终止，
32 个 worker 已退出；保留日志、63 项已完成 PASS 和已有产物，
[中止记录](../results/full-native-parallel32-production-20261010-v2/cancelled.json)
明确标记未完成、未发布，不能作为完整通过。

正式源码现按 `bpuverify/<dut>/<role>/` 组织，公共设施放在 `common/`。
Agent、静态 Bundle、事务类型、Driver 适配、Monitor、Env、Case、Model、
Checker、Coverage 已拆分；集成 BPU 的内部组件留在 BPU 对应角色内。
`conftest.py` 只注册环境 fixture；测试支持模块不再混入 `testcase/`。
旧 `interfaces/` 测试目录改为 `bundle/`，没有新增 Interface 抽象。
详情见[目录与职责](repository-layout.md)。

生产入口在新布局下实际执行 **9996 PASS、0 SKIP、32 worker**；pytest
74.09 秒，含源码核验、收据、十 DUT native 合并与局部 HTML 的完整 owner
121.31 秒，退出 0。其中包含新增 6 项目录契约与 192 项 TAGE 流水线矩阵，
两组功能覆盖均 100%，未缩小 schema。只运行部分功能点，未执行项保留 NOT_RUN，
没有改写全量报告或声称覆盖率提升。

- [生产验收终态](../results/directory-migration-20261010/parallel-qualification/exit.json)
- [旧源码可恢复备份与迁移记录](../results/directory-migration-20261010/applied.json)
- [当前目录](repository-layout.md)

进一步的绑定／编码／解码与十 DUT 真实冒烟 **224 PASS**，完整 owner
64.13 秒、退出 0。全仓收集逐项核对：原 11263 项全部保留，加 6 项目录契约，
合计 **11269**；仅源码位置／绑定测试目录改名导致相关参数 ID 的路径变化，
没有移除场景。两批资格与新全量使用同一个 1628 文件源码 ledger：
`85817eb3989a6ea8754d743be950083b3294e0b946da3e6e4e9c832db539cb74`。

**本段为10:17 UTC启动时记录；当前已结束，终态与FC恢复见本文顶部。**
源码重新冻结；此轮仍须全部 strict XFAIL、功能点、native 无退步和 FC 合并门禁通过
才可发布，不能拿上述局部资格代替全量。

- [启动时状态](../results/production-parallel-migration-v5.json)
- [逐项保留证明](../results/directory-migration-20261010/collection-retention.json)
- [模块职责及冒烟终态](../results/directory-migration-20261010/dut-role-smoke/exit.json)
- [新布局全量 owner](../results/full-native-parallel32-role-layout-20261010-v1/owner.json)

下方 09:29 的“正在运行”描述是中止前历史状态，不代表仍在运行。

### 10:52 UTC：冻结期间的隔离后续验证

生产源码未改变，新布局全量仍在运行，正式全量报告尚未刷新。
SC 的真实非均匀 SRAM 响应证实旧 checker 延后一拍关联会误报正确数据；
隔离修复通过 2925 项模型／契约和双 bank 原生测试，完整 80-bin dirty-overwrite
矩阵、270 次 SRAM 响应、22 项原始采样故障拒绝均通过。它修复检查能力，
相对已发布基线没有新增命中的 LCOV 行，不计行覆盖率增益，也未合入本轮冻结源码。
见[隔离资格](../results/line-gap-probes/sc-response-native-v1/qualification.json)。

真实 BPU+FTQ 已生成 RTL，包括实际 Ftq、ResolveQueue、CommitQueue；独立的
memory-direct 包正在构建，不覆盖十个生产 DUT。完整 FTQ 合法性仍未证明，
见[构建记录与待验证范围](../results/line-gap-probes/ftq-memory-direct-v5/README.md)。

### 11:35 UTC：行缺口补充实验取得真实增益，生产仍冻结

此前bank2/set31、45的later-taken各18/32路径失败已通过输入节拍修复；
两项原生重跑均保持完整四way的32/32门禁，共64/64路径。256项纯输入计划
契约同时通过，不依据DUT结果筛way。独立LCOV审计发现正式46541行集合中
新增54个命中，保留在[隔离资格](../results/line-gap-probes/later-taken-resident-v7/qualification.json)，
未合入正式报告。完整256个cell的新候选已启动32worker，仍在运行，
不能以两个cell或输入计划契约替代全矩阵原生资格。

真实BPU+FTQ的MEM_DIRECT构建已实际退出0。跨页冷fetch、停顿/释放、实际
backend commit、三次commit指针环绕和重复commit不推进，共6项原生与10项
便携契约通过，206次比较。保持AsRiseWrite，以独立committed-memory视图
观察ready/reset，修复原监视提前接受；未放宽顺序断言。见
[FTQ局部资格](../results/line-gap-probes/ftq-memory-direct-v5/probe-v6/qualification.json)。
完整resolve/redirect/call-ret仍未证明；原失败、完整目标与strict XFAIL均保留。
本轮生产11269项仍用冻结源码，尚未达到全量发布终态。

## 2026-10-10 09:29 UTC：最终源码全量生产验收已启动

日常选跑与完整回归已使用同一正式入口：`python3 tests/run_all.py` 默认32进程；
`--select tests/<模块或nodeid>` 用于快速迭代，只生成局部报告，不覆盖全量报告。
生产迁移的全量发布验收仍在进行，不能宣称已完成。

此前阻止发布的四处native命中已由新的真实受检方向恢复场景补回：
`BypassShadowBuffer_1.sv:8223,8255,8287,8319` 本轮各64次；要求的
table1/slot2/fallback也独立检查并采样64次，未导入旧coverage。原有稳态
四way严格检查作为对照仍PASS。新增场景只关闭这个要求，不宣称整个选择矩阵完成。

长用例现在按确定性耗时提示优先分发，不减少用例、不改变超时或切断连续状态。
真实串行/xdist收集顺序及构建凭证契约54PASS。十DUT旧flags记录已根据成功
构建日志修正，60个包文件哈希均未改变；保留原构建时间和可恢复的原metadata。

最终1367文件源码ledger上的框架和各模块scoreboard资格为9798PASS，
pytest 34.43秒、完整owner 75.07秒。同一ledger
`8745aa46590713c2327430878278c73c7eaaf5b51f36a2429ac11ccc8267b6ca`
已启动默认32进程全仓回归，完整收集11263项。实际32个不同PID同时执行；
收集开头已是连续老化、方向恢复和final-NT长场景。源码在本轮终态与报告发布前冻结。

- [当前迁移状态](../results/production-parallel-migration-v4.json)
- [本轮全量owner](../results/full-native-parallel32-production-20261010-v2/owner.json)
- [最终源码框架终态](../results/production-parallel-final-framework-v1/exit.json)
- [四处恢复资格](../results/direction-recovery-native-v1/qualification.json)
- [构建记录修正资格](../results/production-build-provenance-correction-v1/qualification.json)

本轮仍须完成全部用例及既有7个strict XFAIL核验、worker收据、十模块native合并、
完整FC矩阵与无退步检查，最后发布报告。以下为此前记录，其中当时未解决的问题
和运行状态按历史理解，不代表本轮live状态。

## 此前的生产入口与全量验收记录

生产并行入口已经落地，不再仅有试点；**全量发布验收仍未通过**。

```sh
# 完整回归：本机默认32进程，满足所有门禁后才发布全量报告
python3 tests/run_all.py

# 日常迭代：同一入口、同样隔离，只运行指定模块/用例，不覆盖全量报告
python3 tests/run_all.py --select tests/tage/testcase/test_dual_shadow.py tests/tage/testcase/test_retained_owner.py
python3 tests/run_all.py --workers=8 --select tests/framework

# 串行诊断也走同一入口
python3 tests/run_all.py --workers=1 --select tests/tage/testcase/test_retained_owner.py
```

完整与选跑均冻结源码、独立创建worker/DUT、按run/worker/完整nodeid隔离产物，
并核对完整收集、JUnit、controller和worker receipt。选跑只验证自己的完整
collection；没有执行的功能点标记NOT_RUN，不冒充全仓通过。纯模型测试无需
伪造native或功能覆盖；没有覆盖输入时不生成虚假的覆盖HTML。

这次实际完成的全仓32进程回归为 **10900 PASS / 7 XFAIL / 0 SKIP**，
pytest耗时 **9721.89秒（2小时42分钟）**。原owner在JUnit后处理失败：参数
`SystemC::Coverage`内部的`::`被误当作测试层级分隔符。修复已进入正式脚本，
改用pytest自身的身份编码，仍拒绝未知、重复、失败、跳过或缺失用例。
旧失败receipt保留，没有假装原owner退出0。

重新核验原仿真结果时，十模块原生行分母全部不变；BPU新命中4305个源行键，
但4个旧命中未重现，因此无退步门禁阻止发布。测量为
**40035/46541（86.02%）**，旧发布值为35734/46541（76.78%）。这只是本轮
未发布的独立测量，没有把历史hit并入本轮。其余九模块命中与旧报告一致。
四处为`rtl/bpu/BypassShadowBuffer_1.sv:8223,8255,8287,8319`，历史各64次，
已定位到旧bank3/set63 final-NT原始文件并核验其归档SHA；对应上层MicroTAGE
secondEntry选择slot2的fallback路径。旧场景源码身份也匹配1218文件的历史
ledger；后来稳态residency驱动改变了方向恢复轨迹。是否为该变化的直接因果
仍需针对性复现，**没有证据把它归因于进程并行**。

另一个真实长尾已修复：TAGE dual-shadow原来一个pytest用例内循环128场景，
retained-owner循环64场景；它们均在场景入口独立reset。现在为192个参数用例，
底层driver/monitor/模型检查未改变。实测32进程 **192 PASS / 61.88秒**，
原全量运行中两个串行用例分别约944秒和507秒（不同负载，非严格串并行AB基准）。
每个贡献仍保留完整384/192-bin schema，未缩小分母；合并后分别
**384/384、192/192**，每bin恰好一次，192份证据、32个独立PID及产物哈希
重新核验通过。全量owner新增合并后完整矩阵门禁，不能用局部100%冒充整体。

最终代码通过同一正式入口再次验收：TAGE **192 PASS / 58.98秒**（pytest；
含收集、源码核对、native/FC合并和局部报告总计73.11秒），框架及scoreboard
**9715 PASS / 34.88秒**（完整owner75.50秒），无覆盖输入的纯JUnit契约
**30 PASS**、owner退出0且coverage_report为null。这三次运行使用相同的
1359文件源码ledger；未改写全量报告。完整入口耗时与pytest测试耗时分开记录，
不把后处理时间隐藏掉。

相关证据：

- [原全量pytest日志](../results/full-native-parallel32-fine-20261010/pytest.log)
- [原owner失败终态](../results/full-native-parallel32-fine-20261010/exit.json)
- [十模块native增减及四处历史来源](../results/production-parallel-native-delta-v1.json)
- [192项TAGE原始资格](../results/production-parallel-tage-matrices-v1/qualification.json)
- [真实默认入口选跑终态](../results/production-parallel-selected-tage-entry-v2/exit.json)
- [最新迁移状态与源码核验](../results/production-parallel-migration-v3.json)

功能点增长门禁也已修复：按当前verification_plan完整ID、执行状态和summary
核验，允许增加功能点，但不能删除旧点或漏跑。完整回归仍要求既有strict
XFAIL集合不变。UTAGE address scenario中遗漏的逐周期直接JSON导出已接入
`--dump-trace`开关；默认不序列化，启用后压缩导出，live checker和FC不减弱。
原全量运行发生在此修复前，不能宣称其UTAGE逐周期JSON也已关闭。

当前剩余生产验收事项：补回四处fallback路径的真实受检场景，保持现有稳态
四way严格32路径门禁；对最终源码重新完成全量回归及发布。不能拿这192项
局部成功替代全量成功，也不会通过合入旧coverage、删除点或放宽门禁来通过。
连续老化等依赖硬件状态演化的用例仍需保持连续，不做不合法的进程切片。

## 早先记录（历史观察，不代表当前live状态）

### 当前结论与使用入口

生产接入已实现，但完整生产资格尚未验收通过。两者不能混为一谈：
十模块串并行等价、32 worker 资源资格和入口契约已经通过；首次默认入口
全量运行仍需完成测试、覆盖率合并及报告发布，才能宣布生产迁移验收完成。

```sh
python3 tests/run_all.py
python3 tests/run_all.py --workers=8
python3 tests/run_all.py --workers=1
```

三条命令分别使用本机默认32进程、显式8进程和串行诊断，均走同一个正式
刷新 owner。每个 worker 独立创建 DUT，产物按 run/worker/完整 nodeid 隔离；
只合并本次 manifest 中的功能覆盖和原生覆盖，完整通过后才发布汇总。
普通回归默认不导出波形或逐周期 JSON，不需要 `/tmp` 试点依赖。

2026-10-10 07:36 UTC 实测：10907项完整回归仍在运行，32个 worker 同时活跃，
合计生命周期平均约3196% CPU，当前 RSS 86.00 GiB（不是峰值）；1354份源码身份未改变。
pytest 显示约73%，256组 five-alias 和160组 final NT 已提交 FC，但这些仅是
运行进度，不是全量通过，也不能按用例百分比线性推算剩余时间。
终态以 `results/full-native-parallel32-fine-20261010/exit.json` 为准。
07:43 UTC 再次确认 owner 与 pytest 存活，final NT 已推进到192/256组；
重新校验1354份源码仍无变化。该条是进度观察，不是终态验收。

当前优先级是完成生产并行验收，不再启动新的重型覆盖率试验来分散资源。
验收必须同时满足：完整 collection 全部执行且只有既有七项 strict XFAIL；
所有 worker 的收集身份、三阶段结果及产物 receipt 完整；十模块 native 与
本次 FC 成功合并，原生行分母不变且历史 hit 不丢失；最终报告成功发布。
已有小样本加速和局部通过均不能替代这条完整链路。

07:54 UTC 检查出另一项后续发布问题：当前脚本把功能点总数与旧报告总数
比较，导致新增已执行的功能点也被拒绝。这不影响本轮未增点的288项计划。
隔离目录中已用实际 `main()` 的无DUT夹具复现拒绝，并验证按当前计划完整
ID/执行状态校验的修订版，25项测试通过；其他运行／合并／发布逻辑AST不变。
修订版尚未迁入生产，避免改变当前冻结源码，见
[修订资格与范围](../results/production-parallel-plan-growth-staging-v1/qualification.json)。

08:05 UTC：final NT已推进到242/256组，1354份源码再次核对无变化。
构建记录的legacy flags继承问题也完成隔离修正资格：39项测试通过，含
十模块真实成功build receipt和全部六项包身份核验；修订仅在夹具中安装，
未重建、未修改任何生产DUT或冻结源码。它记录构建日志中的实际
`SIMULATOR_FLAGS`，明确不是完整Verilator argv。迁入仍等待本轮终态；见
[构建记录修订资格](../results/production-memory-direct-provenance-staging-v1/qualification.json)。

### 当前：32 worker、细粒度分发

八进程完整运行暴露了默认 xdist load 的大批次问题：10906项初始每worker
约340项，五alias单例实测约220秒，final NT约778秒。改为
`--dist=load --maxschedchunk=1`，保留xdist必需的current/next两例lookahead，
此后逐例补发，不再把数百重任务固定在一个worker。

默认并行度上限提高到32（不超过CPU亲和性核心数）。实测32个不同PID的worker
各完成2个独立memory-direct BPU，共64PASS / 24.14秒，所有receipt与native
输入计数吻合，无崩溃重启；实际cgroup线程上限629145，当前资源允许此并行度。
生产入口/证据/collect-only契约107PASS / 1.93秒。

原八进程全量已明确取消并保留证据：7333PASS、1XFAIL，pytest退出2、owner退出1，
不是完整成功，也未发布新报告。两个非试点final NT场景bank1/set16与bank2/set45
已完成严格32路径门禁；它们不代表256组闭合。替换原因是调度长尾，不是观察超时。
新的默认入口运行目录为 `results/full-native-parallel32-fine-20261010`，终态以
其中的 `exit.json` 为准。以下八进程启动记录保留为历史，不代表当前live任务。

### 前一轮：八进程入口资格

生产路径已接入 run/worker/完整 nodeid 隔离、进程内 DUT 和 native 分批合并、
controller-only evidence，以及严格 worker receipt / 文件哈希门禁。26 个模块的
155 个功能覆盖写入入口已统一路由，默认不导出逐周期轨迹。

`python3 tests/run_all.py` 统一调用完整刷新 owner，默认 8 worker；可传
`--workers=1` 做串行对照。它从本次 manifest 获取 FC/RTL，不使用历史目录 glob
或 mtime 猜测输入；完成完整收集、七项已知 strict XFAIL、十模块 native 和
功能点检查后才发布报告，并自动同步 canonical LCOV。

`pytest-xdist 3.8.0`、`execnet 2.1.2` 已系统级安装并声明到 requirements；
保留 pytest 9.1.1 版本。无需临时 shim 或 `/tmp` 依赖。

通过正式仓库 nodeid（不是试点拷贝）运行十模块 17 个真实 memory-direct 测试，
串行和四进程均为 17 PASS，分别 28.89 秒、12.75 秒，小样本约 2.27 倍。
补齐 UBTB 测试层 FC 写入与少数诊断固定路径后，系统级依赖下再次完成串行／
八进程对照，分别 17 PASS / 29.27 秒、17 PASS / 12.49 秒。十模块完整 native
点表与 LCOV 一致，全部 10 份 FC 在校验原始 snapshot digest 后，仅对隐式
UUID 双射重命名及重算派生 digest，完整语义一致；默认没有波形或逐周期轨迹。
证据：[十模块正式路径资格](../results/production-parallel-native-equivalence-v2/qualification.json)。

八进程全框架与 scoreboard 回归 **9632 PASS / 35.41 秒**，无 skip。
前一轮两个 collect-only 兼容失败已修复，并保留失败证据，没有增加 XFAIL。
证据：[完整模型回归](../results/production-parallel-model-regression-v3/evidence.json)。

已从默认 `tests/run_all.py` 启动实际 **10906 项、8 worker** 全仓刷新，输出目录
`results/full-native-parallel8-20261010`。源码纪元 1354 文件，owner PID 3071433，
pytest PID 3071435。本段启动记录不代表终态；以该目录 `exit.json` 为准。
全量尚未通过前，不声称生产资格全部完成，不增加已发布覆盖率数值。

使用方式见 [产物策略](artifact-policy.md)。下文保留 2026-10-09 试点的历史边界，
其中“尚未迁移”等状态只描述当时版本。

## 2026-10-09 历史试点

四进程试验已通过，但正式全量回归尚未启用并行。原 full、metrics、dynamic
仍绑定同一源码/运行库纪元运行，本次没有修改生产 `tests/`、`bpuverify/`、
系统 pytest、DUT 或四份正式报告，也没有重启原全量回归。

## 实际结果

隔离目录：`/tmp/bpu-pytest-parallel-jUpVZd`。`pytest-xdist 3.8.0` 和
`execnet 2.1.2` 仅安装到其中的 `deps/`，保留系统 pytest 9.1.1。

同一组现有测试分别在单进程和一个 `pytest -n 4` 会话中执行，均为
17 PASS。涉及 ABTB、BPU、ITTAGE、MBTB、RAS、SC、TAGE、UBTB、URAS、UTAGE
全部十个 native memory-direct DUT，包括已有的背靠背预测/transfer 关联检查，
以及十个模块的功能覆盖率用例；没有把驱动时序重写进测试。

并行启动了四个不同 PID，每个进程独立创建 DUT、Execution、agent、driver、
monitor 和 scoreboard。17 份原始 RTL 覆盖率与串行版本逐字节一致。
10 份功能覆盖率文件的完整语义一致：只对隐式采集 origin UUID 做双射重命名，
并按 xreactor 规则重算对应 snapshot digest；每份原始 digest 先验证，
不丢弃 schema、bin/count、provenance、diagnostics 或完整性字段。

独立契约 34 PASS，覆盖串行/xdist 汇总、同名参数用例输出隔离、collect-only
保留执行证据、setup/teardown 失败、FAIL、SKIP、XFAIL、strict/non-strict
XPASS、worker 崩溃、不一致收集，以及 FC 身份规范化/损坏哈希拒绝。
最初 crash 分类预期错误及两次 FC 等价审计失败均保留在隔离目录，没有
新增 XFAIL 或修改原始数据来隐藏失败。

本机这个小试验的总时间为串行 25.28 秒、四进程 12.29 秒，约 2.06 倍。
这是一次小样本对照，不能外推为全量回归的加速保证。
功能点只覆盖本次七个已标记 feature，另 279 个 NOT_RUN；十份 FC 的合并
不是全量功能点通过率，也不是全量覆盖率增益。

仅使用本次 controller manifest 中的 17 份 raw 和 10 份 FC，已完成全部
十个 DUT 的 native LCOV 合并和 xreactor HTML 报告；未混入旧 VPI 数据或
历史目录 glob。

证据：[只读试验摘要](../results/coverage-bpu-native-pytest-parallel-pilot-v1-readonly.json)。
完整审计和 HTML 位于隔离目录 `review_v3/`，其哈希记录在摘要中。

## 必须迁移的四个位置

1. `DutFactory` 和结果 fixture：每个 run/worker/完整 nodeid 独立目录，
   不能只用 `request.node.name` 或所有 worker 共用 `verilator-coverage.dat`。
   DUT 必须在 worker 内创建，不跨进程传递原生指针或复制已运行的 DUT。
2. pytest evidence 插件：worker 上报报告/产物清单，只有 controller 写最终
   功能点报告与 manifest。controller 不执行 collection，不能照搬当前
   依赖本进程 `_bpu_feature_nodes` 的汇总。缺 worker receipt、崩溃、收集不一致、
   缺阶段报告或产物损坏都必须失败，不能输出“空集合全部通过”。
3. 测试输出：BPU/ABTB 的 output fixture 以及 TAGE/UTAGE 等直接使用
   `REPO_ROOT/results` 的诊断、FC 写入必须统一迁入结果 fixture。
   本次仅在隔离 shim 中重定向导入用例的输出根；不将 monkeypatch 作为
   最终生产设计，也不声称所有 8197 项已完成并行迁移。
4. `tests/run_all.py`：透传 pytest 参数，并从当次 manifest 获取 FC/RTL 输入。
   当前 FC 的历史目录 glob 不适合作为并行运行的结果依据；RTL 合并还需
   明确支持 run 根/worker 子目录和完整文件身份。

先固定 `-n 4` 或 `-n 8` 做资格验证和资源测量，不直接使用机器全部核心。
本次明确 `--max-worker-restart=0`，worker 崩溃保留失败，不自动重跑。
session fixture 也会在各 worker 执行，不能把“session”误当作跨进程单例。
参见 [xdist 运行机制](https://pytest-xdist.readthedocs.io/en/stable/how-it-works.html)、
[worker 隔离](https://pytest-xdist.readthedocs.io/en/stable/how-to.html) 和
[并行分发选项](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)。

## 与流水线并发的关系

pytest 多进程并行解决“多个独立测试/DUT 同时运行”。一个 DUT 内 predict、
train、commit、redirect 的流水线重叠仍由 xreactor driver/monitor/transfer
负责，两者是不同层次。不会为了多进程而向用例暴露 asyncio.gather、
clock edge 或引脚调度，也不会让多个 worker 共同驱动同一个 DUT。

历史试点当时的下一步是将资源隔离和 controller 汇总迁入生产路径。
这些实现现已完成，当前待完成的是上文首次全量生产验收；历史试点本身
仍不是正式覆盖率 current 的依据。
