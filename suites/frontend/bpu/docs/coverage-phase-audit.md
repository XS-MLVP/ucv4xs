# 覆盖率插桩相位与工具版本审计

本次审计区分三件事：RTL 行为、插桩计数是否正确、计数怎样映射到源码行。
它们不能只靠一个覆盖率百分比判断，也不能把低计数一律当成缺少测试。

## 可重复的相位复现

入口为 `python3 -m bpuverify.common.coverage.phase_audit`，结果为
`results/coverage-phase-audit.json`。它原样编译 `rtl/tage/WriteBuffer.sv`，
通过正常端口写入，内部寄存器和条件仅只读观测，不改 RTL、不改正式 DUT、
不改正式 `.dat`。准备后清零的是独立诊断模型的计数，不是正式回归数据。
`tools/coverage_phase_repro.cpp` 是编译器诊断夹具，不是 BPU pytest 用例；
正常用例仍通过 agent/driver/monitor 驱动，不暴露边沿调度。

准备目标 A 在 row 1，邻项 C 在 row 0。从 port 0 更新 A 时应跨 row 命中：

| 序列 | A 的实际变化 | 应记录的跨 row 更新 |
| --- | --- | ---: |
| 单笔 | 4→5 | 1 |
| 两笔相邻 | 4→5→6 | 2 |
| 两笔间隔 | 4→5→6 | 2 |
| A 后切换到 C | 4→5→5 | 1，第二笔不得增加 |
| 到达饱和后再更新 | 6→7→7 | 2，其中一步保持 |

C 的 tag 和 counter 始终应保持。每一笔后额外保存原始 counter 快照，
防止末尾总数碰巧相同却把 C 的执行误记成 A 的命中。

复现命令：

```sh
PYTHONPATH=/usr/local/share/picker/python python3 -m bpuverify.common.coverage.phase_audit \
  --verilator /opt/verilator5/bin/verilator \
  --verilator /opt/verilator-5.052/bin/verilator \
  --o0-control --output results/coverage-phase-audit.json
```

Verilator 5.026 `-O3` 五种逐笔检查均失败：单笔/间隔执行漏计，切换目标时
计到上一拍条件。其生成代码先读取 `_GEN_66` 等 automatic 临时条件更新
coverage counter，再计算本拍条件并执行真实寄存器更新。5.026 `-O0`
对照及 5.052 `-O3`/`-O0` 均为五种检查通过，实际寄存器结果一致。
这解释了合法反馈已经跨 row 转发，但旧 `.dat` 对相应分支仍为零。

此证据针对该最小复现，不宣称新版全部插桩都已证明正确。行覆盖原理参见
[Verilator 官方说明](https://verilator.org/guide/latest/simulating.html#line-coverage)。

## 编译器与处理器分开对照

`results/coverage-toolchain-factorial-tage.json` 使用完全相同的 TAGE RTL、
40 份现有测试原始文件集合，做四组对照；测试节点集合经过逐名核对。
这些是隔离结果，不冒充完整正式回归刷新。

| DUT 插桩编译器 | 原生 coverage 处理器 | 命中／映射源码行 |
| --- | --- | ---: |
| 5.026 | 5.026 | 5336/5653 |
| 5.026 | 5.052 | 5361/5653 |
| 5.052 | 5.026 | 4257/4587 |
| 5.052 | 5.052 | 4311/4587 |

处理器对共享条件锚点的归并方式不同；编译器对 branch 与 `S` span 的映射
也不同。即使关闭新版新增的 expression/FSM coverage，映射分母仍会变化。
因此不能把 `5653→4587` 宣称为关闭 1066 个缺口，也不能直接比较两百分比。

精确坐标交集为 3743 行，其中旧命中 3426、新命中 3471。
旧零计数中 65 行现为真实正计数，旧正计数中 20 行现为零；还有四个新映射
的未命中行。1910 行只在旧映射、844 行只在新映射，这两类单列而不计为提升。
旧 317 个缺口没有因新映射而消失；已有 88 个局部不可达赋值仍为零。
新增顶层缺口包含 alternate 选择、selector 高 bucket 和训练 counter 分支，
应结合有效分支资格及可观察行为继续分析，而不是仅发送无效 slot 来刷数。

## 正式报告与恢复

新包保留 `build-provenance.json`，记录插桩编译器、选项、原生处理器路径、
原始 export 目录、主 RTL 与信号结构指纹。`bpuverify.common.coverage.rtl` 校验
指纹并选择该包记录的处理器；报告把编译器与处理器分开记录。
历史包缺少来源时不冒称 PATH 上的处理器就是它的插桩编译器。

picker/xcomm/RTL 源码分支未切换，系统默认 Verilator 未修改。
新包使用已有 `/opt/verilator-5.052` 安装，关闭新增 expression/FSM 项，
启用 VPI；所有 RTL 与端口结构均与原包一致。旧包当时保留在
`/tmp/bpu-coverage-v5052-26DlAX/backup-dut/`，旧报告在同目录的
`reports-before/`。这两个过时临时副本已按用户要求于 2026-10-10 删除，
不再提供恢复能力；清单见 `results/tmp-scoped-cleanup-v3.json`。

正式安装与 staging 校验见 `results/dut-coverage-toolchain-refresh.json`。
是否已完成正式刷新要核对其中状态、本次 pytest manifest、LCOV 和 HTML，
不能仅靠 staging PASS。新旧基线及映射差异都应保留，局部不可达行不手动
从任何一次原生分母中剔除。

同工具链基线先由 TAGE-031/032 同拍双写／省写门控矩阵刷新：
553 PASS、6 strict XFAIL、0 SKIP，TAGE 4341/4587、v_line 96/132、
分支 1424/1598。与上一轮 4335/4587 比较恰关闭六个 WriteBuffer 行，
源码、处理器、分母和其他九 DUT 指标不变；不是新旧编译器映射差带来的提升。
324 份当次 raw 与十份原生 LCOV、JSON、HTML 的时效和一致性见
`results/coverage-tage-mixed-writes-refresh-audit.json`。局部证明仍保留全部
112 个未命中赋值于原始分母；另外 134 行未分类。

下一阶段基线由 TAGE-033 相邻／间隔饱和转发对照刷新：580 PASS、
6 strict XFAIL、0 SKIP，TAGE 4344/4587、v_line 96/132、分支 1426/1598。
与上一轮同工具链数据相比恰关闭 WriteBuffer 844/845/888，其他九 DUT
及映射分母不变；243 行缺口中仍有 112 行局部分类、131 行未分类。
完整时效、325 raw、十份 LCOV/JSON/HTML 一致性和局部守卫复核见
`results/coverage-tage-overlapped-saturation-refresh-audit.json`，586-item
collect-only 保护见 `results/coverage-tage-overlapped-saturation-collection-protection.json`。

上一轮同工具链基线由 MainBTB-020 双 key counter 排队/跨 bank 直通矩阵刷新：
632 PASS、6 strict XFAIL、0 SKIP；247/247 功能点执行、241 PASS，140 个功能组
聚合 99.45%。MainBTB 840→851/1056（80.59%）、v_line 仍 29/38、分支
317→332/442；关闭 queue/RAM 四行和替换状态七行，其他九 DUT 和映射分母不变。
326 份本次 raw、139 功能 JSON 和十份 LCOV/JSON/HTML 一致；SC 336 个局部
矛盾行、TAGE 112 个局部分类行和 131 个未分类行均复核且不扣分母。
完整审计见 `results/coverage-mbtb-counter-pending-refresh-audit.json`；638-item
collect-only 保护见 `results/coverage-mbtb-counter-pending-collection-protection.json`。
该阶段 MainBTB 205 行缺口继续审查；entry 同 key pending 目标改写的 16 组候选临时
再关闭六行，证据保留在 `results/coverage-mbtb-entry-retarget-readonly.json`，
未纳入此正式主表，也不代表目标已完成。

上一阶段 MainBTB-021 正式交叉低/高 set、四 bank、双 way、阻塞/直通及三种
carry 变化，共 96 组合、288 个断言后 phase cross bin。726 PASS、
6 strict XFAIL、0 SKIP；248/248 功能点执行、242 PASS，141 组聚合 99.45%。
MainBTB 851→857/1056（81.16%）、v_line 29→31/38、分支 332→348/442；
恰关闭六个 WriteBuffer 行，其他九 DUT 的指标与未覆盖集合、源码/工具/分母不变。
327 份本次 raw、140 功能 JSON 和十份 LCOV/JSON/HTML 时效/一致性通过；
SC 336、TAGE 112 个局部分类行继续复核，131 个 TAGE 未分类行保留。
五个普通 FAIL 负对照带 request/accepted_tick/observed_tick/status，无清理错误。
完整审计见 `results/coverage-mbtb-entry-retarget-refresh-audit.json`；732-item
collect-only 保护见 `results/coverage-mbtb-entry-retarget-collection-protection.json`。
MainBTB 199 行缺口仍需审查。不同 key 双 pending entry 的 32 组候选临时
再关闭 20 行，见 `results/coverage-mbtb-entry-two-keys-readonly.json`，不计正式主表。

上一阶段 MainBTB-022 将不同 key 双项保留交叉低/高 set、四 bank、双 way、阻塞/
直通、双向反馈顺序及三种目标 region 配对，192 组合、576 个断言后 phase
cross bin。872 PASS、6 strict XFAIL、0 SKIP；249/249 功能点执行、243 PASS，
142 组聚合 99.45%。MainBTB 857→877/1056（83.05%）、v_line 31→32/38、
分支 348→351/442，恰关闭第二槽 20 个 WriteBuffer 行；其他九 DUT 指标与
未覆盖集合、源码/工具/分母不变。328 份本次 raw、141 功能 JSON 与十份
LCOV/JSON/HTML 时效/一致性通过；SC 336、TAGE 112 个局部分类行继续复核，
131 个 TAGE 未分类行仍保留，不扣分母。六个普通 FAIL 负对照有完整上下文，
没有超时、teardown 或未取回 task 错误。完整审计见
`results/coverage-mbtb-entry-keys-refresh-audit.json`；878-item collect-only 保护见
`results/coverage-mbtb-entry-keys-collection-protection.json`。
正式 MainBTB 仍有 179 行缺口（WriteBuffer 126、ReplacerState 53）。跨 way
shadow 和全替换索引两项隔离候选分别关闭 44 和 53 行，均未计此正式主表；
见 `results/coverage-mbtb-crossway-shadow-readonly.json` 与
`results/coverage-mbtb-replacer-index-readonly.json`，不代表整个目标已完成。

上一阶段 MainBTB-023 用独立 LRU 区分 captured-cold 请求 victim 与 retained
shadow owner，192 个上下文/bank/owner/clean-dirty/mode/carry 组合、576 个
断言后 phase/status cross bin。1124 PASS、6 strict XFAIL、0 SKIP；250/250
功能点执行、244 PASS，143 组聚合 99.46%。MainBTB 877→921/1056（87.22%），
v_line 32→36/38、分支 351→365/442，恰关闭 44 个 WriteBuffer 行；其他九
DUT 的指标与未覆盖集合、源码/工具/分母保持。329 raw、142 功能 JSON 和
十份 LCOV/JSON/HTML 时效/一致性通过；SC 336、TAGE 112 个局部分类行及
131 个未分类行继续复核且不扣分母。六个负对照均带上下文普通 FAIL，无
超时或清理错误。审计见 `results/coverage-mbtb-shadow-refresh-audit.json`；
1130-item 收集保护见 `results/coverage-mbtb-shadow-collection-protection.json`。
此正式 PASS 只覆盖初始 counter-2 居民。另一 tag 的条件邻项为 counter=3
时，16 个有序模块诊断均观察到 3→2，而 entry owner/目标/时序正确；异常
raw 保持隔离，未登记 PASS 或 blanket XFAIL，完整 FTQ/redirect/资格仍待
审查，见 `results/coverage-mbtb-shadow-counter-side-effect-readonly.json`。
该阶段仍缺 WriteBuffer 82、ReplacerState 53 行；40 个双写复制赋值不能仅因
训练 one-hot 而划为不可达，flush 另一路 valid 必须纳入前提，见
`results/coverage-mbtb-flush-overlap-source-readonly.json`。目标仍未完成。

上一阶段 MainBTB-024 将 PC[9:4] 的替换状态与 PC[10:5] 的 SRAM set 分开，
在同一次复位后保留目标、set+32 alias、邻接索引和另一 align 的居民。
64 索引 × 两 align × 两 set 高位 × 四种 touch 共 1024 组合；正常 conditional
taken 2→3 且更新 LRU，实际 NT mispredict 2→1 而不更新 LRU，读取不 touch，
新分配 reset counter=2。独立 indexed LRU 与完整 profile 正反异步比较
通过后，6144 个 phase cross bin 闭合。112 项纯检查及七个普通 FAIL 负对照
通过；原 direct 试验刷新因后端资格检查主动停止，中断报告单独保留，
conditional 版本重新完整运行。
1237 PASS、6 strict XFAIL、0 SKIP；251/251 功能点执行、245 PASS，144 组
聚合 99.46%。MainBTB 921→974/1056（92.23%），分支 365→418/442，v_line
仍 36/38，恰关闭全部 53 个剩余 ReplacerState 行，无新行缺口。其他九 DUT
指标/缺口集合、源码/工具/分母及六项 XFAIL 不变。330 raw、143 功能 JSON
和十份 LCOV/JSON/HTML 时效/一致性通过；SC 336 与 TAGE 112 个局部分类
行和 131 个未分类行均复核且保留原始分母。审计见
`results/coverage-mbtb-replacement-refresh-audit.json`，1243-item 收集保护见
`results/coverage-mbtb-replacement-collection-protection.json`。
MainBTB 仍缺 82 个 WriteBuffer 行；counter 诊断需要真实 FTQ pointer/epoch/
redirect/train.fire 见证，tag=0/position=0 与 flush key 的边界也仅有源码
依据，分别见 `results/coverage-mbtb-ftq-qualification-source-readonly.json` 与
`results/coverage-mbtb-zero-tag-source-readonly.json`。不记额外 PASS、blanket
XFAIL 或不可达，不代表整个目标已完成。

上一阶段 MainBTB-025 用正常双 key 反馈与真实读压力填充 depth 0/1，静态只读
Bundle/@on Monitor 证明 depth 1 的 retained owner；独立预期区分 entry owner
与 request-way counter 初始化。32 组合、23 项手算纯检查、六个普通 FAIL
负对照和双 key 正反异步完整 profile 回读通过后，96 个 cross bin 闭合。
1261 PASS、6 strict XFAIL、0 SKIP；252/252 功能点执行、246 PASS，145 组
聚合 99.47%。MainBTB 974→1016/1056（96.21%），v_line 36→38/38、分支
418→426/442，恰关闭 42 个 WriteBuffer 行；其他九 DUT 的指标和缺口集合、
源码/工具/原始分母不变。331 raw、144 功能 JSON 和十份 LCOV/JSON/HTML
同源/时效一致；SC 336 与 TAGE 112 个局部分类行及 131 个未分类行继续
复核并保留分母。见 `results/coverage-mbtb-depth-one-refresh-audit.json`；
1267-item 收集保护见 `results/coverage-mbtb-depth-one-collection-protection.json`。

025 阶段正式剩余 40 个双写复制行，未分类为不可达。清理独立诊断有 256 组合、
192 PASS、64 个零 tag/位置零错 owner 的普通 FAIL，四 bank 均复现；64 例
真实同拍训练/flush。排空后其他 set 更新保留，首次旧值为 pending 写回。
通过诊断的数据可再命中 20 行至 1036/1056，但不计正式覆盖；见
`results/coverage-mbtb-flush-key-expanded-readonly.json`。诊断入口为
`python3 tests/mbtb/diagnostics/run_flush_key_probe.py`，输出隔离并保护正式报告。
完整 FTQ pointer/epoch/resolve/redirect 资格未证明，未登记新的 PASS/XFAIL，
也不宣称 overflow、任意饱和邻项或整个目标完成。

最新 MainBTB-026 正式覆盖 dirty/clean 清理与训练双写：四 bank × training
depth 0/1 × 两种清理 shadow 状态 × 三种非联合零 key，共 48 组合。
完整输入、两端口 payload/read 资格、全 shadow 前后状态、四周期延迟及
双 set 完整 profile 正反流水线回读均独立比较，144 个 cross bin 断言后闭合。
21 项纯模型/scope 检查通过，八个带 request/tick/status 的普通 FAIL 负对照
有效，没有超时、清理或未取回任务错误。
1283 PASS、6 strict XFAIL、0 SKIP；253/253 功能点执行、247 PASS，146 组
聚合 99.47%。MainBTB 1016→1056/1056（100%），v_line 38/38、分支
426→434/442，恰关闭剩余 40 个 WriteBuffer 映射行，无新行缺口。其他九 DUT
指标/未命中行集合、源码/工具/原生分母及六项 XFAIL 不变。332 raw、145
功能 JSON 与十份 LCOV/JSON/HTML 同源/时效一致，SC 336 与 TAGE 112 个
局部分类行及 131 个未分类行复核且保留分母。正式审计见
`results/coverage-mbtb-cleanup-overlap-refresh-audit.json`；1289-item 收集保护见
`results/coverage-mbtb-cleanup-overlap-collection-protection.json`。

MainBTB 剩余八个分支由实际父模块连接、16 格布尔对照及四项源码变异负对照
分类，见 `results/coverage-mbtb-branch-unreachable.json`；raw/分母原样保留。
这项证明只涉及清理 mask 的常零 bit 及 counter queue RAM 的恒一读使能，
不是所有功能组合的证明。新的隔离路由诊断在一个 bank 的更早训练偏移观察到
联合零 key 下另一 set 更新丢失，排空后仍旧值；见
`results/coverage-mbtb-cleanup-routing-readonly.json`。它不同于旧 delay 0/1
诊断中的 pending 首读，未计正式 PASS/XFAIL，完整 FTQ 资格仍未证明。
整个覆盖率目标仍未完成，其他模块和已发现缺陷继续保留。

## TAGE-034 retained owner 正式刷新

请求 physical way 与 retained shadow owner/depth 分离的四 bank × 双向 owner ×
四 depth × pending/clean 共 64 组合正式通过；独立输入、完整 shadow 周期和
正反流水线完整居民状态比较后，192 个 cross bin 闭合。117 项纯检查及八个
带 transfer/接受/观察时刻的普通 FAIL 负对照通过；无超时或悬挂任务异常。
完整回归 1401 PASS、6 strict XFAIL、0 SKIP，254/254 功能点执行、248 PASS。
TAGE 4344→4397/4587（95.86%），v_line 96→105/132，分支 1426→1472/1598；
恰关闭 53 行且无新缺口。其他九 DUT 的指标及缺口集合、源码/工具/原始分母、
六项 XFAIL 不变；本轮没有重建或修改 RTL。
333 raw、146 功能 JSON、147 组和十份 LCOV/JSON/HTML 同源/时效一致，
147 组聚合 99.47% 仍不等于行覆盖率或功能点通过率。SC 的 336 个局部矛盾
赋值复核；TAGE 112 个局部矛盾赋值加八个同条件块头仅分类，不补造命中、
不扣分母，正式剩余 190 行中 120 行局部分类、70 行未分类。
详见 `results/coverage-tage-retained-owner-refresh-audit.json`；刷新后 1407-item
收集保护见 `results/coverage-tage-retained-owner-collection-protection.json`。
后续双端口诊断及其候选行增量不是本次正式覆盖；FTQ 资格、其他模块缺口
和已知六项 RTL 缺陷仍未闭合，整个目标尚未完成。

## TAGE-035 同拍独立双写正式刷新

四 bank × 四 depth × 八种 owner/pending/clean/companion 状态共 128 组合；
同一 prestate 独立解析两写、drain 一次，独立输入/完整 shadow 周期及正反
流水线完整居民状态比较后，384 个 phase cross bin 闭合。509 项纯检查和
十个带请求/接受/观察时刻/状态的普通 FAIL 负对照通过。
完整回归 1911 PASS、6 strict XFAIL、0 SKIP，255/255 功能点执行、249 PASS。
TAGE 4397→4467/4587（97.38%），v_line 105→116/132，分支1472→1513/1598；
恰关闭 70 个 WriteBuffer 行，无新增缺口。其他九 DUT 的指标/缺口集合、
源码/工具/原始分母及六项 XFAIL 不变，本轮未重建或修改 RTL。
334 raw、147 功能 JSON、148 组和十份 LCOV/JSON/HTML 同源/时效一致；组
聚合 99.48% 不是行覆盖率或功能点通过率。993 份运行源码身份一致，SC336、
TAGE 剩余112赋值+8块头、RAS16赋值及 MainBTB8分支的源守卫证据复核，
全部保留原生分母。审计见 `results/coverage-tage-dual-shadow-refresh-audit.json`；
1917-item 正常收集不改新版四报告，见
`results/coverage-tage-dual-shadow-collection-protection.json`。

正式 RAS 仍520/585。完成的这份新鲜基线随后允许验证 RAS 整合候选：只合并
16份本轮正式 RAS raw 与三份实际候选正向 pytest raw，候选精确关闭45行至
565/585，无新缺口；剩余16个分类赋值和4个待 FTQ 资格的 bos 行，不扣分母。
170项候选pytest、25项普通FAIL负对照与旧RAS15PASS/1原strictXFAIL均通过，
见 `results/coverage-ras-integration-candidate-readonly.json` 及
`results/coverage-ras-candidate-legacy-readonly.json`。候选尚未迁入仓库或注册
功能点，不能计正式覆盖。ABTB/BPU/MicroTAGE 缺口、六项缺陷和 FTQ 资格
仍未完成，整个目标保持进行中。

## RAS-013/014/015 仓库迁入与刷新门禁（运行中）

前节候选随后已迁入现有 `RasAgent`，不是临时子类：公开 `RasOperation`、
相邻 `act_many()`、完整 committed 被动观测及 `restore/recover(cfi_pc=...)`。
独立模型、静态 Bundle/@on Monitor 和覆盖定义放入 `bpuverify`；测试只组织
场景与比较，不暴露边沿/get-set/asyncio gather。覆盖定义不反向依赖测试刺激。
登记 BPU-RAS-013/014/015，计划增至 258 点，当前最新已审计正式报告仍为
255 点和 RAS 520/585，不能提前称作正式 PASS。

实际仓库函数与实际 `tests/ras` fixture 的隔离测试 170 PASS，含 167 项纯模型/
能力/缺 bin 检查及三项硬件入口的 16/27/24 组合；6700 个完整观测周期、
36339 项比较与独立重放证据一致。25 项观测/返回数组负对照均为带请求/
观测时刻/状态的普通 FAIL；旧 RAS 保持 15 PASS/1 原 strict XFAIL。
初版旧测试 wrapper 误把 driver/monitor/interface 文件放在 testcase 下，收集失败
日志保留；修正独立 wrapper 后通过，没有改旧测试断言或伪装 DUT 缺陷。
登记后所有正向、旧用例和 25 项负对照已在新输出目录重跑通过。
冻结的 16 份正式 raw 与三份实际仓库正向 raw 隔离合并，精确关闭 45 行至
565/585，无新缺口；三个覆盖组的 16/27/24 个 bin 均经比较后各命中一次。
见 `results/coverage-progress-ras-state-scenarios-registered.json`。

2087-item 正常收集保持四份正式报告字节不变，见
`results/coverage-ras-state-scenarios-pre-formal-collection.json`。完整 pipeline
于 2026-10-08 02:19:29 UTC 启动，冻结 1004 份运行源码，仍在执行；日志和
终态保存在 `/tmp/bpu-ras-formal-sbopyX`。结束后必须独立审计 337 份新鲜 raw、
150 份功能 JSON、151 组、十份 LCOV/JSON/HTML、六项原缺陷及其他九 DUT
指标/缺口集合；这些是待验证门禁，不是本段已经获得的正式结果。
旧缺口分析同时绑定了旧 `ras.py` 身份，新源证明明确核对保存的正式旧哈希与
已通过实际仓库门禁的新哈希，逐项复核未改变的 RTL 条件与源变异对照；初次
历史身份冲突日志保留，不改写旧证据。源证明 v2 预检已通过。

剩余四个 bos 行的新端口诊断另已通过：四个 predicted indirect Push 与实际
Pop/PopAndPush 不同的序列，全部用真实捕获的 pre-operation metadata 和非零
退休 action，不伪造 actionNone commit。静态只读观测检查完整输入、注册提交
延迟、bos 与 committed 存储；独立重放和八个精确源条件变异对照通过。
在临时目录合并该 raw，候选再关闭 RasStack.sv:598/600/601/602 至 569/585，
没有新缺口，原生分母保留。见 `results/coverage-ras-bos-nonpush-port-readonly.json`。
它仅证明端口行为：IFU 在合法/taken/非 invalid 的条件下及后端在 target 正确/
无 fault 时不要求 RAS action 相等；尚未实例化 IFU/FTQ 或证明真实 BPU alias/
陈旧属性、正确 target 执行与按序退休的完整轨迹，故不计正式覆盖或新功能
PASS/XFAIL，也不并入本轮完整刷新。目标仍未完成。
