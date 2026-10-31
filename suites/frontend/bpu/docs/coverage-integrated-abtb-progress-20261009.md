# 集成 AheadBTB：自然预测流与覆盖率刷新进展

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


## 当前生产并行验收：2026-10-10 15:59 北京时间

正式默认入口已接入最多32个独立worker和run/worker/nodeid产物隔离；
完整10907项同纪元回归仍运行，final NT已提交224/256组FC，未发布新完整
报告。十模块等价和资源/隔离资格不能替代这轮终态验收。
SC原80-bin full-dirty交叉已在隔离候选中全部通过，但对当前正式基线新增
行hit为0；later-taken新八例是6PASS/2FAIL，bank2两例严格路径仍缺，不能
记作全256组闭合。先前重型试验均已终结，当前不再启动新重型试验。
最新证据及未完成项见[行覆盖分析顶部](rtl-coverage-analysis.md)和
[生产并行迁移](pytest-parallel-migration-20261009.md)。下方按时间保留历史。

## 用户授权退休旧审计，默认不导出逐周期轨迹：2026-10-10 11:00 北京时间

三个旧审计进程组2741663/2944971/2951541及其worker已全部退出，不标
completed。已有报告、日志及23份修改前源码保留。新的1221源码版本将
22个场景轨迹写入点统一接入默认关闭的导出策略，只有显式
`--dump-trace`才生成gzip JSON；不关闭原生line/branch/toggle与功能覆盖。
2269项回归、4个默认关闭真实场景和1个显式开启SC对照均实际0，默认轨迹
文件数为0；SC原生raw逐字节相同，功能bin/计数完整性验证通过。
见[策略及存储原因](artifact-policy.md)、
[当前版本必要验证](../results/coverage-artifact-policy-v1-readonly.json)。

原1218全量报告仍是历史版本证据。2648契约的旧冷分配native owner从未启动，
不能直接在新版本运行；后续必要诊断需重新资格化并显式开启轨迹。完整覆盖
目标保留，局部策略验证不增加物理bin，也不替代全量刷新或未完成审计。

## 当次串行审计实际完成，矩阵审计接续：2026-10-10 10:09 北京时间

metrics实际0/966fresh raw/728FC/200groups，并确认十模块原生LCOV、JSON、
HTML一致。serial完整457个reset重放和882故障检查于10:01实际0；原repair
sequence2713471终结0，矩阵2767544自动接续并有八个CPU-active完整case
工作进程。full261/263counter/wholeFC仍未完成，不能宣布正式审计全部闭合。
见[串行审计终态](../results/coverage-current-hybrid-serial457-dynamic-v1-readonly.json)。

针对负向reset重叠，冷分配事件触发场景已实际2275契约PASS，完整旧比较
循环与非零门禁保持；只通过公开Driver/XTransfer提交。此资格不是DUT验证，
两原因真实同cell重叠新增bin仍0。另有57项无损归档契约实际0，既有24MB
原生文件在真实tmpfs与持久存储间逐字节恢复一致；尚未接入native owner。
磁盘余量仍不满足固定80MiB持久预留，旧later审计/行队列仍拥有资源，未
额外启动DUT、未删除任何旧证据或降低80.5GiB正常安全线。见
[冷分配资格](../results/coverage-bpu-allocation-pulse-readiness-v1-readonly.json)、
[存储资格](../results/coverage-bounded-evidence-archive-v1-readonly.json)。

40份旧新冻结账本严格实际0；生产源码未改。当前行覆盖35734/46541、
物理路径2046/12288、reset优先级836/12288均未虚增，完整目标继续保留。
详细范围和待办记录在[行覆盖分析](rtl-coverage-analysis.md)。

## 统一报告已发布，物理 cross 暴露真实缺口：2026-10-10 09:24 北京时间

既有repair后处理已实际0，根summary/功能点/原生行覆盖/HTML与combined
逐文件SHA一致：10363PASS/7strict XFAIL/0SKIP，281/288功能点PASS、全部
执行。BPU35734/46541=76.78%，较旧正式新增3470行，旧命中全部保留。
后继metrics2956340已实际启动；serial457/882、matrix261/263完整独立审计
未完成，formalcurrent仍false，原完整目标不缩减。

本轮FC实际200组、190全覆盖、10缺口、组等权98.334987%。完整1024cell×12
路径schema未缩减：转换2046/12288，仅1cell十二路径齐全；reset优先级
836/12288，仅same-position before2/3，两负向原因所有before仍0。高组均值
不能替代物理矩阵闭合。见
[本轮物理缺口](../results/coverage-current-published-functional-physical-gap-v1-readonly.json)。

fresh/历史隔离逐行Python与AWK对账实际0/7契约：469历史隔离行键尚未进入
fresh，fresh另有137个独有行键，并集36203；不能用两个总数相减得332。
原生raw没有混入历史隔离候选。later分配顺序v4真实DUT已实际0/1PASS、
30082帧与32路径门禁齐全；owner2944971仍完整重放和故障检查，readonly
linequeue2951541仍等待同一完整parent0，未提前入库。

新写入来源诊断实际28契约/16918帧通过，reset生成132次写响应均与观测
一致。laterTaken五次cleanup全是position7/branchType3 fallback重复，
条件重复cleanup为0；最后cleanup reset way1而负反馈命中way0。必须改变
真实条件驻留/重复分配与drain时序，不是继续冷延迟扫描。原两DUT FAIL
与所有证据保留，不声称完整PHR/SRAM/parent/fault审计。见
[写入来源诊断](../results/coverage-bpu-negative-write-origin-v1-readonly.json)。

38份冻结账本严格实际0，生产1218源码/350RTL/runtime未改，未删证据、
未额外启动DUT。完整详情见[行覆盖率分析](rtl-coverage-analysis.md)。

## 原10370项执行完成，报告后处理推进：2026-10-10 08:59 北京时间

串行实际10102PASS/7strict XF、退出0；并行实际261PASS、退出0。合并证据经
独立jq核对为10370唯一node、10363PASS/7XF/0SKIP；288功能点全执行关联，
281PASS/7XF。原owner2655665于00:56:45Z以已知空node前缀关联错误退出1，
两个pytest真实成功不受影响，原失败保留。repair2713471已自动严格恢复，
postprocess2951851/native_merge2951940在966当次raw/728FC上工作；没有重跑
DUT。旧审计等待器2692242按预期在oldfull成功门禁退出1，新的复制算法队列
仍由repair执行。统一报告发布和全部独立审计尚未完成，不宣布formalcurrent。
见[精确执行终态](../results/coverage-current-full-shards-terminal-v1-readonly.json)。

later分配顺序修复的真实DUT仍运行。新增只读行测量队列2951541/session3823
实际187契约PASS，14份签名历史LCOV准备完毕，并用pidfd等待同一完整parent
成功；逐条拒绝32物理路径的缺失/零/bool/错cause，不以nativePASS替代完整
故障循环。64MiB子预算包含在512MiB既有预留内，无额外DUT；新增行未知，
不能先记增益。36份冻结账本严格检查实际0，原始完整范围不缩减。见
[测量资格及等待](../results/coverage-bpu-later-allocation-native-line-readiness-v1-readonly.json)。

## 失败原因已取证，公开分配顺序修复进入DUT：2026-10-10 08:49 北京时间

原full2655665/serial2655922实际99%，parallel261已实际0；repair2713471和
matrix2741663/2767544仍等同一原执行终态。不得把未结束的10370项提前写成
全部PASS，或把候选3802行并入正式32264/46541。

later-taken完整失败轨迹的reset counter/PLRU与十次T1完整请求诊断实际0，
确认条件角色分配0/3/0/3/0、fallback角色2/1/2/1/2。新v4通过公开negative
stream给alias3先分配fallback，再保留原正/负/正三阶段；全部8种初始PLRU
计划均覆盖四个条件way，但实际DUT仍须独立证明。531契约实际PASS（34新），
九旧helper字节相同，原完整比较循环除一个prefill分支外AST保持；新owner
2944971/session97305、pytest2947563、worker2947564实际运行，仍要求32条
物理路径、全部parent/reset/525-direct及故障审计。不把计划way当监测结果。
旧v3的529PASS/2FAIL来自复制末尾多空行，XML与源码保留，新版恢复字节一致
而非弱化检查。见[新资格](../results/coverage-bpu-later-allocation-order-readiness-v4-readonly.json)
和[旧失败诊断](../results/coverage-bpu-later-way-diagnosis-v1-readonly.json)。

negative-overlap v3因无关sshd环境权限读取而契约失败，未派发DUT；修正版v4
仍对无法确认的Python worker严格拒绝，实际231契约PASS。仅资源等待依赖
解耦，旧audit_case AST相同。但两个真实DUT8126/8792帧均因目标重叠为0而
FAIL，owner2922605和所有子进程已终结，不能继续标live或算PASS。只读完整
16918帧counter/PLRU诊断实际0：多数负向任务没有条件命中，最后alias两原因
各21次命中但没有同拍reset。下一步须安排真实驻留、分配/drain和反馈的
相遇，而不是继续增加冷stream发送延迟。原失败保留，新增重叠bin仍0；见
[失败终态](../results/coverage-bpu-negative-overlap-native-failure-v4-readonly.json)
及[时序诊断](../results/coverage-bpu-negative-overlap-diagnosis-v1-readonly.json)。

35份冻结账本严格检查实际0，生产源码未改。新later实验独占原512MiB预算，
正常80.5GiB安全线不变，未并发其他native实验；原完整需求与SC/FTQ等缺口
保持，formalcurrent=false。

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


## SC 完整重放与原生行增量终态：2026-10-10 07:54 北京时间

SC reset审计2871467/session94448已实际整体0并关闭句柄：457+1493=1950帧
完整重放，不复用live模型状态；21+48=69个原始fault全部在目标拍被有context
的ScoreboardMismatch拒绝，9次满dirty覆盖再次确认。见
[完整原始审计](../results/coverage-bpu-sc-full-reset-audit-v1-readonly.json)。

原生行测量v1的19契约PASS/10FAIL发现十数字夹具仍提供旧12文件，而新范围
为13（11既有候选+SC候选+formal），未启动DUT/原生测量。新v2仅修正夹具
数量和报告版本；29契约实际PASS，12份已签名历史LCOV及两次SC原始coverage
重新合并后，Python与独立AWK一致：额外新增0行、累计候选仍3802，正式
32264/46541未变。owner2874467/session60247实际0并关闭。见
[SC原生行增量](../results/coverage-bpu-sc-full-native-line-v2-readonly.json)。

这是有意义的功能缺口发现：已有行命中没有证明满dirty覆盖行为已被检查。
不能为行率而抹去该需求，也不能把9次事件等同全物理交叉100%；仍需导出
完整功能bin、扩展两bank/五表/四victim/同拍drain并完成真实SC-used场景。
25份旧新源码账本已检查实际0；全部原始失败、成功产物保留，未修改冻结
1218源码/RTL/runtime。原full/serial仍77%；later-taken缺way及负向未派发保持
未完成，正式current=false、完整目标不变。

## 四 way 完整审计终态与 SC 容量场景：2026-10-10 07:46 北京时间

四way parent2817594/session92850已实际整体0，29184帧完整reset重放、53个
parent原始故障、135个读回关联故障全部完成，结合76个direct故障共129个
原始反例。line-v2_2819191/session21267随后实际0，原生/AWK测量再新增19个
行键：AheadBtb4、UTAGE shadow8、ReplacerState7。累计候选额外行3783→3802，
并集36066/46541；这些仍未并入正常manifest，正式仍32264/46541。
见[原生行增量](../results/coverage-bpu-long-cycle-four-way-native-v2-readonly.json)。

later-taken v2_2831179于23:37:39 UTC实际退出1：29288帧真实轨迹通过live状态
比较，但五alias只产生way0/3的16个目标路径，缺少way1/2共16条，严格32路径
门禁正确拒绝。原始轨迹与所有源码保留；不能视作四way完成，也不能把final-NT
替代它。negative-overlap v2_2852138因上一链实际失败的成功前置门禁退出1，
未派发DUT；205项契约通过仍有效，但新负向重叠bin仍0。这两PID不再live。

SC缺口分析发现旧模型会拒绝满dirty，而WriteBuffer.scala明确允许非反压的
满行miss覆盖dirty victim。新增私有模型保持旧bounded转换完全一致，扩展
miss-only PLRU、完整mask/data、旧payload drain与同拍write优先，阈值仍从
reset1130推导；35个threshold/pipeline加10个PLRU信号均静态memory-direct
绑定，继承Bundle/@on lossless订阅，无VPI/internal回退。2960契约实际PASS，
八份Python源码已冻结。模型测试不当DUT功能覆盖计数。

短phase真实DUT实际1 PASS：457帧、54017次比较、两笔相邻反馈、451次阈值
检查；十buffer全槽/PLRU、T0/T1/T2、读响应及最终阈值1131/1131/1130/1130
一致。见[原生phase资格](../results/coverage-bpu-sc-full-native-phase-v1-readonly.json)。

五key首次v1在第五key准备阶段失败，目标SC反馈0笔：0x80间距让TAGE set
绕回，tag xor position与第一key另一分支别名。这不是MainBTB容量不足或已
证实RTL缺陷。v1冻结失败与原始轨迹保留；新v2只调整已测试地址规划为0x40
间距及版本，2063项signed读回/双bank联合容量/旧别名复现/AST保持契约PASS。

v2真实DUT已实际1 PASS、owner0：1493帧、177521次比较、十笔相邻接受、30个
完整shadow动作/15个drain，确认bank1的path/imli/bias三表共9次满dirty覆盖，
五key全部实际公开读回，并按reference SRAM中真正留下的数据比较预测。
不是强行要求合法victim数据都保留。最终阈值1135/1135/1130/1130。
见[满dirty真实pilot](../results/coverage-bpu-sc-full-overwrite-native-v2-readonly.json)。

新独立reset/原始故障审计2871467/session94448已实际live，共需重放1950帧，
不复用live模型状态，不新增DUT；它尚未终态，SC新增原生行尚未测量/计入。
两bank、五表、四victim、drain重叠、非零CommonHR、deep SC-used及完整FTQ
仍未由该pilot闭合。正常full/serial仍是原进程、77%，parallel261已0；正式
current=false，完整目标与7strictXF保留，未修改1218冻结生产源码/RTL/runtime。

## 实际故障循环修复与v2资格：2026-10-10 06:52 北京时间

复查发现新v1运行器的35个关联故障共用一个Scoreboard，却逐次断言
failed==1；异常状态实际累计，第二个正确拒绝会误报审计失败。该问题
不在DUT或xreactor比较语义。已核实v1 owner2848249无子进程、未生成
dispatch/DUT回执，只停止这个自建等待器；session74677实际退出143，
全部冻结源码、201契约成功日志及取消回执保留，未触碰现有DUT/原full。

新 `/tmp/bpu-abtb-negative-overlap-audit-v2-NetXl1` 七份源文件字节相同，
运行器仅为每个故障重建独立Scoreboard并调整版本/测试登记。新增四项
回归提取并执行真实owner的AST故障循环：两原因各复现旧版failed==2，
新版两原因各完成35个context/status正确的异常。完整205契约实际PASS，
251项helper已冻结；owner2852138/session51257实际pidfd等待同一
later-taken owner2831179，没有重启DUT。见
[v2审计资格](../results/coverage-bpu-negative-overlap-full-audit-readiness-v2-readonly.json)。

原full/serial与四way完整parent均仍实际运行，CPU增长；原生/later-taken
仍等同一parent。新负向DUT仍未派发、负向重叠新增bin=0，正常80.5GiB
安全线、512MiB联合预留、全部完整原始需求和正式current=false不变。

## 负向重叠完整审计入口与排队：2026-10-10 06:40 北京时间

新独立目录 `/tmp/bpu-abtb-negative-overlap-audit-v1-KQoxHO` 已完成实际
201 契约 PASS，正式资格回执退出0；owner2848249/session74677仍实际
存活，通过pidfd等待同一later-taken owner2831179终态。这是资源顺序
约束：两个32768帧DUT共用已验证512MiB上限，不与旧链预留重复支出，
原正常回归80.5GiB安全下限未降低。资格及250项helper身份已冻结。
见 [完整审计资格](../results/coverage-bpu-negative-overlap-full-audit-readiness-v1-readonly.json)。

独立parent保留旧完整`current_tick`逐帧重放循环，AST完全相同；525端口
direct和标准库priority见证算法均为已验证副本的字节相同版本。新增关联
检查逐笔比较完整来源、公开反馈payload和真实接收拍，核对source到反馈
接收之间预测ready始终为1、五次delay顺序、真正后续MainBTB2→1及对应
S3负向结果；不会把真实采样重复metadata强制归给错误的唯一早期token。

真实DUT后每原因要求完整parent/counter/write/direct/shadow重放、35个
关联反例、76个direct原始故障、9个counter原始/8个导出故障、10个一般
parent故障，以及每个实际命中的负向priority bin所对应的counter故障。
reset见证必须同一物理cell、真实更早metadata、真实写响应，且到下一
checked rising才确认。原值3时dec3→2与reset→2数值相同，仍记录真实
重叠但不声称数值差异；不能因此删除before3需求或拒绝合法见证。

此时新DUT仍未派发，新增负向重叠覆盖为0。完整全256/四way/双原因/
所有原值矩阵仍未闭合。原full/serial与四way完整parent继续同一进程；
后者CPU实际增长，原生测量/later-taken仍等其终态。正式current=false，
旧279/286和BPU32264/46541基线、3783候选未准入状态均不变，完整
非零CommonHR/GHR/BW、deepSC-used、dirty overwrite、FTQ及7strictXF
要求不缩减。

## 四 way 第一层审计完成、负向重叠刺激资格：2026-10-10 06:18 北京时间

四way probe2816026/session43120已于22:08:31 UTC实际整体退出0，句柄关闭。
29184帧完整独立counter/write/525-direct/shadow重放通过，9个原始counter、
8个导出和76个direct故障全部拒绝，direct未确认动作0。实际四way正向/
final-NT路径32个仍全部为正。新证据见
[四way第一层审计](../results/coverage-bpu-long-cycle-four-way-pilot-v1-readonly.json)。
parent2817594已从pidfd等待转为实际CPU执行，仍须完成完整parent reset
重放、53原始和135读回关联故障；line-v2_2819191、later-live-v2_2831179
继续等待同一parent。尚无parent或原生增益终态，不把第一层成功当全链完成。

依据65次旧正向重叠与稳定循环0次重叠的差异，新增短循环真实流中负向
反馈实现。公开异步driver.send返回原生XTransfer，提交时不暂停预测，
等待/取消仍由transfer和现有bounded封装管理；测试入口只有一次意图调用，
没有get/set、时钟边沿或gather。两原因分开：final-NT只有条件项不取，
later-taken仍有真实A:7无条件项取走。全256坐标各五alias、20/25个完整
MainBTB条目key和最多双way容量、非零52位历史及旧两拍索引验证通过。

新资格owner已实际整体0，1149契约PASS，含24个完整环形历史/索引联合
case、十个实际嵌套prepare/prime协程、原生transfer因果/取消边界，以及
相反原因/错误坐标/零命中不得导出的门禁。七个已有setup/观测helper和
完整finally保存逻辑有AST保持证明。源码位于
/tmp/bpu-abtb-negative-overlap-stimulus-v1-whV41t，11项helper身份已冻结。
见 [刺激资格回执](../results/coverage-bpu-negative-overlap-stimulus-v1-readonly.json)。

这不是DUT成功：两个真实DUT入口虽已实现，独立完整parent/写回/counter/
direct/fault审计运行入口仍需补齐后才派发。本轮该新场景DUT PASS=0、
新增负向重叠bin=0，不计行覆盖或功能点通过。后续不修改冻结资格副本，
在独立审计/调度目录实现；需要实际同cell负向反馈和write-reset见证。
原full/串行仍live，正式current=false、候选3783未入账；全256/四way/
双原因/0与3保持、真实overlap、非零CommonHR/GHR/BW、deepSC、完整
dirty overwrite/FTQ和七strictXFAIL需求继续保留。

## 四 way DUT 通过、重叠缺口与方向协程修复：2026-10-10 05:54 北京时间

四way长循环真实DUT于21:31:07 UTC退出0，1 PASS；bank1/set0四物理way
各四递增和四final-NT递减/保持共32路径全部出现，370个已比较事件。
完整路径分母仍为12288，该隔离场景是32/12288，不把选定坐标的32/32
写成全局100%。probe owner2816026继续执行完整独立counter/write/direct/
shadow及故障审计；parent2817594和line-v2_2819191继续实际pidfd等待，
没有重启DUT、没有提前准入原生行数。该稳定长循环的reset-priority组为0。

新的只读重叠盘点已实际整体0：59契约PASS，五份既有完整审计later-taken
原始轨迹再次从reset独立重放，确认65个下一rising已比较的真实重叠见证。
其中same-position-taken原值2为50次、原值3为15次；没有final-NT、
later-taken或原值0/1见证。不能把“存在重叠”当作完整优先级矩阵完成。
见 [真实重叠盘点](../results/coverage-bpu-reset-feedback-overlap-inventory-v1-readonly.json)。

进一步执行路径检查发现later-taken live-v1的方向协程在真实反馈后引用
未定义taken；原475模型/过滤契约并未执行这个嵌套协程。旧等待器2824370
在确认无子进程、无DUT目录且仍等待同一parent后以SIGTERM退出143，
全部源码/475通过回执/日志保留；不是DUT或RTL失败。

新live-v2只将该判断改为counter<goal，其他十份helper字节不变，scenario
AST仅此一处差异。新增22项直接执行真实steer协程的回归：六种切换复现
旧NameError，八种切换/已达目标通过，六种错误响应仍被比较拒绝。
完整497项实际PASS；owner2831179/session11640真实pidfd等待同一parent，
成功后仍须满足32个later-taken物理路径、15完整窗口、53原始/135关联
故障及全部独立重放。真实DUT尚未启动，final-NT不能替代later-taken。
新副本：/tmp/bpu-abtb-long-cycle-later-taken-live-v2-h00AQy。

原10370项full/串行仍live，parallel261已实际0；严格归并、指标、
serial457/882及matrix261/counter263/wholeFC审计仍待上游。正式279/286、
197组99.2058%和BPU32264/46541仍是旧纪元基线；候选3783未入账。
全256/四way/双原因/真实overlap、非零CommonHR/GHR/BW、deepSC、
完整dirty overwrite/FTQ与七strictXFAIL均继续保留，不缩小目标。

## 四物理 way 长循环资格与实际运行：2026-10-10 05:19 北京时间

从已审计的十节点单alias低way场景扩展到五alias，不假设alias与way对应。
新增API强制32个实际物理路径（四way各四递增、四final-NT递减/保持）全部
出现才导出FC，保留12288/1024/12288完整schema分母。原289模型加新99
契约实际388 PASS，含每个路径缺失/零命中、live/独立65536帧预算保护。
owner2816026/session43120与pytest2816061/worker2816062实际live，尚无DUT
终态，不能提前认定四way达到或准入行覆盖。原生产源码与所有旧算法冻结。

新parent2817594/session92850的70契约实际PASS，真实pidfd等待上述owner；
成功后要求15窗口完整reset重放、原21加全32物理路径共53原始故障、135
读回关联故障。line-v2 owner2819191/session21267的32契约实际PASS，11份
签名历史LCOV已保存（含旧低way增益），真实pidfd等待parent成功再做原生/
独立AWK测量。它不读正在变化的root raw/FC/LCOV。

line-v1新增正例失败暴露索引转换误改AWK数字字符类，实际1 FAIL/21 PASS；
旧代码、退出1、快照及日志保留。v2只修复该转换，新增十个逐数字正例，
不重启真实DUT，不把入口失败算RTL失败。派发前另一错误账本名的shell
检查退出9，尚未启动owner/DUT；修正为实际已有账本后完整核对通过。

磁盘预算依据旧8704帧全部45,956,600字节产物按65536帧保守缩放约346MB，
另留64MiB仍小于512MiB私人预留；正常full80.5GiB底线不变、证据未删除。
原full/serial仍live，parallel261实际0已完成；repair、serial457及matrix261
完整审计仍待上游。正式current=false、候选3783未入账，原双原因/全256/
deepSC/dirty overwrite/真实overlap/完整FTQ/七strictXFAIL目标全部保留。

## 完整低 way 审计与原生增益：2026-10-10 04:52 北京时间

低way全链现已实际成功：parent于20:50:21 UTC整体0，8704帧完整从reset
重放、21个parent原始故障、27个读回关联故障全部完成；结合先前76个
direct故障，共97个原始故障，另有9counter原始/8导出故障。probe、parent、
line三个owner/session均已正常结束，不再当live等待器轮询。

独立原生/AWK测量于20:50:40 UTC整体0，全DA分母46541不变。相对旧
全部候选与旧正式命中并集，实际新增9行：AheadBtb.sv:7564/7565/7566
是bank1/set0/way0的递减选择、非零判断、递减赋值；另有低/高UTAGE
BypassShadowBuffer的2+4行。旧候选潜在3774→3783；正式BPU仍是历史
32264/46541，这9行和全部候选都未写入正常manifest。9行来自完整运行
（含setup），不能全部归因于目标counter，也不证明deep SC或其他缺口闭合。
见 [完整parent审计](../results/coverage-bpu-long-cycle-low-way-parent-v2-readonly.json)
与 [原生/AWK逐行测量](../results/coverage-bpu-long-cycle-low-way-native-v1-readonly.json)。

当前原矩阵261 PASS已完成，串行10109项仍live，严格归并/指标/serial457
及matrix261完整审计仍待上游终态。later-taken纯规划291 PASS并非DUT
覆盖。完整四way/全bank-set/双递减原因及其他原始目标保留，正式current
仍false，目标active；不把这一个物理cell的完整八路径当全矩阵完成。

## 最新实际进展：2026-10-10 04:49 北京时间

原并行矩阵已于20:44:20 UTC实际退出0：261 PASS，八worker都正常退出，
783份raw/FC产物齐全。串行10109项与原full owner2655665仍live，尚无整轮
终态；不能将并行成功表述为10370项全部通过。新只读预检也已实际0：
严格复用已资格化的carrier/worker/node绑定，重新核对全部783份raw/FC、
261份完整trace的SHA和本轮时间边界，1048输入身份最终检查通过。预检
不执行DUT或reset重放，不代替完整matrix261/counter263/wholeFC审计。
见 [已完成矩阵身份预检](../results/coverage-current-matrix261-completed-preflight-v1-readonly.json)。

低way probe2773178/session45504于20:42:36 UTC实际整体退出0：8704帧
独立counter/write/525-direct/shadow重放通过，9个counter原始故障、
8个导出故障、76个direct故障全部拒绝；33个direct动作全部确认。
bank1/set0/way0实际inc0_1/inc1_2各1次、inc2_3两次、高保持44次，
三个递减各1次、低保持23次。完整parent2783267已接着运行；21个parent
原始故障和27个读回关联故障仍需全部完成，line2789645继续实际pidfd等待。
这份raw还没有进入正式manifest，原生新增行数尚未测量。

下一项later-taken长循环纯输入规划完成：修正版v2实际291 PASS、整体0，
全部256坐标各五alias/十节点，A:6条件项和A:7无条件fallback均计入容量；
每组最多两条、55个MainBTB完整条目key唯一，完整非零52位历史、旧两拍
索引及12组joint参考通过。负向阶段确实taken=1/position7并推进PHR指针，
final-NT不能满足它的递减过滤。初版7失败/281通过揭示三个非零bank/set0
在新增fallback后过容量；旧版本保留。新规划逐peer调整128半字倍数地址，
不删fallback、不减五alias，保留索引低位并重新证明全部历史。
见 [later-taken输入资格](../results/coverage-bpu-long-cycle-later-taken-plan-v2-readonly.json)。

该later-taken规划没有运行DUT，不能计为物理way可达或功能覆盖；当前磁盘
接近新probe准入门槛，本轮没有再派发DUT，也没有删除证据。已复核冻结
源码不变；仍须严格修复归并、指标、serial457/882和matrix完整审计全部0
才能标正式current。四way/全bank-set/两递减原因/两饱和、deep SC-used、
完整dirty overwrite/真实overlap/完整FTQ与7 strict XFAIL均继续在原目标内。
以下记录按当时口径保留。

## 最新实际进展：2026-10-10 04:32 北京时间

原 full2655665／串行2655922／并行2655921 及八 worker 仍 live，继续同一
10370 项回归，没有重启 DUT。正式 279/286、197 covergroup（189 全覆盖、
组等权均值99.2058%）和 BPU32264/46541 仍是上一源码纪元的已审计结果，
不是当前1218源码纪元已刷新。当前登记288点；新增两点没有提前计 PASS。

修正版 matrix 资格已实际退出0：547 契约及两个真实生产 pilot 的完整
重放成功。queue2767544 已启动，实际 pidfd 等待 repair2713471；仍须先
完成原 full、严格节点归并修复、指标和 serial457/882 审计，之后才执行
完整 matrix261／counter263／whole728-FC/HTML 审计。原版资格的两个
pilot 也已退出0；旧九份文件和原停止等待器回执继续保留。

从低 way 缺口提出十节点自然循环，新 v2 探针已实际300模型 PASS、
1 DUT PASS，完整8704帧；live 比较及导出要求 bank1/set0/way0 四种
递增和四种 final-NT 递减/低保持全部出现。probe owner2773178 还在执行
独立 counter/write/525-direct/shadow 和故障审计，不能仅凭 DUT PASS 准入。
新 parent owner2783267（9契约PASS）实际等待该 probe，随后做完整 parent
reset 重放、21原始故障和27读回关联故障。另建 line owner2789645，
19契约PASS、十份历史签名LCOV已复制核对，实际 pidfd 等待 parent 成功后
才做新 raw 原生导出及独立AWK增益检查；不读取变动中的 root raw/FC。

初版十节点探针在 Python required_operations 固定四节点解包处失败，
不是 RTL 比较失败，失败轨迹/raw/日志保留且不入账。修正版在独立目录
使用可变长度解包并新增七个过滤适配回归，没有改冻结生产源码。新 parent
的完整比较算法与旧副本字节相同。完整四 way／双递减原因、deep SC-used、
dirty overwrite、真实 overlap、完整 FTQ 等原始目标均仍保留；正式时效
false，目标 active。以下记录的运行状态按当时口径理解。

## 最新独立审计入口：2026-10-10 03:55 北京时间

新增 261 场景的完整 parent/write/525-direct/SRAM/readback 审计入口已实现，
复用已签名的纯重放算法，不调用旧 support/native_gate 资格门禁、不补造
已从生产 trace 删除的缓存功能计数。另使用标准库独立 counter 模型检查
261 新场景及两个自然循环，保留全部物理分母与故障反例。

全局聚合已实现：serial17+matrix261 对应 shadow/training/useful/ring/RAS，
natural2+matrix261 对应 counter 三组；必须与本轮 728 导出／200 组和 HTML
实际数据核对，不能用串行范围聚合代替全量。完成门禁要求 22501 个旧算法
原始观测故障、2979 个 readback claim 故障、2367 个独立 counter 原始故障
及 2104 个导出故障全部被拒绝。

复核发现新入口的一处错误顺序假设：CoverageDatabase 回读保留插入顺序，
不能与另行字典排序的列表比较。停止了本轮自己新建且尚未启动审计的等待器
2738873（实际退出143），未终止 DUT 或 pilot。原九份文件及回执全部保留；
修正版另建目录，七份字节完全相同，两份分别只改一个回读断言和资格报告
目的地，重放算法不变。修正版实际 101+166+266+14=547 PASS，0 SKIP；
14 项顺序回归使用六份真实生产导出。

修正版 chain2741663/session58477 实际运行，qualification2742969 及两个
只读 pilot worker 正在完成全重放。成功后才启动 matrix queue，再通过
pidfd 等待原修复 owner2713471 完成指标／serial457 审计。原版资格仍保留，
其正向 pilot 已完整通过 86/9/9/8 四类故障，负向仍运行。以上不代表本轮
261 已审计。原 full2655665、串行2655922、并行2655921／八 worker 仍实际
存活，1218／1234／1268 和原版审计帮助文件身份重新核对通过。

正式覆盖率尚未刷新；完整负向物理路径、deep SC、dirty overwrite、完整
FTQ 等原始缺口不变，目标 active，检查点 v86。

## 最新报告归并修复：2026-10-10 03:27 北京时间

发现并只读复现了一个后处理缺陷：外部载入生产测试时，实际 pytest 节点
形如 `::test_integrated_abtb_…`，原合并器却要求 `test_production.py::`。
与原并行运行相同参数的 collect-only 实际退出 0，261 节点均为空前缀；
真实 bank0/set25 的 worker 目录 SHA 也完全匹配这个节点格式。
原 full2655665／串行2655922／并行2655921／八 worker 均仍存活，尚未
观察到原控制器终态，不能把“已确认将触发的归并错误”说成 DUT 已失败。

没有修改任何冻结源码或原控制器。独立修复严格绑定原命令唯一 carrier、
全部八 worker 完整一致的收集、261 用例三个生命周期、783 份产物及按
节点 SHA 隔离的目录、BPU-INT-055/056 精确映射。38 项反例／正例实际
通过；审计复制版另实际 133 PASS。11 份复制文件中八份字节不变、三份
只改 FULL 结果目录常量，指标／457 重放／882 故障算法均未改变。

新 owner2713471/session29856 已通过实际 pidfd 等待原 full2655665。
仅当原 pytest 两个分片都实际退出 0、原控制器只发生这一个精确已知归并
异常且源码身份不变时，才使用原证据重新归并；不重启 DUT，不把原失败
receipt 改为成功。之后执行独立指标及串行完整重放审计。原等待器2692242
保持原门禁和文件不变，其因上游错误产生的失败也会保留。
见 [修复资格](../results/coverage-current-node-prefix-repair-qualification-v1-readonly.json)。

新增 261 的 worker/node/产物绑定已实现；完整 parent/write/direct/SRAM
故障审计及全局 shadow/counter 独立聚合仍待完成。正式覆盖率未刷新，
3774 潜在行仍未准入，原始硬件缺口范围保留，目标 active，检查点 v85。

## 最新审计进展：2026-10-10 03:09 北京时间

原 10370 项完整回归仍在运行，owner2655665、串行2655922、并行2655921
及八 worker 均已实际核实存活；没有重新启动。1218 源码／1234 全量帮助文件
身份重新核对通过。正式覆盖率仍是历史基线，不能提前计入新增 PASS 或行增益。

当前纪元审计契约已实际 **133 PASS**：原 66 项完整保留，加 67 项源码、
精确用例集合、功能点映射及原生 LCOV 反例。旧完整重放 worker／history AST
不变，四份核心／契约文件字节不变；run 仅四处明确的编排／报告替换。
审计 owner2692242/session68082 已通过实际 pidfd 等待原 full2655665；其后
自动执行 fresh native/FC/feature/HTML 核对与原范围 457 次重放／882 个故障。
这是串行范围，不包含新增 261 矩阵的完整独立审计。

另一个只使用标准库、没有导入生产 counter／coverage 算法的物理重建模型
已通过 **51 项契约**，并实际重放迁移资格的六份生产观测，共 **67160 帧**。
全部 1024 counter、256 PLRU 状态从 reset 推导，S1→S3 资格、两类递减、
饱和、同 cell reset 优先级均核对；下一拍完整状态通过后才记覆盖。
独立计数与六份实际 FC 导出完全相同，拒绝 **54 个原始观测故障／48 个
导出故障**，整体实际退出 0。路径 bin 仍为 8/8/8/6/32/18（分母12288），
没有把低 way 缺口隐藏。见 [独立真实观测资格](../results/coverage-current-independent-counter-pilot-v1-readonly.json)。

新增 261 矩阵的完整 parent/write/direct/SRAM/readback/fault 编排，以及
serial17+matrix261 的 shadow、natural2+matrix261 的 counter 全局独立聚合
仍待完成；六份 pilot 不代替这个范围。合格模型和当前审计帮助文件已冻结。
全量及审计均无完整终态前不标 current；检查点 v84，原始硬件目标范围不变。

## 最新状态：2026-10-10 场景生产迁移与全量刷新门禁

合格五 alias/四节点 final-NT 场景和 index/write/SRAM 支撑已迁入生产。
14 模块迁移 AST/await 门禁通过，3263 项模型回归实际通过，六个迁移 DUT
已实际 6 PASS；六份完整新观测重放及最终源码身份检查也已通过，迁移资格
整体退出 0。独立审查六份实际导出并拒绝 48 个数据故障。
见 [生产迁移说明](integrated-abtb-scenario-migration.md)。

当前完整 collect-only 为 10370 项；计划新增 BPU-INT-055/056 后为 288 点，
旧正式结果仍为 279/286，不把登记、收集或六例 pilot 当作新增正式 PASS。
旧 results 完整归档的 3950 成员均 SHA 校验通过，原始约 25.35 GB 无损
压缩为约 1.02 GB，无原文件删除。完整刷新将使用同一 1218 源码纪元：
原套件/纯模型 10109 项串行，新矩阵 261 项八 worker 隔离；必须核对
无交集并集恰好等于全部 10370 项。合并门禁 15 项反例/正例已通过。
控制器现已在迁移资格完整退出 0 后实际启动：owner2655665、串行2655922、
并行2655921/八个 worker 已核实存活。全量尚无终态，不提前宣称完成。
当前检查点 v83，1218 项生产/测试/运行库源码冻结，旧证据以完整归档保护。

完整四 way 负向/保持、两种递减原因、deep SC、dirty overwrite、真实
overlap、完整 FTQ 和六个 RTL 问题范围不变；3774 潜在行仍不是正式增益。

## 历史状态：2026-10-10 01:44 北京时间

集成 ABTB 的物理 counter 功能覆盖组件已进入生产并接入正常自然循环。
完整矩阵为 12288 个更新路径 bin，另有 1024 个 write-reset 和 12288 个
真实同 cell reset 优先级 bin；两种 decrement 原因不再合并。完整状态
重放通过后才入账，晚期失败不提交覆盖，reset 抑制的训练不冒充已执行更新。
见 [组件说明](integrated-abtb-counter-coverage.md)。

接入后的 1389 项模型回归通过，两个实际生产测试由独立 pytest worker
执行并整体 2 PASS，完整新观测重放通过。独立标准库导出审查也退出 0，
拒绝 16 个真实 FC 文件数据故障。当前完整 collect-only 实际 8254 项；
旧 normal raw/FC/四正式报告身份保持不变，没有把新试验写进正式 manifest。

新矩阵揭示两个自然循环各只命中 10/12288 个物理路径 bin；PC bank
参数 0/1 实际对应观测 ABTB bank0/2，不能拿场景编号代替物理身份。
两个已有 final-NT 归档的生产只读重放分别为 32 和 18 个路径 bin，
继续确认非零 bank 的低 way 缺口。以上都不代表完整矩阵闭合。

先前生产报告归因补丁的 35 回归/364 raw 重合并现已实际退出 0；
不再等待 owner2646046。当前 1194 项源码身份账本和检查点 v82 已保存，
所有本轮工作句柄均 terminal。正式基线仍为旧源码的 8190 PASS、7 XF、
279/286 功能点及 BPU 32264/46541；新正式全量尚未刷新，3774 个候选
行增益未合入。没有为了 collector 增加新的 PASS 功能点。

下一步迁入合格的五 alias/四节点场景及其 index/write/SRAM 支撑，再
登记新功能需求、正常刷新。完整 CommonHR/GHR/BW、deep SC、四 way
负向/保持、full dirty overwrite、real overlap、完整 FTQ 和 RTL 问题
范围保留，目标 active。检查点 v82。

## 历史状态：2026-10-10 01:13 北京时间

上一正式正常 memory-direct 基线为 8190 PASS、7 strict XFAIL、0 SKIP；
279/286 功能点 PASS，BPU 32264/46541，功能覆盖等权均值 99.205805%。
本轮报告归因修复已经应用到生产代码，35 项原有与新增回归通过；
当前源码已进入新纪元，旧四份正式报告保留，标为待正常全量刷新。
新的隔离潜在增益为 3774 行，未合入正式表；正式功能点仍为 286。
完整目标仍 active，不把报告修复或隔离行增益当作完成。

本轮完成了报告归因补丁的隔离回归（41 PASS），以及审查器测试
（10 PASS）和正式 364 份 BPU raw 的真实重合并。原生 LCOV 逐字节
不变，原有字段全部相同；5042 个未覆盖源代码行现可准确归因到
counter 的 bank/set/way/更新角色，独立 AWK 复核一致。2024 个未覆盖
v_line 点另列，不能把二者当同一分母。此补丁现已应用到生产代码，见
[真实重合并验证](../results/coverage-bpu-integrated-counter-reporting-draft-remerge-v1-readonly.json)。
生产后验证使用新源码账本重新运行 35 项回归及正式 364 raw 隔离重合并，
原 owner2646046/session23684 正在运行；它不会覆盖旧正式报告。

四节点 final-NT 五 DUT 已整体 5 PASS；完整物理 way 诊断退出 0，
bank0/set0、bank0/set56 四 way 各全八迁移，三个非零 bank 的 way0/1
仅 inc2_3。早期重复分配和 multi-hit 清理的真实时序已定位并保留，
见 [五坐标诊断](../results/coverage-bpu-native-final-NT-physical-way-review-v1-readonly.json)。
266 项契约通过的新完整独立审计已整体退出 0，五例全部完成，拒绝
485 个原始观测故障及 675 个读回关联故障。见
[final-NT 完整审计](../results/coverage-bpu-native-final-NT-full-audit-v1-readonly.json)。

新重复分段节奏版本仅通过现有 driver 将每相位切为 32 次 4-cycle
运行与 4-cycle 提交暂停；47 项契约通过，三个非零 bank DUT 已整体
3 PASS。但完整 gzip 逐 way 复核仍为 way0/1 仅 inc2_3、way2/3 全八种，
没有补齐低 way，不扩大此激励，也未准入这三份 probe raw。见
[分段节奏诊断](../results/coverage-bpu-native-final-NT-sliced-cadence-way-review-v1-readonly.json)。

原正向剩余 221 审计已于 00:51:57 整体退出 0，28 个 cohort 全部通过，
拒绝 19006 个原始观测故障和 1989 个关联故障。结合先前 35 例，
全部 256 个 bank/set 的正向 DUT 和独立审计均已完成。见
[全 221 例审计](../results/coverage-bpu-native-five-alias-remaining221-audit-v1-readonly.json)。
这不等于全部四 way 负向路径或完整 FTQ 已闭合。

新 221 份已准入 raw 的隔离原生行增益测量已实际退出 0；22 项门禁
通过，1931 项输入身份最终核对通过。独立 AWK 的 9 项合同及完整
复核也实际退出 0，1938 项输入身份最终核对通过。相对所有旧候选和
正式命中，新增 2364 个行键；候选并集潜在增益从 1410 增至 3774。
这批 raw 自身为 28735/46541，是子集，不拿它替换正式 32264/46541。

新增行归因：AheadBtb 1651（861 递增赋值、790 初始化为 2 的赋值）；
AheadBtbReplacer 608；ReplacerState 102；MainBTB 的 ReplacerState_4 3。
这是完整 setup 与自然循环运行的贡献，不声称仅由目标 counter 激活，
不把调试一致性逻辑行或源代码行键算作新功能点。见
[独立行增益复核](../results/coverage-bpu-native-whole221-positive-line-review-v1-readonly.json)。

旧源码的所有依赖任务均已退出后才应用生产修复；旧签名 helper、
失败版本、normal raw/FC/四正式报告保留不改。生产后验证期间新源码
暂时冻结，后续需要登记已资格验证的功能点/覆盖组并正常全量刷新。
不可继续调用强制旧源码相等的 native_gate 来验证新纪元。原完整范围
不缩小，四 way 负向矩阵、真实 overlap、完整 FTQ 和 RTL XFAIL 仍未闭合。

## 历史状态：2026-10-10 00:09 北京时间

正式正常 memory-direct 全量、原生指标重合并及完整动态审计均已退出 0。
当前为 8190 PASS、7 strict XFAIL、0 SKIP，279/286 功能点 PASS；
BPU 正式 32264/46541，功能 covergroup 等权均值 99.205805%。
隔离候选并集潜在新增 1410 行，尚未并入正式报告或新增正式功能点。

本轮新证据：

- 三个提交节奏 DUT 虽然 PASS，完整 gzip 的独立物理 way 诊断证明
  way0/1 缺口仍在，不直接扩大这种激励。诊断已退出 0。
- final-NT 三节点初版五 DUT 全部 FAIL，原因是输入资格误用当前
  A→B token；40 个真实稳态 A 事件确认其当前索引来自两拍前 B→C。
  失败版本、轨迹和 raw 保留且排除准入，不作为 RTL 缺陷结论。
- 四节点修正版直接检查 A 当前使用的两拍前 C→D token。563 项
  纯模型与 50 项真实探针契约全通过；五坐标 DUT 在三个原生 worker
  中执行，原 session43785/owner2637047，没有提前宣称 PASS。
- 原剩余 221 正向独立审计已验证 live，170 个成功回执、0 失败；
  整轮未结束。原 256 坐标正向 DUT 全部通过，不重跑已完成 DUT。
- 行缺口已提取成 [待登记功能需求](coverage-integrated-abtb-functional-draft.md)：
  每物理 cell 的 final-NT/later-taken 分离、真实低饱和保持、final-NT
  副作用和 reset/write-feedback 重叠优先级。草案 bin 不算功能覆盖。

检查点 `/tmp/bpu-abtb-production-Cqa2Di/continuation-checkpoint-v78.json`。
生产源码、正常 raw/FC 和四正式报告继续冻结；完整原目标仍 active，
未由 ABTB 局部实验替代。以下为按时间保留的历史记录，不是当前数字。

## 历史记录

记录时间：2026-10-09（北京时间）。原全仓测试和报告生成已实际以0退出：
7848 PASS、7 strict XFAIL、275/275功能点，正式报告已生成29954/46541。
全部200份新轨迹的独立审计仍在原后继进程运行，正常收集保护尚未完成；
此前完整审计基线仍为29205/46541。最新隔离准入候选32264/46541不能提前
代替正式结果，也没有把隔离raw注入正式manifest。

## 本轮发现的实际刺激缺口

集成 AheadBTB 必须接收真实 S3 fastTrain。仅向某 PC 反复 redirect，不能保证
AheadBTB 的 S1 metadata 有效：原两个场景有目标 S3 token，却没有目标条件
计数器转换。失败 raw 已隔离，不参与正式 manifest。

新增隔离 monitor 使用 Bundle 绑定 S1/S2/S3 metadata、完整 fastTrain、公开
反馈接收、1024 个 counter、四个 replacer 的全部 256 个 PLRU state/shadow。
Rising 检查提交状态，DriveStable 检查实际转换控制；从 reset 开始独立维护
counter/PLRU 和 metadata 流水线，并复用完整 PHR 参考及精确 token 关联。
它没有建模完整 AheadBTB SRAM 或独立推导 write response 生成，不能作此声称。

自然循环配方使用条件自环及三块 fallback：所有分支的 path hash 为零。
测试文件只有场景意图，时钟、绑定、反馈、观测和比较留在复用组件中。
诊断进一步发现：

- 在 MicroBTB 首次有效读取前关闭它，会使父模块使用尚未更新的预测位。
  新版本先捕获真实冷启动结果，不改 RTL、不给参考模型灌入观测状态。
- MainBTB 的新分支分配需要选中该分支的 mispredictInfo；提交一个 valid
  分支但不选中它，并不能证明分配发生。前一版 metadata 读回实际只有位置 4，
  没有预期的位置 7 fallback。新版本先把早分支准备到 not-taken，再用唯一的
  晚分支 mispredict 分配 fallback，并要求实际 metadata 和三 PC fastTrain 见证。
- 切换阶段确实有 counter 从 3 被 reset 到 2 的轨迹。这不是 `dec3_2`，不能
  用来填 decrement bin。增加排空也没有单独解决缺口，仍须先保证 fallback
  真正驻留和闭环。没有据此认定 RTL 缺陷。

v7、v8 均实际为 1 PASS、1 FAIL：bank0 有全部八类转换，bank1 缺少下降阶段
`dec3_2`。整批 raw 全部排除。对已通过的 bank0 轨迹，独立 reset 重放与
15 类观测扰动已实际通过检查：counter、PLRU state/shadow/victim、两级
metadata、fastTrain PC/valid、最终 target、enable、S1 metadata、PHR cell/fold
和反馈 metadata 的扰动均触发普通、带状态的 ScoreboardMismatch。
这是单例重放调试证据，不是两例准入，更没有增加原生行命中。

最新刺激位于 `/tmp/bpu-abtb-integrated-430CGL/v9`；22 项纯检查、两个实际
DUT 场景均已实际通过，两个 bank 的真实 fallback PC 均被见证。完整两例
独立重放与 30 类负对照也已实际通过：共 3588 个 rising 帧和同数 preedge 帧。
ABTB bank0/set0/way3 和 bank2/set0/way3 各自实际完成全部八类转换，
不是跨不同 way 拼凑。独立重算的 16 个 PC-bank × transition bin 全部命中。
当前选择仅涉及 ABTB banks 0/2 的 set 0，不能代表所有物理格子或完整 FTQ。

仅合并这两份通过的 raw 与已封存的 SC 候选 29954/46541，精确额外关闭
213 行，得到新候选 30167/46541：两个 BypassShadowBuffer 分别 51/127 行，
MicroTage 八行、AheadBtb 18 行、AheadBtbReplacer 六行、CommonHR 两行、
ReplacerState_4 一行。没有新缺口，456 个已分类缺口及完整分母全部保留。
正式四份报告保持字节不变；没有注册新功能点或正式入账。

证据见 `results/coverage-bpu-natural-integrated-abtb-native-candidate-readonly.json`
及 `results/coverage-bpu-natural-integrated-abtb-v9-replay-readonly.json`。
其中 178 个旁路缓冲命中是随自然流发生的旁带命中，不等于该模块已完成
功能验证。例如 `rtl/bpu/BypassShadowBuffer.sv:2265` 是训练 counter 的更新
选择，`:2280` 起是 shadow enqueue 的完整 payload 赋值；对应
`XiangShan/.../utage/BypassShadowBuffer.scala:185..195,231..234`。
下一批须为真实 fastTrain 下的分配/更新选择、同 index 转发和 shadow
enqueue/回绕/排空建立独立状态与公开结果检查，不能借用独立 MicroTAGE
覆盖命中，亦不能把其余旁路缺口全部归因为 tag-width 缺陷。

## 全仓刷新与外部源码变化

原始正常全仓 pytest 没有重启。外部 xcomm 从旧 master 切到
`fix/native-memory-boundaries`，随后又有未提交编辑；本轮运行的 1087 个
ROOT/DUT/xreactor 文件及四个系统运行库仍与启动时 SHA 一致。
新资格门禁显式保存当前分支、commit、工作树差异和运行库身份，不声称
这些新 xcomm 源码已构建、安装或正确性/ABI 已验证。

旧门禁及其拒绝记录全部保留。新增 v3 接续等待现有任务，只在先前门禁
因未编译源码状态拒绝时，接续完整独立审计：新 200 个场景、既有 96 个 SC
和 144 个 AheadBTB 场景、676 份 raw、十个 DUT 的 JSON/LCOV/HTML、
275 个功能点、精确 749 行候选增量，以及 456 个已分类缺口的原分母保留。
结构检查已实际通过；这不等于完整刷新审计已经通过。

运行库身份与源码变化证据：
`results/coverage-bpu-xcomm-mutable-source-runtime-qualification-v3-readonly.json`。
接续门禁位于 `/tmp/bpu-sc-promotion-sXKZEx/branch-qualified-v3`。

完整目标仍包括集成 TAGE、PHR、RAS、bypass、SC 更广历史/SC-used/overlap/
overwrite/FTQ，以及剩余分支和功能组合；不得以这批 AheadBTB 诊断完成替代。

## 旁路伴随命中的独立检查

后续隔离原型 `/tmp/bpu-bypass-integrated-znyFfC` 已为两张集成
MicroTAGE 表增加静态只读 Bundle、两相位 monitor 和 reset-derived reference。
逐帧比较全部 16 个 shadow cell（包括两层 valid）、16 个 status cell、1024
个 useful counter、两套环指针/flag、priority mask 和注册选择状态。分配与更新
counter 的来源、同索引训练转发及预测端最新项选择独立推导；写回成功由
预测的环状态与实际请求 bank 推导，不以观测到的 writeSuccess 代替预期。
训练输入仍取自真实表边界，未独立预测父模块完整分配策略或建模 SRAM 保持。
已知同槽 dirty 清除缺陷仍会违反参考契约，没有被复制为“正确行为”。

实际结果：29 项纯检查、两个真实 DUT 场景、两次完整 reset 重放和 60 项
观测扰动均已通过。两例合计 7176 个交替相位帧、160 笔写入：每例低表
一次分配，高表一次分配及 78 次 resident 更新。上层表各有九次 enqueue
回绕；低表未回绕。case0 两表都没有写回成功，case1 两表各一次成功，均
没有 force-write，不能以回绕声称 SRAM 持久化验证完成。

训练来源使用独立 functional coverage：PC-bank × table × source 共
12 个 cross bin，只命中 6 个，**不是 100%**。缺少低表 resident、两表
captured-counter 来源。两个测试通过率与此覆盖率是不同口径。
这批正例重新合并封存候选后精确复现原 213 行增量，仍为 30167/46541，
额外新增行为零。旧正式四报告不变，未注册功能点、未正式入账。

证据：`results/coverage-bpu-integrated-bypass-reset-replay-readonly.json`、
`results/coverage-bpu-integrated-bypass-native-equivalence-readonly.json`。

原生候选的两份旁路文件还缺 3708/3112 行，共 6820 行。其中 4600 行
直接引用 useful 单元，分别涉及每表全部 512 个 index；其余行保留原样，
没有把未分类行判成不可达，也没有移植独立 UTAGE 的 tag-width 排除范围。
新清单逐行保留代码、bank/inner index 和原 LCOV 身份，指向 useful 索引/
强度/aging、低表 resident/环回绕、捕获 counter、读写 bank 冲突/force-write
和全 shadow 替换后的公开读回。
见 `results/coverage-bpu-integrated-bypass-native-gap-inventory-readonly.json`。

低表新刺激保留了实际失败：v2 四边路径未全满足零 path hash，纯检查失败，
没有运行 DUT；v3 修正完整路径后五项纯检查通过，真实 DUT 在“至少八笔
低表更新”前提处普通失败。实际只有一次低表分配、一次 resident 更新；
首个低表分配后四周期，旧流水 miss 又分配高表，后续 166 次更新转向高表。
该版所有状态比较均先通过，但不足以满足低表回绕，失败 raw 全部排除。
v4 实际 DUT 已通过，五项路径/tag 纯检查也已通过：首个合格 S3 后对年轻
预测背压，排空后用实际 checkpoint 丢弃 held stale miss，再恢复自然流。
没有写内部状态或伪造 metadata。实际低表一次分配、48 次 resident 更新，
八个槽位全部使用、六次 enqueue 回绕；高表随后一次分配、125 次更新。
共 4486 个交替相位帧通过在线状态检查。独立 ABTB/PHR 和旁路完整重放、
30 项观测扰动及正例原生行增量准入已实际全部通过。

仅合并该正例 raw 与已封存的 30167/46541 候选，精确新增 **85 行**：
`BypassShadowBuffer.sv` 83 行，`BypassShadowBuffer_1.sv` 两行，得到隔离
候选 **30252/46541**。没有新增缺口，完整分母与 456 个已分类缺口保留。
这才是本轮新增行数；前述 213 行复现没有重复累计。正式四报告仍字节不变，
尚未注册正式功能点或入账。证据：
`results/coverage-bpu-integrated-lower-shadow-ring-native-candidate-readonly.json`。

此例只证明实际 index0 的下层 resident、八槽和六次回绕，不证明所有索引、
捕获 counter 来源、force-write 或完整 SRAM 持久化。父模块完整分配策略仍
未作为独立参考模型；tag-width 与同槽 dirty 两项 RTL 缺陷也未修复。

特别是新增行中虽有低表 `:1617/1618` 的 captured-counter 加减表达式，
它们位于无条件求值的局部组合计算；后续 Mux 仍可能选择 resident counter。
实际参考回放没有观察到 captured-counter 来源，不能用这两行命中填补该
functional bin。这也是行覆盖与功能覆盖必须交叉分析而不能互相替代的实例。

当前 30252 候选旁路剩余缺口为低表 3625、高表 3110，共 **6735 行**；
其中直接 useful 引用 **4596 行**。旧 6820/4600 清单仍保留其对应的旧候选
身份，新清单见 `results/coverage-bpu-integrated-bypass-native-gap-inventory-v2-readonly.json`。

## SRAM 边界检查：实际复位、请求与有定义的响应

行缺口分析还指出“环回绕”不能替代真实 SRAM 写回和替换后读回。因此在
同一隔离原型中新增四 bank SRAM 参考：初始内容未知，从实际复位扫描和
独立预测的 shadow 写请求推导 512 个 entry；不读取 DUT RAM 内容作为
预期，也不使用观测到的 writeSuccess、resetDone 或读数据推进参考。
检查覆盖两表八个 bank 的 read/write 请求、复位计数、clock-enable、
array 地址／写模式／17-bit payload，以及有定义时的完整响应。
原始 `array_128x17.sv` 在写模式下规定输出 X，因此不把两态仿真返回的
零值当作“保持上一读值”，也不将这类未定义 payload 纳入比较。

v5 保留了一个实际失败：tick12 bank selection 预期 8、实际 0。源码和
实际跟踪确认这里不是 RTL 缺陷，而是 monitor 将 Rise-written reset 的
Python 待提交缓存当作当前 RTL 输入。tick11 的实际证据是 requested=0、
committed=1；该边沿仍须执行复位。v6 改为静态 Bundle 绑定实际 RTL reset
wire，原有 driver 和测试相位不变，没有引入 testcase FallingEdge。

v5 的 22 项纯 SRAM 规则检查通过；v6 一个真实 DUT 用例通过，4486 个
交替相位帧完成 106570 次 SRAM 比较和 8458 次有定义的表响应检查。
独立从 reset 重放全部 SRAM／旁路和 ABTB／PHR／公开 metadata，再执行
165 项观测故障对照，均抛出预定 tick 的普通 contextual ScoreboardMismatch。
另外反转每一帧的 pending reset 缓存，独立参考的推进和比较结果保持不变，
证明参考只依赖 committed RTL reset，而非待提交请求。

独立门禁 v1 保留摘要比较失败记录：原刺激和外层 wrapper 各调用一次
`finish()`，该 API 的“已观察 reset”检查会增加通过计数；首次回放只调用
一次，因此 checked/passed 各差一。v2 分别精确复现两次调用，逐一核对两份
原始摘要后通过，没有删减状态比较或放宽计数条件。

只合并本次通过的 raw 与已封存 30252 候选，原生行集合精确不变：
**额外新增零行**，全部 456 个已分类缺口及完整分母保留。此批完善的是
检查能力，不应算成覆盖率提升；仍不证明 force-write、完整 shadow 淘汰或
父模块完整 allocation 策略。v5 失败 raw 和 no-clock capability raw 均排除。
证据：`results/coverage-bpu-integrated-SRAM-defined-response-v2-readonly.json`。

下一隔离 v7 使用两个不同 index、同 bank 的真实零历史程序，先于任何
训练捕获全部六个 genuine checkpoint，再通过正常反馈安装两组分支。
目标是见证旧 key 的 forced SRAM 写入、冲突响应 invalid、旧 shadow 八槽
全部淘汰，以及旧 key 的 SRAM 和公开 UTAGE metadata 读回。六项路径／
索引纯检查实际通过。真实 DUT 随后因冷 checkpoint 顺序超时而失败：先扫描
到旧程序高地址，再等待已经走过的新程序低地址；3220 个监控帧没有状态
比较失败，但刺激未满足前提。该版失败 raw 全部封存，不参与合并。

v8 将冷 checkpoint 按地址排序，增加单调扫描及旧错误顺序的回归检查，
八项纯前提实际通过。真实 DUT 完成 7008 个监控帧，在第二 key 上层至少
八次更新的场景前提处普通失败：实际两表都只各分配一次，没有 resident
更新、force-write 或 SRAM 写入。生成 RTL 的完整 tag 比较确认，该 PC
低表 full tag1040、上层 full tag2336，分别只存入16／32，故两表均不能
resident；不能把无更新误判为等待不足。该版失败 raw 全部排除。

v9 换成上层 full tag0 的合法 position4 程序，但其旧 PC 辅助回归断言
将上层 full tag 错写成288，纯检查实际九通过一失败，未运行 DUT。
v10 修正该辅助断言为2336，十项路径／索引／两表完整 tag／冷扫描前提
实际全部通过；新的第二 key 为 index128，上层 full tag0，下层 full
tag2080 的既有缺陷仍保留。真实 DUT 已启动，实际结果和独立准入前没有
功能 PASS、原生行增量或正式入账声明。额外两表 × 四 bank 的八项纯
force-write／全 shadow 淘汰后 SRAM 读回契约检查也已通过，JUnit 保存在
`/tmp/bpu-bypass-integrated-znyFfC/v8/checks/force-contract-v2.xml`；它不创建
DUT 或 raw，不能代替上述真实场景。

v10 的真实 DUT 最终普通失败于首次旧 key 公开 metadata 没有有效条件槽位，
不是 SRAM payload 比较失败。之前已实际见证：上层 index128 四十次 resident
更新；tick6733 以 force=1 在 bank0 写回旧 index0 的 valid1/tag0/position0/
counter7；tick6735 冲突 raw valid=0；tick7017 shadow miss 时完整 SRAM
响应仍为上述 counter7。全部 7020 帧的旁路／SRAM 状态比较先通过。
新程序已替换旧 ABTB 条件项，而首个 redirect 返回还使用规定无效的 UTAGE
metadata，readIndex 为前一个160。故不能用这个 transaction 判定公开读回
失败，更不能把失败批次合入原生覆盖；本版 raw 仍全部封存排除。

v11 保留同一真实写回路径，让正常 S2 MainBTB correction 和 S3 fastTrain
恢复旧 ABTB 条件项，无新增 redirect、内部状态写入或 fabricated metadata。
只跳过没有 valid／目标 position 条件槽位的 transaction；遇到首个有效槽位
就立即比较 hit／provider／counter，不按 counter 正确与否筛选。十四项
路径、tag、扫描及该资格谓词的纯检查实际通过，包括有效但 counter 错误时
不得过滤的反例。真实 DUT 最终在 7148 个监控帧后普通失败：连续等待的
32 笔旧 key transaction 均没有有效目标条件槽位，因此没有跳过一个错误
counter 来挑选正确结果；该版 raw 仍全部排除。真实强制写回、冲突 invalid
及 shadow miss 的 SRAM counter7 读响应仍然存在，公开接口路径尚未闭环。

源码复核找到缺失的刺激前提：`AheadBtb.scala` 的正常 fastTrain 可以在
miss 时分配条件项，但 `AheadBtbBank.scala:72..99` 明确规定 SRAM 读优先，
`writeBuffer.io.read.head.ready` 和 `writeValid` 均被 `!io.readReq.valid`
门控。连续同 bank 预测不会给已排队的恢复写入机会，单纯增加等待无效；
这不是一个新确认的 RTL 缺陷。现有 `BpuAgent.pause_prediction_reads`
已封装该读空窗，不需要测试暴露 edge 或底层信号写入。

新隔离 v12 在首个无效旧 key transaction 后，等待真实 S3 fastTrain 入队，
再由上述 driver API 暂停预测读 12 周期。后续仍按顺序检查全部已捕获任务，
首个 valid／目标 position 槽位必须立即比较 hit／provider／counter；不按
正确值筛选，也不写内部存储。十四项纯前提和资格检查已实际通过，真实
DUT 已启动。新的准入脚本还要求监控记录证明读空窗内确有 ABTB 写提交，
并将扰动实际 force-write、SRAM 读回及公开 metadata 检验异常敏感性。
v12 真实 DUT 已以 1 退出，7078 个监控帧。读空窗内 tick7041／7043／7047
已发生真实 ABTB 写提交；首次有效旧 key 公开预测 tick7074（meta7078）
的两个条件 way 均返回 hit1／table1／counter7，预测为 position0 taken、
目标旧 key 自循环。失败在原测试要求“只能有一个条件槽位”的前提，非上述
provider／counter 错误。失败 raw 仍全部排除，没有给此版原生行命中入账。

`AheadBtb.scala:322..361` 明确实现 detectMultiHit 和排队 invalidation，
`MicroTage.scala:216..237` 的公开 metadata 则逐 ABTB way 返回，并非 one-hot
协议。因此新 v13 不取第一个正确结果：根据同 prediction tick 的 ABTB
输入推导完整四 way valid mask，逐项比较 valid／hit／provider／position／
counter／predTaken，同时检查完整公开预测 PC／target／taken／position。
重复项清理前先核对全部 way，再提供真实读空窗，要求实际清理回一个条件
way，期间所有返回任务仍逐项比较。完整 ABTB SRAM／writeResp 生成参考
仍未实现，不将观测输入关联误写为这部分独立模型证明。

v13 三十三项纯检查已实际通过，包含两个重复 way 分别六字段错误、公开
预测四字段错误、readIndex 错误及缺失向量元素的普通异常反例。真实 DUT
最终通过：7132 个监控帧、183820 次 SRAM 比较、13750 次完整已定义 table
响应核对；公开多 way 及清理后单 way 均为 counter7。独立 SRAM／shadow
完整回放和 pending-reset-cache 反转也通过，但后续 ABTB／PHR 回放在
严格的结束排空条件处退出 1：最后一帧 fastTrain.valid／meta.valid／enable
仍为 1，正常接收的任务尚在 counter 参考流水线中。未修改该旧检查，v13
raw 未准入，也未生成 native 合并候选。

该轨迹还自然出现了之前缺失的上层 captured-counter 来源：tick7083 在
旧 index0 已从八槽全部淘汰、train_has_hit=0 时，使用真实公开 metadata 的
counter7 做更新，并非把无条件算术行命中当作功能覆盖。此路径仍需最终
准入和实际观测故障对照，不能以未完成的独立审计宣称功能点闭合。

新 v14 保留全部逐 way 和 multi-hit 检查，在结束前停止新预测、排空真实
已接收任务，且现场断言 counter 参考流水线的 pending1／pending2 均为空。
三十三项纯检查及真实 DUT 已实际通过：7152 个监控帧、184340 次 SRAM
比较、13790 次完整已定义 table 响应核对；末帧 fastTrain.valid／t1_fire
均为 0。新的准入还将扰动实际
captured-counter 输入，要求下一拍的 committed state 通过普通异常拒绝
错误值；同时保留原完整回放、两次真实 ABTB 写提交和公开接口故障对照。
独立 SRAM／shadow 完整回放、pending-reset-cache 反转，以及此前拒绝
v13 的完整 ABTB／PHR／metadata 回放均已实际通过，末尾未完成任务问题
已修复。准入脚本随后实际以 0 退出：178 项真实状态／输入观测故障、28 项
公开 metadata／预测字段故障均触发普通带上下文的 ScoreboardMismatch；
captured-counter 输入错误在下一 rising committed state 被拒绝。它们是
轨迹故障回放，不是 206 个实际 DUT 负向用例，也不产生可合并 raw。

仅合并 v14 这一份通过且独立准入的 raw 与 30252 封存候选，精确新增
24 个原生映射行至 **30276/46541**：`AheadBtbReplacer.sv` 15 行、
`ReplacerState.sv` 三行、`AheadBtb.sv` 两行、`CommonHR.sv` 两行、
`BypassShadowBuffer_1.sv` 一行、`ReplacerState_4.sv` 一行。没有新缺口，
456 个已分类缺口和完整分母仍保留；v11／v12 失败 raw 与 v13 未准入 raw
均未合并。新增旁路行是 upper `t1_trainReadEntry_takenCtr_value` 的
captured-counter 转发赋值，不应把全部 24 行都归为“强制写回分支”。
旧 key 的真实强制写回、raw 冲突 invalid、全 shadow 淘汰后 SRAM 回读、
公开两 way 全比较和 multi-hit 清理仍由完整行为见证证明，不依赖行命中
冒充功能验证。证据：
`results/coverage-bpu-integrated-upper-force-writeback-native-candidate-readonly.json`。

新原生缺口清单精确剩余 6734 个旁路行，其中 useful cell 直接引用仍有
4596 行；未把 missing 认定为不可达，也未从独立 MicroTAGE 转移任何排除。
见 `results/coverage-bpu-integrated-bypass-native-gap-inventory-v3-readonly.json`。
全 bank × 两 table × 三种训练来源的功能矩阵使用四份已准入 DUT 轨迹
重新采样，实际仅 **8/24** 个 bin 命中：下表 captured-counter、bank1
lower resident／两表 captured-counter，以及 bank2／3 的全部来源仍缺失。
此矩阵与本用例六个阶段 bin 全命中是两个不同口径，均非功能点通过率。
见 `results/coverage-bpu-integrated-bypass-training-source-matrix-v2-readonly.json`。

上述均为隔离准入候选，未注册到正式功能点或注入正式 manifest。原始
275 功能点全仓刷新及其完整独立审计仍未结束，当前已审计正式基线仍为
29205/46541；后续须保留原范围完成正式迁移、刷新及其他模块缺口验证。

### 非零 PHR 的真实物理 bank 与训练来源补齐

继续从上述 8/24 来源矩阵分析，发现零历史自循环不能通过简单更换 PC
覆盖所有物理 bank。实际编译的 `rtl/bpu/MicroTage.sv:238..240` 使用
lower 的 `(6,6)` fold 和 upper 的 `(12,9)` fold 计算索引；upper 的低两位
还受历史高位折叠影响。因此 PC bank、path-hash 低两位和实际 SRAM bank
不能混用，也不能按当前 Scala 默认参数替代已编译 RTL 的参数。

隔离 v15/v16 使用真实 conditional/fallback 自循环与正常 MainBTB 反馈，
分别以 PC `0x40010004/5/6`、条件位置 `8/7/6`、fallback 位置 `12/11/10`
构造非零历史。两条分支都返回自身 PC，条件方向通过实际公开反馈改变；
连续自然流窗口内没有外部 redirect。checkpoint 来自 reset 后真实捕获的
同半块 `PC-1` transaction，而非复制 DUT 状态或伪造 metadata。

新的通用参考仅移除了旧刺激专用的“历史必须为零”限制，仍从 reset
比较完整 52 个 physical PHR cell、76 个 fold register、1024 个 ABTB
counter 和 256 个 PLRU 状态。额外的静态只读 Bundle 逐相位采样 parent
hash 输入，独立检查 oldFoldedPhr 的 redirect/S3/S2/S1 优先级、四个 S1
tag fold 连线，以及两表由 PC 和参考 PHR 推导的真实 readIndex。
既有完整 shadow/useful/SRAM 参考保持复用，测试用例不处理 edge 或信号。
完整 UTAGE allocation policy、ABTB SRAM/writeResp 生成及完整 FTQ 资格
仍未宣称已建模或证明。

v15 两项真实 DUT、九项纯配方检查通过；v16 一项真实 DUT、五项纯检查
通过。三个场景各保存 4564 个交替相位帧，全部独立从 reset 重放、重新
关联真实公开 transaction/反馈，并通过 pending-reset-cache 反转对照。
新通用 PHR 参考也重新通过此前已准入 v14 的完整 7152 帧零历史轨迹。
46+23 项高位 physical history/fold、parent hash 连线、readIndex、深槽
状态、未选 useful cell、ABTB counter 和 SRAM valid 观测故障均在目标拍
抛出带上下文的普通 ScoreboardMismatch；它们不是 69 项 DUT 负向运行。

只合并这三份实际通过且独立准入的 raw：v15 新增 119 行至 30395/46541，
v16 再新增 65 行至 **30460/46541**，本轮精确增量 184 行。按文件为
`BypassShadowBuffer.sv` 69、`BypassShadowBuffer_1.sv` 52、`AheadBtb.sv`
33、`AheadBtbReplacer.sv` 24、`ReplacerState.sv` 六行；无新增缺口，
完整 46541 分母、456 个已分类缺口和四份正式报告均保持不变。
准入见 `results/coverage-bpu-integrated-nonzero-bank-native-candidate-readonly.json`
及 `results/coverage-bpu-integrated-nonzero-bank1-native-candidate-readonly.json`。

全四 bank × 两表 × 三来源矩阵重新按实际 `index % 4` 采样，先从 8/24
升至 20/24，再补 bank1 lower resident 至 **21/24**；剩余三项均为 upper
在 bank1/2/3 的 captured-counter，未从分母删除。lower 的全部 12 个
定义来源 bin 命中不代表所有地址、counter 方向或 useful/aging 状态闭合。
矩阵见 `results/coverage-bpu-integrated-bypass-training-source-matrix-v4-readonly.json`。
新的精确原生缺口清单仍有 6613 个旁路映射行，其中 4545 行直接引用
useful cell；没有将这些 missing 行认定为不可达。清单见
`results/coverage-bpu-integrated-bypass-native-gap-inventory-v5-readonly.json`。

本轮仍是隔离候选，未注册正式功能点或注入正式 manifest。原始全仓刷新、
完整独立审计和正常收集保护仍须完成；正式已审计基线仍为 29205/46541。

附加的独立来源门禁已实际通过：三份轨迹共九次 lower captured-counter
更新，覆盖实际四个 bank，均为非饱和 **3→4**。对于更新 preedge tick N，
精确使用 N-5 的真实公开 metadata、N-4 的 S3 fastTrain 和 N-2 的训练
读响应，推导优先级选中的 way、完整 tag 截断、position、counter、taken、
useful 两字段及注册 index；不按正确 counter 筛选 transaction，不使用
周期容差。九次更新时八个 shadow 槽均不含该 key。分别改错九次真实
captured-counter 输入后，完整 reset 回放均在 N+1 的 committed state
处抛出普通带上下文的 ScoreboardMismatch。见
`results/coverage-bpu-integrated-nonzero-captured-lineage-readonly.json`。
它不创建 DUT/raw，不增加原生行命中，也不证明 negative/saturation 全矩阵
或完整 parent allocation policy。

### Upper captured-counter：失败刺激诊断与来源检查补强

继续补查 upper 在实际 bank1/2/3 的 captured-counter。v17 在首个时钟前
失败；v18 的冷启动流错误地期待后续非对齐 PC 再次出现，实际以 2 退出；
修正真实 aligned cold lead／同半块 checkpoint 后，v19 三项 DUT 仍全部
失败。数学上相同的 path hash 不保证实际 upper 训练，更不保证旧 shadow
条目已被驱逐。上述失败 raw 全部保留但不准入，不能据此补齐来源矩阵。
三份实际失败轨迹及来源计数见
`results/coverage-bpu-integrated-upper-captured-failed-scenario-diagnosis-readonly.json`。

通用 captured-counter 来源检查器还补上完整 source PC 比较：仅比较 tag
会漏掉 hash 未使用的 PC 位。新版本已在四份既有已准入轨迹中，独立从
reset 重构训练缓存，重新通过十次真实更新（九次 lower、一次 upper），
并逐次拒绝 counter／position／readIndex／tag fold／完整 PC／taken 的
六种扰动，共 60 项普通带上下文 ScoreboardMismatch。它不创建 DUT/raw、
不增加行覆盖率，也不证明实际 DUT 已覆盖 shadow-tag-mismatch 来源。
见 `results/coverage-bpu-integrated-captured-provenance-generalization-v2-readonly.json`。

新的 v20 双程序尝试实际失败于旧 SRAM 持久化的过早前置条件：旧 upper
index25 的八份 shadow copy 都已有 counter7，但该索引还没有一次 bank
write。最后 preedge tick3375 的 readIndex 与 writeIndex 同为25、force=0、
writeSuccess=0。完整 shadow 的 3376 帧独立 reset 回放通过，live SRAM
比较器没有状态首错；失败来自前景意图检查，而非允许忽略状态不一致。
实际 `MicroTageTable.scala:106..109` 的 writeSuccess 只按 bank 不同或 force
判断，并不包含 read-request-valid，因此暂停预测读不等于该写回已提交。
见 `results/coverage-bpu-integrated-upper-premature-persistence-diagnosis-readonly.json`。

后续 v21 保留全部逐拍参考和比较，只修正场景前置条件的顺序：先检查
selected shadow payload，再运行另一个经过正常反馈训练、索引和 bank
都不同的程序，要求旧条目从全部八槽消失且完整 SRAM payload 正确，
最后返回旧程序检查 no-shadow SRAM 响应、所有公开 way／预测及真实
captured-counter 更新。新增 19 项纯检查已实际通过；真实 DUT 和独立
准入结果须以其退出收据和准入报告为准，不能以此段计划计账。
本段诊断未改变 30460/46541 隔离候选或 21/24 来源矩阵，正式已审计
基线仍为 29205/46541，完整目标及其他模块缺口保持不变。

v21 随后实际以 1 退出：第二程序真实产生 112 次 upper 更新，旧 index25
已从全部八槽消失，完整 SRAM payload 保持 valid/tag99/position6/counter7。
独立 shadow 重放及精确来源投影确认返回阶段六次 upper captured 更新，
实际涉及 bank1/2/3；但前景公开检查错误地用当前 PHR echo 资格化较早任务。
例如 prediction tick6464 的 echo 已为31，关联 readIndex 却仍来自较早的
`(31,25)` index folds，为 `[25,31]`，不能期待 `[25,25]` 或 counter7。
整项用例失败，故这些更新不作为 PASS 或覆盖率入账；见
`results/coverage-bpu-integrated-upper-public-qualifier-diagnosis-readonly.json`。

新 v23 增加独立 a0/a1/a2/a3 index-token 参考：按实际 enable/fire、S2 hold、
S3 优先复用和 reset 推进，不使用固定 tick 延迟；静态只读 Bundle 采集控制
及模块 metadata 输出，monitor 同时比较模块索引寄存行为和精确关联的
公开 metadata。旧 SRAM 返回的资格只看独立 token 的原始 PC/folds、ABTB
输入和 redirect guard，不按实际 UTAGE index/hit/counter/预测筛选。

v23 已实际通过 25 项纯检查和一项真实 DUT 检查，保存 6632 个相位帧，
完成 6631 次索引寄存检查、1100 次公开索引关联和 230805 次 SRAM 比较。
第一 reset 边沿前的未初始化帧单独保留，不当作已定义状态来比较。通过
轨迹同时见证 bank1 旧索引的饱和7→7，以及 bank1/2/3 的非饱和4→5
captured 来源。完整独立 reset 重放、pending-cache 反转及 30 项来源／
下一拍状态／公开索引故障对照已启动；只有全部准入后才能合并这份 raw。
截至本段，尚无本批新增原生行或正式功能点计账，旧失败 raw 全部排除。

### Upper 来源准入完成与 useful 行为缺口

v23 的第一版准入脚本在所有回放及故障检查后，因报告阶段引用了错误的
provenance helper 路径而失败。保留该版本及未准入的中间产物；新 v2 修正
实际 helper 路径并完整重跑，已实际以 0 退出。6632 帧完整 reset 回放、
pending-cache 反转和 30 项带上下文 ScoreboardMismatch 对照全部通过。
只合并该项 PASS 的 raw，精确新增 **96 行**，隔离 BPU 候选由
30460/46541 提升至 **30556/46541**。其中 lower/upper bypass 分别新增
24/18 行，AheadBtbReplacer 27 行，AheadBtb 20 行，两个 ReplacerState
分别 6/1 行。456 个已分类 missing 行全部保留，不缩减分母。
见 `results/coverage-bpu-integrated-two-program-upper-bank1-native-candidate-readonly.json`。

八份已独立准入的正向轨迹将四 bank×两 table×三训练来源矩阵补齐为
**24/24**；新增的是 upper bank1/2/3 的真实非饱和4→5 captured 来源。
完整旧 key SRAM 持久化及八槽驱逐仍只证明了 bank1；来源 bin 闭合不
代表所有地址、方向、useful 强度、老化、重叠或 FTQ 合法性闭合。
见 `results/coverage-bpu-integrated-bypass-training-source-matrix-v5-readonly.json`。

新的精确旁路缺口为 **6571 行**，其中 **4527 行**直接涉及 useful cell。
按真实源码块进一步分为老化 1536 行、饱和更新 2023 行、分配 968 行；
其余行和所有未分类行原样保留。两 table×四 bank×七种 useful 行为矩阵
目前仅 **21/56** 命中：分配、增加、减少、高/低饱和保持、零/非零老化
分别定义，不以训练来源闭合代替行为覆盖。完整 reset 重放了上述八份
轨迹的全部 shadow 和 1024 个 useful 值；没有观察到老化。
见 `results/coverage-bpu-integrated-bypass-native-gap-inventory-v6-readonly.json`
及 `results/coverage-bpu-integrated-useful-operation-gap-matrix-v1-readonly.json`。

### 父级训练策略与真实老化阈值资格化

新增独立父级参考以真实公开 metadata 和 reset 推导的 T0 useful/position
读响应为输入，推导 mispredict 选择、provider/keep mask、分配优先级、
更新及 useful 条件和注册的失败分配计数。18 项纯策略检查及一项已准入
真实轨迹重放通过，共 29606 次比较、1100 个精确关联的公开来源。八次
失败都发生在两个程序的 positive_again 阶段：选择 lower provider，而
upper 的 useful 非零阻挡继续分配；不是 upper provider 失败。旧轨迹未
直接采样数字 lowTickCounter，该限制明确保留。见
`results/coverage-bpu-integrated-parent-policy-failure-analysis-readonly.json`。

隔离 `policy-live-v1` 又通过 43 项纯检查和一项真实 DUT 检查，在原先
全部 SRAM/PHR/ABTB/index 比较上新增 **19893 次**父级策略比较，并通过
静态只读 Bundle 直接采样 lowTickCounter、T1 fire/needAlloc/normalMask。
实际数字计数与 reset 参考一致，累计八次失败、最高8、零次老化。
这不证明完整公开预测参考，也不增加原生行命中或正式功能点。

其第一版新门禁沿用了“坏 counter 必须到 N+1 才报错”的旧假设，实际
父级输入参考在 N 拍已经抛出带状态的 ScoreboardMismatch，因此脚本
以 1 退出；不是 DUT 比较失败。旧脚本保留，新 v2 严格要求 N 拍检测，
重新执行完整回放、pending-cache 反转、30 项来源/索引和六项父级控制
故障对照。准入须以新门禁实际退出结果为准，不提前合并其 raw。

新的隔离 `aging-v1` 场景通过 **49 项纯检查**后已启动真实 DUT。它只用
正常预测、真实 checkpoint 和完整公开反馈切换方向，在最多40对负/正
方向训练内尝试累积128次失败并触发老化；没有内部计数器写入、伪造
metadata 或 testcase 边沿/get-set。全部逐拍参考保留，若不能达到阈值
则普通 assertion 失败，失败 raw 不准入。当前不计老化命中或行增量。

原始完整正式刷新及两个等待后继进程仍按原句柄运行，没有重启。
1087 个 ROOT/runtime 源文件继续冻结；正式审计和正常收集完成前，
正式已审计基线仍为29205/46541，30556只是独立准入的隔离候选。
完整目标仍包含集成 TAGE/ABTB/bypass/PHR/RAS/replacer、SC 的非零
历史/all-index/SC-used/重叠/完整覆写/FTQ，以及七项严格 XFAIL 对应的
六个 RTL 问题。上述来源矩阵闭合不是目标完成。

### 数字父级策略门禁完成，长场景记录预算诊断

`policy-live-v1` 第二版门禁完成了全部正向及既有来源故障重放后，新增
fire 故障选点误选 tick1、首次 reset 前的未定义帧，因未检测该无定义
状态而失败。保留 v1/v2 源文件和失败记录；v3 只在 reset 后有效帧选点，
完整重新运行，已实际以0退出。6632帧 reset 重放、pending-cache反转、
36项来源/索引/数字控制/输入故障对照全部通过。此项刺激与既有 v23
相同，原生新增为 **0**，候选仍为30556/46541，不重复计账。见
`results/coverage-bpu-integrated-parent-policy-numeric-aging-qualification-readonly.json`。

`aging-v1` 的真实 DUT 用例实际失败于 tick16385 的验证器记录容量断言：
旧监测器最多保存8192个 preedge。独立从 reset 回放全部16384个有效
相位帧，共 **81915次**父级/旁路比较全部通过，数字失败分配计数最高
**32**、零次老化；未发现状态首错。12个完成的方向 epoch 中，第一对
产生5次、后续每对只产生2次失败，因此原计划40对即使不撞记录上限也
不足以达到128。失败用例不算 PASS，所有 raw 和功能 bin 均不计账。
见 `results/coverage-bpu-integrated-aging-record-cap-diagnosis-readonly.json`。

新增 **32项纯检查**已通过：从 reset 通过输入构造每张表全部512个
useful值，覆盖四种强度和四个bank；分别将老化与 idle、分配、增加、
减少同拍，比较全部512个结果，确认老化使用旧值且优先于当拍训练。
这仅是参考模型资格化，不证明真实 DUT 已覆盖这些同拍场景。

新的 `aging-v3` 长场景已通过 **51项纯检查**并启动真实 DUT：正常反馈
在弱负/弱正的 MainBTB counter1/2 之间切换，最多80对，preedge记录
预算明确有界为65536。AST等价检查证明完整 monitor 除8192→65536
容量常量外没有删除或改变任何检查。中间 v2 的50PASS/1FAIL仅来自
文件尾空行的逐字等价误报，没有启动DUT；该版本仍保留。

独立 watcher 只等待当前实际 DUT owner，不重复运行；只有退出收据为
PASS才启动完整 reset/缓存反转回放、真实127→128→0及全部1024个useful
状态检查、16项独立reset前缀边界故障对照、captured来源重关联和原生
行增量核验。边界故障对照不冒称其他模块的全故障重放。真实 DUT 或
门禁失败均不准入。当前尚无本实验老化命中或行增量计账，完整目标、
正式回归和冻结约束保持不变。

### 集成 RAS retirement：从原生行缺口补齐提交能力

继续复核集成 `RasStack` 的159个正式行缺口，发现 RTL/picker 已导出
`io.fromFtq.commit` 与 `io.toFtq.meta.bits.commitMeta`，但当前 `BpuAgent`
没有绑定这两组端口。既有 BPU-INT-033 只检查推测嵌套 call/return 的
LIFO 与 S2/S3 修正；训练反馈不是 RAS retirement，不能替代 commit。
正式运行期间1087个ROOT/runtime文件仍冻结，因此新能力在隔离目录实现，
尚未修改正式 agent 或注册功能点。

隔离扩展使用静态 Bundle/PulseBinding、现有 PulseDriver、`@on` passive
Monitor、独立 bounded CommittedStack 与普通 Scoreboard。调用者传入已由
完整 PHR/pipeline fire/flush 关联的 transaction，扩展只从该事务**同一
S3 tick**的公开输出提取真正 commitMeta；不伪造、不从内部状态初始化模型。
逐拍检查完整8个 committed cell、head、公开输入、父级 register 和连续
commit 接收。用例没有 FallingEdge/get_set/asyncio.gather。

第一次真实运行停在 picker schema 绑定：输入实际为 `meta_ras`，输出为
`commitMeta_ras`，并非 Scala 的嵌套名字。失败源码、结果和raw已封存且
排除。v2修正静态绑定后，31项纯检查和一个两层嵌套真实DUT场景全部通过。
独立门禁的v1曾误设 rising tick 从1开始；实际采样从2开始。保留失败门禁，
v2按实际首tick检查完整等步长序列，并重新完成全部284帧reset回放、缓存
expected-state反转及37项观测故障对照，实际以0退出。精确新增24行：
`RasStack.sv`20行、`Ras.sv`4行，候选30556→30580。见
`results/coverage-bpu-integrated-ras-retirement-native-candidate-readonly.json`。

随后复用同一扩展，增加4/7/8层自然调用链。34项纯检查与三项真实DUT
全部通过，分别接收8/14/15个连续commit beat。八层场景实际分配全部8个
committed槽位并首次回绕替换初始sentinel；只返回7层，未伪造空栈返回。
独立从reset重放414/609/641帧及全部PHR/pipeline状态，每份再执行37项
输入、S3来源、register与全部8槽观测故障，共111项，全部抛出带差异和
首错上下文的普通ScoreboardMismatch。故障对照不创建DUT或raw。

只合并上述三份通过raw与已准入30580候选，额外精确关闭75行：
`RasStack.sv`66行、`ReplacerState_4.sv`9行。最新隔离候选为
**30655/46541**；本批两层加深调用链合计99行，不能再重复叠加24或75。
所有456个既有分类缺口和原生分母保持不变。证据见
`results/coverage-bpu-integrated-ras-deep-retirement-native-candidate-readonly.json`。

新候选的集成RasStack为485/558、仍缺73行。重新确认独立/集成RasStack
逐字一致，并针对集成父模块重新检查action连接和全部布尔组合：其中8个
赋值受同slot优先级排除，8个要求call/return action同时成立。只分类16个
赋值，不把其if/else块头也宣布不可达，不转移独立DUT覆盖命中，不删分母。
其余57行仍未完成分类。三种深调用链的所有committed repeat counter都为0，
因此**槽位分配全覆盖不等于重复计数器增减/饱和已覆盖**。下一批仍需真实
重复call组、超过一圈speculative queue的合法commit重用，以及FTQ资格下
的redirect/非push bos回收。见
`results/coverage-bpu-integrated-ras-remaining-native-gap-review-readonly.json`。

### 长 useful-aging 完整准入与 RAS 原生并集完成

原`aging-v3` DUT进程已自然以0退出：1 PASS，耗时1325.01秒。既有watcher
只启动了一份独立门禁（PID1746693），没有重跑DUT。该门禁和watcher均已
实际以0退出：完整reset重放42126个相位帧及缓存反转通过，实际1次老化，
失败分配133次、low tick最大128，严格确认127→128→0；全部1024个useful
边界、16项边界故障及805笔captured来源重新关联均通过。

只合并本次通过raw与30556封存分支，精确新增1595行至32151/46541：
lower BypassShadowBuffer1034行、upper559行、MicroTage2行。老化功能bin
实际13/16，仍缺lower表bank0/1/3的非零老化，未宣称完整地址/强度/同拍
训练老化覆盖。证据见
`results/coverage-bpu-integrated-natural-useful-aging-native-candidate-readonly.json`。

随后核实三个独立准入收据和全部raw身份，原生合并aging候选与四份通过RAS
raw。重新导出的缺口集合精确等于两个已准入候选缺口的交集，确认本次
1595个aging行与99个RAS行没有交集：**最新隔离并集32250/46541**，相对
共同30556分支新增1694行。不是靠相加百分比或复制命中数得到结果，未创建
新DUT或把隔离raw注入正式manifest。见
`results/coverage-bpu-integrated-aging-ras-native-union-readonly.json`。

已资格useful操作见证矩阵也从21/56更新到34/56，新增13个真实aging bin；
其余22个是尚无已准入见证，并非已证明DUT完全没有命中。没有重新扫描新
长轨迹的其他操作，也没有把旧4527个useful缺口沿用成当前计数。见
`results/coverage-bpu-integrated-useful-operation-witness-matrix-v2-readonly.json`。

上述一节封存时，正式完整回归原PID1515810仍实际运行，后继审计和正常
收集尚未完成；当时没有改动冻结ROOT/runtime，正式四份报告仍为已审计
29205/46541基线。最新进展见下节。
完整目标仍保留集成ABTB/TAGE/bypass/PHR/RAS/replacer、SC非零历史/
all-index/SC-used/重叠/完整覆写/FTQ和七项strict XFAIL对应六个RTL问题。
32250是隔离准入候选，不是正式刷新完成或总体目标完成。

### 正式报告生成完成；重复调用计数器场景独立准入

原`tests/run_all.py`已于北京时间05:14实际以0退出，完整测试结果为
7848 PASS、7 strict XFAIL、0 SKIP，275/275功能点。原生LCOV和HTML均已
生成，BPU报告为29954/46541，其余九DUT的行数和分母不变。
旧严格审计及v2审计因外部xcomm源码分支/未提交文本变化退出1；失败收据
和日志全部保留。预先启动的v3后继正在完整重放全部200份新ROOT轨迹，
并显式区分可变、未编译的xcomm源码与冻结的实际安装运行时，没有声称
新源码已编译/安装或通过ABI验证。独立审计和正常收集均完成前，1087份
ROOT/runtime/test/RTL/DUT源码仍保持冻结，不重复启动正式回归或审计。

对RAS缺口的分析发现，深调用链虽覆盖全部八槽分配，repeat counter却全为
零。新增隔离v4复用已准入的静态CommitPorts、PulseDriver、@on监控、完整
PHR关联与reset起始CommittedStack；测试只表达真实自调用意图，不拼
commitMeta、不写原生状态，不在测试中暴露边沿/get_set/gather。

41项纯模型测试通过；2项真实BPU DUT测试通过（6.94秒）。分别请求9/10
次自调用后暂停年轻S1接受，完整排空并保留各一笔较旧transfer，实际关联
并退休10/11笔。逐笔确认原S3 metadata、真实spec action/字节PC/position、
连续提交和全部8个保留槽状态。真实计数为0→7，第九笔在旧槽保持7的同时
分配新槽，再继续递增到1/2；没有把被排空的额外transfer丢弃。

独立门禁实际以0退出：完整reset重放218/221帧、反转缓存预期后重放结果
不变、86项观测故障均抛出带差异和首错上下文的ScoreboardMismatch。包含
原37类完整槽位/输入/来源/注册状态故障，以及每例6项递增、正饱和与分裂
边界故障。独立重放依据所有真实post-redirect speculation选择意图，不用
缓存expected状态驱动参考模型。限定的counter/head/operation功能bins均
有见证，不等于八个槽位的重复操作全覆盖。

仅合并上述两份通过raw与已准入32250候选，精确新增14个RasStack原生行，
更新到**32264/46541**。旧候选保护的是正式回归前四份报告，新测试保护的
是原run_all成功更新后的四份报告；门禁保留两个报告epoch及实际full退出
收据，并验证执行源码/安装运行时仍完全相同，没有把原独立审计说成完成。
证据见`results/coverage-bpu-integrated-ras-repeat-retirement-native-candidate-readonly.json`。

新RAS原生缺口复核为499/558、剩59行。其中仍有16个局部矛盾赋值，全部
保留为missing，另43行未分类；没有把块头推断成不可达，也未转移独立DUT
覆盖率。重复递增/饱和分裂只资格槽1/2，重复递减、其余槽位、完整spec queue
复用及真实FTQ redirect资格仍开放。见
`results/coverage-bpu-integrated-ras-remaining-native-gap-review-v2-readonly.json`。

原生bypass缺口也已从实际aging/RAS并集刷新：共4978行，其中2958行直接
关联useful cell（lower1494、upper1464）；不再沿用历史6571/4527计数。
只是缺口定位，不增加覆盖率或剪除分母。见
`results/coverage-bpu-integrated-bypass-native-gap-inventory-v7-readonly.json`。

完整目标不变：后续生产迁移须包含全部已准入ABTB/bypass/SRAM/force/
nonzero/two-program/parent/aging/RAS能力，不只最新重复调用；继续覆盖
集成TAGE、PHR、replacer及SC非零历史/all-index/SC-used/重叠/完整覆写/
FTQ，保留7项strict XFAIL对应6个RTL问题。当前不是总体目标完成。

### 生产迁移候选：固定核心依赖与全部 RAS 模式等价验证

在原独立审计继续运行、ROOT源码保持冻结期间，新建隔离生产候选
`/tmp/bpu-integrated-production-uNrKzv/coverage_runtime`。目前实际有36份
候选源码：已包化ABTB metadata/完整counter/PLRU/PHR观察、shadow/SRAM、
committed reset、forced conflict、非零PHR hash、index pipeline、parent
training policy、aging配方和完整已准入RAS实现。生产候选源码不含`/tmp/`
路径、`tests.*`依赖或通过文件路径装载旧版本的importlib bootstrap。
同名模块不再靠搜索路径覆盖；zero/nonzero/long-aging检查单独保留，不能
互相替代。模型、monitor、checker实现体的AST与原已准入来源保持一致。

核心迁移首轮为246 PASS、1 FAIL。唯一失败是新增MRO契约错误地把原v14
monitor重导出当作新增继承层；原实现实际为`SramMonitor = _v6.SramMonitor`。
全部27份核心AST等价检查已通过，没有发现monitor绑定被移除。保留原测试、
失败日志和退出1收据；新建完整v2测试集，明确检查重导出身份及真实继承链，
不修改monitor/checker实现、不删任何模型测试。v2实际247 PASS、0 FAIL。
该数字已包含RAS等重叠模型测试，不能与此前113项RAS运行相加当作独立项。

RAS所有已准入模式——两层嵌套、深度4/7/8、重复调用9/10——均通过新包执行，
6项真实DUT测试实际PASS（24.23秒）。独立生产迁移门禁实际以0退出：对
284/414/609/641/218/221个reset起始帧重新完整验证PHR及retirement，六例的
cycles、phr_cycles、accepted、applied、summary均与原已准入轨迹逐项相同；
反转缓存expected后结果不变；234项观测故障全部产生带差异和首错上下文的
ScoreboardMismatch。新旧六份raw重新原生聚合后的缺口集合完全相同；将
新raw并入32264候选后缺口也完全不变，456个分类缺口和46541分母均保留。
因此本轮新增原生行数为0，不能把包化后的重复运行算作新覆盖率。
证据见`results/coverage-bpu-integrated-pending-production-ras-equivalence-readonly.json`。

这不是全部生产迁移已完成：RAS包已完成真实DUT/完整重放/原生等价验证；
其他核心包目前完成模型、AST、固定依赖/继承资格，尚待全部已准入刺激场景
的显式组合、真实DUT重放和等价门禁，尤其不能遗漏zero/nonzero/index/policy/
aging上下文原先由搜索路径选择的检查层。原独立200轨迹审计及正常收集完成
前仍不改ROOT；随后迁移必须保留原275功能点、七项strict XFAIL和全部原
目标范围。ROOT加入新包后需以精确新增源码清单/计划追加差异建立新阶段
资格，不能继续假设ROOT源码数仍为1087，也不改旧冻结资格门禁来放行。

## 正式迁移与新全量回归（2026-10-09 06:18 起）

原全量回归、独立审计v3和正常后收集v3均已实际零退出。审计保留全部
200条新SC、144条原ABTB和96条原SC完整重放，重新合并本轮manifest中的
676份raw、十种DUT。结果为7848 PASS、7 XFAIL、0 SKIP，275/275功能点执行；
BPU原生行覆盖29954/46541，比上一独立审计基线29205增加749行，全部456个
分类缺口保留。详见`results/coverage-bpu-sc-role-history-production-refresh-audit-v3.json`。
该结论属于原1087源文件快照，不冒充后续迁移代码已完成全量DUT验证。

全部已准入的ABTB/bypass、zero/nonzero、SRAM/force/index/policy/aging刺激
已固定其检查器组合；325项候选纯测试先通过，随后新增函数内依赖闭包检查，
查出并在新版本修复三处`bypass_model`延迟导入。九个场景新增成功报告返回，
刺激主体保持AST一致。完整候选343项测试通过，旧候选及失败证据均未覆盖。

当前已实际迁入`suites/frontend/bpu/integrated`：60个与最终候选逐字节相同的组件，
另加一个RAS意图/覆盖封装。正常测试不依赖临时路径或迁移契约文件，也不
接触edge/get_set/gather。功能覆盖使用xreactor CoverGroup/Scoreboard，从
真实采样输入重放全部shadow和1024 useful值；只有下一观测状态比较通过才
取得操作证据，且全段检查通过后统一提交bin。晚到错误、相邻cell错误、
断帧、错误reset及缓存写入列表造假均有故障控制。24训练来源bin、56 useful
操作bin及原lower-ring定义全部保留，未命中bin不因场景PASS而消失。

原275个功能点定义保持原样，追加BPU-INT-044..054共11项；新增真实DUT意图
17例，含全部11个核心上下文及6种RAS模式。深度8只含七次合法return，不
凭空补第八次空栈return。正式目录、无旧临时模块搜索路径下288项模型/封装
测试实际通过（关闭报告插件导致两个已知ini选项警告，不是SKIP）；正常
pytest收集8160项，原7855节点全部保留，四份正式报告保持逐字节不变。
迁移资格见`results/coverage-bpu-integrated-production-migration-qualified-v1-readonly.json`。
精确源文件差异为75个授权新增文件及计划追加；原1086个非计划源文件、
RTL/DUT、xreactor及已安装二进制不变。xcomm用户分支/未编译文本变化单独
记录，未宣称重新编译、安装或ABI验证。

新正常全量回归已实际启动：owner1790426、run_all1790607、pytest1790608，
工具会话88357，日志`/tmp/bpu-integrated-production-formal-EeYNyP/formal-full.log`。
执行环境不含旧临时模块路径；先归档了原已审计四报告和十份LCOV，没有把
任何隔离raw注入正式manifest。当前1162个源文件重新冻结，直到新全量、
完整独立审计及正常后收集完成。新回归尚无退出回执，不能将隔离候选
32264/46541当成正式数值；完整目标仍未完成，所有SC-used/有效非零history/
全dirty-overwrite/overlap/FTQ、TAGE/PHR/RAS/bypass及七项strict XFAIL继续保留。

## 独立审计辅助的实际缓存污染与关联边界（06:18 回归继续运行）

当前全量仍由同一pytest1790608运行，1162个正式源文件没有改动。准备新
审计时核实了一个旧证据局限：nested/deep的缓存反转只修改未使用的副本，
不能证明工作轨迹的cached expected真正被污染。旧门禁和证据保留，新版
重放实际污染每个applied条目的head及八个cell的address/counter，再从reset
比较全部真实native/PHR观测；缓存expected不作为模型输入，也不自证正确。

以原已准入六种RAS轨迹验证，30项辅助测试实际零退出：六例共1054个缓存
字段真的改变且结果不变；原234项观测故障全部按精确的来源关联边界检出；
新增六项独立训练程序position故障控制通过。特别是S3提交元数据错误会在
对应commit接受拍检出，spec.position错误在原checker中到对应栈更新拍检出；
新版审计另从已准备程序固定position检查S3源，避免按观测位置推导期望位置。
这些点分别核对准确tick和phase，不放宽为“以后某处失败即可”。异常tick
在CommitChecker的request上下文中，不强求其放在observed_event字段。

首次辅助测试v1为7PASS/6FAIL（错用observed_event），v2和v3各为18PASS/6FAIL
（先错误假设所有故障同拍、再遗漏position派生地址的注册延迟）；全部失败
日志和退出回执保留。v4实际30PASS包含所有原测试、正确关联边界、六例真实
缓存污染及新增program-source位置检查，没有删除故障用例来变绿。

另外已提取九份已准入的完整核心重放函数，固定zero/SRAM/hash/index/policy
上下文依赖；函数主体AST契约通过，原件hash与历史独立准入相符。SRAM/force
通过显式参数接收同案seed，two-program通过显式参数选择index/policy/aging
检查层；不再以搜索路径决定模型。全部函数内导入也已检查。
证据见`results/coverage-bpu-integrated-production-audit-helpers-qualified-v1-readonly.json`。

此处仅证明审计辅助与旧已准入输入，没有创建DUT或raw，没有更新正式覆盖。
新全量仍须实际完成，再以新轨迹执行全部17场景及原200SC+144ABTB+96SC
完整重放、故障控制、功能JSON/HTML/bin计数一致性和十DUT原生重合并；
随后正常收集保护也仍须完成。正式已审计数仍为29954/46541，候选32264不变。

## 独立功能计数与完整审计后继（同一 06:18 全量继续运行）

新建独立功能核算器，不调用正式`IntegratedCoverage.collect`、其操作选择
函数或sample回调。它从真实preedge输入、reset派生的训练缓存和useful旧值
单独判断来源/操作；只有下一rising的两张完整表状态全部比较通过后才计数。
缓存writes、requested_reset和expected标志均不提供覆盖证据；末个只有输入
而没有结果观测的操作不计数。保留24训练来源bin、56 useful操作bin以及
lower-ring原定义，不以场景PASS替代覆盖。age与同拍更新的优先级有实际控制。

独立功能测试实际34PASS/退出0：包含七种useful操作、晚到状态/邻项错误、
断帧/错误reset/漏表、最终preedge不计数、六种RAS及13类导出篡改。重新签名
后的虚增bin/sample、改goal/百分比/covered/schema、gated/unmatched、伪造
provenance计数/边界/metadata、增删group均拒绝。schema/snapshot完整性、
逐bin计数、sample、覆盖率、目标和手工采样provenance都比较；不只是百分比。
另9项流水线结构/依赖/聚合测试实际PASS，确认多个独立case的计数聚合与
xreactor数据库聚合一致，未命中useful bin保留。两批均没有DUT或raw产物，
正式1162源文件和四报告保持不变。

完整17场景组合审计已创建并封存已准入旧输入目录：642个core旧故障、234个
RAS旧故障、六个独立program-source位置故障，共882项。保留全部公开回读、
captured source、SRAM defined-response、parent index/policy、真实aging及其
805条captured lineage；aging故障仍明确是reset-prefix检查，不冒充其他模块
完整故障重放。新core轨迹必须与旧准入轨迹逐字节一致，RAS则全字段语义
核对；否则拒绝复用旧故障拍号，而不是放宽边界。组合器正在以旧输入验证，
此时并未声称全部17例/882故障已通过，更不是新ROOT轨迹审计已完成。

新完整审计主程序保留原200SC+96SC+144ABTB，并加入全部17集成场景，合计
457条完整重放；还要求本轮693份normal-manifest raw独立重合并十DUT，核对
整个原生映射行集合、HTML/JSON/LCOV、原275功能点及所有456分类缺口。
204功能文件/197组和新增四组的逐case、聚合schema/bin/sample/provenance均
独立核对；新open bin允许诚实存在，不要求靠删分母得到100%。这些数字是
待实际运行验证的精确门禁，不是已经取得的正式结果。

后继等待器实际pid1811013、工具会话36151，等待的是原owner1790426和同一
pytest1790608，不会重启全量。仅在原全量及17例旧输入资格实际零退出后，
才运行完整审计；审计零退出后再执行正常ROOT-only收集，保护四报告和十份
LCOV。收集子进程不含旧临时模块搜索路径。此时全量仍无退出回执，后继没有
完成审计或收集；正式已审计BPU仍29954/46541，32264仍只是隔离候选。
准备证据见`results/coverage-bpu-integrated-production-audit-preparation-qualified-v1-readonly.json`。
完整目标及全部原先未闭合的SC-used/nonzero-history/full-overwrite/overlap/FTQ、
TAGE/PHR/RAS/bypass与七项strict XFAIL均继续保留。

## RAS 重复调用后的真实返回递减（同一 06:18 全量继续运行）

从剩余原生缺口定位到`rtl/bpu/RasStack.sv:580、582`：重复返回地址的
committed counter 为正时，return 应递减计数而不是移动 nsp。此前重复调用
场景只验证 increment/saturation/split，没有退休 return，不能声称此功能已测。
新隔离场景使用真实 MainBTB call/return 训练、正确 RAS action 的 FTQ redirect、
真实 S3 metadata 与 commit driver；没有在 testcase 加 edge/get_set，也没有
修改正式1162源文件、RTL、DUT、xreactor或已安装运行时。

首次v1两例失败：试图修改同属性 MainBTB 直接分支命中的 target，但 RTL 只在
miss、OtherIndirect 或属性变化时写 entry。不是 RAS 错误，失败原件和 raw
保留且排除。v2纯模型37PASS，但DUT两例在驱动前被代理类型检查拒绝：新增
ActionRedirect未继承BpuRedirect。v3保留两版失败，改为合法事务子类，新增
继承、父类参数校验与真实BpuAgent.redirect转发契约检查；纯模型实际42PASS，
DUT实际2PASS，均退出0。每例实际退休10个相同call，再分别退休1、5个return。

为切换到return PC，先退休9个older call，用最后一个真实call的原始redirect
metadata、正确cfiPc和rasAction=2恢复，再退休youngest call。return训练的
MainBTB fallback刻意与RAS返回地址不同，逐笔检查实际S3 taken/PC/target，
不能把目标恰好相同或早期S1预测当成RAS正确。全部8个retained committed
cell每周期比较，所有提交边界另用独立闭式公式比较；没有伪造commitMeta、
直接初始化native状态或丢弃未退休的真实call/return。

新独立回放从reset开始，以单独PHR公开流重新发现/关联S3源，按准备程序和
阶段推导PC/action/position；四次redirect逐字段核对真实源metadata和动作。
实际投毒442个cached expected字段后结果不变；206个观测/源/注册payload/
恢复metadata/实际return目标故障全部抛出ScoreboardMismatch，逐项核对准确
检测tick、phase（适用时）、差异与失败状态。独立审计实际退出0，不产生DUT/raw。

随后只把v3两份PASS raw与原签名候选合并，独立native准入实际退出0：
32264→32267/46541，新增3行全部属于RasStack：325（redirect重做push的计数
分支）、580和582（slot1、slot2的positive-counter递减）。整个46541行映射集合
与全部456个已分类缺口保留，没有failed/probe raw进入候选。功能覆盖保留所有
8槽位及8种counter-before bin；只见证slot1/2递减和slot2 zero-counter pop，
不声称其余槽位、全部计数值、完整specQueue/FTQ或RAS全部功能闭合。

证据见`results/coverage-bpu-integrated-ras-repeated-return-native-candidate-readonly.json`；
完整原件在`/tmp/bpu-ras-repeat-return-ZsfiHv`。这些是新增隔离准入候选，尚未
注册正式功能点，不注入正式manifest。正式已审计BPU仍29954/46541；原全量
及后继完整审计继续由原进程运行，尚不能声称正式覆盖刷新或完整目标完成。

## 返回计数边界与槽位交叉缺口（同一全量继续运行）

上一轮虽关闭slot1/2的递减行，但只观察到counter-before的0、1、5、6、7，
不能据此认为计数边界验证完整。新v4保留全部v1/v2失败和v3已准入原件，
新增7、9次真实return序列；每例仍先退休10个同地址call，最后保留至少一个
有效call，不触发或冒充empty-return。纯模型/接口实际43PASS，DUT实际2PASS，
真实退休数分别7、9，没有将请求数当作已执行数。

新独立审计完整回放两例，实际投毒612个cached expected字段且结果不变，
286项负控在准确边界检出，实际退出0。连同v3共四例、22笔已核验return，
共492项负控、1054个实际投毒字段；不同版本的已执行源码全部保留不改。

功能覆盖直接使用xreactor的CrossDef，增加head_before×counter_before的
全部8×8=64个组合，不按已观察值缩减定义。四例确实见证全部8种计数值，
但head_before仍只有2/8，交叉仍只有9/64，55个open组合完整保留。采样得到
19次positive decrement、3次zero-counter pop；前者只涉及slot1/2，后者仅slot2。
独立计数器从固定程序和返回ordinal闭式推导预期22笔，不调用生产采样回调
推导预期；逐点及64个交叉bin、sample、schema、goal、百分比、来源与snapshot
完整性都核对。12项正向/篡改检查实际PASS，含重新签名后的五种计数虚增及
六种见证修改。隔离测试禁用了功能点插件，产生两条未注册ini项的配置警告，
没有SKIP或DUT/raw，不能把警告隐去声称零警告。

仅合并v4两份PASS raw后的native准入也实际退出0，但没有新增行：仍为
32267/46541，完整行映射和456分类缺口不变。功能计数值覆盖的改善不能冒充
行覆盖增量；同样，行已命中也不代表64种槽位×计数行为都验证过。新增cross
改变了功能schema，不能拿新组67.8125%与旧无cross组71.875%直接比较回退。

证据见`results/coverage-bpu-integrated-ras-repeated-return-boundary-native-candidate-readonly.json`。
正式1162源文件、已安装运行时和四报告仍保持冻结；未注册新功能点、未注入
正式manifest，当前完整回归的冻结门禁仍应期望32264，而不是这些新候选32267。
原旧输入组合审计已实际完成10/17例和626项负控，尚无全部17/882的退出证据。
整个目标和原有SC-used/nonzero-history/full-overwrite/overlap/FTQ等未闭合范围不变。

## 原旧输入17例组合审计实际完成；分批调用进入第三RAS槽位

原checker1810449（工具会话11527）已经实际退出0，所有17个独立case产物
签名存在，882项负控全部完成。完整结果在
`/tmp/bpu-integrated-production-formal-EeYNyP/old-input-composite-v1/result.json`，
原始退出回执`composite-old-inputs-v1.exit.json`与日志签名核对一致。独立功能
计数和生产collector的17例语义全部一致，包括aging全轨迹及805条captured
lineage；故障范围仍保持原限定，不把prefix故障冒充完整其他模块负控。
这是旧已准入输入的辅助资格，不是新ROOT457条轨迹审计完成。原pytest1790608
及等待器1811013仍是同一进程；等待器取得此前置条件后仍等待正式回归退出。

进一步分析RAS缺口发现，进入第三槽位需要超过16个累计call，但不能把它们
一次全部保留在16项specQueue中。新v6用两批真实S3 call（10、9个）推进：
第一批全部退休并排空后才恢复预测接收第二批，最后youngest仍用原始真实
metadata和正确action恢复再提交。随后分别退休1、17个return。新增静态Bundle
被动采样tosw、bos、near-overflow及其输入，从reset推导每一拍的指针回收；
整个轨迹最大distance为10，未触及14的安全上限。元数据的tosw flag确实跨环，
但不宣称全部队列内容或完整FTQ合法性已经证明。

v5纯模型50PASS，但DUT两例失败：queue callback先于其他monitor更新record，
首次事件访问空列表。不能依赖同一事件多个@on capture回调的执行顺序。
失败原件/raw保留排除，v6将队列状态、完整commit观察输入和公开redirect
放在同一静态Bundle中原子捕获，并补上不提供其他monitor records的独立契约
测试。v6实际51项模型/接口PASS、2项DUT PASS；没有修改冻结的正式源或框架。

新完整独立审计从单独PHR公开流重建全部19个call与1/17个return，并以另一份
整数指针模型核对原子捕获输入与独立monitor每拍完全相等、bos回收、写指针
跨环、near-overflow和容量。两批源由时间序列重新发现，第一批全部applied
早于第二批源；cached expected不提供模型输入。实际952个缓存字段污染后
结果不变，392项native/source/redirect/queue/原子输入负控均在精确tick和适用
phase被拒绝，异常包含差异与失败状态；独立审计实际退出0。

波次功能组从固定19-call程序和return ordinal闭式推导18笔样本，再独立比较
原生xreactor定义、逐bin及64交叉计数、sample/schema/goal/百分比/provenance。
它见证3/8个head、8/8个counter-before值、17/64个head×counter组合，仍47个
open交叉，不以全计数值覆盖冒充全槽位组合。功能辅助v2为10PASS/2FAIL：
沿用旧常量的两项“篡改”写回了原值，没有实际制造错误。原件保留；v3用异或
确保字段真的改变，保留全部12项检查后实际PASS，且已注册ini项、无配置警告。

仅合并v6两份PASS raw后的native准入实际退出0：32267→32278/46541，新增
11行全部属于RasStack。精确映射为517、518（第三槽位计数increment分支），
584（第三槽位positive decrement），718..721和724..727（specQueue第14、15项
retAddr/ctr/specNos flag/value写入）。后8行不是写指针赋值行；写指针跨环是
独立队列观测证明的关联场景，不混淆其源位置。RasStack目前513/558，余45行。
整个46541行集合和全部456个分类缺口保留，失败v1/v2/v5 raw均未合并。

证据见`results/coverage-bpu-integrated-ras-bounded-wave-native-candidate-readonly.json`。
此处仍是隔离准入，尚未注册正式功能点；正式四报告及1162源文件保持冻结，
正式已审计BPU仍29954/46541，当前被冻结全量的严格门禁仍期望32264。后继
457条新轨迹完整审计和ROOT-only后收集尚未执行成功；所有原始未闭合目标保留。

## 全八槽重复计数与真实return恢复：隔离候选32300

64-call场景v7先扩展独立闭式到1..64个call、所有非空return前缀，物理槽位
按mod8处理且保留弹出槽的数据；65个call、空栈return仍拒绝。94项模型检查
实际PASS，两个DUT场景实际PASS：七批10+6×9个call，每批之前的工作全部
退休后才接受下一批，随后分别完成1、63个return。完整状态从reset推导，
所有八个保留槽逐拍比较；最大specQueue distance为10，没有触及14安全上限。
写指针实际两次mod32回绕，不将其解释成全部队列内容或完整FTQ资格。

原audit_v4实际零退出，133+781=914项观测故障准确检出；实际投毒3264个
cached expected字段后，独立重放结果不变。额外62个关键负控的目标完整性由
独立重建的boundary再次验证，不依赖测试缓存expected来证明目标选择。
12项独立功能检查通过且无配置警告。功能定义保留全部8×8交叉，64笔样本
见证全部head和counter值、63/64个组合；head1/counter0将进入空栈，当前仍
保留open，未证明不可达、未从分母删除。

一次性后继只等待原审计1841250/1841251的实际退出回执，没有重跑审计或DUT。
仅合并v7两份PASS raw，native_v5实际零退出，候选32278→32293/46541。
新增15行：RasStack505/506、521/522、525/526、529/530、533/534为其余槽位
increment分支，578/586/588/590/592为其余槽位positive decrement。
证据见`results/coverage-bpu-integrated-ras-full-compressed-stack-native-candidate-readonly.json`。
独立缺口复核v3重新验证全部16个局部/父级互斥赋值，未转移独立RAS命中，
未推断块头不可达；当时RasStack528/558、余30行，其中14行未分类。见
`results/coverage-bpu-integrated-ras-remaining-native-gap-review-v3-readonly.json`。

由剩余源码进一步发现：普通return退休不能替代redirect.isRet恢复/redo。
新recovery_v1仍使用静态Bundle、已有PulseDriver、@on monitor、完整PHR关联
和reset起始CommittedStack；测试仅表达意图。11项纯模型和2项DUT实际PASS。
每例先完整退休10个真实call，再分别执行1/2个return；恢复最年轻return时
只退休较老项，使用该return原始S3 redirect metadata、实际cfiPc、branchType3、
rasAction1，转向未训练冷目标。在最年轻return尚未退休前，公开冷目标metadata
已核对SSP/counter/topRetAddr：分别2/1→2/0、2/0→1/7。之后才提交同一笔
原始commitMeta，逐拍核对全部保留槽；没有用退休结果掩盖错误恢复。

恢复独立审计v1在reset处失败：PHR事件将invalid redirect的bits表示为None，
原子Bundle保留总线值，不能比较invalid payload。原件和退出1保留；v2新增
valid门控及六项有效/无效payload敏感性契约，但负控预期又错误地要求专用
比较先报错，实际三类S3输出故障先被完整PHR检查器在同tick检出。v2失败
原件也保留；v3严格区分该PHR检查器/observed-event/scope与其他精确phase，
完整重新执行后实际零退出：108项负控、391个cached字段投毒，完整正向
reset/PHR/retirement/原子来源/整数queue指针重放通过，六项契约再次PASS。

新增功能组只描述positive/zero两条恢复分支与“在youngest退休前检查”这项
契约，两个真实样本；8项独立计数/见证修改/报告虚增检查实际PASS。此限定组
100%不代表八槽恢复、inflight所有路径、完整队列内容或FTQ已经验证。仅合并
上述两份PASS raw后native准入实际零退出，再新增7行：RasStack749、752、
755、756、827、831、832；候选32293→32300/46541。RasStack535/558，剩23行，
其中16个已分类赋值仍missing，另330、598、600、601、602、748、801七行
仍未分类。748块头不能因为相邻表达式已命中而删除；饱和call redo、非push
bos回收及writeBypassNos相邻call/return仍需真实场景及来源资格。
证据见`results/coverage-bpu-integrated-ras-youngest-return-recovery-native-candidate-readonly.json`。

两次准入完整46541行集合、全部456个共享WriteBuffer分类缺口和正式四报告
均保持不变；本轮隔离增量15+7=22行。未新增正式功能点，未注入manifest，
ROOT1162源/RTL/DUT/xreactor/安装运行时仍冻结。原全仓pytest1790608和等待器
1811013仍运行同一批次；被冻结完整审计仍严格期望32264，而非新候选32300。
后续迁移必须包含全部已准入场景，继续保留集成TAGE/PHR/RAS/bypass/replacer、
SC-used/有效非零GHR/BW/commonHR/all-index/深生命周期/full-overwrite/overlap/FTQ
以及7项strict XFAIL对应6个RTL问题，不能用这两项RAS增量宣称总体目标完成。

## 饱和call恢复关闭赋值头；转向其他bank的自然aging

call_recovery_v1以真实8/9个自调用对比饱和边界：年轻call的原始checkpoint
分别为SSP1/counter6和SSP1/counter7。只退休较老call后，用该年轻call未经修改
的metadata、正确cfiPc及rasAction2重定向到冷目标；在年轻call提交前核对公开
metadata分别为1/7和2/0，之后才提交原始commitMeta。10项模型检查、2项DUT
实际PASS。完整reset/PHR/retirement/原子queue来源重放实际通过；108项负控
准确检出，301个缓存预期字段投毒后结果不变，其中包括新增before/after投影
缓存的全部6个字段，不能把这些缓存当参考输入。六项源契约、八项功能计数及
篡改检查通过；限定的counter6/7两分支不代表全槽恢复或完整FTQ资格。

call native首版失败在准入报告读取：重命名功能bin时误把case['positive']变成
case['below_max']，没有合并raw。失败源码、日志、退出1及空evidence目录保留；
新v2修复这个字段，八项功能检查实际再次通过后，仅合并原两份PASS raw。
native_v2实际零退出，新增RasStack330和748两行，候选32300→32302/46541。
748此前是未命中的ssp赋值头，本次被真实场景覆盖；不能仅因相邻表达式命中
而把块头判成不可达。RasStack现在537/558，剩21行：16个互斥赋值仍missing，
另外598、600、601、602（非push bos回收）及801（writeBypassNos）五行尚未分类。
证据见`results/coverage-bpu-integrated-ras-call-saturation-recovery-native-candidate-readonly.json`。

不把剩余目标缩成RAS。新的bypass inventory_v8从32302候选LCOV重新逐行
读取两份BypassShadowBuffer，验证全部46541行集合、原源码及缺口集合与v7
对应文件相同，重新核对useful物理bank/index映射：仍缺4978行，其中2958行
直接关联useful单元。完整56-bin定义与已独立准入矩阵核对，34个有见证、22个
缺少合格见证；没有复用未经当前LCOV验证的旧行数，也不宣称缺见证等于RTL
中不存在该行为。见`results/coverage-bpu-integrated-bypass-native-gap-inventory-v8-readonly.json`。

下一步扩展自然failed-allocation aging到bank2/3。生产意图入口目前只登记bank1，
底层配方和完整检查器支持另两bank；ROOT仍冻结，因此新增隔离意图封装，复用
现有driver/monitor/全状态参考和IntegratedCoverage，测试只传bank，不搓底层。
阶段在`/tmp/bpu-integrated-aging-extra-kiZpME`。首版纯测试为6PASS/2FAIL，错误地
把打包整数PHR历史当作序列；启动编排未阻止失败后的DUT运行，该批只作诊断，
无论其最终结果如何均不入账。首版源码保持不变。v2改为MASK范围内非零整数
检查，并在run.py内部强制校验8项纯测试零退出、日志和完整源码签名后才允许
启动DUT；v2模型8PASS、0警告，bank2/3资格DUT批次已启动且当前仍运行。
新aging raw、功能bin和原生行均未准入，必须先取得实际成功及完整独立重放。

正式四报告仍29954/46541，原全量pytest1790608及后继1811013仍是同一批次；
冻结的457轨迹完整审计仍严格期望32264，而非新隔离32302。保持1162源文件、
RTL/DUT/xreactor及安装运行时冻结；全部原始SC-used/nonzero-history/all-index/
deep-lifecycle/full-overwrite/overlap/FTQ、TAGE/PHR/RAS/bypass/replacer和七项strict
XFAIL范围继续开放，当前不是总体目标完成。

## bank2/3 aging独立审计准备：40项工具契约通过，DUT证据仍待终态

本轮新增隔离审计`/tmp/bpu-integrated-aging-extra-kiZpME/aging_audit_v1`，
未修改ROOT1162生产源、RTL/DUT、xreactor或任何安装运行时，也未重启原全仓
或两个aging批次。工具的40项pytest契约实际全部PASS、零警告；合成边界覆盖
两张表、aging前后、每表512个useful单元共2048个单点观察错误，均核对普通
ScoreboardMismatch的精确cell路径、tick、上下文及failed=1。另检查不完整／
越界／bool向量、错误aging变换、缺表／重复见证、自然失败分配门控、实际状态
破坏，以及非零退出、日志／源码签名变化、错误测试数量及PID复用等拒绝路径。
该40项是审计工具测试，不是新DUT功能点或原生行命中。

实际审计入口复用已冻结的完整two-program/aging参考：从reset重新验证PHR、
ABTB、真实feedback/recovery来源、shadow、SRAM及父级分配策略；再把每个
requested_reset缓存位投毒并完整重放。自然pulse的127→128→0控制与两表512
单元aging结果须来自新轨迹，不复用旧bank1的tick或805条captured来源数量。
所有实际captured-counter写入都要独立关联到真实S3 metadata、fastTrain、
第一eligible way和reset-derived training cache，不能只检查首尾样本；首尾
仅用于按实际table/bank/cache-cause选择六类来源负对照。独立重算功能输入／
状态计数并比较完整数据库schema、samples、bins、goal、provenance，保留
24个training和56个useful bin，不把缺见证的bin删除。

负控范围明确区分：完整正向与缓存投毒各重放整条轨迹；控制fault逐项执行
reset-derived prefix；每个useful cell的前后fault复用已经独立从reset推导并
核对的边界oracle，不声称2048项每项都重新执行完整prefix；来源fault是精确
局部关联检查，也不称全轨迹负控。这些fault不生成DUT raw、不增加覆盖率。

等待器session19008、owner1890967已实际挂接原v2 runner1877507／pytest1877508，
只在原批次2项DUT实际成功、模型8PASS、日志与源码签名均一致后启动该审计。
任何非零终态或身份不符均保留失败并拒绝准入，不自动重启。原v1因模型失败
仍是诊断批次，其raw无论终态如何均排除。当前bank2/3 DUT仍无终态，新审计
尚未执行实际轨迹，不宣称新的aging见证、functional bin或native行。

正式BPU仍29954/46541；独立候选仍32302/46541，本轮native增量为0。原全仓
pytest1790608仍在70%，后继1811013继续等待同一批次；冻结的完整审计仍严格
期望32264，而不是新隔离候选。全部原始范围和七项strict XFAIL继续开放。

## lower useful饱和保持的真实来源分析与PC别名单例

继续检查4978个bypass行缺口和56-bin矩阵，没有把范围缩成等待aging。
当前集成RTL的MicroTAGE与AheadBTB共用abtbEnable，不能假设有独立UTAGE
开关；BPU的S3 fire直接等于S3 valid，不能假设拉低metadata ready就能保持
同一S3 task并重复训练。这两种设想均未用于新场景，也没有改RTL补测试控制。

对已准入v4 lower轨迹再次实际完成4486帧独立ABTB/PHR/metadata与shadow
reset重放，以及独立功能计数复算，实际零退出。两次增加在tick3419/3425：
真实S3 metadata的baseTaken=1、predTaken=0，较早条件分支实际未taken，
useful由1→2→3；进入positive_from_zero前仍是3，场景结束却降至0。
因此旧测试虽然经过3，并没有验证饱和后的再次正确纠偏3→3。每次来源分别
篡改baseTaken、predTaken、takenCtr，六项均触发带精确tick和failed=1的普通
ScoreboardMismatch；这是局部来源关联负对照，不称六次完整负向轨迹重放。
证据在`results/coverage-bpu-integrated-lower-useful-saturation-causal-analysis-v1-readonly.json`。

新增隔离场景`/tmp/bpu-useful-saturation-uDVVrT`：先用真实feedback和原有
lower-only bootstrap建立负向lower provider及useful3，省略会把useful降回0
的最后正向阶段。再以四个真实PC别名共享lower index0/full-tag0，但使用不同
ABTB PC身份；通过普通MainBTB feedback及共用enable准备新基准，最后从真实
前一fetch block进入别名，避免把redirect排除周期当作有效训练。对第一笔
输入限定的别名transaction直接检查lower provider是否正确纠偏，并核对随后
useful保持3；不筛选观察结果后才选择通过的transaction，不写内部状态或伪造
metadata。只有新DUT及后续独立来源重放都实际通过才能确认这条路径可用。

新场景复用静态Bundle、现有agent/driver、@on monitor及完整PHR/ABTB/shadow/
SRAM/index/policy Scoreboard；测试函数只调用意图入口。15项纯模型／非法参数
检查实际PASS、零警告；run.py严格核对模型零退出、日志和六份源码签名后才
启动单例DUT。session85458、runner1898504／pytest1898505目前仍运行，无DUT
终态，也无原生或功能点入账。该单例仅针对lower bank0/index0的一个功能组合，
不代表其他bank、全部index、非零历史或完整FTQ已经验证。

原bank2/3 aging批次session36058仍是同一进程；bank2已实际PASS并产出轨迹，
bank3尚待终态，整批仍不准入。等待器1890967/session19008保持原挂接，两个
成功后才执行完整独立审计。原v1仍只作诊断，其raw全部排除。全仓1790608仍
在70%，后继1811013等待同一原任务；ROOT1162、RTL/DUT/xreactor及安装运行时
冻结。正式29954、隔离32302、46541分母、全部456分类缺口和原始完整目标不变。

## 实际终态更新：两 bank aging 已通过，别名场景保留两次失败并修正关联

本节取代上一节中已经过时的“session85458仍运行”和“bank3尚待终态”。
v44检查点的实时job字段已看到别名v1非零终态，但实验说明仍写pending；
后续v45检查点显式修正这一状态，不修改或删除v44历史凭据。

原bank2/3 aging v2是同一批次session36058，pytest1877508已于
2026-10-09 01:14:36 UTC实际零退出：2 PASS，2812.02秒。模型8 PASS、
日志及源码签名门禁通过后，原等待器1890967/session19008已经启动独立审计，
runner1910023／checker1910024；当前只确认审计运行，尚未宣称审计成功。
两份raw在整个审计完成前仍不准入。诊断aging v1虽然也实际2 PASS，
但其先前模型失败、启动门禁不合格的事实不变；它的raw仍全部排除。

别名饱和保持v1实际1 FAIL、退出1，不再是pending。第一处失败位于tick8730，
`first_input_qualified_alias_has_real_lower_provider`期望True、实际False。
它的warm fastTrain在tick8197虽valid=1且enable=1，ABTB metadata.valid却为0，
没有被接受；此前只有tick1303的冷启动、不taken任务。useful在失败时仍是3，
但不能据此认定已覆盖“再次正确纠偏后3→3”。全部v1 raw排除。
证据见`results/coverage-bpu-integrated-real-alias-useful-saturation-v1-failure-diagnosis-readonly.json`。

新的v2从前一fetch block进入，19项模型检查实际PASS；DUT仍实际1 FAIL、
退出1，但失败的是新增准入检查自身的时间关联，而不是warm任务未接受。
实际transaction的prediction_tick=8194、meta_tick=8198；ABTB在8195捕获S1
metadata，并在8199接受valid=1的taken conditional任务。旧检查直接比较
source_S1_tick与prediction_tick，把两种采样边界当成同一个tick，得到0个匹配。
独立核对实际捕获和fastTrain完整身份后，错误关联仍触发带tick8234、
failed=1及字段差异的普通ScoreboardMismatch，正确关联唯一匹配。这里是局部
来源关联诊断，不称完整reset重放。全部v2 raw也排除。
证据见`results/coverage-bpu-integrated-real-alias-useful-saturation-v2-tick-diagnosis-readonly.json`。

上述失败版本和日志均保留。新的v3把输入捕获身份和S3接受身份同时对齐到
同一transaction，在辅助层处理采样边界，测试函数仍只表达验证意图。
新增两项契约明确区分预测采样tick与下一tick的metadata捕获，连同原检查共
21 PASS、零警告。六份新源码签名相等后才启动v3单例DUT：session45706、
runner1911451／pytest1911452。当前没有v3成功或功能覆盖入账的声明；即使
DUT通过，也须完整独立reset/PHR/ABTB/shadow/SRAM/policy及真实来源审计、
24/56-bin计数复算后，才能合并唯一通过的raw。

正式四份报告保持不变：BPU29954/46541；最新隔离已准入候选仍32302/46541。
原全仓session88357已到71%，后继session36151仍绑定同一原任务。
ROOT1162/RTL/DUT/xreactor/安装运行时冻结不变；不削减46541行分母或456项
分类缺口。有效非零GHR/BW/commonHR、全索引、深层SC-used/full dirty overwrite、
真实overlap、完整FTQ及七项strict XFAIL／六个RTL问题仍属于原完整目标。

## 新负对照资格修正与真实同索引入口：不放宽饱和保持目标

原bank2/3 aging独立审计v1已实际退出1，不能据DUT的2 PASS直接入账。
失败发生在bank2的table1/tick3661来源负对照：该provider对应较早条件分支，
最终taken CFI在它之后。旧工具只翻转最终taken位，所选条件分支仍是not-taken，
因此输入语义没有改变，不能要求比较器报错。审计此前已经完成bank2完整
reset与缓存毒化重放、2048项共享reset oracle的逐cell故障、8项完整reset前缀
控制故障及全部805项实际captured来源正向检查；这些是失败审计的局部进度，
不是整批准入，也没有新增功能bin或行覆盖。原失败源码、日志和receipt保留。

新的`/tmp/bpu-integrated-aging-extra-kiZpME/aging_audit_v2`保留原全部检查，
新增`source_faults.py`：先验证真实正向来源，再构造所选条件分支实际taken
结果相反的私有反事实输入，确保扰动不是被更晚CFI掩盖。四项新增契约覆盖
最终CFI与所选分支同位置／更晚、最终taken为0／1，均触发精确tick、差异字段
和failed=1；原始输入不变。共44项工具检查实际PASS后，新审计session72376、
runner1916136／checker1916137重新重放原两份已通过DUT轨迹，没有重跑DUT。
原共享`audit_v1/lineage.py`和运行中的正式全仓审计来源未改动。

饱和保持v3也已实际1 FAIL、退出1，首错tick8732是readIndex期望[0,0]、
实际[496,496]。它确实看到了baseTaken=1/predTaken=0的lower provider，
但这不能代替正确训练索引资格。对全部8732帧独立重放a0/a1/a2/a3索引token，
并重新关联所有公开transaction，确认tick8728这笔预测的token来自tick8723
输入的`alias_pc-16`，两个索引确为496。这里没有把metadata改写为0，
也没有删除索引断言；全部v3 raw排除。证据见
`results/coverage-bpu-integrated-real-alias-useful-saturation-v3-index-diagnosis-readonly.json`。

新的v4将真实PC别名间距改为0x10000，并为每个别名通过普通MainBTB feedback
安装独立的无条件入口分支。入口PC=alias_pc+0x800，入口与别名的真实低位
索引均为0，入口→别名的path hash为0；四个别名和全部既有边仍保持零历史。
因此进入请求可在真实数据流中携带目标index0，而不是筛掉第一笔不合格输出
直到观察到命中。warm接受、第一笔输入限定的lower纠偏、两个readIndex=0及
useful3→3要求均保留。新增4项入口契约后共25 PASS、零警告，DUT仅启动一次：
session33797、runner1918010／pytest1918011。当前仍待实际DUT终态。

为新别名场景准备完整独立审计，24项工具契约实际PASS，50份辅助／场景源码
已签名冻结。它从reset重放PHR/ABTB/shadow/SRAM/index/parent policy，逐次
核对真实public metadata与S3来源及全部512个useful邻项，重新计算24/56-bin
数据库；还包括缓存毒化、来源／邻项局部负对照和两项完整reset前缀故障。
该工具契约不是实际DUT审计。等待器1919102/session74720只挂接原v4，
必须实际1 DUT PASS并核对25项模型、日志和签名后才运行审计；拒绝所有失败
或身份不一致的数据，不自动重启。旧工具v1仅24项契约通过，绑定的v3已失败，
没有执行或通过实际轨迹审计。当前两类新raw均未准入，原生增量仍为0。

正式29954/46541、隔离已准入32302/46541和全部456分类缺口不变。原全仓
session88357在71%，后继36151仍等待同一原任务。生产1162份来源、RTL/DUT/
xreactor及安装运行时继续冻结，原完整目标没有缩减或完成声明。

## 两份额外老化轨迹完整准入：精确关闭201行，不按用例名计物理bank

同一bank2/3原DUT批次的独立审计v2已于2026-10-09 01:51:55 UTC实际退出0，
源码签名不变，没有重跑DUT。两份完整轨迹各42126帧，共1609项实际captured
来源（805／804）、4096项逐cell故障、16项完整reset前缀故障及144项局部
来源故障均通过；每份都核对真正127→128→0老化脉冲、两张完整512-cell
向量、PHR/ABTB/shadow/SRAM/index/parent policy及独立24/56-bin数据库。
原v1的失败审计仍保留，未把其部分结果当成完整准入。

正样本原生准入工具的25项契约实际PASS，55份辅助／场景来源签名冻结。
原等待器只在上述审计实际成功后启动一次合并，admission子进程1926964
于01:52:44 UTC实际退出0。只合并原v2的两份通过raw与既有32302行候选，
正序／逆序合并的全部原生计数相等，46541个文件／行身份完整保留，没有
丢失原命中行，也没有删除456项已分类缺口。

隔离已准入候选精确成为32503/46541，增加201行：AheadBtb.sv 29行、
AheadBtbReplacer.sv 14行、BypassShadowBuffer.sv 42行、
BypassShadowBuffer_1.sv 113行、ReplacerState.sv 3行。候选dat SHA256为
`3ebf17047c82a71c9c33ce901861ea68cf3f77892b94416f5e1558fbfb98cad5`。
证据见`results/coverage-bpu-integrated-extra-aging-native-candidate-readonly.json`。
这不是正式全仓刷新，也没有新增正式pytest功能点PASS。

在实际准入后，新的只读分析工具实际退出0，追加功能见证矩阵v3、bypass
原生缺口清单v9和ABTB逐cell清单v2；旧版本没有覆盖。它重新检查当前LCOV
的完整46541行宇宙，并使用两份完整审计独立复算的全部操作，而非只读age
计数。56个原有useful行为bin的已准入见证由34增至47，仍缺9个：

- lower bank2：increment、saturated_high_hold。
- lower bank3：age_nonzero、increment、saturated_high_hold。
- upper bank2／3：各自decrement、saturated_low_hold。

这里用实际`index % 4`判定物理bank，不能把用例参数bank2/3当作age_nonzero
的证明。例如，两份新轨迹的lower非零老化单元分别只有index4和index5，
实际属于bank0和bank1；它们同时证明目标bank2/3的captured来源和其他真实
操作，但不能因此关闭lower bank3非零老化或全索引要求。当前两个bypass
文件的原生缺口由4978降至4823，其中直接useful引用2869行，未分类项仍保留。
集成ABTB现为10287/15300，仍缺5013行，分布在1010个计数器单元；bank1
的256个单元仍都有缺口，不能转用独立AheadBTB的100%覆盖。逐行证据见
`results/coverage-bpu-integrated-useful-operation-witness-matrix-v3-readonly.json`、
`results/coverage-bpu-integrated-bypass-native-gap-inventory-v9-readonly.json`与
`results/coverage-bpu-integrated-abtb-native-cell-gap-inventory-v2-readonly.json`。

饱和别名v4也已于01:52:53 UTC实际1 FAIL、退出1，六份源码签名未改动。
首错tick37874仍为第一笔输入限定alias的lower provider不存在；这次公开
readIndex确为[0,0]，因此正确索引不能单独证明有效read payload／位置命中。
失败raw全部排除，原审计等待器按失败终态退出1，没有运行正样本审计或
进行原生合并。v4及之前三版原始失败、日志、raw均保留。新的只读诊断已
实际退出0，完整从reset重放37874帧shadow/SRAM/index，完成454478项shadow
和907882项SRAM比较、75234项defined table response核对，并重新关联所有
公开index token。首错预测的index token来自tick37863入口PC，确为[0,0]；
但是lower位置匹配依赖的read payload来自tick37867，data_valid实际为0。
S2 override保留这个旧payload／posHit，后来有效read response不能代替它。
16847项公开transaction的无效lower来源检查也与该保守模型一致。没有把
失败轨迹改成passed，也不称完整PHR/ABTB/parent policy或功能正样本审计；
没有删除provider或useful3→3断言。下一版刺激需真实建立入口ABTB接受与
有效read payload／位置来源，不能仅检查index相等或筛到hit才开始比较。
证据见`results/coverage-bpu-integrated-real-alias-useful-saturation-v4-source-diagnosis-readonly.json`。

正式四份报告仍是29954/46541，原全仓session88357与后继36151继续绑定
同一任务；生产1162份来源、RTL/DUT/xreactor和安装运行时仍冻结。原完整
目标中的有效非零GHR/BW/commonHR、全索引、深层SC-used/full dirty overwrite、
真实overlap、完整FTQ及七项strict XFAIL／六个RTL问题没有缩减或完成声明。

## 已准入来源的因果分析，以及隔离补充场景的新证据

新的只读因果分析实际退出0。它只读取已完整准入的原bank2／3两份轨迹，
重新关联5001次实际bank2／3更新的public metadata、真实S3、训练read与后继
完整512项useful状态，10002项普通比较全部通过；重新计算的操作数与独立
审计数据库一致。lower bank2／3各有236次base=predicted=actual=0的正确
预测，但这种一致不产生useful递增；其余观察到的是decrement／low-hold。
upper bank2／3则只有正确provider的agreement／increment／high-hold，尚无
provider错误的decrement／low-hold见证。不能用captured来源数、写入数或
用例参数代替这些条件。原缺失9-bin仍完整保留，分析没有新增raw或计分。
证据为`results/coverage-bpu-integrated-bank2-3-useful-missing-cause-analysis-v1-readonly.json`。

为lower bank3的age_nonzero增加独立三程序实验。seed v1的24项模型检查
通过，但DUT实际退出1，发生在外部feedback／redirect之前：old与seed两个
PC映射到同一cold lead，场景重复等待已消费的公开transaction。1300帧失败
和raw保留且排除。新的诊断工具v2实际退出0，核实唯一cold source，以及
511笔实际冷启动fallthrough的完整S1 capture／S3来源；它们不是外部训练
或shadow写入。旧诊断v1因误认为冷启动没有fastTrain而失败，文件未覆盖。
没有将此刺激管理错误称为RTL缺陷。证据为
`results/coverage-bpu-integrated-seeded-bank3-aging-v1-failure-diagnosis-readonly.json`。

seed v2对真实cold source去重，并将第三程序移至独立的MainBTB块，保留
实际allocation、bank3非零状态、真正127→128→0脉冲和完整512项后继状态
要求。lower老化是逐项减1，upper才是减半。26项模型实际PASS，七份场景
来源冻结；DUT仅启动一次，session93796、owner1948776／pytest1948777。
新的独立审计工具52项契约实际PASS，52份场景／辅助来源签名冻结；等待器
1952932/session8918只挂接这次原DUT。成功后才完整reset回放PHR/ABTB/
shadow/SRAM/index/parent policy、缓存毒化、逐cell／完整前缀负对照、全部
captured来源和独立24/56-bin数据库；额外关联seed allocation真实来源并
检查所有512个后继邻项。工具契约通过不等于实际DUT审计或native准入。

四别名饱和场景v5的27项模型和配套32项工具契约实际PASS，但DUT实际
1 FAIL，首错tick37908仍是第一笔输入限定alias没有lower provider。六份
源码保持签名；等待器按失败终态退出1，没有启动正样本审计，没有合并raw。
新增入口接受断言确实通过，不能因此声称最终入口命中。只读来源诊断实际
退出0，完整37908帧shadow/SRAM/index回放、454886项shadow和908698项SRAM
比较通过，16854项无效lower公开来源检查一致，并独立重新关联真实入口
capture／S3。alias索引为[0,0]，但位置匹配依赖tick37901的无效payload，
被后续S2 override保留。证据为
`results/coverage-bpu-integrated-real-alias-useful-saturation-v5-source-diagnosis-readonly.json`。

RTL的AheadBTB由前驱startPc索引，再用newStartPc查tag。因此v5从前驱块
warm、最终直接进入entryPC改变了ahead索引：该计划的前驱映射bank0/set56，
直接入口映射bank0/set0。新v6令warm与最终进入复用同一真实前驱路径，
保留全部四个独立alias、第一笔provider、索引及useful3→3断言；28项模型
实际PASS后才启动一次DUT。该刺激修正仍待硬件结果，不能提前报PASS或
行覆盖增量。v1至v5全部失败raw继续排除。

v6 DUT为session73367、owner1955530／pytest1955531。新的独立审计v4保留
全部入口／provider／完整reset回放和负对照，32项工具契约实际PASS、51份
辅助／场景来源签名冻结；等待器session10764仅挂接原v6。复用日志中的
旧phase标签不是绑定依据，实际检查的是精确owner／child、v6来源和28项
模型门禁。当前没有实际v6 DUT PASS、完整审计通过或raw准入声明。

正式四份报告仍为29954/46541，隔离已准入候选仍为32503/46541、useful
见证47/56。原全仓session88357已达72%，后继36151等待同一任务；原严格
正式刷新候选32264不能替换为隔离32503，也不能注入隔离raw。生产1162份
来源、RTL/DUT/xreactor及安装运行时保持冻结；原完整目标仍未完成。

## 首次 upper promotion 的真实原因、seed 容器修复和共同分支链模型

新增只读分析v2实际退出0，18348项普通比较通过、0失败。它只分析已完整
准入的两条aging轨迹，32／31次allocation与独立功能数据库完全一致。
两者首次目标upper allocation均在tick3057、old_positive_again阶段，来自
真实lower provider：hit=1、table0、predTaken=0、baseTaken=1、counter=0，
实际条件分支taken=1。source prediction在最后一次同键lower allocation
提交之后，不是stale miss。lower稳定路径tag分别为189／175，conditional
与fallback相同且可表示；upper tag分别为62／61和45／40，不同方向被
历史分到不同key。因此不把“修复旧miss bootstrap”当成剩余useful缺口的
解法。分析v1曾错误假定upper初始useful也是1，失败文件保留；v2按原模型
lower=1、upper=2核实所有512项后继状态。证据为
`results/coverage-bpu-integrated-first-upper-promotion-cause-analysis-v2-readonly.json`。

seed v2实际1 FAIL，七份来源签名未变，旧审计等待器与native等待器均按
失败门禁退出1，没有启动完整正样本审计或native准入。新的只读诊断实际
退出0：44162帧完整shadow/SRAM/index回放和所有公开index来源关联通过，
另核对三笔seed allocation来源与完整512项后继邻项。真实age发生于
tick40495→40496，bank3 index159、183、191实际由[1,1,1]变为[0,0,0]，
全部512项等于独立reset推导的减1结果。失败原因是见证helper将live tuple
直接与计算所得list比较；同值保存为JSON list后通过，转回tuple则重现失败。
没有改变失败trace的passed标记，没有绕过正样本成功门禁；这不是完整
PHR/ABTB/parent policy审计，失败raw仍全部排除。证据为
`results/coverage-bpu-integrated-seeded-bank3-aging-v2-boundary-diagnosis-readonly.json`。

新seed v3仅归一化见证比较容器，保留真实bank3非零、实际age脉冲和完整
512项状态断言，并增加live tuple／saved list两项回归。28项模型实际PASS
后仅启动一次DUT，session40578、owner1968154／pytest1968155。新审计v2
的52项工具契约实际PASS，52份来源签名冻结；等待器1974157/session99566
精确绑定该原DUT。v1／v2全部失败raw继续排除；v3仍待实际硬件结果、完整
独立reset回放、全部来源／负对照和独立24/56-bin数据库审计，不能提前计分。

四别名v6已实际1 PASS，1440.81秒，pytest1955531退出0、六份来源签名未变。
原审计等待器1956259没有重启DUT，已启动run1973294／checker1973295，
正在完整回放43038帧reset/PHR/ABTB/shadow/SRAM/index/parent policy。
新的native门禁v1实际25项契约通过、57份来源签名冻结；等待器1968145/
session78350仅绑定原audit waiter1956259与DUT1955531，完整审计实际退出0
以后才允许合并该唯一positive raw，并检查完整46541行身份、全部456分类
缺口、反向合并全部计数一致及无已命中计数丢失。目前还没有actual完整
审计或native准入成功，不能仅凭DUT PASS宣称行覆盖率提升。

针对剩余lower increment/high-hold及upper decrement/low-hold，新增隔离
共同taken分支链的纯模型证据。44项pytest实际PASS、来源签名未变；每bank
穷举全部4096种低12位前缀，六个共同taken分支后得到相同index／完整tag。
bank2为indices[6,2]、tags[135,32]；bank3为[7,3]、[135,33]。完整52-cell
PHR参考模型另做1680项逻辑状态比较，涵盖连续taken、pending提交、空闲
间隔和pointer环绕；只做五个共同分支的负对照证明upper key并不普遍收敛。
两条路径的高52-bit状态仍不同，不宣称完整history相等。证据为
`results/coverage-bpu-integrated-common-taken-chain-model-feasibility-v1-readonly.json`。
这是刺激的模型可行性，不是硬件provider正确性或base disagreement见证。
下一步需通过现有agent/driver送入真实分支与反馈，逐笔关联公开checkpoint/
metadata、真实provider及正反结果；仍须独立完整审计与逐邻项负对照后，才
能准入raw。没有新DUT或raw，也没有functional/native/formal credit。

正式报告仍为29954/46541，当前隔离已准入候选仍32503/46541、useful47/56
且9个缺失见证保留。原全量与ROOT-only审计/后收集链未重启；严格正式
候选32264与隔离候选继续分开。全部非零GHR/BW/commonHR、全索引、深层
SC-used/full dirty overwrite、真实overlap、完整FTQ，以及七项strict XFAIL／
六个RTL问题均继续开放，不缩减原目标、不删分母、不转移独立DUT覆盖率。

## 四别名实际准入新增35行，以及共同链流水来源诊断

四别名v6的完整独立审计实际退出0：43038帧完整reset回放及缓存毒化回放
通过，四别名／四入口来源、四次真实useful3→3和26个来源／邻项／完整前缀
负对照通过，独立功能数据库一致。该轨迹实际captured-counter lineage为0，
没有把空集合核对宣称为新增captured功能覆盖。原审计等待器10764自然退出0。
原native等待器78350随后完成唯一正样本raw准入，实际admit1987828退出0。
新候选32503→32538/46541，新增35行：BpuDut顶层3、AheadBtb13、
AheadBtbReplacer16、ReplacerState3。候选SHA为
`00a8ddea07e9e4c2c4af3e2b41526240536dc7c96318ac6b5e3783d9057978da`。
完整46541行身份、全部456分类缺口、反向合并全部计数一致及无旧命中丢失均
通过；v1至v5失败raw全部排除。证据为
`results/coverage-bpu-integrated-real-alias-v6-native-candidate-readonly.json`。

新的只读清单刷新实际退出0：useful见证矩阵v4仍47/56、9个缺失项未变，
bypass逐行清单v10仍4823项缺口／2869项direct useful；AheadBTB逐cell清单
v3从5013降至5000个缺失行、1010降至1008个有缺口cell。bank1全部256个
cell仍有缺口，不能用独立ABTB的100%代替此集成证据。三个清单逐项校验
当前32538 LCOV和源码，不沿用未经当前候选验证的旧计数。

seed v3实际1 PASS、1453.59秒，pytest1968155退出0，七份来源签名未变。
原audit waiter1974157/session99566启动run1989277／checker1989278，正在
执行同一条轨迹的完整独立审计。新seed native v2实际25项契约通过、58份
来源签名冻结，等待器1990845/session78620仅挂接该审计链；基线明确采用
已经实际准入的32538，不再从32503分叉。成功完整审计之前不准入seed raw，
也不提前关闭bank3 age_nonzero功能缺口；seed v1／v2失败raw继续排除。

共同链硬件首版位于独立临时目录，76项模型／输入资格／checkpoint路径
检查实际PASS后启动一次两bank DUT批次。它复用现有agent/driver与完整
PHR/ABTB/SRAM/shadow/index/parent policy monitor/checker；测试入口只有
场景意图，没有edge/get_set/gather。DUT实际2 FAIL、217.40秒，七份来源
签名未变。两例均在warm_negative、tick3472因真实同键输入资格数量为0
失败；没有删除资格断言，两个raw保留且排除。

新失败诊断v2实际退出0，从reset完整重放两例共6944帧，重新关联所有公开
transaction、真实反馈、每个checkpoint hop和完整PHR/ABTB/shadow/SRAM/
index/parent policy。bank2六条预期共同taken边均实际发生，但目标公开
index是[0,132]，独立token的PC为最后共同分支0x40012800，而非目标PC；
公开完整tag为[129,28]，不是纯路径模型预期[135,32]。bank3还有第一条
共同taken边未发生，实际两笔fallthrough替代；目标index[0,133]、tag[129,57]。
实际物理banks分别为[0,0]／[0,1]，不能按case名报bank2／3覆盖。
诊断v1错误断言两例都发生六条预期边而退出1，旧文件保留；v2如实记录
缺失边，失败trace passed标记未变，也未绕过正样本门禁。证据为
`results/coverage-bpu-integrated-common-chain-v1-failed-source-diagnosis-v2-readonly.json`。

因此44项纯PHR模型的收敛定理仍只是该模型的数学证据，不能外推为硬件
当前PC→readIndex/public-fold的对应关系。下一版须结合真实前驱token、
a0/a1/a2/a3 fire/override/hold和实际MainBTB分支驻留重新设计来源路径，
并先解释bank3缺失首边；不能仅修改预期值或把物理bank0重新命名为bank3。
该失败实验和诊断没有新增functional/native/formal credit。

正式四报告仍29954/46541，原全量session88357及原审计/ROOT-only后收集
36151未重启。严格正式刷新候选32264仍独立于隔离32538。生产1162份来源、
RTL/DUT/xreactor及安装运行时仍冻结；全部原始非零history、全索引、深层SC、
真实overlap、完整FTQ及七项strict XFAIL／六个RTL问题继续开放。

## Seed完整审计与实际新增33行，以及共同链双历史快照

seed v3的原独立审计checker1989278实际退出0，来源签名未变，原等待器
1974157/session99566也自然退出0。完整44162帧reset/PHR/ABTB/shadow/
SRAM/index/parent policy回放、缓存毒化重放、805条实际captured lineage、
2048个cell负对照、8个完整前缀control负对照、72个局部来源负对照及12个
seed来源负对照均通过；独立24/56-bin数据库一致。bank3三个真实非零单元
index159、183、191在tick40495→40496从[1,1,1]变为[0,0,0]，全部512项
后继状态比较通过；独立计数table0.bank3.age_nonzero为3。

原native v2实际退出1，失败证据保留：虽然admit读取并检查了32538基线，
native_delta helper仍默认prior_hit=32503，调用遗漏该参数后拒绝当前基线。
这不是DUT或完整审计失败，也没有准入该失败后处理版本的candidate raw。
新native v3将prior_hit改为必填关键字，调用显式采用已准入报告的hit，新增
完整46541项／456个分类缺口的当前基线接受、旧基线拒绝及省略参数拒绝回归。
28项契约实际通过；不重跑DUT或审计，沿原成功链完成准入，admit1999255
和session83686实际退出0。新候选32538→32571/46541，精确新增33行：
AheadBtb12、AheadBtbReplacer4、lower BypassShadowBuffer15、upper2。
候选SHA为55d75449d233330fe41441920cf739a7bfceb913693a434c155c0cecafdd8c7d。
完整46541行身份、全部456分类缺口、反向合并全部计数相同及无旧命中丢失
均通过。seed v1／v2失败raw和native v2失败候选继续排除。证据为
`results/coverage-bpu-integrated-seeded-bank3-aging-v3-native-candidate-readonly.json`。

新只读清单逐项重查当前LCOV：useful见证48/56，新增且仅新增bank3
age_nonzero；仍缺lower bank2／3的increment和high-hold、upper bank2／3
的decrement和low-hold，共8项。bypass缺口4823→4806，direct useful
2869→2864；AheadBTB缺失行5000→4988，有缺口cell1008→1006，逐bank
为247／256／251／252。第一次刷新实际退出0，但比较版本键误写v30、
分类器来源SHA误填旧refresher SHA；原版不改。新刷新v3实际退出0，明确
保留并替代这两项来源元数据错误，逐项校验数字不变，不重复计分。当前
权威只读清单为useful matrix v6、bypass inventory v12、ABTB cell inventory v5。

共同链的公开证据进一步解释bank3缺边：first common0x40012000、last
common0x40012800及conditional0x40010005/pos7均落在align0/internal0/
set0，要求三个不同resident同时占据两路，容量上不可能。公开readback先
显示first在way1、last在way0，conditional随后占way1；后续first的两个
rawHit均0，读出的两路payload分别为unconditional pos0和conditional pos7。
这是容量冲突及实际公开miss证据，不宣称观测了完整MainBTB SRAM写链。

另确认旧bank2最后target的index token使用normal folds[0,132]，公开tag
则使用更新一条共同分支后的folds[0,7]；bank3对应[0,133]和[0,3]。不能把
二者折成同一个history端点。七边路径首模型32项PASS且明确无硬件映射
声明；新的八边双快照模型34项实际PASS，4320项完整52-cell状态检查和
每bank全部4096种低12位前缀通过，分别保留index六条共同边／tag七条
共同边的历史。新末共同PC为0x40012102／0x40012103，模型预期index
[306,498]／[307,499]、tag[130,38]／[130,39]，全部共同分支避开set0。
证据为`results/coverage-bpu-integrated-common-chain-source-alignment-model-v2-readonly.json`；
仍不是新硬件provider或useful见证。

新硬件场景v2的模型负对照实际2 FAIL／59 PASS，原因是测试fixture中token
与预期recipe共用list，故障注入同时改变两者；没有创建DUT或raw。失败版
保留，v3仅隔离fixture容器并新增回归，62项模型实际PASS、七份来源签名
冻结，随后仅启动一次两bank隔离DUT批次。场景复用现有agent/driver及完整
monitor/checker，额外检查全部分支在conditional分配后仍驻留、自然窗口
中每条共同taken边实际发生，并严格按两个来源快照资格检查。尚无实际
新DUT PASS／完整独立审计／native准入，不能提前关闭剩余8项见证。

正式报告仍29954/46541；原完整回归已观察到73%，同一owner1790426／
pytest1790608及后收集owner1811013仍实际运行，未重启。正式严格候选
32264不接收隔离raw，隔离32571不冒充正式数值。生产1162、RTL/DUT/
xreactor和安装运行时冻结边界及全部原目标范围继续保留。

### 共同链v3实际失败与准确S3事件比较修正

上述v3隔离DUT随后实际2 FAIL、174.45秒，原session57908及pytest2018259
退出1、七份来源签名未变，两个raw保留且排除。两例均在tick2806新增
驻留后检查失败：接受的早阶段public prediction为fallthrough，而检查把它
直接与MainBTB的后阶段taken结果比较。没有任何自然窗口完成，也没有
新增provider/useful见证。v51检查点记录的是该进程退出前的实际活性，
不能把它视为终态；应以下述新诊断及后续检查点为准。

新失败诊断实际退出0，完整重放两例共5612帧reset/PHR/ABTB/shadow/SRAM/
index/parent policy，重新关联全部公开transaction、真实反馈及checkpoint。
同一source的prediction_tick2802／meta_tick2806，metadata确实rawHit=1、
branchType=3；在准确meta事件上，最终S3为valid1、PC0x40012020、taken1、
position0、target0x40012040，两例均完全等于场景意图。诊断明确保留
passed=false，不绕过正样本门禁、不准入失败raw。证据为
`results/coverage-bpu-integrated-common-chain-v3-failed-stage-diagnosis-v1-readonly.json`。

新v4仅将这项比较改为source.meta_tick对应的valid public-meta事件上的
最终S3，仍检查所有分支rawHit驻留、自然窗口每条共同taken边以及完整
index/tag双快照输入资格。新增合法早fallthrough／正确最终S3回归、六个
最终字段错误的Scoreboard异常负对照、两个错误metadata事件拒绝回归。
71项模型实际PASS，随后只启动一次新两bank隔离DUT批次；尚待实际结果，
仍无新增functional/native/formal credit。隔离候选32571及48/56见证不变。
原完整回归同一进程实际已到83%，后收集链仍等待；冻结与原目标范围不变。

### 共同链v4真实bank来源已对齐，缺少的是conditional ABTB入口

v4实际2 FAIL、223.75秒，原session46470／pytest2036495退出1，七份来源
签名未变；两例均在warm_negative、tick3582因同键输入资格数量0失败。
所有八条共同分支在conditional分配后仍有公开rawHit且准确同源最终S3
等于意图；新增S3检查通过，不再比较错阶段。两个失败raw保留并排除。

新失败诊断实际退出0，完整独立重放两例共7164帧，重新关联所有公开
transaction、真实反馈、checkpoint和八条驻留后S3 readback。每例自然窗口
均有27个目标source：bank2实际index[306,498]、tag[130,38]，bank3实际
index[307,499]、tag[130,39]；真实前驱PC分别0x40012102／0x40012103，
normal folds均[48,240]。物理banks确实[2,2]／[3,3]，不是重命名bank0。
八条共同taken边每条均实际出现至少两次。27项source的PC／token PC／
index／fold／完整tag／redirect guard全部等于预期，唯一拒绝维度是
conditional_ABTB_input；两例27/27均没有条件分支ABTB入口。证据为
`results/coverage-bpu-integrated-common-chain-v4-failed-input-diagnosis-v1-readonly.json`。
失败passed标记及正例门禁未改变，此诊断不产生functional/native/formal credit。

原因是MainBTB设置阶段关闭ABTB，之后第一窗口直接运行negative路径；
真正S3 fastTrain学习的是被选中的taken分支，故只建立fallback，而非尚未
被选中的conditional。新v5在原五窗口之前增加bootstrap_positive/goal3，
先通过真实预测／S3 fastTrain建立conditional入口，然后运行negative等
异向窗口；不删conditional输入资格，也不按provider结果筛选。增加阶段
先后／三个正向三个负向窗口／未primed条件入口仍拒绝的五项模型回归，
计划总数76；尚未执行，不记为PASS。新七份来源已由等待器冻结。

原正常完整回归已观察到96%，同一owner1790426／pytest1790608仍实际运行。
run_all会在pytest结束后合法刷新四份报告；为避免新隔离scope跨越这一刷新
而触发“报告变动”伪失败，v5精确等待该原full实际退出0，再一次性执行
76项模型、成功后一次性执行DUT。等待器2050100/session75790实际已启动，
只挂接原owner，没有重启full、没有放宽隔离报告保护。ROOT-only postcollect
已经明确逐字节保护四报告和十份LCOV，因此full实际0后可在保持生产冻结
的前提下运行新隔离case；原full的独立审计和postcollect仍是另外的必需门禁。

当前隔离候选仍32571/46541、已准入useful见证48/56、8项缺口不变。旧正式
29954/46541是上次独立审计值；即使正常full生成新报告，也必须完成同一原
完整独立审计及ROOT-only后收集后才确认刷新有效。严格正式候选32264不
接受隔离raw；不缩减集成模块、全部非零history、全索引、深层SC、真实
overlap／full dirty overwrite、完整FTQ、七项strict XFAIL／六个RTL问题范围。

### ABTB全索引计划纠正：半字地址单位与前瞻阶段分别验证

新隔离all-index v1的809项模型实际通过，分析器实际退出0并关联现有
4988条native缺口／1006个cell，但后续对照冻结的编译RTL发现其错误：
模型把Pc.addr直接作为字节地址参与ABTB索引。`PrunedAddr.scala:29/31`
明确addr已裁掉instOffsetBits，实际字节PC需左移一位；奇数Pc.addr不等于
奇数字节PC，不能据此判断指令地址非法。`rtl/bpu/AheadBtb.sv:1374`
的实际_GEN为`{io_startPc_addr[2:0], 1'h0} ^ foldedHist[3:0]`，setIdx
再拼接addr[6:3]。正确物理索引为`((Pc.addr << 1) & 255) ^ (fold6_6 & 15)`。
PHR自身的CFI／target公式此前正确：编译RTL的CFI addr[8:0]左移4位，
异或target addr[15:1]，不能把不同模块的位段选取混为同一地址规则。

旧v1源码、809 PASS日志、收据和只读报告全部保留，不回写伪造历史。
新v2实际1069 PASS／退出0，新增只读纠正报告：
`results/coverage-bpu-integrated-abtb-halfword-pair-stimulus-model-v2-readonly.json`。
旧计划256组中255组物理索引标签错误，真正单节点自环只能到达64组，
每bank16组；不能继续按旧“256组双射”安排硬件场景。

新计划以A→B→A双节点taken链解除PC／history耦合，显式区分before-B和
before-A两个数学history快照，每组规划五对alias，peer ABTB key不占用
目标组。256组均经全部64种低6位前缀检查；选定边界组的完整52位PHR
pending／指针回绕／空闲拍模型共15360次检查。MainBTB非对齐起点的
read地址轮转和FTQ train起点轮转按实际RTL／FTQ源码建立静态模型，
每组十个计划分支在每个物理align/internal/set下最多两项，不超过两路。
这些仍是静态可行性，不是实际写入、四路victim或完整FTQ合法性的证明。

另新增独立ABTB index token重放：148项pytest契约实际通过，覆盖reset、
前瞻a0源、hold、S2/S3 override优先级与地址单位错误。完整读取原v4两份
失败轨迹的7164帧，实际检查3426次有效ABTB元数据bank/set，全部符合
从输入推进的独立状态模型，不用DUT输出初始化索引状态，也不用固定tick
偏移。两份轨迹各1713次有效检查、各13个实际bank/set组合；normal合计
3358次、S2 override合计68次。轨迹没有有效S3 override见证，不能把
契约中S3优先级测试当成硬件S3覆盖。把地址左移故意改为0，两份完整
重放都检出错误。诊断实际退出0，证据为
`results/coverage-bpu-integrated-abtb-index-phase-failed-trace-diagnosis-v1-readonly.json`。

上述只增强地址／阶段解释，原v4仍2 FAIL，其raw仍全部排除；新增native
行和功能见证均为0。当前已准入隔离候选32571/46541、useful 48/56、
ABTB缺口4988行／1006 cell均未变化。新的双节点计划仍需真正DUT
运行、源token／override／hold关联、完整独立审计及负对照后才能准入。
同一原full和post链继续运行，v5等待器仍精确等待原full实际0后执行，
没有重启full、没有提前运行v5、没有修改生产1162来源或安装的运行时。

### 双节点硬件pilot就绪：真实前驱边界与PHR／前瞻联合推进

新pilot v1在任何DUT启动前实际33 FAIL／324 PASS／退出1，来源九份均
未改动。失败全部来自更广地址集暴露的checkpoint边界：Pc.addr模16为1
时，旧`(pc-1)&~15`把cold lead选到pc-1本身，却需要用前一个halfblock
中的pc-2作为真实CFI。旧源码／日志／收据保留，无DUT或raw；新v2用
`(pc-2)&~15`选起点，并补齐全部16种余数的实际两段checkpoint检查，
没有删掉“前驱与CFI同halfblock且位于CFI之前”的资格条件。

编写pilot时再次核对Bpu.scala的s0_startPc选择和Phr.scala的oldFoldedPhr：
当前S1为A时，s0地址已是其目标B，但normalPathHist仍是更新A之前的
s1_foldedPhrReg，不是A→B之后的history。因此先前只验证独立数学
before-B快照的双节点静态计划不能直接充当运行时前瞻索引计划。
新的联合模型每拍先用旧PHR fold1和当前S1目标推进已通过148项契约／
7164帧重放的ABTB索引流水线，再推进完整52位PHR；idle时由真实fire
条件保持pipeline。目标A的index源PC为B，使用before-A的history；
peer B的index源PC为A，使用before-B的history，两者分别建模。

新v2实际377 PASS／退出0，九份源码冻结。所有256组保留五对alias规划，
缩短A/B地址间距以便用真实cold metadata建立前驱；每个MainBTB物理
组最多两项。边界组完整PHR模型检查15360次、联合前瞻阶段检查9600次。
证据为`results/coverage-bpu-integrated-abtb-pair-pilot-v2-model-readiness-v1-readonly.json`，
当前运行时计划以该报告为准；旧独立静态模型及其尚未证明运行时关联的
限制原样保留，不把旧数学检查回写成新硬件证明。

硬件pilot只执行四组：bank/set为0/0、1/0、2/31、3/63，每组先执行五对
规划中的第一对。用既有BpuAgent反馈driver、静态Bundle、@on并行
monitor、既有完整PHR／ABTB／shadow／SRAM／index／parent-policy检查器；
组合增加独立ABTB索引token，不在测试用例中处理edge、get/set或gather。
通过真实MainBTB反馈建立A条件分支和B直接分支，用确切meta_tick关联
最终S3结果。natural窗口的输入资格只检查真实PC、源token、bank/set、
旧history相位、normal路径及无redirect，不按conditional hit或provider
结果筛选输入。之后另断言条件入口实际建立、两条S3边实际运行、目标
cell出现inc2_3及inc3_3，保留全部完整轨迹与失败状态。

一次性等待器2060999/session52864已实际启动，先等待同一原full
owner1790426真实退出0，再等待既有common-chain v5等待器2050100
进入实际终态；若v5失败，保留其失败和排除raw，独立pilot仍可执行。
pilot启动前冻结正常生成后的四报告和十份LCOV，执行后逐字节保护。
它不会重复启动full或v5，也不会放宽生产来源／运行时冻结。
当前只有377项模型实际通过，四项DUT尚未执行；全索引、五alias／四路
替换、完整ABTB SRAM写生成、真实overlap／full dirty overwrite及FTQ
仍未证明，native与功能见证增量为0。成功pilot还需完整独立正向审计、
负对照及准入，再扩展全索引／四路矩阵；整体目标继续保持原范围。

### ABTB写生成独立化：完整失败轨迹诊断，不把模型事件当硬件覆盖

新增隔离`abtb_write_lineage_v2`，生产1162来源、既有pilot v2的九份
冻结来源、RTL/DUT/xreactor及安装运行时均未修改。现有集成检查器的
`CounterReference`接受实际bank writeResp作为输入，只能独立检查其
计数器／PLRU影响；新增模型从真实S1→S3元数据关联、最终训练事务、
PC／history／stage control推导T1/T2写请求、四个WriteBuffer的保留／
覆盖／排空和SRAM写响应，不再用观察到的writeResp推进参考状态。
drain-ready也不是DUT提供的答案：独立建模64拍SRAM reset walker，
单端口读压力由正常路径PC、fold和fire0推导，只阻塞所选bank。

三条写路径分别处理：cold-taken新分配用T1旧PLRU决定并锁存victim；
indirect目标低22位变化修正最低matching way，不reset counter；
预测侧多命中清理写零entry，并受同bank正常T2写优先级约束。
清理选择按ABTB Helpers的嵌套循环最后一次matching pair，而不是
“取最低命中way”；新清理请求优先于清除旧已应用请求。

源码复核纠正一处描述：`BranchType.Direct=2`、`Indirect=3`。
前节pilot所称“B直接分支”实际发送kind3，即固定目标的间接分支；
冻结源码不改写，后续描述以真实编码为准。模型专门检查kind0/1/2
不会走indirect target-correction，kind3在matching且低位目标不同时
会走此路径；当前RTL条件没有taken门控，not-taken组合也按实际实现
建模，并不把这种实现行为表述成架构正确性结论。

首版v1实际366 PASS／退出0，但pytest对迭代器参数发出弃用警告，
保留其七份源码／日志／收据，不用于清洁证据门禁。新v2将参数集合
明确为tuple，实际366 PASS／无警告／退出0，来源七份冻结。契约涵盖
四bank×64set分配、四种branchType×taken×way×目标差异、全部8种
PLRU状态的T1锁存、64拍复位、read-pressure、cleanup优先级、真实
训练流水线中的full dirty overwrite及同拍drain/write旧值语义。

完整回放原common-chain v4的两份失败轨迹，共7164帧，独立推导并
逐次比较28个实际写响应的valid/set/way/reset_counter，所有非复位
帧继续比较全部1024 counter和256 PLRU寄存器及shadow。8项实际
负对照分别破坏两条轨迹的写响应四字段，均由Scoreboard在精确tick
抛出包含差异、请求上下文和失败状态的异常。实际回放退出0，证据：
`results/coverage-bpu-integrated-abtb-write-lineage-failed-trace-diagnosis-v2-readonly.json`。

该诊断从输入推导30个分配／5个cleanup请求，以及1次buffer full
overwrite、1次同slot drain/write等模型事件；尚未直接采集并比较
ABTB各buffer slot／完整T2请求，也未检查ABTB SRAM读数据内容，
不能将这些派生事件当成已闭合的硬件功能覆盖或full-overwrite证明。
两条轨迹均无target-correction模型事件，实际覆盖缺失仍保留。
原v4仍为2 FAIL，raw全部排除，native与功能见证新增均为0。

同一原full已经推进到99%且真实pytest进程仍存活；没有重启full。
新正向写链路审计正在使用既有已准入seed-v3的44162帧，而不是重跑
DUT或重新合并raw；终态尚未产生，不预报通过。common-chain v5和
双节点pilot仍由原等待器按既定顺序等待。全索引／五alias四路替换、
全部非零有效history、深SC-used／生命周期、直接buffer/SRAM验证、
真实overlap／full dirty overwrite／完整FTQ和既有strict XFAIL问题
仍在原目标内，当前没有完成声明或新增行覆盖率计账。

上述正向审计随后已真实退出0：完整44162帧、624532项Scoreboard
比较全部通过，32个独立推导的SRAM写响应与实际valid/set/way/
reset_counter一致，四字段实际负对照全部在原tick抛出异常。
来源九份冻结，旧正向DUT／完整审计／raw／native候选身份均核实。
新增证据为
`results/coverage-bpu-integrated-abtb-write-lineage-positive-audit-v1-readonly.json`。

该正向轨迹推导的请求仅涉及bank0/2，183次分配、71次cleanup，
未出现indirect target-correction；也没有full-overwrite模型事件。
这些缺失不能用前述失败轨迹的事件或纯模型契约补成正向覆盖。
当前下一步仍需按真实pilot结果扩展bank/set／alias矩阵，并单独安排
目标变化的indirect路径及直接buffer观测。这里没有新DUT、没有重合并
已准入raw，native增量严格为0；32571/46541和其完整分母保持不变。

### 新直接观测层：完整T2／shadow／SRAM端口，仍待真实DUT绑定

隔离新增`abtb_direct_observation_v1`，静态Bundle计划采集524个VPI
叶子：四bank外部T2请求及buffer输入的完整九字段、16个shadow
slot的valid/dirty/完整payload、四个miss-PLRU、dirty drain的完整
payload/valid/ready、正常读请求、SRAM reset-done/ready、四路写
data/waymask和完整SRAM读回。事件调度复用既有lossless同步`@on`
RisingEdge/DriveStable捕获，不在DUT测试用例编排edge或pin get/set。

新增检查器复用逐字节相同的已签名写入与索引模型；读压力从真实
PC／fold／fire0推导，64拍SRAM复位和ready独立推进。SRAM读期待
来自复位遍历及预测写入内容，同步读后保持；未完成真实读之前的
未知输出不当成零，不以实际输出初始化。buffer动作只在后继rising
完整slot比较成功后确认，复位／失败前的pending动作不冒充硬件见证。
比较异常通过owner传播到前台，保留字段差异、事件和Scoreboard状态。
新scope兼容agent shutdown的resume_streams参数，子monitor关闭
失败时也执行其余资源清理；没有改动冻结生产类的teardown实现。

v1实际804 PASS／退出0，九份来源及只读准备报告保留。随后补查发现
兄弟bypass checker已有异常时，新直接层可能把后续关联错误盖到
owner上；新v2保留第一次兄弟异常，并令summary调用父检查器的
raise_failure，不能把自身零错误摘要当整体成功。v2实际805 PASS／
退出0，其中366项是原模型回归、439项是新静态／替身契约；完整字段
逐项故障均被检出，两相快照及资源关闭实际由MemoryBackend执行。
证据：`results/coverage-bpu-integrated-abtb-direct-observation-model-readiness-v2-readonly.json`。
上述仅证明软件机械行为及生成RTL中字段存在，不证明已安装DUT的
实际VPI可用性；实际DUT绑定／案例数仍为0，无native或功能覆盖增量。
它只能用于后继新版本场景，未修改当前排队pilot v2及其九份来源。

### 同一原全量正常刷新已退出0：32264／46541，独立完整审计继续

同一原pytest实际结束：8153 PASS、7 strict XFAIL、无SKIP；总8160项。
随后原tests/run_all.py正常生成RTL JSON、十份LCOV及HTML并实际
退出0，receipt的run_all child仍为1790607，1162来源及安装运行时
均保持原冻结身份。新功能点报告为286/286 executed，279 PASS、
7 XFAIL、FAIL/ERROR/XPASS/SKIP/NOT_RUN均为0，不能把XFAIL算PASS。
正式manifest保留693个raw文件，不注入隔离32571候选的额外raw。

本次正常生成的BPU RTL行覆盖从旧已审计29954/46541（64.36%）
到32264/46541（69.32%），新增2310行。对旧归档LCOV和新LCOV的
完整源文件／行号集合进行只读比较：46541个DA键完全相同，无旧命中
行丢失，全部456条已分类缺失行仍未命中且未从分母移除。
增量按文件为：AheadBtb73、AheadBtbReplacer72、下级BypassShadowBuffer1261、
上级BypassShadowBuffer759、CommonHR4、MicroTage10、Ras4、RasStack100、
ReplacerState15、ReplacerState_4为12。这里只归属文件，不声称某个
功能点单独造成某一行命中；不同完整回归epoch也不要求每个原始计数
值单调增加，比较的是完整行全集及命中集合，不是加法合并的计数约束。
证据：`results/coverage-bpu-normal-formal-native-epoch-delta-v1-readonly.json`。

这是正常刷新结果，尚非完整独立审计完成：原post owner1811013已
自动启动audit child2095683，须重新读取200+96+144+17份实际新轨迹、
完成规定负对照／功能数据库／HTML／raw审计，然后ROOT-only
postcollection实际0，才能解除生产冻结和声明此轮全链审计完成。
原v5 waiter2050100已自动完成76项模型／退出0，并启动既有两个
DUT案例（owner2096076、pytest2096077）；双节点pilot waiter2060999
仍等待其实际终态，不重复启动任何full、v5或pilot。

隔离已准入候选仍为32571/46541，不替换本轮正式32264；全部原范围
继续保留，包括实际有效非零GHR/BW/commonHR、SC-used深层路径、
所有bank/set/four-way alias、真实overlap/full dirty overwrite、完整
FTQ及七项strict XFAIL／六个RTL问题。整体目标仍未完成。

## 2026-10-09 14:16：用户要求立即替换 VPI，改用 trace + memory-direct

以上冻结／审计等待状态已由用户新指令覆盖。旧独立 VPI 审计2095683
按明确授权终止，实际exit=-15，post owner最终exit=1；全部日志和报告
保留，不能称为完整独立审计通过，也不将取消解释为RTL功能失败。

首次 memory-direct 构建漏开trace，只生成物理variables；随后强制
`--public-flat-rw`的判断也不正确。用户指出已有波形解析还原能力，
核实picker确实会解析trace代码并把direct/projection/expr/const映射
合入offset YAML。新方案是`--rw mem_direct -w memory-direct.fst`，
VPI OFF、无`--internal`、无`--public-flat-rw`；普通pytest关闭运行时
波形写出，但保留编译trace feature与native读取。

实际MicroRAS trace-only构建退出0：670个物理字段、633个direct
trace映射，共982个不同名字；`MicroRas.reset`正确恢复为顶层reset
offset1并实际读取成功。已安装该包，旧包可恢复。native/derived API
四类映射回归24 PASS，安装后选定测试25 PASS；不能据此声称十个
DUT全部迁移或完整功能回归通过。其余九个trace-only构建仍在进行。

25个生产monitor及三个诊断程序改用XSignalCFG，不调用旧wrapper
getter，不共享其内部缓存，不允许VPI回退；合法只读派生映射不会
因没有独立物理字段而被拒绝。构建和安装仍分离，新权威目录为
`/tmp/bpu-memory-direct-trace-k8aQV8`。已有根目录报告/raw完整备份于
`/tmp/bpu-memory-direct-public-pTahtW/backup-reports/results-before-memory-direct.tar`。
旧VPI隔离候选只保留历史身份，不作为memory-direct新native增量。
后续需完成真实Bundle绑定、全模块pytest及原始行覆盖重新刷新，
检查新旧行全集，原目标范围不缩减。续跑检查点为v58。

## 2026-10-09 本轮续跑：原生迁移落地，四路替换试点完成全帧重放

十个 trace-only memory-direct DUT 的构建和安装均实际退出0。集成BPU
六个生产monitor绑定4511个句柄，额外RAS retirement接口28个句柄；
均没有VPI或internal getter回退。native/derived API当前27 PASS，
普通完整收集8197项。MicroRAS完整组件20 PASS、15个功能点执行，
原始映射源行91/91；这些不能替代全量功能回归。

RAS/SC/MicroTAGE/MainBTB完整组件回归1202 PASS、4项预期XFAIL，
源码前后指纹相等，原生转换实际0。逐源文件逐行比对，四者的原生
DA行全集和命中集合与旧epoch完全相同，新增/丢失命中行均为0：
MainBTB1056/1056、RAS565/585、SC3145/3481、MicroTAGE9901/11053。
121份本轮raw（450398122字节）在后续全量测试覆盖同名文件前已保存至
`/tmp/bpu-memory-direct-trace-k8aQV8/components-v1-preserved/`。
此处是原始映射源行，不是把v_line采样点数当作RTL文本行数。

旧隔离direct observer仍有VPI依赖，已保留旧版本并新增
`abtb_direct_observation_v4`：810项纯契约通过，真实525个ABTB
shadow/T2/SRAM端口句柄绑定通过。新的`abtb_direct_pair_pilot_v5`
默认规划全部256个bank/set，每组五对alias；当前实际只运行bank1/set0，
不能据收集矩阵声称256组执行。382项纯模型和该真实DUT试点通过；
五个alias均读回完整SRAM内容，实际分配遍历四路，并确认第五个tag
复用已分配路。5546个连续双相位帧完成76451次直接比较，91个写入
动作已确认，无未确认动作；测试用例仅声明场景意图，调度仍在生产
driver/monitor/@on层。

离线审计v1实际失败：负对照选中了reset时尚未资格化的tick1
drain_valid。失败日志保留。v2只修正选点，要求非reset状态，SRAM读
响应等待真实preedge读取提交；比较模型未放宽。104项审计契约通过，
完整parent/history/index、独立写链路及全部直接端口重放通过，功能
数据库独立重构一致，86个真实观察负对照全部检测到；另有1404对
相邻周期fastTrain接受见证。此重叠仅指硬件fastTrain流水线，不代表
所有host train/predict、FTQ或dirty full-overwrite组合闭环。
摘要见`results/coverage-bpu-memory-direct-five-alias-pilot-v1-readonly.json`；
无正式或原生覆盖率增益准入，full FTQ和全部256组仍未证明。

另核对350份原始RTL与迁移前逐字节一致，四个已安装运行库文件指纹
及当前进程加载的库匹配既有安装。源码分支未切换；xcomm在原
`fix/native-memory-boundaries`分支已有8929374提交和未编译改动，
本轮未重装，不能声称当前源码已编译。证据为stage中的
`native-rtl-runtime-v2.json`。

唯一全量memory-direct回归从06:54 UTC启动，仍在运行。204份旧功能
JSON已可恢复地隔离至`before-formal-v1/results/`，根正式报告目前
仍属历史VPI epoch。覆盖一致性审计已排队等待它实际0：独立重合并
原生raw、核对HTML/JSON/LCOV、区分12份新基础设施smoke raw的独有
命中，并执行不改报告的正常收集。它不替代457份完整动态重放和882个
集成错误注入。原目标及CommonHR/GHR/BW、deep SC-used、full-overwrite、
FTQ、全部bank/set/four-way和剩余useful场景不缩减；检查点更新为v60。

## 2026-10-09 续跑：原生动态审计入口与 FTQ 功能缺口

在不改动运行中源码的前提下，新增隔离入口
`/tmp/bpu-memory-direct-trace-k8aQV8/dynamic-audit-v1/`。40项契约测试
实际通过，预检实际0，校验1189个源码/RTL/运行库文件及109个帮助
程序身份；旧VPI admission主程序不会执行。等待器PID2283986
（session97323）只等待既有指标审计PID2272492成功，不重新运行回归。
之后保存本次完整轨迹与204份功能JSON的不可变快照，重放
200条SC history、96条SC masked、144条ABTB、17条集成轨迹及
882个集成故障检查，并独立重构逐例/聚合功能覆盖计数。
目前只有门禁测试与预检通过，不能称457/882动态审计已经通过。

FTQ源代码复查发现具体功能缺口：实际导出DUT的`bpuPtr.value`为
3位，即8槽，不是Chisel默认参数64槽。BpuPorts.control未绑定此
指针，生产Python及测试未显式引用bpuPtr/s2FtqPtr/s3FtqPtr；初始化
会将这些输入置零。现有S1/S2/S3关联器检查fire/flush和metadata回声，
但BpuTransaction没有FTQ槽位或generation，不能替代FTQ生命周期模型。
这是源码推断，尚未宣称取得新的FTQ波形观测。

尤其要注意：生成源`dut/bpu/BpuDut.v`的2037、2038、2347、2348行
在历史LCOV里均已有非零DA命中，分别为145746、145746、124166、
124166；这些是映射DA计数，不是四个独立采样点的证明。因此“指针
赋值行已命中”仍不代表指针前进、回卷、容量反压、override重写、
redirect回退或元数据槽位生存期验证完备。缺口应增加功能场景与
对应checker，而不是修改行覆盖率分母。

五alias试点保存并多次使用早先真实redirect metadata；来源真实
不等于对应FTQ generation仍有效，full_FTQ_legality_proven继续为false。
也不能反过来简单禁止所有延迟training：Ftq.scala的resolve/train
cache可保存快照，必须分别建模FTQ槽位、redirect、resolve缓存和commit
生命周期。可复查的源码/schema/历史DA证据及待实现场景在
`results/coverage-bpu-ftq-lifecycle-gap-v1-readonly.json`；无正式覆盖增益准入。

## 2026-10-09 续跑：FTQ 指针客户端真实验证，明确零行增益

新增隔离`ftq_native_v1`，使用静态Bundle、SignalDriver所有权和双相位
`@on`被动监视。预测器控制driver排除ready/meta_ready，避免与FTQ
driver争用；AsRiseWrite保持不变，提交细节藏在driver中，测试用例
只声明fill/hold/retire/wrap/refill意图。生产suites/frontend/bpu/tests未改，
原生全量回归及两个审计等待器继续运行。

23项纯模型测试实际通过；真实BPU试验1 PASS、源码和四份正式报告
未改。先填满8槽并保持反压，允许无分支块退休后继续回卷，最后
再次填满。618帧完成3461次指针比较，69次分配、69次真实S2重写、
69份S3元数据、61次软件客户端退休；全部8个槽位和两个flag均被
S3元数据检查覆盖。这里的退休是无分支FTQ客户端策略，不是已经
实现完整ROB/resolve/train cache/RAS commit队列。

离线审计v1实际失败，日志保留：将S2修正后的最终prediction当成
S3 perf.s1Prediction的期望。RTL保存的是最初S1预测，S2重写不应
覆盖其来源。v2按sequence/generation保存最初接受的S1信息，新增
对应契约；20项契约实际通过。完整618帧从复位重放通过，额外1618次
输入/状态/metadata比较，并独立重构16个slot×flag交叉bin；16种
真实观察字段错误均抛出带采样点/状态的ScoreboardMismatch。
摘要：`results/coverage-bpu-ftq-native-branch-free-pilot-v2-readonly.json`。
该16-bin组覆盖100%仅说明指针组合，不代表完整FTQ覆盖100%。

独立转换此试验的原生raw，DA全集46541与历史相同，单例命中21394，
触及历史未命中行数为0。没有混入旧VPI raw，也没有把该试验写入
正式manifest或计算正式增益；测量见
`results/coverage-bpu-ftq-native-line-pilot-v1-readonly.json`。
本轮是输入合法性/关联能力进展，不是行覆盖率提升。后续需补
redirect提前读、resolve/train缓存、分支退休及RAS commit，才能
用于全部bank/set等场景的完整FTQ准入；同时继续针对已知漏行与
table0 bank2/3 high-useful hold缺口推进。检查点更新为v62。

## 2026-10-09：原生 useful 强化刺激的失败诊断与 base-alias 新路径

没有将基础设施迁移、纯模型通过或失败 raw 计为行覆盖率增益。
正式 memory-direct 全量 owner 仍为 2237467/2248059，日志已推进到70%；
metrics owner 2272492 与动态重放 owner 2283986 仍等待同一全量运行。
生产源码、十个 DUT 与正式报告继续冻结，以下工作仅在新隔离目录进行。

`native_useful_hold_v1` 与 `native_useful_hold_v2` 均为82项模型通过、
两个真实 DUT 普通 FAIL；并未新增 XFAIL 或宣称新 RTL 缺陷。
缺失条件是 table0 bank2/3 saturated-high-hold，连续状态观察器在
场景最终“必须触发该操作”的断言前没有报告不匹配。两个版本的
退出码均为1，源码与四份正式报告保持不变，全部日志、轨迹及 raw 保留。
v2审计队列正确拒绝失败数据，实际终态1；未启动正向重放或 raw 合并。
相应两个离线审计版本各102项契约通过，但这不是 DUT 正向审计通过。

需要纠正最初“一次强化只让 base 从0到1”的解释：真实记录表明，
redirect后首笔虽然在S3呈现条件分支taken，但ABTB metadata.valid为0。
v2 bank2三轮中的12次正向fastTrain均被ABTB资格拒绝，原base counter
始终为0；重复首笔无法强化它。失败诊断同时使用已寄存T1 index
提取useful操作，不能误用当前T0 read index。分析记录见
`results/coverage-bpu-native-useful-reinforcement-failure-diagnosis-v1-readonly.json`。

纯模型重新搜索既有八个common分支的子路径。只需把第二个common
分支临时retarget到最后节点，就能在正常路径模型中保留ABTB base
index（bank2为4、bank3为6），同时改变两张MicroTAGE表的index：
bank2从306/498变为258/259，bank3从307/499变为259/451。
没有增加MainBTB同时驻留项，也没有构造metadata或写内部状态。
全部4096个低12位前缀、非零高位与完整52位PHR/指针回卷检查通过，
10项模型测试实际通过；这仍不是override replay后的硬件别名证明。
模型v1曾在pytest通过后因父进程后处理导入失败而退出1，该失败保留；
修复仅在新v2完成，详见
`results/coverage-bpu-native-base-alias-logical-plan-v2-readonly.json`。

新`native_useful_hold_v3`复用该路径，92项模型测试实际通过。
真实bank2/3测试已启动（PID2325375，session66121），先断言实际
同ABTB base/不同MicroTAGE key、至少四次有效正向来源、base恢复正向，
并确认目标useful未受短回路更新，才检查负向目标窗口的高保持。
仍须等待实际结果和完整离线重放，再单独测量原生漏行；当前增益未宣称。
完整FTQ、全部bank/set/four-way、深SC-used与dirty-full-overwrite等原范围
继续保留，目标未完成。检查点更新为v63。

交接前v3 bank2实际call PASS，完整trace为passed=true且无failure：
10298帧、目标T1 index306/tag130/position8的五次useful 3→3高保持，
采样preedge tick6313/8131/8153/9971/9993，下一rising值均为3。
三个base-alias窗口实际合格来源29/30/30笔，六次真实retarget读回通过，
原目标高层分配为零。bank3仍在同一进程运行；尚无全进程退出0凭据，
也未做v3完整独立重放和原生漏行测量，不能据此更新正式56-bin矩阵
或宣称正式行增益。失败v1/v2仍全部隔离保留。

## 2026-10-09：双 bank useful 完整审计通过，原生漏行实测新增20条

补正前节的中间状态：`native_useful_hold_v3`的bank2/3两个真实DUT
用例均通过，父子进程实际退出0，源码与四份正式报告保持不变。
每例10298帧、六次实际retarget读回，三个base-alias窗口分别有
29/30/30笔合格来源；目标useful在窗口中保持2/3/3，没有更新原目标
高层provider。两个目标分别是index306/tag130/position8和
index307/tag130/position7，每个目标确认五次已提交T1 useful 3→3。

离线审计也暴露了两处审计器问题，而非DUT失败。v3的132项契约
通过后，完整重放因误用`start_pc`而退出1；实际BpuBatchTraining
序列化字段是`pc`。v4新增真实事务序列化契约后158项通过，但实际
metadata-set故障没有触发异常：逐帧检查读了变异值，后置因果检查
仍读原值。两份失败日志、回执和签名源码均保留，未准入raw。

仅在新v5修复：故障形成只读overlay，逐帧重放和所有后置检查共用
同一观测视图；未捕获故障的兜底失败放到整条检查链末尾，没有删除
故障或降低准入条件。169项契约实际通过。两个完整轨迹合计20596帧
从reset重放通过，包括PHR、公共输入/metadata关联、ABTB counter/PLRU、
hash/index/policy、shadow/SRAM写谱系及独立功能覆盖数据库检查。
42个真实观测故障全部抛出带tick、差异和状态的ScoreboardMismatch，
完整审计父子进程实际退出0。结果见
`results/coverage-bpu-native-lower-useful-high-hold-audit-v5-readonly.json`。

`native_useful_hold_coverage_v3`只合并上述两份成功且已审计的
memory-direct raw，测量进程实际退出0。原生DA全集仍为46541行，
该两例独立命中26114行；这是子集运行，不能与全量比例直接比较。
它触及历史32264行基线中的131条漏行，其中20条连之前的隔离
common-chain合并命中集合也未覆盖：BypassShadowBuffer18条、
AheadBtb1条、AheadBtbReplacer1条。

目标饱和保持赋值确实包括`rtl/bpu/BypassShadowBuffer.sv:6485`和
`:7509`，分别对应bank2/index306和bank3/index307。其余新增行包含
短回路其他useful单元的分配/算术路径、AheadBtb的bank0/set34/way1
初始化到2（:5774）和set34替换状态更新（AheadBtbReplacer.sv:474）。
不能把整批20条全部归因于高保持本身。完整行位置和Scala来源见
`results/coverage-bpu-native-lower-useful-high-hold-line-pilot-v3-readonly.json`。
没有混入旧VPI raw、缩减分母或写入正式manifest；尚非正式全量增益。

同时复用不变的`abtb_direct_pair_pilot_v5`，新批次
`dut-pilot-cross-bank-v2`的bank0/set0、bank2/set31、bank3/set63
三个五别名/四路替换用例全部PASS，实际退出0。原来已独立审计的
bank1/set0没有重复运行或计入这三例。新`native_five_alias_audit_v3`
的116项契约实际通过，完整三组/258故障审计已启动；检查点写入时
bank0/set0已完成完整重放及86故障，正在bank2/set31，不能准入部分。
其测量器`native_five_alias_coverage_v1/run.py`已准备，但必须等整批
审计实际退出0才允许执行；当前未合并这三份raw。

原全量owner2237467/2248059实时确认存活，日志推进至71%；
metrics2272492和dynamic2283986仍等待同一原运行。生产源码、DUT、
正常raw/trace/功能覆盖输入继续冻结。旧v7 useful矩阵54/56仍是
历史报告，新两个bin仅有本次独立原生见证，未宣称当前全量56/56。
全部bank/set/four-way、合法完整FTQ、深SC-used、dirty-full-overwrite、
真实overlap及其他模块原范围继续保留，目标未完成。检查点为v64。

## 2026-10-09：三组跨 bank/set 审计及原生漏行测量完成，补齐 FTQ 消费者模型

补正前节的运行中状态：`native_five_alias_audit_v3`已完成全部三组，
父子进程实际退出0，116项契约通过，16656帧从reset完整重放通过，
258个真实观测故障全部检出。每组均检查parent/PHR/hash/index/policy、
独立ABTB写谱系、完整shadow/T2/SRAM端口及功能覆盖数据库。
源码、原始输入和四份正式报告保持不变。新三组为bank0/set0、
bank2/set31、bank3/set63；旧bank1/set0没有重复计入。
结果为`results/coverage-bpu-native-five-alias-cross-bank-audit-v3-readonly.json`。

随后`native_five_alias_coverage_v1`仅合并这三份已审计native raw，
实际退出0。DA行点全集仍为46541，三例独立命中25645行点；
它触及历史基线的120个漏行点，这120个也均未被之前的隔离
common-chain命中集合覆盖。按文件分别是AheadBtb41、
AheadBtbReplacer49、ReplacerState19、ReplacerState_4 11。
独立子集命中比例不能代替全量结果；旧VPI raw没有被合并。
结果为`results/coverage-bpu-native-five-alias-cross-bank-line-pilot-v1-readonly.json`。

新归因报告进一步区分了行点与功能点：41个AheadBtb行点中，
32个是新条目counter初始化到2的赋值，9个是counter递增赋值。
其中包含setup路径的bank0/set12/13/14/15/28/60，不能全部归因于
三个目标set。49个AheadBtbReplacer行点属于
`EnableCommitGHistDiff`下的PLRU一致性对照逻辑，分为8个训练touch
赋值和41个预测touch语句/条件；不应视为49项新增独立需求。
实际ReplacerState新行点为8个predict-write条件、19个predict-write
赋值和3个train-write赋值。这里统计的是生成SV中的SF+DA行键，
不是去重后的Chisel源码行数或功能点通过数。

与前批useful测量的20个额外行键去重后没有交集，合计140个新增
隔离行键；两批合计触及251个历史漏行点。没有把数学集合对比
宣称为当前native全量增益，也没有写正式manifest。新汇总器的
v1/v2/v3分别因合并冻结标志、故障列表与计数、来源纪元结构的
schema差异失败，全部源码/失败回执保留，没有产生汇总报告。
仅v4分别严格使用原有门禁后实际退出0，见
`results/coverage-bpu-native-isolated-line-progress-v4-readonly.json`。
原DUT、独立审计和两批测量均不受这些摘要辅助脚本失败影响。

FTQ方面，新增隔离`ftq_lifecycle_v2`先实际通过94项纯模型契约，
签名覆盖1204份文件；两个pytest参数化迭代器弃用警告保留在日志中。
它区分物理metadata的存续、live FTQ条目、已复制的train cache和
commit FIFO出队时的晚读；实现提前一周期redirect快照、严格的
first-mispredict mask（含同位置重复）、正确的Direct/Pop过滤及IFU
不滤、resolve合并/头阻塞/旧占用full/drop/三周期冲刷/槽位复用、
train同周期出入/stall回卷/current+previous redirect和commit顺序。
独立签名v2保留；新v3改用tuple参数化并增加三个组合时序反例，
实际97项通过且无警告，源码与正式报告不变。结果见
`results/coverage-bpu-ftq-consumer-lifecycle-v3-readonly.json`。

组合检查还指出一个不能忽略的边界：ResolveQueue冲刷检查旧mem，
新到达条目可能在下一周期冲刷生效前出队，而train cache只持有
当前和前一周期backend redirect。在always-ready、空闲队列的
源码推导模型中，redirect同周期到达的年轻resolve在下一周期被杀；
晚一周期到达则于第2周期加载、第3周期train，晚两周期则于第3周期
加载、第4周期train。三种实际模型timeline已记录在
`results/coverage-bpu-ftq-redirect-window-review-v1-readonly.json`。
这只是SOURCE_DERIVED_MODEL_COUNTEREXAMPLE_ONLY，不是实际FTQ RTL
缺陷证明：当前导出的BPU DUT不实例化FTQ，后端是否允许该时序
还需核实。没有新增RTL缺陷/XFAIL。后续driver必须单独跟踪取消的
allocation generation，不能仅凭队列/cache valid准入错误路径训练。

这仍未完成完整FTQ：尚需公开commitMeta监测、真实DUT驱动整合、
显式分支退休策略、reset/refill/wrap/stall/redirect/消费者寿命场景，
以及完整独立实际轨迹与故障审计。四个代表五别名组也不等于全部
256个bank/set组，更不能证明负向counter/低饱和转换已闭合。

交接前原owner2237467/pytest2248059实时存活，CPU约99.6%，
实际pytest运行约212分钟，日志为71%后43个点；metrics2272492与
dynamic2283986仍在等待同一原运行。没有重复启动或修改生产源码、
十套DUT、正常raw/trace/功能覆盖输入。正式报告仍为历史VPI纪元，
当前memory-direct全量、metrics与dynamic实际完成前不能标记current。
全部bank/set/four-way、完整FTQ、深SC-used、dirty-full-overwrite、
真实overlap、RAS及其他模块范围保留，目标未完成。最终检查点v66。

## 2026-10-09：FTQ 分支客户端实际 DUT、全轨迹审计与漏行复核

本轮在全量回归仍运行的条件下，只增加隔离版本；生产源码、十套 DUT、
系统运行库、正常 raw/trace/FC 输入和四份正式报告均未改动。

`ftq_branch_client_v2` 实际通过 179 项模型契约和 1 个 DUT pilot，
前后校验 1218 个源文件。客户端绑定公开 commitMeta 和完整 perfMeta，
区分物理 metadata、live allocation generation、resolve buffer、train
cache 和 commit FIFO 生命周期。测试只提交 resolve/redirect 意图、等待
transfer 和周期，不操作边沿、引脚或 asyncio.gather；驱动内部保留
AsRiseWrite，通过 @on 被动 monitor 采样并把比较异常交给 pytest。

实际 1444 帧包含 72 次分配、72 次 rewrite、72 次 S3 metadata、43 次
退休、2 次 backend redirect、4 次训练和 2 次 RAS commit。首对 backend/
IFU resolve 同拍接受，训练连续两拍完成；观察到 4 拍预测/训练重叠和
2 拍预测/commit 重叠。验证了全部八个槽值、两个 flag、回卷后的新代次、
redirect 取消、reset/refill，以及消费者不得重新使用取消代次。

第一次 commit 来自真实冷 S3 source 经 redirect 修复的 call，第二次
来自 MBTB 学会后真正预测出的 S3 call；全八个 committed RAS cell 和
head 均逐周期比较。第二次相同返回地址把 cell1 counter 从 0 更新为 1，
head 保持 1，返回地址为半字地址 1073815572。该证据不代表所有 RAS
speculative/recovery 路径已经关闭。

首版 DUT 因新驱动提前提交输入、旧检查器在 rising 使用另一种提交时序，
发生 registered-commit-valid 比较失败及 teardown ERROR；失败源码、
日志、JSON 和 raw 保留。新 v2 将检查器适配为 preedge 连续观察后通过，
没有修改 RTL 或增加 XFAIL。首版审计虽然拒绝全部 46 个故障，仍因六个
旧 RAS 异常缺少 observed_event 而得到 50 PASS/6 FAIL；新审计 v2 保留
实际差异和统计，补齐采样事件后 56 项契约全部通过。

最终只读审计 `ftq_branch_audit_v2` 独立于 FtqClient/driver，重建指针、
真实 S3 metadata、resolve/train cache、晚读 commit FIFO 和 committed
RAS。完整 1444 帧和 46 个实际观测故障均通过资格门槛，parent/child
实际退出 0。输入故障同时污染 intent 和跨接受沿输入，避免仅靠
intended-versus-observed 比较取得虚假的 provenance 检查能力。
证据：[分支生命周期审计](../results/coverage-bpu-ftq-native-branch-lifecycle-audit-v2-readonly.json)。

只测量该 pilot 的一个已审计 native raw，DA 宇宙仍为 46541，隔离命中
22123；这是单场景覆盖，不是全量覆盖退化。命中 4 个历史漏行：
RasStack 的 325/330/748 和 ReplacerState_4 的 340。前三行此前隔离
common-chain 已命中，与已有三组隔离 keyset 去重后只有一条新键。
340 行是 MainBtbReplacer 的 port1/set43 训练状态写入，对应
MainBtbReplacer.scala 的 trainWrite；不是 ABTB 调试 PLRU，也不凭行命中
推断完整 MBTB victim/state 正确性。

重新审阅 RasStack.scala:203..210 后明确：330 行 fallback0 同时可由
返回地址不同或计数饱和触发。本次冷 call 即可走地址不同分支，因此
不能把这次命中记成“redirect 计数饱和功能已验证”；该边界仍需专门场景。
证据：[原生漏行测量](../results/coverage-bpu-ftq-native-branch-lifecycle-line-pilot-v1-readonly.json)。

从完整已审计轨迹导出独立 xreactor FC：27/32 个 bin 命中，框架按组
等权汇总为 75%，不是 27/32 的二项比例，也不是 pytest 功能点通过率。
保留五个可达未命中 bin：backend.filtered、return、indirect、
train_redirect 和 training_backpressure。没有设置不可达的 IFU-filtered
bin，也没有合并进正式 FC 或改变 286 功能点的既有口径。

去重复核 v5 实际退出 0：useful20 + five-alias120 + 本轮1，共 141 个
相对旧 isolated common-chain 的额外 SF+DA 键；三组扩展共触及 255 个
历史漏行。这里仍是生成 SV 的文件+DA 行键，不是唯一 Chisel 行数或
新增功能点数，绝不混合旧 VPI raw，不宣称 current native-full 增益。
证据：[去重及源码因果复核](../results/coverage-bpu-native-isolated-line-progress-v5-readonly.json)。

交接时原 full owner2237467/run_all2248058/pytest2248059 仍存活，实际
pytest 约 4 小时 24 分、CPU99.6%，日志 72% 后 20 个点；metrics2272492
与 dynamic2283986 仍等待同一原运行。完成 exact full0/metrics0/dynamic0
之前，正式报告不能标记 current。

当前 BPU DUT 不实例化 FTQ RTL；有界分支客户端通过不等于完整 FTQ
合法性已证明，late wrong-path resolve 的后端时序仍待核实。下一步应在
新隔离版本补 return/indirect/backend filter/IFU redirect/真实训练背压
与 train-redirect 冲突，并推进全部 bank/set/four-way、负向/低饱和、
deep SC-used、full dirty overwrite、真实 overlap、RAS 及其他模块原范围。
目标保持 active，最新检查点 v67。

## 2026-10-09：完整 RAS 物理检查、return 恢复与全部 bank/set 扩展

本轮完成上一轮已运行的 `ftq_branch_client_v3` 资格链：248 项模型契约、
1 个实际 DUT pilot 均退出 0，前后 1222 个签名源文件未变。新增物理参考
模型从真实 reset 建立全部八个 committed cell、十六个 speculative cell、
全部 NOS、指针、write bypass 和延迟写寄存器，不使用 DUT 状态初始化
expected。未初始化 Reg 的 payload 仅在首次源使能后纳入比较，此后即使
valid 为零也检查 retained 状态。独立 committed architectural oracle
仍保留，不用物理模型替代架构检查。

1686 帧包含 110 次分配/rewrite/metadata（最终 reset 前 102 次、之后 8 次）、
54 次退休、7 个真实训练拍、6 次 redirect、2 call + 2 return commit。
两次 return 分别验证 counter 从 1 到 0、head 从 1 到 0，旧 cell 的返回
地址与零 counter 保留。两次 backend Pop resolve 均被正确过滤；实际观察
到 6 拍 predict/train、4 拍 predict/commit、1 拍 train/redirect 重叠，另有
backend indirect 和 IFU direct-jump 恢复。测试仍只使用高级意图和周期。

`ftq_branch_audit_v3` 的 200 项契约全部通过，完整 1686 帧独立重放和
190 个真实观察故障拒绝的最终审计实际退出 0。故障包括 103 个完整 RAS
物理状态叶子，以及 87 个输入、metadata、RAS commit 和流水指针边界；
异常保留采样事件、实际差异和失败状态。全部 5057 次物理比较通过。
审计只用普通只读进程重放，不创建 DUT、不生成 raw、不修改原轨迹。
证据：[完整物理状态及生命周期审计](../results/coverage-bpu-ftq-native-branch-lifecycle-audit-v3-readonly.json)。

仅测量这一个已审计 native raw，DA 宇宙仍为 46541，单场景命中 22414，
命中 13 个历史漏行：RasStack.sv 的 325/330/580/748/749/752/755/756/
827/831/832，以及 ReplacerState_4.sv 的 258/340。其中 580 对应实际
committed counter 递减，258 是 MBTB set2 的训练写入。与之前四个已审计
isolated keyset 去重后，本轮新增 DA 键为 **0**，不能报告为新的行覆盖增益。
证据：[原生 return/recovery 行测量](../results/coverage-bpu-ftq-native-branch-lifecycle-line-pilot-v2-readonly.json)。

重新直接读取 LCOV、复核 raw/审计身份的 `native_line_progress_v6` 实际
退出 0：相对旧 common-chain 的累计额外 SF+DA 键仍为 141；四组扩展触及
的历史漏行集合从 255 增至 263，新增触及的八行是 RasStack.sv 的
580/749/752/755/756/827/831/832，它们此前 common-chain 已命中。
因此“扩展场景触及历史漏行”与“相对已有原生场景新增行键”是不同口径。
生成代码多行表达式的 DA 命中也不证明其中每条 Mux 路径都执行过。
证据：[独立 LCOV 去重及因果限制复核](../results/coverage-bpu-native-isolated-line-progress-v6-readonly.json)。

独立 xreactor FC 为 38/43 bin，九组等权汇总 87.037037%，不是功能点
通过率。保留 training.backpressured、committed.saturated 及三个 inflight
return counter 上下文缺口。NOS 是否在 inflight 范围只表示存储上下文；
计数非零时直接递减，只有零 counter 分支才从下一项恢复计数。实际见证
仍是 redirect-call saturation=0、nonpush BOS advance=0，不能因 330 行
命中就关闭同地址饱和场景，也不能用纯模型的 BOS 测试充当 DUT 证据。

为推进全部 bank/set/four-way 范围，新增隔离调度
`/tmp/bpu-integrated-common-chain-HmuJ2C/native_five_alias_matrix_v1`。
复用已通过 382 模型契约的 immutable five-alias 驱动和检查器，排除已
审计的 (0,0)/(1,0)/(2,31)/(3,63)，把剩余 252 组分为 63 批，每批 4 组，
最多 16 个普通 DUT 测试进程并发。12 项分组契约实际通过；日志另保留
`-c /dev/null` 导致 pytest cache 路径权限 warning，不涉及 DUT 或 SKIP，
没有修改已签名版本掩盖 warning。调度者 PID 2403385、session 49092，
首批 16 个 pytest 子进程 2403402..2403417 已实际存活并占用 CPU。

矩阵只写隔离 trace/raw/结果，不重跑已有四组，不修改生产源码/DUT/
系统运行库/正常输入。任一批失败、正式报告纪元变化或磁盘空闲低于
80 GiB 时停止派发新批，已启动任务继续保留完整证据，不自动重试或
新增 XFAIL。当前尚无完成批次，不宣称 256 组通过；后续仍需逐轨迹独立
审计、实际故障拒绝和原生行测量，DUT 通过本身不等于已获覆盖率资格。

原 full owner2237467/run_all2248058/pytest2248059 仍活跃，最新核实时
pytest 约 5 小时 1 分、CPU99.6%、日志 72% 后 53 个点；metrics2272492
和 dynamic2283986 继续等待同一原运行，未重复启动。正式报告仍需 exact
full0/metrics0/dynamic0 后才能标记 current。实际 FTQ RTL/后端合法时序、
全部 bank/set/four-way、负向/低饱和、deep SC-used、完整 dirty overwrite、
真实 overlap、RAS 以及其他模块原范围均保留。目标 active，检查点 v68。

## 2026-10-09：pytest 真正多进程试跑、矩阵失败与读回关联定位

根据用户建议，增加一个统一 `pytest -n 4` 会话的隔离验证，而非多个独立
pytest 的外部调度。`pytest-xdist 3.8.0`、`execnet 2.1.2` 仅安装在
`/tmp/bpu-pytest-parallel-jUpVZd/deps`，没有更改系统运行库或正式源码纪元。

十个模块的现有 native DUT 测试共 17 项，四进程和串行各 17 PASS。
每个 worker/test 独立 DUT 与产物目录，controller 只汇总本次生命周期报告
和完整文件身份；17 份 RTL raw 与串行逐字节相同。10 份 FC 保留全部语义
字段，仅允许隐式 origin UUID 双射重命名及派生 snapshot 哈希重算；原始
snapshot 哈希均先校验。独立契约 34 PASS，包含 worker 崩溃、不一致收集、
setup/teardown 错误、strict XPASS、collect-only 不覆盖及损坏哈希拒绝。
最初一项 crash 分类契约失败和两个 FC 等价审计失败都保留在隔离目录。

串行 25.28 秒、四进程 12.29 秒，约 2.06 倍，只代表本机这次小试验。
明确 manifest 中的 17 raw、10 FC 已完成十个 DUT 的 native LCOV 合并和
xreactor HTML 渲染，复核实际退出 0。功能点为 7 PASS / 279 NOT_RUN，
不把十份 FC 当成全部功能点通过，更不宣称新的正式行覆盖率增益。
生产迁移仍需要统一输出 fixture、controller-only evidence、`run_all.py`
参数透传及当次 FC 输入，并在当前 full/metrics/dynamic 纪元结束后执行
完整串并行资格验证。详见 [迁移记录](pytest-parallel-migration-20261009.md)
和 [只读试验摘要](../results/coverage-bpu-native-pytest-parallel-pilot-v1-readonly.json)。

此前全部 bank/set five-alias 矩阵现已终止退出 1，不再是上一节的运行中状态。
首 16 批 64 项实际为 53 PASS、11 FAIL，全部失败在 bank0 的
set1/2/3/4/6/7/9/11/12/14/16。五个整批通过的 cohort 共 20 项可进入
独立审计；11 个失败 cohort 的全部 raw 均排除，不把其中成员的 PASS
单独计为有资格的覆盖率。47 批 188 项尚未派发，未自动重试或增加 XFAIL。

新增 completed-cohort 门控契约 34 PASS。只读审计队列复用已签名的完整
reset 重放和真实观察故障检查，20 项各自审计退出 0，总计拒绝 1720 个
实际故障。队列整体退出 1 是全 252 项范围未完成，不是 20 项案例审计失败。
与此前四个 qualified group 合计仅 24/256，仍需后续 native 测量，不能
认领全部 bank/set/four-way 或新的覆盖率增益。

对保留的 bank0/set1 原失败 trace 做只读关联诊断：窗口 tick2118..2794
中，同记录 read_input/set 与 registered SRAM output 的筛选匹配为 0；
preedge 请求与下一 rising 响应关联后，99 个响应样本含 132 个匹配 way
payload。首个请求/响应为 2279/2280，完整 tag/target/attribute 正确。
这证明原生 trace 中存在期望内容，并定位了同步读回的请求/响应错配。
诊断窗口含最后 drain，不能直接替代原场景的精确 alias-window 资格检查，
该失败仍然保留。应在新版本修正关联、补边界契约后重新覆盖失败组；不能
修改 signed v5 或将失败改为 XFAIL。见
[只读关联诊断](../results/coverage-bpu-native-bank0-readback-association-diagnostic-v1-readonly.json)。

最后核实时，原 pytest2248059 仍运行约 5 小时 40 分、CPU99.6%、日志约
95%；原 metrics2272492 与 dynamic2283986 仍等待同一运行，未重启。
完整 FTQ RTL/后端合法时序、RAS 饱和/BOS/inflight、训练背压、全部 bank/set、
负向/低饱和、deep SC-used、完整 dirty overwrite、真实 overlap 及其他
模块原范围继续保留。正式 current=false，目标 active，检查点 v69。

## 2026-10-09：修正同步读回关联，11 组原失败重验及原生行增量

新隔离 `abtb_direct_pair_pilot_v6` 保留既有 five-alias 驱动、模型和 525
端口 reset 重放，仅把 SRAM 观察改为 preedge 请求关联下一 rising 响应，
且要求两条记录都处于同一个精确 alias 窗口内。测试用例不增加时钟边沿
或底层引脚操作。382 项原模型契约加 38 项关联边界契约，实际 420 PASS。
真正的 pytest-xdist 四 worker、七 worker 两批分别 4 PASS、7 PASS，
原失败 bank0/set1/2/3/4/6/7/9/11/12/14/16 全部通过；两批 pytest 均约
220 秒，源码纪元及四个正式报告未改变。原 v5 失败记录保留，不转 XFAIL。

首次独立审计 v4/v5 在最终 JSON 编码遇到 xreactor MISSING 哨兵而退出 1；
它们的部分 proof 无资格使用，源码、日志和失败产物均保留。新审计 v6/v7
明确区分缺失值与显式 None，并在创建文件前完成编码，各 166 契约 PASS。
11 项完整 reset 独立重放及逐端口检查实际全部退出 0，共拒绝 946 个真实
raw 观察故障，以及 99 个请求/响应 tick、bank/set/way/tag、缺失和重复
关联见证故障。异常仍保留差异、状态和采样上下文，不吞错或新增 XFAIL。
证据：[四组审计](../results/coverage-bpu-native-bank0-corrected-readback-audit-v6-readonly.json)、
[七组审计](../results/coverage-bpu-native-bank0-corrected-readback-audit-v7-readonly.json)。

此前已审计四组加 20 组矩阵案例，又完成只读关联补充审计 v2：38 契约、
24 项原完整 reset 审计的 132878 帧、120 个精确 alias 窗口均通过。
不复用旧同记录读回见证，不创建 DUT/raw。v1 因 JSON list 与模型 tuple
直接比较而失败的版本保留；v2 使用原有 canonical() 后验证全部计划字段。
证据：[24 组关联补充审计](../results/coverage-bpu-native-five-alias-24group-readback-association-audit-v2-readonly.json)。

只合并 20 项原整批通过、完整审计及正确关联均有资格的 native raw，
Verilator 原生 DA 宇宙仍为 46541，独立候选命中 26100。相对 common-chain
加此前四个扩展场景，新增 **390 个 SV SF+DA 行键**，累计额外键从 141
增为 **531**；扩展触及历史漏行集合从 263 增为 659。独立 AWK 读取全部
七份 LCOV 重算，实际退出 0 且逐项一致。没有合并历史 VPI raw。
证据：[原生测量](../results/coverage-bpu-native-five-alias-twenty-matrix-line-pilot-v1-readonly.json)、
[独立行键复核](../results/coverage-bpu-native-five-alias-twenty-matrix-line-review-v1-readonly.json)。

390 行中，AheadBtb.sv 为 190 行 counter 赋值，其中 110 行初始化到 2、
80 行其他更新；ReplacerState.sv 为 19 行状态赋值和 8 行写入条件；
AheadBtbReplacer.sv 的 173 行来自 EnableCommitGHistDiff 启用的 PLRU
调试一致性状态。已直接复核 Chisel AheadBtbReplacer.scala 与 RocketChip
Replacement.scala 的 state_vec 路径，不能将这些行键当作 390 个新功能点，
也不能把整个 setup/五 alias 场景的增量全部归因到单一 allocation 动作。

当前 qualified 为 **35/256**：原四组、20 组整批通过案例、新修正 11 组。
尚余 221 组，其中 188 组未派发、33 组属于原失败 cohort 的 PASS 成员而
仍排除；不能直接相加旧 53 PASS 与新 11 PASS。新 11 组尚未单独测量
native 行键增量。原 pytest2248059 仍活跃，日志 99%，原 metrics2272492
及 dynamic2283986 继续等待同一运行。没有重复启动、生产迁移或 formal
current 声明。全部原集成范围仍保留，目标 active，检查点 v70。

## 2026-10-09：原生全量与指标审计完成，新增 64 行键，剩余矩阵推进

原 sole full 实际于 13:20:59 UTC 退出 0，源码纪元不变；8190 PASS、
7 strict XFAIL、0 SKIP，286/286 功能点执行、279 PASS。十模块使用
memory-direct/FST 编译特性，VPI OFF，没有合并旧 VPI raw。BPU 正式行数
为 32264/46541；十个模块相对封存旧 LCOV 的源行宇宙和命中集合均相同。
这次换观察后端不是新的功能行增益。全量 session94331 已正常关闭。

独立指标审计原 owner2272492 于 13:28:08 UTC 实际通过并退出 0，
705 份 fresh raw 已封存，十个模块重新 native merge 与正式 LCOV 字节相同，
JSON/HTML 一致；12 份基础设施 raw 没有独占新增命中行。204 份 fresh FC
对应 197 个组，报告组等权平均 99.205805%，189 组完全覆盖、8 组未闭合。
正常 collect-only 8197 项与预收集完全相同，正式四报告及十 LCOV 不变。
证据：[原生指标审计](../results/coverage-memory-direct-normal-metrics-audit-v1-readonly.json)。
session7825 已正常关闭，不再等待 full。原 dynamic owner2283986 的实际
子进程2523263 已进入 200 SC history、96 SC masked、144 ABTB、17 integrated
完整轨迹及 882 故障重放，仍未完成；在其实际终态前继续冻结生产源码。

11 组修正 bank0 的首次行测量 v1 子进程虽退出 0，父门控却因 full 正好
刷新正式报告而退出 1；其 helper、日志和 diagnostic 摘要均保留并明确
不准入。新 v2 在刷新后的稳定报告纪元重测同一 11 组审计合格 raw，
不重跑 DUT。27 个门控契约实际通过；因关闭功能点插件，日志另保留两条
xreactor_feature_plan/report 未注册配置 warning，没有 DUT/SKIP 影响。
v2 子进程和父门控均实际退出 0，正式报告不变，仅父通过后才发布摘要。

新增 64 个 SV SF+DA 行键：AheadBtb.sv 41 行 counter increment、
AheadBtbReplacer.sv 20 行 EnableCommitGHistDiff 调试 PLRU 一致性，
ReplacerState_4.sv 三行 MBTB set18/34/50 状态写入。相对 common-chain
加既有扩展的累计额外键从 531 增为 595，扩展触及历史漏行集合从 659
增为 724。独立 AWK 解析九份 LCOV 再计算，实际退出 0；它同时确认
当前正式 BPU 的 32264 行与历史基线命中集合相同，所有现有隔离 keyset
（含 common-chain）的并集相对正式基线可补 997 行。这是待准入的潜在
增量，不是已改写的正式覆盖率，也不是 997 个新功能点。见
[11 组测量](../results/coverage-bpu-native-five-alias-fixed-bank0-line-pilot-v2-readonly.json)、
[独立九份 LCOV 复核](../results/coverage-bpu-native-five-alias-fixed-bank0-line-review-v1-readonly.json)。

完整剩余 221 组采用修正 v6 检查器，隔离 matrix_v2 已通过 12 项契约。
依据原 24 组关联审计和新 11 组完整审计排除 35 个既有合格组，28 批每批
八案例（最后五案例不丢弃），同时两个真正 pytest-xdist 八 worker 会话，
最多 16 个 DUT worker。原失败 cohort 的 33 个 PASS 成员仍包含在新计划，
不混用旧 raw；188 组原未派发案例也全部保留。owner2523204、session51244
实际运行，首四批 32 PASS、0 FAIL，尚未增加独立审计 qualified 数。

新 remaining221_audit_v1 只读队列的 27 项完整 cohort 门控契约通过，
复用 signed v7 的完整 reset、parent/write lineage/525 端口/FC 算法及
86 个真实 raw 观察故障、9 个关联 claim 故障，未降低检查范围。
每个 DUT 完整通过的 cohort 才能派发最多八个普通只读审计进程，不创建
DUT 或 raw；整批审计通过后才具备覆盖率合并资格。owner2543026、
session62772 已实际启动并接收通过批次。后续仍须核对真实案例终态和
原 dynamic 审计终态，不能把队列启动或模型契约当成 256 组完成。

实际 FTQ RTL/后端合法时序、RAS saturation/BOS/inflight、低饱和／负向、
deep SC-used、完整 dirty overwrite、真实 overlap 及其他模块原范围均
保留。正式 current=false，目标 active；进展记录对应检查点 v71 及其
后续审计队列检查点。

13:40 UTC 后续核实：matrix_v2 首六批已实际 48 PASS、0 FAIL，cohort6/7
继续运行。只读队列 owner2543026 的八个实际子进程2543691..2543698
均持续占用 100% CPU；首个 5546 帧案例已进入 parent、write lineage、
direct 全端口重放，尚无新增完整案例终态，qualified 仍为 35/256。
原 dynamic 审计实际 SC history 进度为 57/200，未重启。磁盘仍约 140 GiB
空闲；首八案例产物约 1.7 GiB，新增 dynamic 归档约 14 GiB，剩余案例
产物估计约 37 GiB，继续保留 80 GiB 停止派发门控，不删除任何已有证据。
检查点 v72。

## 14:20 UTC：精确计数器缺口与正负方向场景

只读检查发现生产 `rtl_coverage.py` 的 `counter_gap` 和矩阵生成条件
仅包含独立 ABTB，没有集成 BPU；旧匹配还要求 `_needIncrease_T_`，
遗漏无数字后缀的第一个 cell。当前正式 BPU 的 AheadBtb 模块映射
15300 行、命中 10258 行，其全部 5042 个缺口均精确对应计数器块：

| 未命中语句角色 | 源码行键数 |
| --- | ---: |
| 递减选择 | 1014 |
| 递减非零判断 | 1014 |
| 递减赋值 | 1014 |
| 递增赋值 | 1010 |
| 弱正复位赋值 | 990 |

隔离 `native_abtb_counter_gap_inventory_v2` 从实际复位／递减／递增
赋值确定全部 1024 个物理 cell 的无重叠边界，12 项契约通过，验证
formal 行文本与源文件一致。独立 `native_abtb_counter_gap_review_v2`
使用 AWK 读取 RTL 的 5120 个语义行，再从原生 LCOV 计算同一 5042
缺口，八个实际错误／损坏反例均被拒绝；进程实际退出 0。首版失败
证据保留。正式分母、raw、四报告均未改变。详见
[复核摘要](../results/coverage-bpu-integrated-abtb-counter-gap-native-inventory-v2-readonly.json)。
低饱和保持没有独立递减赋值，必须检查真实状态及 accepted transaction，
不能通过 guard 行命中或模拟模型通过替代。

新负向输入使用同一块条件分支 position6 与较晚 fallback position7
跳向同一目标，目标处无条件分支返回原块。实际最终 taken 仍为 1，
但条件分支 position6 在最终 position7 之前，应触发 ABTB 递减。
两条路径完整 PHR 不同，而 normal ABTB 索引所需低四位保持一致；
没有伪造 metadata／内部写入／假设 UTAGE tag 相同。每个 bank/set
保留五个 alias、15 个真实分支程序和 MainBTB 两 way 容量约束。

规划 v1 在 bank0/set56 第五 alias 的正向路径发现完整 PHR 抵消为零，
失败原样保留，不能放宽非零条件。v2 实际 530 PASS／2 FAIL，失败是
回归测试过度指定必须使用 upper-region salt，实际另一合法低地址偏移
已满足所有不变量。v3 不指定具体修正地址，保留全部非零要求，并对
所有 256 坐标检查正→负→正及完整 PHR／索引流水线，实际 **532 PASS**。
这是纯模型资格，不是 DUT 功能 PASS 或覆盖率增益。

真实 `abtb_negative_pair_native_v1` 五个案例均普通 FAIL：在首个自然
窗口调用 compare 时，额外 phase 与 checker 拥有的异常上下文重名，
抛出 TypeError；之前的分支设置和完整 MainBTB residency 检查已通过。
原日志、轨迹和 raw 全保留并排除入账，不转 XFAIL 或宣称 RTL 缺陷。
新 v2 只修正该上下文字段，补充 AST 契约拒绝 case/phase 冲突及场景
中 FallingEdge/RisingEdge/ClockCycles/get_/set_。24 项契约实际通过。
owner2597386／pytest2597389／session40402 用五个 xdist worker 运行
(0,0)、(1,0)、(2,31)、(3,63)、(0,56)，全部从 reset 开始，每个 alias
要求八种计数器状态迁移、真实 S3 结果、实际条件项及 SRAM 读响应。
当前仍 live，未登记任何新 DUT PASS。即使通过仍须完整独立重放及
故障／关联声明审计；既有正向审计硬编码 position7／五个正向窗口，
不能直接当作新负向场景的证明。

原剩余 221 组 matrix_v2 已实际新增 **208 PASS、0 FAIL**，26 批结束，
最后 13 组仍运行；原只读审计队列有 40 份单例 audit.exit 成功收据、
0 失败，但整轮 owner 尚未退出，不宣称 all256 审计完成或新增正式行。
原 dynamic 日志已完成 200 SC history 与 96 SC masked，进入 integrated
完整 reset／全部 882 故障控制；原 owner2283986 和实际子进程2523263
仍 live，不重启。全部相关任务仍绑定原源码纪元，继续冻结生产代码、
正常 raw／trace／FC 和四正式报告。磁盘约 105 GiB，80 GiB 停止派发
门控不变，不删除既有证据。检查点 v73。

完整目标仍包括有效非零 CommonHR/GHR/BW、全 bank/set/fourway、
deep SC-used、full dirty overwrite、真实 overlap、完整 FTQ 以及七项
strict XFAIL／六个 RTL 问题；本节没有缩减范围或完成声明。

### 14:31 UTC 后续终态与观察容量修正

原 matrix_v2 实际于 14:22:17 UTC 退出 0，session51244 已关闭。
28 批全部完成、221 个新增 DUT 案例全部 PASS、0 FAIL，与此前 35 组
合计覆盖全部 256 个 bank/set 的正向 DUT 执行范围；源码纪元不变。
实际收据是 `native_five_alias_matrix_v2/run.exit.json`，不是
owner.exit.json，SHA256 为
`da8e6d1be91718c13e2df4c1f3fe04fa6c6757ae80118190d317ce64717516bd`。
独立剩余 221 组审计队列仍 live，当前 56 份单例成功收据、0 失败；
不把 all256 DUT 完成写成 all256 审计或正式覆盖率完成，不重跑矩阵。

负向 native_v2 于 14:23:34 UTC 实际退出 1，五个案例均在 direct
checker 的 20000 帧上限、第 20001 帧失败。bank0/set56 的完整失败
轨迹显示此前已完成四个 alias、14/15 个方向窗口，最后 alias 的
再递增窗口被容量限制中断。其首个负向窗口实际有 120 个输入资格
source、124 个正确 SRAM 响应，以及 dec3_2/dec2_1/dec1_0 各一次、
dec0_0 118 次；再递增窗口有 inc0_1/inc1_2/inc2_3 各一次和 inc3_3
128 次。没有计数器／端口数据比较错误的完成声明，也不能据此宣称
全场景 PASS。全部失败证据及 raw 保留并排除入账，见
[预算失败诊断](../results/coverage-bpu-native-negative-pair-budget-diagnostic-v2-readonly.json)。

新 native_v3 不缩短自然窗口、减少 alias 或删状态要求。新隔离
BudgetedDirectChecks 仅将原 20000 上限参数化，默认仍 20000，本场景
显式配置 32768；继承原 static monitor 生命周期。35 项契约实际通过，
包括原整个比较算法与签名原版除预算／诊断字段外逐字相同、无效预算
拒绝，以及到达预算边界仍抛出含事件、差异和状态的 ScoreboardMismatch。
owner2615065／pytest2615067／session19584，五个真实 native worker
2615068/71/74/77/80 已确认运行，尚无终态。所有 helper 新版本独立，
旧 signed direct.py、v1/v2 及生产代码均不修改。后续完整独立重放也
必须显式适配新预算、position6 和 15 个方向窗口，不能沿用旧正向
资格结论。可用空间约 99 GiB，80 GiB 门控和证据保留策略不变。
当前检查点 v74，完整目标仍 active。

### 15:15 UTC：负向完整审计通过、四 way 缺口与全量审计修正

native_negative_pair_native_v3 于 14:43:45 UTC 实际退出 0，五个 DUT
全部 PASS，完整原始 5 alias × 3 方向窗口、八种计数器迁移均保留。
独立负向审计的 247 项契约通过；五个只读 worker 从 reset 重放全部
状态／反馈／PLRU／完整 PHR／索引／525 个 direct 端口及 SRAM 写读
关联，父进程于 15:02:52 UTC 实际退出 0，拒绝 470 个原始观测故障、
675 个序列化读回声明错误。见
[完整审计](../results/coverage-bpu-native-negative-pair-full-audit-v1-readonly.json)。

按真实目标窗口和反馈 PC 统计物理 way 后，五坐标均只有 way2/3
包含全部八种迁移；way0 只有 inc2_3/inc3_3（bank3/set63 仅 inc2_3），
way1 没有迁移。因此不直接把此场景扩展成 all256 四 way 负向完成。
见 [逐 way 清单](../results/coverage-bpu-native-negative-pair-physical-way-gap-v1-readonly.json)。
新的 prefill_v3 使用真实预测／反馈预填充 1/2/3 个已有 alias，再完整
执行原五 alias／15 窗口；不写内部状态、不伪造 metadata。57 项契约
包含原比较算法逐字保持、完整轨迹 gzip 无损往返、损坏检测和严格占位
参数。owner2619624／pytest2619625／session7608 的三 DUT 已实际启动，
当前 live；仍需实际迁移证明，不能预先宣称 way0/1 已补齐。预填充 v1
门禁漏收轨迹测试、v2 文件复制多出末尾换行导致两项字节契约失败，
这些版本完整保留；v3 修正且通过，不覆盖已签名版本。

五份已完成负向完整审计的 raw 正在 native_negative_pair_coverage_v1
做隔离原生行测量，18 项准入反例契约通过。owner2624840／child2624859
／session14331 仍 live；此前 595 是相对 common-chain 的累计额外行，
997 是相对正式表的候选行键并集，不把两种基线混用，也不提前更新
正式 BPU 的 32264/46541。测量后仍须独立 AWK 全 DA 行键复核。

另有必须保留的全量失败：原 dynamic-v1 于 15:05:05 UTC 实际退出 1。
日志的 Fresh11/17 aging 是完成标记，真正错误在下一条 retirement-
nested-0；迁移器对全部 RAS 强求 program，而新旧 nested 都没有该
字段。nested 程序本来由固定源码意图独立重建；新 dynamic-v2 仅按
kind 区分该 schema，deep/repeat 仍必须逐项比较 program，并保留
nested 的真实 38 项故障检查。66 项契约实际通过，owner2624298／
session52195 已启动八个只读 spawn worker，全部 457 条轨迹重新重放、
882 个故障不减，不复用旧失败轮的未完成资格，不重复复制 665 份
原不可变快照。旧失败日志、回执及所有证据仍原样保留。

原剩余 221 正向审计 owner2543026 仍 live，当前 107 份单例成功回执、
0 失败，整队列未终态。所有依赖任务继续绑定原源码纪元；原 dynamic
停止不意味着可以解冻生产代码。四正式报告保持字节不变，完整 FTQ、
deep SC-used、full dirty overwrite、真实 overlap、全四 way 和七项
strict XFAIL 等完整目标均未缩减。当前检查点 v75，目标仍 active。

### 15:24 UTC：负向原生行增量已独立复核，预填充不足以闭合四 way

五份已完整审计的 negative native_v3 raw 原生合并实际退出 0；18 项
准入反例契约通过。仅这五份 raw 的 candidate 为 26439/46541，这不是
全量正式结果的替换值。相对此前全部隔离候选，新增 413 个 SF+DA 行键：
AheadBtb 71、AheadBtbReplacer 83、lower/upper BypassShadowBuffer 44/200、
ReplacerState 11、MainBTB ReplacerState_4 四行。增量来自完整五次运行，
包括 setup、方向准备和自然窗口，不能全部归因于五个目标坐标的负向计数。
独立 AWK 的八项小数据反例契约通过，再读取十份完整原生 LCOV，实际
退出 0，确认额外 413、相对 common-chain 累计 1008，以及相对当前正式
32264 行的候选并集潜在增量 1410（此前 997）；46541 分母完全不变。
见 [原生测量](../results/coverage-bpu-native-negative-pair-line-pilot-v1-readonly.json)
与 [独立行键复核](../results/coverage-bpu-native-negative-pair-line-review-v1-readonly.json)。
这些仍不是新增正式行或功能点 PASS，四正式报告字节保持不变。

prefill_v3 于 15:16:17 UTC 实际退出 0，三个真实 DUT 全部 PASS。
解压完整轨迹复查：预填充 1/3 alias 只把 inc2_3/inc3_3 换到 way1；
预填充 2 alias 换到 way0，全部双向八类迁移仍只有 way2/3。因此此
占位实验没有补齐四 way，不据此扩展 all256 或准入其三份 raw。
三份轨迹均 gzip CRC 通过，完整 JSON 共约 2.13 GiB 无损压缩为
79.2 MiB；原始字段、全部 rising/preedge 帧和 direct 数据均未删除。

新 commit_cadence_v1 只在每个原方向窗口内、首轮自然递归前，通过
现有 driver 暂停预测读 4/8/12 周期，让真实 pending 写尽早提交。
保留原五 alias、15 窗口、每窗 4×64 自然周期及全部比较，不引入
edge/get_set、内部写或假 metadata。57 项完整契约通过，owner2627790
／pytest2627792／session38593 的三个 native worker2627793/96/99
已确认 CPU100；能否补到 way0/1 仍待真实迁移结果，不能预先宣称完成。

对照现有 54 个集成功能点，还缺明确的 bank/set/physical-way 计数器
迁移矩阵要求。后续功能点设计需分开两条 RTL 递减路径：
`conditional-hit && final-not-taken`，以及
`conditional-hit && final-taken && entry.position < final.position`。
当前负向窗口使用同块 position6 条件项和 position7 fallback，主要
证明后者，不能替代前者；低饱和保持必须有真实 dec0_0 状态保持见证，
不能仅由 nonzero guard 行命中推出。正式计划仍冻结，当前 286 功能点
统计不变，不为尚未完成的目标预登记 PASS。

dynamic_v2 已实际完成 200 SC history、96 SC masked、144 ABTB、16 个
集成 reset 重放，共 456/457；866/882 个故障已被正确拒绝。六个 RAS
案例均完成，唯一剩余集成 aging-1 仍 live，整轮尚无终态。原 221
正向独立队列当前 119 个单例成功、0 失败，尚未整轮结束。可用约
95 GiB，80 GiB 停止派发门控不变。检查点 v76，完整目标仍 active。

### 15:30 UTC：正常全量原生指标与完整动态审计闭环

dynamic_v2 于 15:26:16 UTC 实际退出 0，session52195 已关闭；完整
457 条轨迹全部由本版本重新重放，882 个原始故障检查完成，逐案和
聚合 FC 一致。1189 份源码、115 个 helper、1378 个输入身份最终检查
全部通过，owner 退出收据 SHA256 为
`98323fc1edb32d7b6796470a9793fe8545ef03ed13b2b40bca62a715f69e6ac6`，
qualified 与根目录报告字节一致，SHA256 为
`2e1a1346595479e8e9c422568e394dfbf10462216d41a8a5b2d694cc80756283`。
见 [完整动态审计](../results/coverage-memory-direct-normal-dynamic-audit-v2-readonly.json)。
原 v1 失败日志、回执、快照和算法仍完整保留，没有覆盖或改判通过。

结合此前已经实际通过的 705 raw／204 FC／197 covergroup 原生重合并
与 HTML/JSON/LCOV 一致性，正常 memory-direct 全量 8190 PASS、7 strict
XFAIL、0 SKIP 的正式报告现标记 current。此标记仅对冻结正常源码／
8197 项测试／286 功能点计划成立，不把隔离候选 1410 个潜在行键、
all256 负向四 way、完整 FTQ 或 deep SC-used 等未完成要求算作已验证。
四正式报告未重写，BPU 行数仍为 32264/46541。

原 remaining221 独立队列当前 126 份单例成功、0 失败，owner2543026
仍 live；三个 commit_cadence native worker 也已再次确认 CPU100，
尚无 DUT 终态。继续冻结生产源码以保持这些任务的准入纪元，正常
全量和已通过负向五例不重复执行。检查点 v77，完整目标保持 active。
