# 集成 ABTB：从行缺口提取功能点与场景

## 拟新增集成功能点：仅草案，未修改当前288点计划

建议新增BPU-INT-057：SC满dirty miss替换及old-drain/SRAM语义；基本物理
cross80bins，当前9/80。建议新增BPU-INT-058：真实SC-used反馈的读/更新
分流及完整流水状态；基础cross24bins，当前3/24，两方向/置信度/有效历史/
阈值边界等扩展仍必须完成。两点均是PARTIAL，不登记PASS。

现有BPU-INT-022已经验证训练后公开useScPred=1，不能说从未观察SC-used；
但它反复使用初始unused metadata，并未把新鲜used metadata送回去检查
三种读/更新分流。INT-039/040/041明确排除full-dirty，INT-041还明确限定
non-SC-used；单体SC-021/022的阈值检查不能替代集成完整十buffer/流水检查。
见[精确功能点缺口与草案](../results/coverage-bpu-sc-missing-feature-inventory-v1-readonly.json)。
冻结纪元结束后才可晋级生产代码/计划并重跑全量，当前288及旧279/286不变。

## SC 功能覆盖与真实 used 分流：2026-10-10 08:14 北京时间

满dirty覆盖的完整物理cross已独立导出：两bank×五表×四victim×有/无同拍
drain，共80bins。190契约实际PASS；从已审计1950帧的原始preedge和下一
checked rising独立核对完整四槽、旧PLRU victim、旧drain payload及写优先，
确认9事件=9个不同bin，9/80=11.25%，仍缺71。九个真实victim数据扰动均
被拒绝。不是按事件数缩减分母，也未合入旧197组均值。见
[满dirty功能覆盖](../results/coverage-bpu-sc-full-functional-v1-readonly.json)。

两个新SC-used真实DUT由xdist双进程隔离，19意图契约/2DUT实际PASS：
各自6笔真实训练后，用新鲜公开metadata自然达到useScPred=1，未伪造metadata
或写内部状态。939+1110=2049帧；bank1/way1观察到used正确且TAGE同意
不读/不更新、used正确但不同意读/不更新、used错误读/更新三个分流。两个
场景最后阈值均1130/1125/1130/1130。见
[原生SC-used](../results/coverage-bpu-sc-used-native-v1-readonly.json)。

独立审计v1因自己把T1 gated qualifier查晚一周期而实际失败；完整失败和
冻结源码保留。v2用两份真实轨迹重现旧错误并修正关联：T0在接受tick-1
的controls、T1在tick+1有效，不能拿tick+3已清零门控当T1。13契约通过；
四进程完成全部2049帧reset重放和74原始故障检查，精确失败拍/context/status
均核对。基础used cross为两bank×四way×三分流，实际3/24=12.5%，不是整项
deep SC-used闭合；两方向、provider置信度、有效非零历史等仍须扩展。见
[完整SC-used审计与FC](../results/coverage-bpu-sc-used-complete-audit-v2-readonly.json)。

SC-used原生行增量的29契约通过，13份签名历史快照与两次新coverage重合并，
Python/独立AWK一致额外0行，累计候选仍3802、并集36066/46541，正式仍
32264/46541。这再次说明旧行命中不能代替功能检查证据。见
[SC-used行测量](../results/coverage-bpu-sc-used-native-line-v1-readonly.json)。

上述新SC所有owner实际terminal0且句柄关闭；没有重跑DUT或删除证据。
30份冻结账本已检查0；生产1218源码、350RTL和runtime未修改。原full/serial
2655665/2655922仍实际存活96%，parallel261已0，repair/matrix等待同一链。
288登记点和旧279/286正式通过数分开；formalcurrent=false，完整目标不缩减。


2026-10-10 07:54：SC满dirty pilot的完整1950帧reset/69原始故障审计已通过，
独立原生行测量额外0行。功能点与行覆盖必须分开：旧行命中不能代表victim
选择、同拍优先级和被覆盖数据的正确性已验证。9个覆盖事件仍需映射到全
两bank×五表×四victim×有/无drain的功能bin，不能从事件次数反推全交叉覆盖。

## 2026-10-10 07:46：SC 满 dirty 与物理 way 的功能需求补充

SC WriteBuffer的满行miss是合法dirty覆盖，不应由参考模型直接拒绝。功能点
应验证：从reset独立维护四槽和PLRU、oldest-dirty先drain、满行用旧PLRU选
victim、write覆盖同槽dirty清除、部分mask合并保留其他lane、覆盖后的真实
SRAM和公开预测保持一致。必须保留两bank×五表×四victim以及同拍有/无drain
的物理交叉，不能只统计请求总数；零CommonHR的三表pilot不代替五表范围。
PLRU命中是否touch须据实际生成RTL核实，此构建是miss-only。

新五key场景已经实际观察9次覆盖并检查公开读回，但不因此登记全部功能点
通过。独立原始重放/故障、原生行增益与全范围FC仍需完成。刺激规划也必须
联合检查TAGE与MainBTB：仅MainBTB最多两resident不足以保证冷provider。
旧0x80间距第五key发生真实TAGE cross-position tag别名；新0x40间距保留
全部五key和原有检查，2063契约实际通过、真实DUT通过。

SC-used另外需要真实metadata的三种分流：used正确且同TAGE→不读/不更新；
used正确但不同TAGE→读而不更新；used错误→读并更新；再与非used的低/高
置信度、阈值净投票/上下界保持、相邻accepted feedback交叉。2048布尔模型
契约与phase通过都不等于这些真实used场景已经命中。

ABTB later-taken v2的29288帧只覆盖way0/3的16路径，way1/2缺16条；保留
完整32条要求及12288全矩阵分母。不要因五alias均运行就认定四way均被训练。
negative-overlap因前置owner失败尚未启动，资源排序与语义依赖需要区分，
不能以等待器/模型资格替代真实重叠覆盖。

2026-10-10 06:52 北京时间：独立审计v2已205契约PASS。补充“多个预期
故障的异常状态隔离”运行器回归：直接执行真实owner的35反例循环，
两原因各复现旧累计failed==2问题，新版各35例均独立failed==1并带
差异/事件/字段上下文。此处修的是审计执行器，不是新RTL覆盖；旧
等待器无DUT/子进程时停止，保留源码日志。真实负向DUT继续等待同一
原链终态，新增bin仍0，288登记点/旧279通过及完整需求保持不变。

2026-10-10 06:40 北京时间：针对真实负向reset-overlap已补齐独立完整
审计入口，201契约实际PASS。将“提交不暂停预测”从刺激声明提升为
source到反馈实际接收拍的逐帧ready核对，并独立验证完整metadata来源、
反馈payload、后续MainBTB2→1及最终S3选择；两原因不能相互抵扣。
见证按同cell和下一checked rising确认。before3虽然reset与递减数值
同为2，也属于真实重叠，不以必须产生数值差异作为过滤器。每原因35
关联反例及完整raw/export故障已接入运行门禁。真实DUT仍按资源顺序
等待现有链终态，实际新增bin=0；288登记点、旧279/286通过数不变，
全256×四way×双原因×四原值及完整原始目标继续保留。

2026-10-10 06:18 北京时间：四way第一层独立重放/故障已实际整体0，
29184帧/32正向与final-NT物理路径；完整parent刚开始执行，仍不能替代
全256与later-taken。为缺失的负向reset-overlap新增公开driver流中反馈
场景，1149契约已通过：两原因独立、全256各五alias、20/25个实际条目
key和双way容量，完整非零52位历史及旧两拍索引；真实setup/prime协程
也已执行，且原生transfer取消不会撤销已接受任务。DUT入口要求实际
同cell负向/write-reset命中才导出，不用正向或相反原因代替。
其DUT尚未派发，完整独立审计调度待补，新增负向重叠覆盖仍为0。
这属于补齐可执行刺激能力，不改变288登记点和旧279/286正式通过数。

2026-10-10 05:54 北京时间：四way final-NT真实DUT已1 PASS，选定
bank1/set0的32条强制物理路径均命中，但完整独立重放/故障与原生行测量
尚未终结，不能登记为全256/双原因闭合。稳定长循环无reset重叠；
五份既有完整轨迹独立盘点只确认65次same-position-taken、原值2/3的
reset优先事件。故“写回与反馈有overlap”必须拆出反馈原因和原值覆盖，
现有65次不能抵扣final-NT/later-taken及0/1的缺口。

later-taken live-v1在尚未启动DUT时发现真实方向协程未定义变量问题，
六种协程切换实际复现；旧等待器退出143，源码和日志保留。新v2仅改
counter<goal这一判断，并增加22项执行协程/拒绝错误响应的回归，
完整497 PASS后继续等待同一前序parent。模型/过滤器通过不等于真实
协程执行通过，更不等于DUT可达；新增功能点必须保留完整证据链。
当前288登记点、旧279/286正式通过数及完整需求均不因此提前改变。

2026-10-10 05:19 北京时间：依据低way新增行证据，五alias十节点场景现已
通过388模型/强制物理路径契约并运行真实DUT；要求四物理way分别具有四种
递增及四种final-NT递减/保持，共32个实际路径，不用alias代替物理way。
完整parent的70契约、原生/AWK入口的32契约已通过并按真实pidfd排队。
尚无该DUT/完整审计终态，当前288登记点与旧279/286正式结果不变；later-
taken双条目、全256坐标、真实写反馈overlap等完整需求没有被缩减。

2026-10-10 04:52 北京时间：十节点单alias final-NT已经完成真实DUT、全部
独立状态/parent/写回/direct/SRAM/读回关联及故障审计。bank1/set0/way0
八路径均有实际完整状态见证，原生/AWK另确认相对旧候选并集新增9行，
其中3行为该cell的递减路径；潜在候选3774→3783，未准入正式报告。
这是“全部状态都比较了”之外确实需要补充物理路径激励的例证；它仍不是
全四way/所有bank-set/两类递减原因的闭合，也不改变当前288登记点。

2026-10-10 04:49 北京时间：新十节点final-NT probe第一层独立审计已整体0，
9counter/8导出/76direct故障全部拒绝；完整parent和原生行增益仍待完成。
另有later-taken纯输入规划v2实际291 PASS，覆盖全256坐标、五alias、双
真实MainBTB条目的容量与唯一key，并验证taken=1/position7确实更新完整
非零PHR及指针，和final-NT的历史保持分开。初版三个非零bank/set0容量
冲突已在新副本通过peer合法地址规划修正；旧失败保留。它尚无DUT证据，
不能因模型通过就认定四way/双原因路径闭合。原并行261 DUT PASS，串行
仍live；288登记点与旧279/286正式结果继续区分。

本文件记录从行缺口提取的完整需求，不是新增 PASS 清单。2026-10-10
04:32 北京时间更新：当前计划已登记 288 点，新增 BPU-INT-055/056；
完整收集为 10370 项。上一轮已审计结果仍是 279/286 功能点 PASS、
BPU 原生行 32264/46541；新全量及独立审计未完成，不能把登记当 PASS。
055 只声明全 256 bank/set 的正向五 alias 分配/四 way 复用；056 只
声明五个明确坐标的真实 final-NT 场景，不声明所有 cell 的双原因迁移。

物理 counter 收集器已进入生产，完整路径分母 12288、write-reset
1024、reset 优先级 12288 均保留。新十节点、单 alias 自然循环的隔离
DUT 实际 1 PASS，bank1/set0/way0 八条正向/final-NT 路径通过 live 检查；
独立完整重放及故障审计仍在运行。它不证明 way1/2/3、全 bank/set、
later-taken 或真实 reset-overlap 已闭合。所有新增实验与正式产物隔离。
以下过程记录保留各自历史时点，不将旧 8254 项/286 点称为当前计划。见
[生产组件说明](integrated-abtb-counter-coverage.md)。

## 已证实的缺口

原生 LCOV 与独立 RTL 块解析共同确认，集成 `rtl/bpu/AheadBtb.sv`
有 5042 个未命中行键落在条件计数器更新块，涉及 1014 个物理 cell。
这不是 5042 个功能点，也不是可以删掉的分母。独立 ABTB 单元的
100% 行覆盖，不能代替集成 BPU 对这些路径的实际激活。

现有 INT-015 验证 MainBTB 修正经 S3 fastTrain 学习到后续 S1，
INT-044 验证两个自然循环，INT-048 验证代表性非零历史，INT-051
验证真实 useful aging。它们没有声明集成 ABTB 的全部 bank/set/way
计数器迁移矩阵，因此不能用这些功能点的 PASS 推断新矩阵已经闭合。

尤其要区分：逐周期比较全部 1024 个计数器状态，与实际触发每个
计数器的每种迁移，是两种不同的证据。

## 递减不是一条路径

`AheadBtb.scala` 的 `needDecrease` 包含两个不同原因：

| 原因 | 真实最终反馈 | 命中条件项的位置 | 所需检查 |
|---|---|---|---|
| final-not-taken | taken=0 | 不依赖最终 taken 位置 | 条件项递减，不因本次反馈分配 taken 项或执行 T2 taken touch |
| later-taken | taken=1 | 条件项 position < 最终 position | 较早条件项递减，真正取走的后项按自身身份参与分配/touch |
| same-position taken | taken=1 | 条件项 position = 最终 position | 条件项递增与高饱和保持 |

已有五 alias 负向实验是第二种：A 的条件分支 position6 不取，后面的
无条件分支 position7 仍取到 B。因此它不能证明第一种。八个迁移标签
如果不保留递减原因，会把这两个需求合并掉。

## 待登记的功能需求

1. **集成物理计数器迁移矩阵。** 每个 4 bank × 64 set × 4 way
   cell 都检查四种递增迁移，以及两种递减原因各自的四种递减迁移。
   高/低保持必须分别看到 `inc3_3`/`dec0_0` 的真实、已比较事件；
   命中非零判断行不是低饱和保持的证明。
2. **final-not-taken 的副作用约束。** 用真实最终 taken=0 和命中
   条件项触发计数器递减，同时按关联任务检查没有本次 taken 分配与
   T2 taken touch。其他在途任务或 writeResp 可以合法改变 PLRU，
   不能把整个周期的 PLRU 不变作为无条件断言。
3. **反馈与写响应重叠的优先级。** 覆盖真实延迟反馈和真实写回重叠，
   检查 resetWeakPositive 优先于同 cell 的增减。是否已经命中必须
   从完整观测和参考任务重放判断，不用 Python 直接写入 DUT 状态制造。
4. **集成重复分配与多命中清理。** 保留真实陈旧预测元数据导致同 PC、
   同 position 重复分配的路径，检查清理选择、正常分配/修正优先级、
   pending 清理更新与全部未选 cell。独立模块的 ABTB-028 已覆盖此类
   行为，但不能代替真实集成 S1→S3 fastTrain 和 SRAM 写回时序。
   清理掉的 way 不能仅凭短暂递增被计为完整双向迁移覆盖。

第一项的候选 bin 组织为 `bank × set × way × operation_path`：
每 cell 有四个递增、四个 final-NT 递减、四个 later-taken 递减，
共 12288 个 bin。reset/write-overlap 另设覆盖组，避免把互斥
原因做成不可达的笛卡尔交叉。该分母现已在生产 schema 实现；两个
自然循环真实试验各只命中 10 个，两个代表性 final-NT 归档只读重放
分别命中 32、18 个，不能称完整覆盖，也尚未进入正式覆盖率报告。

每个采样事件必须具有：独立 oldFoldedPhr 索引来源、真实 PC 与
S1→S3 元数据关联、实际物理 way、完整计数器前后状态比较，以及
需要时的完整 SRAM 请求→下一 rising 响应读回。不能把 alias 编号当 way。

## 新场景：真正最终不取的四节点循环

- A：position6 的条件分支取向 B；A 的真实 fall-through 也为 B。
- B：真实无条件分支取向 C。
- C：真实无条件分支取向 D。
- D：真实无条件分支取回 A。

A 不取时，最终输出是 taken=0/None 属性/真实 fall-through 位置，
而不是 A 内的另一条 taken 分支。重要的是，A 被观测时的 ABTB
元数据来自两拍前 C 产生的 D 请求，不是当前 A 产生的 B 请求。
规划要求 A 按 16 字节对齐：A 取/不取后的 PHR 低两位相同，经过
B 的无条件更新后，C 开始前的低四位相同。因此两种方向下，真正
到达 A 的旧索引 token 可以一致；完整 52 位 PHR 仍须分别推导。

地址全部使用 `Pc.addr` 半字单位。MiniConfig 为 32 字节 fetch、
16 字节对齐、4 KiB 跨页截断，不能普遍用 `pc+16` 代替 fall-through。
纯模型对两页内全部 4096 个半字地址核对了生成 RTL 的位切片公式。

旧三节点 `plan_v1` 的 562 项纯模型虽然通过，但其目标格检查针对
新建请求，而非 A 当前使用的两拍前请求。对应真实五坐标 DUT 全部
在输入资格检查失败；完整状态比较此前没有报错。旧版本、五个失败
轨迹与 raw 均保留且不入账。独立逐轨迹诊断核对实际索引相位，见
[失败相位诊断](../results/coverage-bpu-native-final-NT-index-phase-review-v1-readonly.json)。

四节点修正版 `abtb_final_not_taken_cycle_plan_v2` 的 563 项测试
实际全部通过，包括全部 256 bank/set 的容量、五 alias、方向切换、
非零完整 PHR，以及 **A 当前元数据** 的流水线索引检查。新增回归
明确拒绝三节点的当前请求替代旧 token。真实修正版另有 50 项前置
契约通过，五坐标 DUT 由三个 pytest worker 执行。以上仍不证明
实际 provider way 覆盖完成。

### 五坐标真实结果与低 way 缺口：2026-10-10 00:49 北京时间

上述四节点五个 DUT 已整体以 0 退出，5 PASS，来源和四正式报告未变。
完整 gzip 的独立物理 way 诊断也以 0 退出：bank0/set0、bank0/set56
各自四个 way 均具有八种迁移；bank1/set0、bank2/set31、bank3/set63
的 way0/1 只有 inc2_3，way2/3 才具有全部八种迁移。所有递减见证的
实际反馈 taken 都为 0。五个用例 PASS 不等于五个坐标四 way 均闭合。

非零 bank 的早期真实写入给出了下一步激励依据。例如 bank1/set0，
tick5941 向 way0 分配 A，tick5957 同 A 改向 way2，tick5975 清理
way0（valid=0）。两个 bank0 坐标则是相同 way 的 dirty-hit 合并，
没有这条清理链。清理规则见 `abtb/AheadBtb.scala:323` 与
`abtb/Helpers.scala:52`；不能未经审计把这种正常路径称为 RTL 缺陷。

见 [五坐标完整物理 way 诊断](../results/coverage-bpu-native-final-NT-physical-way-review-v1-readonly.json)。
266 项契约通过的新完整审计现已整体退出 0，五例完整 reset 重放、
485 个原始观测故障及 675 个读回关联故障全部完成。它证明这五例的
检查和路径身份，不把非零 bank 的 way0/1 缺口自动变成覆盖完成。

新隔离 `abtb_final_not_taken_sliced_cadence_native_v1` 保留原地址、完整
参考算法、32768 帧预算与 525 个 direct 观测信号，仅将每相位改为
32 次“自然运行 4 周期 + driver 暂停读 4 周期”。47 项契约通过，
三个非零 bank 的 DUT 已整体 3 PASS，但完整 way 诊断仍为 way0/1
仅 inc2_3，没有保留其完整双向迁移，不扩大这个激励、不准入三份
probe raw。它不同于旧单次初始暂停，但这个差异没有关闭目标缺口。

## 为什么不继续扩大旧节奏实验

4/8/12 周期提交暂停的三个 DUT 都 PASS，但完整 gzip 轨迹独立复查
得到相同物理覆盖：way2/3 各有八种迁移；way0 只有 inc2_3/inc3_3；
way1 没有目标窗口迁移。完整 CRC、输入身份和正式报告身份复查通过。
因此不把三次 PASS 当作四 way 闭合，也不直接扩展到全部坐标。

见 [物理 way 诊断](../results/coverage-bpu-native-negative-pair-commit-cadence-way-review-v1-readonly.json)。

## 入账门禁

先完成真实探针、逐物理 way/路径检查及完整 reset-derived 独立审计，
再扩展尚缺的坐标和场景。原剩余 221 案正向审计已整体退出 0，结合
前 35 例，正向 256 bank/set 审计完成。新 221 raw 的原生增益测量与
独立 AWK 复核也退出 0，新增 2364 行、候选并集潜在 3774 行，未合入
正式报告。旧纪元相关探针/审计全部退出后才应用生产归因补丁。
生产后隔离重合并已实际退出 0。正向全部坐标通过不能代替各物理 way 的两种
负向原因、高低保持、真实写响应优先级及完整 FTQ 验证。

生产报表对集成 BPU 漏附 counter_gap/matrix、首 cell 无数字后缀
选择器漏识别的问题现已修复；源码行矩阵与 v_line 点矩阵分开。
随后仍需登记具有明确边界的功能点/covergroup，执行正常全量刷新和
独立重合并。当前隔离候选的 3774 行潜在增量不提前入账。

报告归因补丁已在新隔离版本通过 41 项回归；独立重合并审查器 10 项
测试通过，并用正式 364 份 BPU raw 完成真实重合并。新旧原生 LCOV
逐字节一致、原有覆盖率和 provenance 字段完全一致：仍为 32264/46541。
新源代码行矩阵映射全部 5042 条缺口、1014 个有缺口 cell，同时保留
1024 个 cell 的完整几何；独立 AWK 解析与其一致。2024 个缺失 v_line
点另列，不能替代上述 5042 个 SF+DA 行键。补丁现已应用到生产源码，
另有 35 项原有/新增可移植回归通过，生产后的隔离重合并已实际退出 0。
见 [真实 raw 重合并验证](../results/coverage-bpu-integrated-counter-reporting-draft-remerge-v1-readonly.json)。

集成 TAGE/PHR/RAS/bypass/replacer、有效非零 CommonHR/GHR/BW、
深层 SC-used、完整 dirty overwrite、真实 overlap、完整 FTQ 和
7 个 strict XFAIL 的原目标仍保留，不能由本 ABTB 场景替代。
