# UT 语义参考模型验收

参考模型的目标是独立判断硬件功能是否正确，不是重复计算内部信号，也不是生成覆盖率。
2026-10-15 起，旧目录中的 `model` 名称本身不再作为“完整参考模型已完成”的证据。

历史生成页面和原生覆盖率文件按[保留策略](../results/RETENTION.md)清理；
下文保留当轮测量值与原因分析，删除生成件的失效链接。当前完整结果以开头
的最新完整证据为准，历史测量不替代当前回归。

最新置信度边界批次保留主TAGE模型，逐笔比较当前版本到界、保持和反向往返。
每笔使用不同真实预测，实际Main辅助更新全部ready接纳，原预测训练折叠
历史也必须保持。四个DUT程序闭合76项义务、19次SDK服务及48个消费者；
另两个taken长来源在历史重建处首先失败，不能把失效来源导致的row/tag变化
称为TAGE算术缺陷。稳定历史的完整往返不缩短学习链，也不删除原反例。

47项新纯检查全PASS，97项独立选测无DUT覆盖。一次全量20209项为20169 PASS／
37 FAIL／3 XFAIL，原20156判定保持。345点状态与原合同保持；459组／411满，
BPU增加1个Main替换副本行，其他九DUT命中集合不变且无旧命中损失。137个
TAGE集成缓冲缺口、完整FTQ资格和原七项失败仍未闭合。见
[六程序语义](tage-confidence-boundaries-20261017.md)及
[完整证据](../results/production-confidence-boundary-20261017-v1/README.md)。

此前相反方向学习批次保持主TAGE参考模型不变，通过正常训练保存正确
taken／not-taken来源，再验证迁移后从最新保留计数学习。50项纯检查全PASS，
6DUT为3 PASS／3普通FAIL；三个非饱和对照闭合45项义务、14次服务及36个
消费者。原A7/current0、B0/current6及A0/current1三个场景少提案，属于有界
UT合同与原快照资格过滤的差异；完整FTQ可达性仍未证明，不直接扩大为
架构错误。一次全量20156项为20118 PASS／35 FAIL／3 XFAIL，旧20100判定
保持，INT-086因新边界由PASS转FAIL。447组／403满，十DUT原生集合不变。
见[语义要求及来源资格](tage-direction-turnaround-20261017.md)和
[完整证据](../results/production-direction-turnaround-20261017-v1/README.md)。

此前IMLI批次新增独立预测版本模型：旧16经历年轻255后，向后taken条件
恢复17，向前／不跳／直接跳恢复0，原255恢复仍255。正常Main/TAGE方向分歧
另产生真实S3修正0→1，准确的新查找身份公开消费1。每拍注册、级间快照、
新查找和两个公开metadata均与独立模型比较，原快照保持，不读取实际值
修补golden。6DUT和59纯检查PASS，45项配对义务完成，一次完整20100项为
20065PASS/32FAIL/3XFAIL。旧20035判定保持，435组／397满，十DUT原生集合
不变。任意延迟GHR/BW查找、SC组合及完整FTQ仍未闭合；原094失败不因新的
IMLI控制通过而关闭。见[语义要求](loop-iteration-source-ownership-20261017.md)
和[最新完整证据](../results/production-loop-iteration-20261017-v1/README.md)。

此前条件历史恢复批次保留自主Micro/Main/路径及条件事件模型，从正常循环
认证原255/15、255/0或交错85/5，再核对四种实际恢复、已提交历史及新有效
公开消费者。85新纯检查和4DUT程序PASS，24项配对义务闭合；独立纯检查
145PASS无DUT覆盖贡献。一次完整回归19902项为19867PASS/32FAIL/3XFAIL，
旧19813节点和343点状态保持，405组／367满，十DUT原生集合无增无损。
IMLI原始值虽保留但未独立验证，原094两项失败不被这些控制PASS关闭。见
[四种语义要求](common-history-recovery-batch-20261017.md)、
[实际端点证据](../results/common-recovery-compatible-20261017-v1/event-qualification.json)及
[最新完整证据](../results/production-common-recovery-20261017-v1/README.md)。以下保留此前阶段。

此前部分服务程序用正常62步保存七份原来源。第一对结果提交后，独立模型
要求新身份复用已释放容量，同时保留其余三份学习；旧目标仍从最新状态
累计至0/7。真实准备事件、十次SDK完整服务、十二个新消费者和七份快照
共同完成10项义务。136项纯检查无DUT覆盖贡献，600相关兼容PASS；完整
19813项为19778PASS/32FAIL/3XFAIL，旧19693及前一轮19812判定逐项保持。
原生十DUT集合不变，不声称新增行覆盖。首轮模型和实际dirty共同暴露
rise-write停止晚一拍；现预约控制和实际确认分开，没有按DUT结果改golden。
另有23步正常程序使一条原身份已被替换、另一条已迁移，当前模型拒绝同
目的地冲突；其允许结果及FTQ来源资格尚待明确，不算DUT缺陷。见
[语义要求](bpu-partial-service-reuse-design-20261017.md)、
[下一模型边界](bpu-partial-residency-feedback-review-20261017.md)和
[最新完整证据](../results/production-bpu-partial-reuse-20261017-v2/README.md)。

最新双路退休程序从正常24步准备保存四份不同原来源，迁移后两个owner交换，
预先声明A服务0/0/0/0、B服务5/6/7/7。SDK八次完整服务、三次前版服务与
后继接纳同拍、两个新消费者及全部原metadata共同完成8项义务，66新纯检查
和1DUT程序PASS，322相关兼容PASS。首轮新检查混淆RisingStable组合观察与
实际接纳相位，现按固定相位规则分别关联，保留完整payload与次数检查，
不按实际偏移拟合。完整19563项为19528PASS/32FAIL/3XFAIL，全部旧19496
判定保持；十DUT原生集合不变，不声称新增行覆盖。邻居共存仅有正常事件
的模型可行性推演，未计DUT信用。见
[语义义务](bpu-dual-retirement-20261017.md)和
[最新完整证据](../results/production-bpu-dual-retirement-20261017-v1/README.md)。

最新双provider程序由正常语义事件建立全部状态，主模型从复位独立维护
历史、MainBTB和TAGE。原A2/B5在正常替换后迁到相反owner且当前为1/4；
旧提案1/6不能作为最终golden，预期累计0/6，干净再激活为0/7。真实接受、
四次SDK完整服务、六个新消费者及原快照共同完成8项义务。首次检查器将
纯推演启动的row122写死，真实启动的独立历史推导row106；现由自有历史
推导坐标，并补两类启动纯检查，不用实际DUT索引修golden。43纯检查和
1DUT程序PASS，255相关兼容PASS；全量19496项为19461PASS/32FAIL/3XFAIL，
旧判定保持，BPU原生DA增7而不关闭其他useful或完整FTQ义务。见
[语义要求](bpu-dual-provider-migration-20261017.md)和
[最新完整证据](../results/production-bpu-dual-migration-20261017-v1/README.md)。

最新MainBTB程序将同位置归属与不同位置的年龄隔离分开收集证据。后者先观察
邻居竞争，再给予合格邻居访问，最后观察目标竞争，防止同值写入掩盖串扰；
默认自主模型保持开启，全部声明消费者必须存在才授予checked。新四个DUT
通过、原四个DUT仍FAIL，54项纯检查通过。完整19452项为19417PASS/32FAIL/3XFAIL，
旧19429项及343点判定保持；两组为reached48/72、checked36/72，不关闭MBTB-017。
见[最新证据](../results/production-mbtb-full-capacity-age-20261017-v2/README.md)。

最新MainBTB满组程序从逻辑分支的分配、方向学习和近期使用顺序预先计算居民，
默认自主周期模型保持开启。四个新DUT程序都发现首个新分支计数应2实1，
35项纯模型及故障注入检查PASS；模型没有按错误输出重同步。后续第三次竞争
及邻居年龄仍被首错阻断。完整19429项为19394PASS/32FAIL/3XFAIL，原19390项
判定保持；硬件MBTB-017由PASS转FAIL。见[语义合同及证据](mbtb-full-capacity-learning-20261017.md)。

2026-10-16框架迁移终态：managed生产18642项/64worker完成，18614PASS/
25普通FAIL/3strict XFAIL；旧18620节点和341点判定精确保持。参考模型、硬件
激励与DUT未改；单独Main场景132900原生点及全部计数与旧流程完全相等。
自动捕获保留异常前已完成比较的覆盖样本，不授予失败功能点PASS；349组/318满
包含4个此前漏导出的未满旧组。纯模型与schema测试不贡献DUT功能测量。
该迁移补强执行/测量完整性，不代表独立参考模型缺口或已知RTL问题已经解决。
见[完整资格与范围](xreactor-managed-runner-20261016.md)。

## 输入、状态与时序边界

```text
driver / 公开输入 monitor → 预测、反馈、提交、恢复等事件 → 独立模型 → expected
输出 monitor             → 请求关联 / 时序检查                  → actual
                                               Scoreboard 比较 → pytest 异常
```

模型只接收 UT 边界上的语义事件与配置。预测表、计数器、替换状态、历史、栈和在途
更新由模型自己维护，从真实复位开始；不读 DUT 内存/寄存器来初始化或修正 golden 状态。
输入输出信号的采样、地址单位转换和事件解码放在 driver/monitor，不放在算法模型里。

公开反馈中的 metadata 对独立 UT 可以是上游输入；但在集成 BPU 中，它属于 DUT 产生
的待验证结果。若直接使用其中的 provider、索引、分配建议等，必须标记为**条件化局部
模型**，不能声称已独立验证预测选择、hash、分配或整体 BPU。

周期精确表示事件的生效与可见性：接受反馈不等于写入已提交；预测需要在取数时保存
上下文；停顿、冲刷、同周期冲突和旁路有确定语义。不能沿内部寄存器逐个复刻得到一个
看似周期精确、实际与 RTL 共用错误的模型。实现一致性检查器可保留作诊断，不替代
上述语义模型。随机分配应独立模拟随机状态，或验证合法候选集合；不能把实际分配结果
直接当成 expected。

### 语义复刻的具体边界

例如TAGE收到的不是“某个`writeReq`为1”，而是“某历史上下文下，一个匹配到上游
分支记录的conditional已经resolve为taken/not-taken”。模型由这个事件独立决定：
是否允许学习、哪个历史表匹配、provider/alternate是谁、方向置信度怎样变化、useful
是否增加、是否有更长历史表的合法分配候选，以及哪些branch-owned更新必须保留。
没有conditional资格的反馈不能改变这些状态；旧预测快照不能被后来训练修改。

算法语义与周期可见性是两类规则。计数器饱和、长历史优先、更新属于原逻辑branch
identity等是前者；接受、学习成熟、待提交和读服务优先是后者。参考模型需要表达
后者才能验证overlap，但不应读取实际内部valid/dirty/writeResp来决定自己何时推进。
有限容量/无背压允许的丢弃、单端口仲裁和固定延迟必须作为明确的配置合同，不能
无意间把RTL现有的错误合并键、错误way路由或截断位宽变成golden规则。

独立性不仅是文件名或“不导入DUT”：纯模型测试从自己的事件程序建立状态；错误
输出注入必须报错而不重同步；即使actual payload在错误上下文下自洽，也必须拒绝
与原请求PC、history、位置或base不一致的关联。实现级只读monitor仍可辅助定位原因，
但不能为主模型提供正确答案。完整BPU必须自行维护历史、选择和恢复，不能直接拿
组件实际输出/metadata拼成一个看似完整的参考模型。

### 093补强：两个独立较早分支的完整类型纠正

既有093在两个真实PC上纠正较晚indirect的target；095在同一个逻辑分支上替换两个
完整版本。新增profile检验**两个不同逻辑分支**的完整类型变化与独立保留：把各自
较早negative conditional纠正为taken indirect，较晚原indirect仍须保留完整内容。
源PC、lookup owner、历史、更新目标、反向邻居和保留版本均来自自有事件历史。
两次公共输入相邻接受、读阻塞服务期间必须同时保留两条entry及两次direction，
且无覆盖/溢出；fresh旧消费者先于释放，SDK确认每个完整服务后fresh消费者再
选中较早的新分支。修正窗口由独立middle/final选择规则推导，不能照抄旧profile
“target-only必然S3”的断言，因为类型/位置改变可能触发结构性S2修正。

较早分支变成taken后，较晚sibling在基址请求中不再被选择。仅检查自身模型中
它的target不变，或检查不含target的公开metadata，都无法发现实际DUT破坏了隐藏
target。现在每个上下文再发一笔从较早指令之后开始的fresh offset请求，过滤较早
分支，让较晚indirect成为实际被选结果；自有source token必须已经与真实stage
choice/metadata/public source比较，再检查其原target、counter及独立修正窗口。
没有这两个真正选中的sibling消费者，最终checked信用一律拒绝。

直接复用自主BranchTargetSources/MbtbReference，未新增信号镜像模型。扩展现有
MainServiceChecks/env的语义profile，case不见edge/task/get_set；同时拒绝把stale
nomination混入当前来源重分类。两组各6义务，最后一项明确保护较晚indirect，
不把被重分类的conditional仍错误称为“保持negative”。旧service/retained-owner
schema保持不变；生产门禁146→148个schema，两个新组已有独立单场景及全量DUT
合格数据。此处是有界预测学习合同，不据此声称完整固定程序/FTQ/全预测器证明。

41个新增纯/负向合同覆盖完整proposal的每个
字段、两条保留义务、direction owner、缺失/错误/重复/提前服务、旧/新端点、
修正窗口、fresh selected sibling错误PC/旧request/错误target/position/counter/
repair/重复、每一义务缺格，以及互斥profile配置。原Main service/rewrite77项纯
合同也纳入真实pytest门禁。合成actual不计DUT信用。
另25项源/native关联纯合同检查完整复制字段、移动行号、所有真实producer、
control-only分支及独立UT签名匹配；不产生功能PASS或不可达证明。前轮125个BPU缺键
对应14个producer，均有同编译体/同构建的历史独立UT PASS输入聚合命中，但没有
因此转移成集成FTQ合法性证据，也不新建重复UT功能点。
旧096 raw在用户新授权后精确删除，保留汇总LCOV/报告/日志及上一轮016完整输入；
没有降低或绕过入场门禁。独立新场景PASS（case1.46秒，pytest11.36秒），门禁
3139PASS（37.89秒）、兼容71PASS（56.98秒）及全量同2107文件epoch。
全量18620项/64进程440.46秒，18592PASS/25普通FAIL/3strict XFAIL；新增73项
全PASS，所有旧节点及341功能点判定精确保持（322PASS/17FAIL/2XFAIL）。
64收据与1501产物hash核验，1182功能输入只合并一次（137.28秒）：345组/318满，
新两个6义务组全满，全部旧343比例及27未满实例精确保持。完整BPU DA
33745→33754/46541，9个新增键恰好等于唯一独立PASS增量，每键孤立计数1；
即WriteBuffer_4.sv549–557完整payload复制。v_line仍2392/8236，十DUT均零旧键
损失、其他九个集合及所有分母/构建不变。9条DA不是9个新功能。

剩余Main116键为74跨owner、42双入口仲裁候选，13个producer（11payload块与
2control-only else）仍有同构建独立UT历史PASS见证，但不转为集成可达或功能信用。
既有026本来已预清理再重放，不新建重复UT需求；028/026/029的集成来源/效果/
消费者资格继续开放。RAS31、其它guard/PHR分类及已知RTL差异保持，不枚举物理
副本，不改RTL/DUT/SDK或五份正式报告，不把失败全量发布为验收。
详见[完整差分](../results/production-main-reclassification-20261016-v1/diagnostic-native-delta.json)
及[当前Main分类](../results/production-main-reclassification-20261016-v1/diagnostic-main-copy-residue.json)。

### 016集成补强：中性提交回收版本寿命但不提交调用栈

096完成后集成RasStack尚有35个原生缺键；其中598、600–602不是更多物理槽，
而是“非push且forward version gap大于2时回收容量”的独立来源/效果要求。
这属于已有RAS016丢失退休通知的防御合同，不新增097同义功能，也不冒称正常
FTQ会允许漏掉此前call退休。独立UT原六个call/return上下文及36格保持不变；
本轮增加一个真实集成neutral direct指令profile。

主语义来自[RasStack.scala:378](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/RasStack.scala#L378)：
push退休设置BOS；否则有效退休的距离大于2，才保留最新一个版本并回收更老信用。
[Bpu.scala:226](../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala#L226)规定
RAS的specIn来自实际S3 fire，而非“只有call/return才有来源”。因此action0的真实
direct指令能携带独立比较过的当前checkpoint，并不是将call来源篡改为neutral。
注册提交与容量guard的不同生效拍，也必须各自检查，不能只等固定周期后看BOS。

一个有界程序依次执行：

1. RAS关闭时正常学习旧self-call、中性self-direct、新self-call及新return；恢复
   冷准备真实checkpoint后启用RAS，真实满速旧call填16版本，额外offer受guard保护。
2. 从真正较老的2-call来源恢复到中性指令。此时speculative SSP与committed head
   可以不同；实际neutral S3来源退休后，间隔恰好2必须不回收，全部8个提交组不变。
3. 从该中性来源恢复旧call并再次填满。切到中性指令的同当前checkpoint恢复不能
   解除guard。真实neutral source应带16版本；它的退休跨注册边界后BOS变15，
   guard仍为真，下一拍才解除；在证明解除前不得有另一次有效恢复作为替代原因。
4. 新身份call真正复用版本16及以后。撤销最年轻新call，再由fresh S3 return消费
   新地址并保留至少一个新live frame。全部旧metadata必须不可变，所有提交组仍
   是复位值；这次只退休两条neutral，不能虚构旧call或新call已提交。

独立[RasReference](../bpuverify/ras/model/semantic.py)仍只维护自己的持久Program、
Frame、版本与退休事件。BOS/guard通过可选静态Bundle只读扩展与public/retained
在同一输出freeze采样，每一拍与模型自有retired_calls/guarded比较，不反灌模型。
[checker](../bpuverify/bpu/checker/ras/neutral_gap.py)要求全部8项因果义务完成，
最后一次真实状态/消费者比较通过后才记checked；两个8-bin FC组不是16个功能。
[case](../bpuverify/bpu/case/ras/neutral_gap.py)只表达prepare/threshold/reclaim/reuse，
等待、源收集、公共驱动和资源时序在env/driver/monitor中，无case级edge/get_set/task。

CommitChecker只为实际neutral新增无栈操作路径：真实S3动作/PC、resolve/redirect、
唯一tick、严格时间顺序、注册valid/push/pop/metadata及全8个提交组比较全部保留。
只有neutral不要求source SSP等于committed head，也不调用栈操作advance；普通
call/return仍严格拒绝stale SSP，CommittedStack对action0的原有拒绝也不放宽。
容量/BOS正确性由独立生命周期模型另行验证，不能用“提交数据没变化”代替回收证明。

43项纯/负向契约覆盖距离0/1/2/3/16、注册延迟、guard解除因果、全部义务缺失、
错误BOS/guard/top/head/非当前提交组、来源错误/重复/篡改实际call或return、复位
以及最终效果尚未比较。合成actual仅资格化checker，不是DUT功能证据。实际单场景
与全量测量均已完成：单case0.97秒，pytest10.73秒；完整18547项64进程449.54秒，
18519PASS/25普通FAIL/3strict XFAIL，50个新增测试全部PASS，旧节点/点状态精确
保持。门禁3067PASS、兼容70PASS与单/full同2103文件epoch；64收据、1504产物
hash核验。341点仍322PASS/17FAIL/2XFAIL；1181功能输入合并一次135.24秒，343组/
316满，旧341比例及27未满实例完全保持。BPU DA33741→33745/46541，严格四键
等于单PASS；v_line仍2392/8236，十DUT无旧命中损失。RasStack剩31键是16局部guard
与15物理副本，不删除分母或默认槽枚举。已知RTL问题不降级、不新增豁免。
详见[完整诊断审计](../results/production-ras-neutral-gap-20261016-v1/lifecycle-audit.json)、
[原生差分](../results/production-ras-neutral-gap-20261016-v1/diagnostic-native-delta.json)
及[FAILED / NOT acceptance结论](../results/production-ras-neutral-gap-20261016-v1/diagnostic-summary.json)。

### 096：guard回滚后的调用版本回收与新身份复用

新增[生命周期程序](../bpuverify/bpu/case/ras/capacity.py)继续使用独立
[RasReference](../bpuverify/ras/model/semantic.py)，不复制specQueue寄存器。
模型从真实复位和语义call/return/recovery/retirement维护持久Program/Frame，
每个调用的版本、重复组和前驱来自自己的操作历史。返回地址由输入指令结束位置
计算；实际top、SSP/SCTR、tosw或committed cells不能初始化/修正golden。

guard是注册容量约束，不是“达到16个offer就算满”。Main-only每次都有修正气泡，
15个版本后下一空拍就关闭guard；这是初次试跑的**验证程序预期错误**，并非RTL
差异。正常学习MicroBTB后，连续真实call在guard生效前填入第16个版本；额外公开
call仍可能正常预测，但不等于RAS又接纳了版本。31项纯/负向测试分别验证15/16
cadence、当前来源拒绝、距离仍大于14的较老恢复不解除guard、回到14的边界恢复，以及
版本/目标/计数/来源/未完成端点/复位错误。原始S3来源逐个与独立投影核对。

主程序的一个容量生命周期是：

1. 正常学习旧self-call、旧return和不同地址的新self-call/new-return。真实旧调用
   达到16个版本，额外call、guarded return以及同当前检查点的恢复均不得改变前缀。
2. 从真正发布过的较老source恢复14个调用，距离不再大于`SpecQueueSize-2`阈值；再消费旧
   return，撤销其最后一个年轻return，仅把存活旧call和较老return按原source提交。
3. 真实新调用使用**不同返回地址**，跨越容量wrap，复用已取消尾部及已提交位置。
   撤销它的最后一个年轻call，所有保留新call恰好提交一次。
4. fresh新return必须消费新地址，保留旧committed groups和所有原始metadata。
   只看写到slot14/15或某个valid脉冲不能代替这条完整生命周期。

[检查器](../bpuverify/bpu/checker/ras/capacity.py)派生现有RAS语义组件checker，
既比较每拍公共投影和全部八个committed groups，也在真实S3 return输入处检查
其消费的实际public target。源码合同分别为
[Ras.scala:71](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/Ras.scala#L71)
guard拒绝call/return、
[Ras.scala:98](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/Ras.scala#L98)
只允许较老来源或未guard状态恢复，以及
[RasStack.scala:416](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/RasStack.scala#L416)
注册距离阈值。八个reached/checked义务是同一版本寿命需求，不按物理slot拆点。

模型输入边界是**集成RAS语义cut-point**；Main/Micro的实际S3解码是这个UT的上游
输入，不冒称已自主推导全BPU预测器。genuine公共source、指令身份、PHR、顺序
提交与实际return consumer另行核对；不声称完整FTQ合法性或任意32-version别名
寿命。runtime collection/recovery公共helper下沉到
[env/ras/program.py](../bpuverify/bpu/env/ras/program.py)，旧case API只保留兼容导出；
case只描述生命周期，不出现edge、task或gather。环境允许显式注入reference，
无需运行时替换对象或把实现级寄存器镜像当语义模型。

最终[完整生产诊断](../results/production-ras-reclaimed-versions-20261016-v1/exit.json)
18497项、64进程443.45秒：18469PASS/25普通FAIL/3strict XFAIL，无ERROR/SKIP/
XPASS。新增31纯/负向、6schema、1DUT共38项全PASS；旧节点和旧340点状态逐项
保持，现341点全执行，322PASS/17FAIL/2XFAIL。门禁3018PASS（218.16秒）、兼容
69PASS（118.24秒）、单096 PASS（case0.95秒，pytest10.91秒）与全量同2096文件
epoch，64收据和1496产物hash复核。旧helper下沉不改变旧场景结果，aging仍414.67秒。

BPU原生33741/46541，严格净增13键等于唯一单096 PASS；12键属于RasStack，1键
属于准备新call PC时的ReplacerState_4物理副本，不据此新增或宣称完整Main-LRU。
十DUT零旧命中损失，其余九个精确集合、分母和构建不变；v_line仅2391→2392。
1180功能输入只合并一次（135.57秒），341组/314满，新两组满；旧339组比例及
27未满实例完全保持，required schemas142→144。失败全量不发布，不授予整体验收。

RasStack剩35键的[完整残留分类](../results/production-ras-reclaimed-versions-20261016-v1/diagnostic-integrated-ras-residue.json)
为16局部guard、15物理组副本、4个non-push提交gap回收键。独立/集成child body
逐字节相等；parent并不相同，故明确重验集成push/pop互斥连接，而非按模块名套用。
16个主张全部native producer的anchor/arm/S span都严格对应源级证明；物理副本
不表示任意地址路由已证明，不删分母。四个gap键要求真实non-push retirement与
forward call-version gap，独立UT已有016不等于集成证明；当前BpuRetirement只支持
有序call/return，尚不能驱动/检查该neutral或缺失通知合同。它是下一步具体功能
缺口，不能用更多slot或本次正常call提交的BOS更新糊过去。
RTL/DUT/SDK、detached HEAD与五份正式报告不改，目标继续开放。

### 095：完整分支记录的pending版本取代与clean重激活

MainBTB剩余WriteBuffer_4缺行不是129个缺失功能。093检查两个**不同记录**均被
保存和服务；[095程序](../bpuverify/bpu/case/main_rewrite.py)检查**同一记录**的
两个真实旧来源如何产生完整新版本，以及clean记录再次修改后的可见性。复用
独立`MbtbReference`/`RetainedEntries`，核心身份为(row,tag,position)，owner和
版本由模型维护，不根据实际dirty、出队口或命中位置决定expected。

正常学习两个受保护PC，每个都有较早negative conditional和较晚indirect sibling。
同一个PC再捕获两个不同预测的确切owner；两次反馈将较早误分类的分支纠正为
taken indirect，完整目标依次为同region A、下一region B。真实Micro自循环产生
连续同bank预测读，两个公共输入必须相邻接受，且每个完整entry和方向proposal
都按原source检查。**entry只保留最新B，独立direction FIFO必须保留两次reset**；
这不是把相同数值的方向效果也顺手合并，更不是允许容量丢失。

fresh旧读先看到原conditional和较晚indirect，全部真实服务仍为零；释放读后，
SDK monitor必须确认恰好一次完整B entry及两次masked direction服务，A不能
偷偷落SRAM。fresh新来源必须看到corrected kind、完整B目标和不变sibling。
然后用这个确切新来源修正到前一region C，clean记录重新产生一次完整服务及
自己的direction update；最后fresh C消费者和另一个受保护PC复核后才闭合。
原始metadata始终不可变，所有新旧branch-owned目标由自有事件和冻结read推导。

`BpuTransaction.prediction`是原S1结果，不能把它误称为已修正的Main结果。
[检查器](../bpuverify/bpu/checker/main_rewrite.py)同时要求Main真实公开metadata
与独立frame匹配，并从自有early/middle选择推导全部S2/S3 correction时刻，再
比较实际public correction事件；每拍完整目标、类型、控制和最终输出仍由原
PipelineChecker检查。只看到模型中的new target或单个valid脉冲不算consumer。
case不包含edge、task、gather；[env](../bpuverify/bpu/env/main_rewrite.py)复用
production AsyncDriver及现有ServiceMonitor/Bundle，并用成熟与服务条件等待。

契约来源是[WriteBuffer.scala:204](../XiangShan/src/main/scala/xiangshan/frontend/bpu/WriteBuffer.scala#L204)
同逻辑记录dirty更新/clean比较重激活，与
[MainBtbInternalBank.scala:149](../XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbInternalBank.scala#L149)
entry和direction各自的读优先服务。第一次试跑到clean C proposal时发现**验证端
协议投影错误**：语义region_delta=-1应保持为负一，但端口TargetCarry为枚举
Underflow=2，不是二补码3。依据
[Bundles.scala:378](../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bundles.scala#L378)
修正[projection](../bpuverify/bpu/model/main_service.py)，并增加Fit/Overflow/Underflow
三个纯契约；不是修改RTL或把实际carry反灌golden。该错误不得记成硬件FAIL。

095为一个需求族，八个reached/checked义务不是八个功能点，不按slot、owner、
bank/set或字段枚举。其容量内同owner版本要求不替代仍普通FAIL的028旧nomination
与保留owner矛盾。全预测器、完整FTQ寿命与剩余缺口仍不在本profile已完成声明内。

最终[完整生产诊断](../results/production-owned-main-rewrite-20261016-v1/exit.json)
18459项、64进程469.06秒：18431PASS/25普通FAIL/3strict XFAIL，无ERROR/SKIP/
XPASS。新增32纯/负向、6schema、1DUT共39项全PASS，所有旧节点和旧339个功能点
状态逐项不变；现340点全执行，321PASS/17FAIL/2XFAIL。最终门禁2981PASS、兼容
68PASS及单095 PASS与全量同2088文件epoch，64收据/1496产物hash复核。
单case1.52秒、含setup的pytest13.69秒；整体仍有412.19秒aging，不声称性能优化。

BPU原生33728/46541，严格净增4键恰好等于单PASS：WriteBuffer_4.sv的581–582、
626–627，隔离计数各1；十DUT零旧键损失，其它九个精确命中集合、所有分母和
构建保持。v_line另2388→2391/8236，不与DA混用。仍缺Main125键，不根据这四个
控制键命中宣称其余都已分类。1179功能输入仅合并一次（134.35秒），339组/312满，
新两组满；旧337组比例和27个未满实例逐项保持，required schemas140→142。
RTL/DUT/SDK及五份正式报告未改，失败全量不发布，目标仍开放。

### 094与043：条件事件序列，而不是CommonHR信号方程

新增[CommonDirectionReference](../bpuverify/bpu/model/common_history.py)以有序的
conditional身份和实际完成结果追加历史：普通fetch block完成可以包含其全部NT
conditional；backend在较早conditional处纠正为NT，只完成截止该指令的前缀，
**后面的conditional尚未执行，不能提前补零**。模型不读取实际s2/s3、内部GHR/BW、
queue指针或输出metadata来决定expected。已有SC组件的CommonHR状态检查器仍有
价值，但其输入来自实际组件边界，不能作为这个自主oracle的替代。

[程序](../bpuverify/bpu/env/common_history.py)组合独立Micro/Main/path模型，正常
学习PC`0x40000800`：位置1为taken后向conditional，位置5分别为direct正对照或
conditional；fallback为direct自循环。独立完成事件自然形成GHR255/BW15。只在
连续完整lookup-window内历史不变、全流水前进且无repair/redirect时，才允许把
该值绑定到新发出的确切owner；容量8来自固定硬件参数，不是“等8拍就当完成”。
任意S0延迟选取仍不支持；未获独立认证的source明确报错，不从实际metadata补齐。

原始公开来源在位置1恢复为NT时，应为GHR254/BW14；later-conditional实际为
252/12。单纯检查恢复中的valid0状态不足以证明对外影响，因此另有**不绑定内部
GHR/BW的public-only profile**：放行后位置5的conditional才实际执行一次，随后
fresh公开prediction的resolve.valid必须先为1，再比较GHR/BW：期望253/12，
实际249/8。later-direct两种profile均为254/14正对照，强化既有043，不另建同义ID。
原始history快照不可变；exact owner、实际redirect全部字段、条件资格与去重身份
都先检查，失败锁存后不推进或修正golden。预期恢复计算本身不算观测成功，必须
再经过post-restore采样；reset失效所有旧source及未完成闭环。

源级原因是[CommonHR.scala:204](../XiangShan/src/main/scala/xiangshan/frontend/bpu/history/commonhr/CommonHR.scala#L204)
的r1_numHit仍统计原预测中全部conditional，而
[Helpers.scala:33](../XiangShan/src/main/scala/xiangshan/frontend/bpu/history/commonhr/Helpers.scala#L33)
在taken=false时直接选择numHit。不要误归因为“nonconditional没过滤”：
[Bpu.scala:483](../XiangShan/src/main/scala/xiangshan/frontend/bpu/Bpu.scala#L483)
本来就发布conditional-only dedupHitMask；我们的direct对照也验证了这一点。
问题是较晚的真实conditional还没有执行，不是direct被误当conditional。

[PipelineObservation](../bpuverify/bpu/env/pipeline.py)把pipeline/CommonHR Bundle
组合为**一次冻结采样**，同一SDK capture内先处理独立pipeline、再处理历史。
不能依赖两个`@on`订阅或异步observer任务的执行先后。MemoryBackend测试在第一
个回调中改变底层信号，第二个仍须读到旧冻结值，且退出后不再采样。cases只描述
学习、原source、NT恢复和fresh consumer，不暴露edge、task或gather。

六个事件义务按reached/checked分别收集；direct/conditional与state/public形成
八个组，生产required schemas132→140。checked只在完整endpoint及原始metadata
复查后一次性记账。合成故障注入不导出DUT覆盖证据，两个conditional差异保留
普通FAIL，未改RTL/DUT/SDK。此核心只覆盖GHR/BW条件序列与明确认证的lookup，
不宣称自主IMLI、任意lookup队列调度、完整SC历史组合或全预测器/FTQ已完成。

最终[完整生产诊断](../results/production-owned-common-history-20261016-v1/exit.json)
18420项、64进程455.81秒：**18392PASS/25普通FAIL/3strict XFAIL**，无ERROR/
SKIP/XPASS。所有旧节点和旧338个功能点状态逐项保留，新094 FAIL；当前339点
全执行，320PASS/17FAIL/2XFAIL。新增60纯/负向、2Bundle、2原子采样、24schema
契约和4DUT场景。最终门禁2943PASS（214.16秒）、兼容67PASS（113.18秒）、
两个单PASS及两个隔离普通FAIL与全量同2081文件epoch；64收据和1502产物hash
复核，五份正式报告未改。隔离state差异tick474、public差异tick506；两个direct
对照case分别0.80/0.86秒，含setup的pytest分别10.75/10.91秒。
十DUT精确原生命中集合、分母、构建和v_line不变，BPU33724/46541、2388/8236；
两个单PASS均无新增DA键。提高独立性并找到真实差异，不等于原生覆盖率上涨。
1178功能输入只合并一次，耗时133.48秒；337组/310满目标，旧329组比例及23未满
实例全部保留。direct四组满，conditional的state/public reached50%/66.67%、
checked均0，未满合计27。未闭合真实缺陷不被框架140个合成schema门禁的通过覆盖。
失败全量不发布、不标验收；保持用户“暂不改RTL”的授权边界，目标仍开放。

下一步语义组合缺口是：用自有预测/完成/repair/redirect事件推导任意S0历史lookup
归属，替代当前明确受限的reset/fixed-point资格；随后加入自有IMLI结果，接通SC
真正的历史输入来源。此顺序不能跳成直接读取实际索引或历史值作为golden。

### 093与028：MainBTB完整目标服务与旧冷源的真实owner资格

MainBTB的entry缓存、方向FIFO不是同一种资源，也不能机械套用ITTAGE/TAGE
profile。新[093程序](../bpuverify/bpu/case/main_service.py)继续使用已有独立
`BranchTargetSources`及`MbtbReference`；两个真实PC各自通过正常公开反馈建立
counter0的较早conditional邻居、counter2的较晚indirect owner。所有表项、LRU、
读快照、原始checkpoint与MicroBTB可信度均从复位/公开事件自行维护。

两个不同的当前hit来源统一异步提交真实目标纠正，不等待各自效果。驱动前声明
完整entry效果及独立masked direction效果：entry仍属于way1；方向同时保留peer0
并把owner设2，故mask3的两个值分别0/2。普通entry缓存每way两槽，方向FIFO总深度2，
所以容量内程序只要求两个效果，不拿四项entry容量假设方向也能无损接纳四项。
所有实际公开输入、offered完整payload、保留顺序、零覆盖/丢弃、满pending与blocked
front分别比较；两个fresh旧consumer看到旧完整target和0/2后才释放读压力。
SDK须确认两个有序entry服务、两个有序masked direction服务；两个fresh新consumer
看到新target、邻居仍0、owner仍2，原metadata不变、所有pending/实际端口均空，
完整repair窗口通过后才统一给checked。

持续读必须由真正的早期预测维持：只用Main的S2纠正自循环会有另一bank的真实读
空档，写入可趁机服务。程序先正常学习MicroBTB自循环，并让两个旧target直接
返回它；不把测试驱动的readBusy当成输入，不靠case等待/边沿/task/gather制造忙。
目标改动本身不会触发S2，最终完整目标差异应在S3纠正；新消费者要求唯一S3
repair，而不是用错误S2断言误报RTL。精确内部采样合同也区分两条路径：方向t1
enqueue与原公开接纳处于同一Rising采样边界，entry经额外RegNext晚一周期。
这都是offered边界，不能当作SRAM已提交。初版严格“入队必须晚于接纳”的断言
经有界异常上下文和源码核实后修正，增加提前/延后一周期的负向契约；没有改模型
算法或把actual值反灌期望，也未导出逐周期轨迹。

[Bundle](../bpuverify/bpu/bundle/main_service.py)仅绑定现有memory-direct完整entry、
方向队列及读服务边界；mask以外的方向payload无定义，不变造成学习许可。共用
[ServiceMonitor](../bpuverify/bpu/monitor/service.py)现在只接收已绑定的静态端口，
不再要求checker带history-table属性，也不将Main的alignment伪装成table。
领域绑定仍在Bundle/env，动态接收仍是SDK原生`ReadyValidMonitor`与lossless`@on`。

已有028原先在独立UT发现counter所有权差异。新增同功能点的真实BPU资格保留
一个**学习前真正发布的cold来源**，正常准备后独立证明该key仍保留于way1，而
当前LRU的cold nomination为peer0。旧输入不伪造metadata，也不选择已被正常
替换的key来假定仍有旧owner。它只纠正后面的indirect，不解析conditional，
所以期望方向mask2、values={1:2}；真实DUT却提出mask1、values={0:2}。
最终单独资格仍为普通FAIL（tick714），在错误masked enqueue处立即抛出带原来源、
预期/实际及状态的异常；**不声称失败后已观察到SRAM服务或新的错误消费者**。
`MainBtbAlignBank.scala:264`以nominated entry way决定counter reset，而WriteBuffer
的全局逻辑key合并会保留另一个owner，这是与独立UT同源的组合差异，不新增同义
功能点或XFAIL。完整FTQ物理寿命/epoch及所有同时启用预测器仍不由此程序证明。

最终093单独资格`owned-main-service-qualified-20261015-v3`为1PASS，场景1.34秒、
pytest11.28秒；两组各六条义务完整。
[原生归因](../results/owned-main-service-qualified-20261015-v3/qualified-line-delta.json)
补中WriteBuffer_4的609、614–623共11个DA键，是第二个完整目标效果的保留路径，
不是11个功能点。最终旧源资格`owned-main-retained-owner-qualified-20261015-v2`
为1普通FAIL，pytest11.31秒。错误在整批driver/monitor收据资格结束前抛出，该模式
两组均保守为0；不能据此反推公开输入没有发生，更不能给checked或把失败刺激算成合格提升。
隔离分子不和历史拼接成新全量。

最终[完整生产](../results/production-owned-main-service-20261015-v1/exit.json)18328项、
64进程446.97秒：18302PASS/23普通FAIL/3strict XFAIL，无ERROR/SKIP/XPASS。
旧节点和逐项状态全部保留，只新增上述028的BPU资格FAIL。338点全执行，320PASS/
16FAIL/2XFAIL，旧337点状态不变，只新增093一个需求族。新增45语义纯/负向、
1Bundle、12schema契约与2DUT场景；门禁2855PASS（203.42秒）、兼容65PASS
（112.82秒）、单PASS/单普通FAIL与全量同2071文件epoch，64收据、1495产物hash
均核验。RTL/DUT/SDK和五份正式根报告不变，未改分支或新增skip/XFAIL。

BPU原生33724/46541（72.46%），净增11键逐键等于单093 PASS，十DUT零旧键损失，
其余九个精确命中集合、所有分母/构建不变；v_line另增1至2388/8236。剩余Main
缓存129个缺键仍待归因。局部guard及有owned-checkpoint前提的PHR分类重验不变，
不缩分母、不填功能PASS。1174功能输入只合并一次（133.85秒），329组/306满目标，
新增服务两组满、旧源两组0；原325组比例和21个未满实例不变，未满总数23。
required schema128→132；框架合成门禁不是实际功能全通过的证据。
[失败回归功能汇总](../results/production-owned-main-service-20261015-v1/diagnostic-functional-summary.json)
明确FAILED/NOT publication/NOT acceptance；417.38秒长老化仍在，不声称本轮加速。
整体目标仍开放。

### 062与092：自主间接目标学习与读压力下的完整目标服务

`IndirectSources`将已有独立`MbtbReference`、`IttageReference`与自有PHR/token
engine组合。期望的索引、tag、provider/alternate、置信度、useful、完整目标、区域
目录及15位分配PRNG均从复位和公开事件推导，不使用actual metadata作为golden。
Main在S0保存自己的读；ITTAGE在S1接受时保存不可变表项，在S2用当时自有区域目录
解码并选择，随后冻结到原来源的S3。区域目录在S1与S2之间变化不能被错误提前冻结，
而已完成S3也不能被后续训练或目录替换重算。所有有定义的实际metadata、S1 PC/
folds和15位PRNG持续比较；PRNG按物理采样相位推进，不随交易停顿或借实际值重同步。

原062增加[自主学习程序](../bpuverify/bpu/case/indirect_learning.py)，保留旧的十步
provider/alternate测试。四次真实原来源纠正必须依次建立长表provider、使confidence
2→1→0而保持旧target、在Main已改新target时产生原来源S3纠正，最后才在旧confidence0
时重学目标。每次反馈都有自己的fresh consumer，原metadata不变，完整S2/S3 repair
窗口比较通过后才获得checked。此项增强原功能点的oracle，不重复增加功能ID或行分。

092补的是另一个真实要求：**公开正确间接反馈已接受，但预测读占用单端口SRAM时，
四个完整上下文目标效果必须保存，释放后按序服务，新请求才看到提交值**。不只是
检查某dirty位变1，也不将“输入接受”当作“内存已更新”。

[服务程序](../bpuverify/bpu/case/indirect_service.py)在同一间接PC，通过真实的直达/
中间路径建立四种历史和四个外部区域目标；每个源都有独立checkpoint、row、region
identity与完整目标快照。短/长历史两类索引宽度分别资格，不遍历中间表、bank或set。
声明四个confidence3的完整效果后才统一通过现有异步training driver发送；反馈是
原预测实际正确的non-mispredict，不为制造覆盖发明错误标志。真实预测必须与四次
相邻接受并行，不能通过暂停预测来帮助写入。

[Checker](../bpuverify/bpu/checker/indirect_service.py)先核对实际offered payload和
独立pending顺序、四slot保留、零覆盖及稳定blocked front。四个fresh旧值consumer
均须仍读到confidence2和自己的完整foreign target。释放读压力后，共用的
[ServiceMonitor](../bpuverify/bpu/monitor/service.py)由xreactor原生
`ReadyValidMonitor`确认恰好四个完整、有序服务，再检查四个新consumer的confidence3、
目标、完整repair窗口、空pending、原metadata与所有region不变，最后统一给checked。
case没有时钟边沿、手写task或gather；等待条件和异步收据留在env中。

[只读Bundle](../bpuverify/bpu/bundle/indirect_service.py)仅绑定现有memory-direct/
trace-projection字段。输入entry.valid已常量折叠，绝不伪造XData；offered比较实际
存在的有定义字段，service输出仍完整检查valid。physical mask是包含padding的36位，
padding本身来自RTL的DontCare，不伪造成独立功能要求。无VPI、内部写入或DUT重建。

最终冻结隔离资格三项均PASS：短历史场景1.98秒、长历史2.99秒、原062自主学习1.08秒
（pytest分别12.48/14.17/11.05秒；均不代表全量时间）。每场景两组各六条义务完整。
相对此前完整诊断，
[短类](../results/owned-indirect-short-qualified-20261015-v1/qualified-line-delta.json)与
[长类](../results/owned-indirect-long-qualified-20261015-v1/qualified-line-delta.json)
各独立补26个DA键，分别为WriteBuffer_24/28的401–413、420–432，计数均为1。
这是同一容量内完整目标保存事件的slot2/3赋值展开，不是52个新功能点。062本身
没有新增原生行命中，但补强独立判断质量。隔离分子不与历史拼接发布；完整FTQ、
其它预测器同时启用、call/return组合仍不在此profile内。

最终[完整生产](../results/production-owned-indirect-service-20261015-v1/exit.json)
18268项、64进程505.72秒：18243PASS/22普通FAIL/3strict XFAIL，无ERROR/SKIP/
XPASS；所有旧节点及逐项状态精确保留。337点全部执行，319PASS/16FAIL/2XFAIL，
旧336点状态不变。新增89语义纯/负向、5Bundle/Monitor、18schema契约与3DUT场景；
门禁2797PASS（197.24秒）、兼容64PASS（112.57秒）、三项隔离资格及全量同2062
文件epoch，64收据和1485产物hash复核。required schema122→128。

BPU原生33713/46541（72.44%），净增52键逐键等于上述两项隔离资格并集；十DUT
零旧命中丢失，其余九个精确集合、所有分母/构建provenance不变。v_line仍
2387/8236。局部guard和有owned-checkpoint前提的PHR分类不变，不因此删分母或
给功能PASS。1172功能输入只合并一次（134.03秒），325组/304满目标；六个新组
全满，原319组比例和21个未满实例精确不变。
[失败回归功能汇总](../results/production-owned-indirect-service-20261015-v1/diagnostic-functional-summary.json)
明确FAILED/NOT publication/NOT acceptance，五份正式根报告未改。已知RTL失败
继续普通FAIL；整体目标尚未完成。

### 091 Useful延后服务：原来源学习、旧值读取与实际写回分开证明

从最新完整诊断的`Queue4_UsefulCtrSramWriteReq.sv:83/85`两个零计数键反查，缺的
不是“又一个bank”，而是**预测读占用SRAM时，合格useful学习必须被保存并在之后
服务**。原086的两个provider与base同向，没有useful增益；预测counter的保留键
合并和写回，不能证明useful独立FIFO的保存、顺序及消费者可见性。073的维护清零/
flush也不是这个普通学习事件。因此091新增一个需求族，包含原正确分歧、读优先
保存、按序服务和提交后可见性四个语义要求；六条采样义务不是六个新功能ID。

[程序](../bpuverify/bpu/case/direction_useful.py)复用真实Main/TAGE/history准备与
`DirectionSources`，所有预期由独立`TageReference`产生。两个真实历史在相同PC
拥有负向counter2/正向counter5的长表provider。暂时禁用TAGE、只把Main准备成3/2，
保留所有TAGE状态；negative provider正确而原base错误，邻居positive provider与
base一致。捕获四个不同公开来源A/B/A/B，再统一异步送入完整NT-prefix/T-tail
结果。所有实际接纳须相邻、伴随真实预测且没有训练重读；不是case里手写task、
gather或时钟边沿。

在驱动前，由自有read冻结四个`(row,useful=1)`义务。目标原useful0；正向邻居在
正常准备阶段已经学到useful1，成为非零隔离sentinel，不能假定邻居也为零。
各原来源只携带自己的旧值0，所以两次同row反馈都提出1，不应无依据叠成2。
相反，TAGE retained counter会将各历史的两次更新合成0/7；Main更新使用各自捕获
的3/2快照，每次提出2/3，不合成0/3。纯模型分别检查这些语义，不能套同一种
“并行更新必然累加”的规则。

[Bundle](../bpuverify/bpu/bundle/tage_service.py)只读memory-direct已存在的useful
enqueue/dequeue、payload、指针和full；优化端口用SDK trace projection还原，
没有VPI、内部写入或DUT重建。指针到occupancy的函数只是actual投影，绝不进入
算法状态。[Monitor](../bpuverify/bpu/monitor/tage/service.py)复用原SDK
`ReadyValidMonitor`及lossless `@on`采样，仅选择独立useful通道，不新造调度框架。

[Checker](../bpuverify/bpu/checker/direction_useful.py)比较每个实际enqueue；所有
四个义务成熟后，在同一独立模型/actual边界核对满容量、稳定blocked front、零
ready、零丢弃及无flush。继续读两个原历史，新公开consumer必须仍看到旧useful0
和counter2/5。两者都完成才释放读压力；SDK必须确认四次完整、按序且不多不少
的useful写服务。之后两个新consumer必须看到目标useful1、counter0/7，邻居useful1
保持，所有原snapshot不变、pending与实际队列均空，完整repair窗口无额外纠正，
才一起关闭checked。四个来源是有重复旧快照的容量内生命周期，不是bank/set遍历。

[75项纯模型/负向契约](../tests/bpu/scoreboard/test_direction_useful.py)全部通过，
包含错误原来源、错误并发接纳、顺序/payload/ready/flush、丢失义务、错误满状态、
过早提交/读取、缺少某历史consumer、useful错误累积和邻居损坏等；synthetic actual
不计DUT覆盖。准备好disagreement不能提前记“correct”：第一条reached与实际反馈
接受同边界，新增专门负向契约拒绝仅有准备、没有真实接纳的虚假事件。
最终冻结隔离资格`owned-direction-useful-qualified-20261015-v2`
为1PASS，场景5.45秒、pytest18.40秒；两组各6条reached/checked完整。首两条reached
在真实接受tick2578；满pending2588、旧值consumer2612、全部提交2622、新值consumer
2696；所有checked均待2696完整闭环才记录，不以程序步骤充当事件。
[合格原生增量](../results/owned-direction-useful-qualified-20261015-v2/qualified-line-delta.json)
相对此前完整失败诊断严格新增上述两个指针推进键，没有覆盖分母修改，也不是两个
新功能点。完整生产结果单独核对；隔离分子不与历史拼接发布。RTL/DUT/SDK不改，
完整FTQ物理寿命及其它预测器组合仍不由这个profile声称完成。

[最终完整生产复验](../results/production-owned-direction-useful-20261015-v2/exit.json)
18153项、64进程444.96秒：**18128PASS、22普通FAIL、3strict XFAIL**，无ERROR/
SKIP/XPASS。旧FAIL/XFAIL节点精确集合与所有旧node ID均保留。新增75纯/负向
契约、2个Bundle/Monitor契约、6个schema契约和1个真实DUT场景；模型/框架门禁
2588PASS（189.71秒），旧DUT兼容60PASS（117.42秒）。资格、兼容、门禁及全量
均为同一个2042文件epoch，64worker收据与1492份产物hash逐一核对。336个功能点
全部执行，**318PASS/16FAIL/2XFAIL**，旧335点的逐点状态完全不变，只增加091的
一个合格PASS，不按两个缺行或六条采样义务拆成多个功能点。

BPU原生诊断为**33661/46541（72.33%）**，只比前一完整诊断多上述两个DA键，
逐键等于单PASS资格，两键各发生4次；`v_line`仍2387/8236，不与原生DA混用。
十DUT零旧键损失，其余九个命中集合、全部分母及构建provenance完全不变。
SC336/TAGE120、BPU写缓存120局部守卫分类及PHR13局部+1404条件键均原样重验，
不删分母、不填功能PASS。RTL/DUT/SDK和五份正式根报告未改，失败全量不发布。

v1因上述“准备不能提前记reached”的自查修正而主动中断，不作为完整结果。
它的约8.1GiB原生临时dat已删除，日志仍保留；这部分可以重跑生成。最终证据
只取v2本次完整集合，不拼接v1或历史覆盖。

1169份本次功能输入只合并一次（135.92秒），
当轮FAILED / NOT acceptance功能诊断
为319组、298满目标。全部旧组比例及原21个未满实例完全不变；两组新事件各6/6。
required schema120→122；功能点通过数、功能事件覆盖和原生行分别报告。

### 066双向反基预测：先声明来源，再验证实际选择和学习效果

在下面NT-over-T资格之上，新增
[双向语义程序](../bpuverify/bpu/case/early_positive.py)，仍强化同一个066，不新增
功能ID，也不替换原高索引程序。真实最终隔离资格
`owned-early-positive-qualified-20261015-v1`为1PASS：场景5.17秒、pytest15.14秒，
两个组各20条reached/checked义务完整。它不是全仓验收，完整生产结果单独报告。

新的事件是**有效T provider推翻NT base，选择较早conditional，而非较晚direct
fallback**；之后必须是这个命名consumer自己的S3反馈使useful增加，并在下一次
完整actual比较通过后确认。它与NT选择较晚分支是不同的选择结果，但共用同一套
独立Main/Ahead/MicroTAGE算法、完整历史和时序模型，不另写寄存器镜像oracle。

准备仍从真实reset和正常分支发现开始，先完成NT方向的实际证明。正方向候选来自
此前原始S3来源的T分配，需先在下一actual边界确认，记录不可变owner、snapshot、
key/tag/position及useful。**在驱动返回之前**冻结所有仍有效、可增加useful的候选，
随后通过另一真实短历史将同一个Ahead owner变成强NT，逐一检查声明的entry/useful
没有改变。只把Main改为强T时，fast learners关闭，并确认旧offered/learning和待
比较effect已成熟；不是重置或丢掉未完成义务来切换检查模式。再启用后，独立最高
provider优先级决定预期，命名公开receipt必须精确对应已声明候选和已比较S3来源。

最初资格实验失败在测试约束而非RTL：把“最早的低表seed”误当成唯一允许的
provider。连续oracle比较仍正确，实际语义返回由更高表候选胜出。现在的候选集合
来自独立模型的已确认历史学习，且在返回驱动前声明；不能读取DUT结果后选择一组
方便通过的期望，也不能要求低表无视真实优先级必胜。
[30项纯契约](../tests/bpu/scoreboard/test_early_positive.py)包括缺少NT证明、seed
未确认、错误分支/来源/时序/key、保护entry/useful变化、借用另一source的gain和
旧snapshot被重绑定等负向注入；这些synthetic actual不计DUT覆盖率。checked时间
不得早于实际效果确认时间，完成时保留两个方向的独立source证明。

更长语义程序还要求
[显式redirect来源关联](../bpuverify/bpu/checker/pipeline.py)：数值PHR encoding
能对应不同完整历史，不能猜最新/最老，或用actual低位修复golden。驱动前验证真实
published receipt并冻结payload；接受时比较cfiPC、target、taken、kind、action与
history，成功比较后才消费计划。待接受来源不可retire；reset取消旧计划。
[15项契约](../tests/bpu/scoreboard/test_redirect_ownership.py)覆盖编码别名、FIFO、
错误字段、失效owner、payload修改、reset，以及反馈/redirect同拍独立归属。这里
证明的是验证层source关联，不是全局FTQ物理容量、回收寿命或epoch合法性；旧的
无显式关联路径遇到完整历史歧义仍拒绝，绝不放宽成“同低位就能恢复”。

[单PASS原生增量](../results/owned-early-positive-qualified-20261015-v1/qualified-line-delta.json)
相对此前完整失败诊断为8键，均在`BypassShadowBuffer_1.sv`：4658/4659是一个
分配副本，4732/4735、4924/4927、5692/5695是三个真实候选的useful更新条件/
算术路径。不是8个新功能，不按这些坐标继续枚举；原生模块满行也不替代这种独立
选择与因果学习证明。隔离分子25788/46541不作为新的全仓分子或与历史拼接发布。

[最终完整复验](../results/production-owned-early-positive-20261015-v1/exit.json)
18069项、64进程446.51秒：**18044PASS、22普通FAIL、3strict XFAIL**，无ERROR/
SKIP/XPASS。精确FAIL/XFAIL集合和全部旧node ID保留；新增45项纯/负向契约、
6项schema契约与1项DUT场景。335功能点全部执行，317PASS/16FAIL/2XFAIL；066
只是被加强，没有重复计算一个新PASS点。59项旧DUT兼容全部通过（108.46秒），
含原高索引066、NT-over-T与044低tag场景；模型/框架门禁2505PASS（186.32秒）。
四轮均使用相同2035文件epoch，64完整worker收据及1485份产物hash复核无误。
20条因果义务的两个组均完整，required schema118→120；旧15位高tag普通FAIL
继续保留，不能因双方向代表场景通过而豁免。

当轮原生测量
BPU为**33659/46541（72.32%）**，净增8键与上述单PASS资格逐键一致。十DUT零旧
键损失，其余九个命中集合、所有分母与构建provenance完全不变。SC336/TAGE120、
BPU写缓存120局部守卫证明仍成立；PHR仍只有13局部键和1404个显式owned-checkpoint
前提下的键。这些分类不删原生分母、不填功能PASS，也不是全局FTQ合法性证明。
正式根报告、RTL、DUT与SDK均未改。完整BPU组合、其它branch组合及FTQ物理寿命/
epoch仍未完成，本轮失败全量不发布为验收。
1168份当前功能输入只合并一次（135.28秒），
当轮FAILED / NOT acceptance功能诊断
为317组、296满目标；旧组比例及原21个未满实例完全不变。功能点通过数、事件组
覆盖率和原生行命中独立报告，不能互相替代。

### 066自主反基预测：原来源选择较晚分支并确认useful效果

这不是新的功能ID。原066的高索引四节点程序与所有检查保留；新增
[语义程序](../bpuverify/bpu/case/early_opposition.py)补的是自主Main/Ahead/MicroTAGE
组合的判断资格：**有效NT provider必须推翻同一条件分支的T base**，选择较晚
direct fallback，并使其原S3来源得到正确的usefulness学习。先前044仅证明NT
provider学习/消费，base也可能同为NT，不能代替本事件。
当前MicroTAGE主模块已无原生DA缺键；其满行不证明该自主判断链已经验证。

程序只用一个半字PC、位置2条件回边与位置4 direct回边，正常学习出Main/Ahead和
NT provider。先消费强NT来源，再暂时关闭两种fast learner，正常把Main方向改成
T；Main-only预测流到达其自身短历史固定点后才重新启用Ahead。相同Ahead
bank/row/way成为强T，但MicroTAGE使用另一真实历史，原NT entry/useful必须不变。
随后只修改Main回到NT，原Ahead强T保持，再恢复原历史；新的有效S1必须选择
位置4、`ahead-direction`来源，并与独立Main一致，不靠后续repair掩盖错误选择。
实际published来源、完整原metadata及全部选择窗口持续比较，不从实际hit/index/
provider/表内容反推golden。

[历史与身份规约](../bpuverify/bpu/model/early_opposition.py)用真实边的贡献计算
短历史固定点，最大历史长度取已有UTAGE配置。它不是“固定等若干周期”：只在
真正接纳的独立Main消费者满足其12位历史前提时推进。位置2和4分别得到
`0xAA0`与`0x540`，低4位相同，但MicroTAGE历史不同。counter0本身还不够：
老snapshot可能已被新tag占用，故强来源还要求当前驻留entry与原read的
valid/tag/position/counter一致。纯程序在不同前序/流水相位下可以选择不同层级
provider；不通过约束实际输出选择一个更容易通过的provider。

期望仍来自`EarlyDirectionSources`的自有模型；新增的不是另一个寄存器镜像。
[Bundle](../bpuverify/bpu/bundle/early_direction.py)只读现有memory-direct布局，
增加两表共1024个useful cell。投影双方各自将完整向量编码为非零字典，零为
固定默认；不是按expected的key过滤actual。缺表/少cell拒绝，实际任意未触及
cell意外非零也会失败。所有有效response字段继续由独立资格决定。

禁用期间，RTL的Main override能改变裸hit寄存器，而没有有效Ahead响应来消费
这些位。模型不应为了比较这种非response而复制无效寄存器的更新树。现在只在
独立Ahead frame有效且enable时比较完整raw hitVec（包含没有conditional的lane）；
valid字段及全部useful状态始终比较，不使用actual valid/hit掩盖错误。
既有15位tag高位失败仍保留，不因此把disabled或wrong-tag当成合格预测。

[checker](../bpuverify/bpu/checker/early_opposition.py)保留原S3 fastTrain对象与
checkpoint owner的身份关联。useful-increase必须来自已经通过coherent S3比较
的反base token，不能因为恰好同一index写入就给分。模型本拍产生的effect先形成
待确认义务；**下一完整actual状态比较通过**后才登记效果，不能用模型自证RTL
已经写入。命名consumer、原始各snapshot不变和逻辑学习成熟全部完成，才关闭
14条checked。八条是已有学习链前提、六条是本次方向/来源/效果义务，不是14个
新功能点。验证source的显式retire不是硬件FTQ commit。

新增33项纯模型/负向契约通过，包括完整自有程序、错误分支位置/目标/种类/
source、过早来源、额外repair、丢失反馈owner、未到actual确认边界、旧快照被
替换、有效/禁用状态下的无关useful损坏、残缺向量及live-tag身份检查。
真实最终资格`owned-early-opposition-qualified-20261015-v1`为1PASS，pytest
14.04秒、场景4.03秒；14条reached/checked均完整。旧DUT兼容58PASS，含原
高索引066及044低tag场景；模型/框架门禁2454PASS、175.25秒。三轮相同2027
文件epoch，生产required schema116→118，不修改RTL、DUT、SDK或XFAIL范围。

[合格原生增量](../results/owned-early-opposition-qualified-20261015-v1/qualified-line-delta.json)
相对此前完整诊断新增11键：下层`BypassShadowBuffer.sv:3890/3891`；上层
`BypassShadowBuffer_1.sv:4730/4731/4922/4923/5690/5691/6004/6005/6007`。
八键为少量真实历史所触及的分配副本，三键为既有useful cell的更新/保持路径，
不解释成11个新功能，也不沿这些cell展开遍历。隔离原生分子不是新全量；后续
完整回归的全部命中、旧键损失及失败集合独立复验。

[最终完整回归](../results/production-owned-early-opposition-20261015-v1/exit.json)
18017项、64进程501.44秒，17992PASS/22普通FAIL/3strict XFAIL；无ERROR/SKIP/
XPASS。旧22FAIL、三XF及所有旧测试ID的精确集合保留。335点全部执行，317PASS/
16FAIL/2XFAIL。64收据、1493产物hash及终态2027文件epoch验证一致，四轮最终
epoch在当轮相同；后续源码与最新完整复验见上节。BPU诊断33651/46541比此前完整多11键，**逐键
等于上述合格单场景增量**；十DUT零旧键损失，其余九个命中集合、全部分母和
构建provenance完全相同。未把失败全量、隔离分子或历史并集发布为正式验收。

1167份当前功能输入只合并一次，135.10秒；
当轮FAILED / NOT acceptance功能诊断
315组中294满目标，新两组各14/14；全部旧组比例及原21个未满实例不变。功能组
分母、功能点分母及原生DA分母不互相替代。RTL、DUT、SDK及五份正式根报告均未改。
本轮总耗时高于前轮453.73秒；最长既有aging场景自身由424.10降至417.78秒，
新场景隔离刺激4.03秒，不能据此断言总耗时变化的调度原因或宣称本轮加速。

该轮仅新增NT provider对T base的自主资格；相反极性的后续资格见上节。更多branch
组合、全部预测器与完整FTQ物理寿命/epoch仍未完成，不能据此关闭完整BPU模型。

### 044条件Ahead/MicroTAGE自主组合：独立标签与原始路径训练资格

在非条件`AheadSources`之上增加
[EarlyDirectionSources](../bpuverify/bpu/model/early_direction_sources.py)，复用独立
`UtageReference`而非集成shadow monitor采到的写命令。它拥有两张表、完整15位tag、
方向/useful、在途更新及不可变读取；正常分支发现、已解析方向和自有Main最终选择
是学习事件，DUT hit/provider/metadata/表内容不进入oracle。诊断中的实际read-tag
只出现在失败上下文，不能反向初始化模型。

四类来源分别保存：

- **读表索引历史**：winning redirect、S3、S2或原S1祖先，不能使用更新后目标历史。
- **标签上下文**：正常匹配用原S1历史；S2/S3重放用相应老token的历史及保留读取。
- **原始匹配位置与呈现位置**：重放保留原读取的匹配位置，不能随当前Ahead布局重配。
- **可训练路径**：S1真实接纳时冻结prediction，按该次early预测的end-position裁掉
  后续条件分支；不能拿S3/Main更晚的end-position放宽资格。

S3 fastTrain注册offer与下一周期enable准入分开处理。暂停后逻辑学习成熟不等于
shadow已经写入SRAM：MicroTAGE持续读表，同bank可合法地长期推迟物理退休。
`main_pending`不把这种待服务的SRAM义务伪装成无限settling等待。旧snapshot必须
保有原checkpoint对象身份，显式retire/reset后不能借用，即使PC/history数值相同。

[静态Bundle](../bpuverify/bpu/bundle/early_direction.py)只读现有memory-direct YAML，
[projection](../bpuverify/bpu/checker/early_direction.py)按独立模型定义的资格比较，
不以实际valid/hit掩盖坏payload。检查raw hitVec、有效provider的方向、原S1 metadata
与合格原S3 metadata、索引和全部19个history folds；当前路径输出、修复和source
编码继续由自主pipeline比较。没有VPI、内部写、DUT/SDK重建或框架补丁。

[场景](../bpuverify/bpu/case/early_direction.py)先正常发现位置2的条件回边，消费真实
Ahead条件预测，再单独resolve该来源为NT。之后从**新的**Main消费者发现位置4的
direct fallback，避免把first-mispredict之后的分支当作同一batch中的有效发现。
自然流继续产生原来源fastTrain，直到一个新S3 receipt消费独立分配出的NT provider。
固定等待、edge和协程编排不出现在case；环境按真实状态完成并冻结wait命中的token，
不会在异步wait恢复后再读取已变化的`last_cycle`。

这里证明的是**负向provider学习及消费**，不是已经证明provider反转了Ahead基预测：
该次Ahead base可能也已NT。两类地址只区分完整tag的高位是否参与，不枚举bank/set。
既有044身份不变；八项reached/checked义务每类独立报告。只有实际新消费者、原始
快照不变及逻辑学习成熟全部通过，才一次关闭该类checked，不用期望分配自证通过。

`owned-early-direction-final-20261015-v1`中，低tag正对照PASS；高位tag场景普通FAIL。
失败tick500中，模型原读取为`tag=0x4000,position=2,counter=3`，实际只读tag为
`0x00`；索引`(0,320)`、全部history、位置、provider payload和counter均一致，
raw hit与metadata hit预期1/实际0。配置
`XiangShan/src/main/scala/top/Configs.scala:139–140`要求15位tag，
`utage/Parameters.scala:55`却固定`MaxTagLen=8`，生成
`rtl/bpu/MicroTage.sv:246`为`reg [7:0] a2_predRead_0_tag`。完整tag保持不截断；
这与独立UT已有宽度差异同类，不修RTL、不新增XFAIL，也不排除失败地址。
低tag两个组各8/8；高tag reached5/8、checked0/8，不能合并称完整044通过。

新增55项纯模型/投影/负向契约包括两类完整独立程序、原source身份、路径截止、
四类历史祖先、跨后续学习的冻结metadata、enable注册准入、错误actual provider/
counter/hit/metadata、错来源与不完整完成，以及monitor先推进再交付wait的竞态。
纯模型全部通过不替代真实DUT高位失败。

最终[模型/框架门禁](../results/owned-early-direction-gates-20261015-v1/summary.json)
2415PASS、171.16秒；[旧DUT兼容](../results/owned-early-direction-compatibility-20261015-v1/summary.json)
56PASS、80.54秒。单独低tag类1PASS，相对此前完整诊断
[合格增量](../results/owned-early-direction-control-qualified-20261015-v1/qualified-class-line-delta.json)
为6键：`BypassShadowBuffer_1.sv:4986/4987/6002/6003/6010/6011`，分别是上层
useful bank1/row81、bank2/row80及row81的分配选择与初始化，并非6个新功能。
隔离25218/46541不是新的完整分子。

[最终完整回归](../results/production-owned-early-direction-20261015-v1/exit.json)
17977项、64进程453.73秒，17952PASS/22普通FAIL/3strict XFAIL，仅新增高位类
普通失败；原21FAIL和三XF的精确集合均保留。335点317PASS/16FAIL/2XFAIL，
044不能因其它三个子场景通过而变PASS。64收据、1487产物及终态2020文件epoch
核验一致，所有此前node ID保留。BPU诊断33640/46541比此前完整增加8键，包含
上述6个合格键及未获PASS类资格的7034/7035；后两键不记合格提升。十DUT零旧键
损失，其余九命中集合、分母及构建identity完全相同。未发布失败完整报告，也未
将任何选测分子或历史并集写入正式五份根报告。

1166份当轮功能输入仅合并一次（134.07秒），
当轮功能诊断
明确标FAILED/NOT acceptance。313组中292满目标，全部旧组的覆盖比例完全不变，
原19个未满实例仍在，仅增加高tag reached/checked两组未满。四个新组进入生产
required schema112→116；缺类、少一规则或有普通FAIL都不能发布。功能组完成率、
功能点通过率及原生DA命中分别报告，不相互代替。
本组合仍未包含TAGE/SC/ITTAGE/RAS、CommonHR和完整FTQ物理寿命/epoch，不能称
完整BPU模型已完成。非条件`AheadSources`仍主动拒绝conditional；新profile单独接纳。

### 015/019自主Ahead/Main组合：提前读、原来源学习与纠正重放

这次补的是独立组合oracle，不是将4926个Ahead counter物理缺键拆成功能点。
已有015/019原场景保留；新增一个正常双边间接分支程序强化它们，功能ID仍335。
[AheadSources](../bpuverify/bpu/model/ahead_sources.py)组合已有独立AbtbReference与
MainBTB模型，自有PHR/checkpoint和流水线token仍由PipelineReference维护。MicroBTB
算法也保留，但本真实DUT程序将它关闭以隔离Ahead来源；不是已验收全部预测器组合。

关键是**Ahead读取的索引来源不是当前匹配PC/history**。模型从winning redirect/
S3/S2或当前S1的自有旧history推导四位特征；发起提前读取，随后将旧读内容对新
目标做tag匹配。S2纠正重匹配旧frame，S3纠正重匹配原replay read；不能重新查看
此时已变化的SRAM或改用新路径history。S1真正接受时保存不可变frame及当时enable，
S3 fastTrain再由该frame和自主最终决策产生完整反馈。实际index、hit、counter、
fastTrain metadata或写回均不进入golden。Main公共反馈仍必须绑定原始准确来源。

公开预测、原S3 metadata及S1 source编码持续比较；Ahead结果/metadata、MicroTAGE侧
当前编译接口实际暴露的valid/taken/type/strong字段、完整fastTrain payload和原
Ahead metadata由同一coherent snapshot比较。position/action同时在Ahead结果及
metadata检查；当前编译的MicroTAGE侧接口不包含这些字段，不伪造接口或加内部写。
所有观察只用既有memory-direct YAML，未改SDK或重建DUT，无VPI/内部注入。

程序正常学习PC→OTHER和OTHER→PC两条间接分支，第二个入口不按bank选择，路径
自然产生不同的提前读上下文。允许预测/fastTrain自然重叠，直到两个真实S3来源
证明两边都由Ahead S1命中；不是先向表注入预期内容再检查命中。随后保持一个真实
OTHER旧Ahead来源，暂停读服务期间正常更新Main的间接目标，恢复后必须得到自主
S3目标纠正、原replay read对新目标重匹配，以及新目标的真实miss消费者。原来源
metadata不能被后来的学习修改。最后关闭Ahead，使用**刚得到的新检查点**恢复，
要求Main-only S2 fallback及准确repair窗口，不重复使用可能已过物理寿命的旧anchor。

七个reached/checked义务为双边Main发现、原S1来源fastTrain、双边Ahead消费者、
旧读跨Main更新、S3目标纠正、replay新消费者、禁用Ahead后的Main回退。checked
全部等到最后一个真实消费者和义务退休；仅看到旧命中、一次提案或模型状态不能
关闭。两组加入生产schema，110→112；不扩大物理分母，不新增同义功能ID。
case只表达发现、运行、改目标和消费；driver/monitor/clock/有界等待仍在支持层。

当前组合有明确能力边界：ABTB enable也打开MicroTAGE。由于其条件学习组合尚未
完成，本profile对条件早期预测/反馈明确抛NotImplementedError，而不是把已学习
MicroTAGE当作永远miss。其它TAGE/SC/ITTAGE、调用返回和完整FTQ epoch/寿命仍需
额外组合。非条件分支的新证据不豁免这些缺口，也不替代018的高位跨区域修复合同。

新增71项纯模型/合成负向契约包括双边DIRECT/INDIRECT自然学习、Ahead读与当前PC
普通查表的区别、旧history输入、外来/复制/释放checkpoint、输出valid不能
掩盖错误payload、完整fastTrain和原metadata、错来源/槽填充/方向/type/action、
重新读SRAM冒充replay、错误新消费者/额外repair/metadata重置、禁用后错误回退及
提前credit。纯测试不贡献DUT功能或原生覆盖。现有循环、跨区域目标及所有旧场景
会在完整生产复验中保留，而不是把这一个新增case作为整个模块通过的证据。

最终[隔离资格](../results/owned-ahead-qualified-20261015-v1/summary.json)1PASS，
[兼容选测](../results/owned-ahead-compatibility-20261015-v1/summary.json)56PASS、4进程
85.87秒；[模型/框架门禁](../results/owned-ahead-gates-20261015-v1/summary.json)
2348PASS、4进程176.20秒，完整保留上一2271项并增加71项纯契约及6项schema门禁。
三轮终态epoch均为2010文件、证据完整；RTL/DUT520个文件、SDK36文件均未改。

严格隔离[差分](../results/owned-ahead-qualified-20261015-v1/qualified-line-delta.json)相对
正式基线与最近完整090都只有1个新键：`ReplacerState_4.sv:322`，为MainBTB替换
状态的物理set33写入赋值。它是正常双边程序的伴随路径，不是新的替换功能或新ID，
也不为该坐标增加遍历。主要增益是把015/019的来源、学习、重放、消费者及禁用回退
交给独立组合模型检查；完整生产增量必须另行复测，不拼接隔离分子。

[完整生产复验](../results/production-owned-ahead-20261015-v1/exit.json)重新执行全部
17908项、64进程、445.10秒：**17884PASS、21普通FAIL、3strict XFAIL**，无ERROR/
SKIP/XPASS，FAIL/XFAIL精确集合与完整090相同。335功能点全执行，318PASS/
15FAIL/2XFAIL，不新增015/019的同义通过点。64收据、1478个产物hash、collection/
JUnit/controller及终态2010文件epoch均复核。原生BPU为**33632/46541**，恰新增
上述Main替换状态1键，与最终资格逐键相等；十DUT零旧命中损失，其余九个命中
集合、所有分母和构建provenance不变。失败刺激包含在诊断内，正式根报告不替换。

当轮完整SDK功能诊断
明确标为FAILED/NOT publication；1164份功能输入仅合并一次，309组中290满目标，
新增两组均七条完整，原19个未满实例集合不变。局部SC336/TAGE120、写缓冲120
及PHR13键/1404有前提键的分类均重验，不缩分母或给予功能豁免。真实差异、条件
MicroTAGE自主组合及完整FTQ合法性仍开放，不能把本轮成功称作完整BPU模型完成。

### PHR检查点余数合同：不等于任意metadata合法性

`PathHistoryReference`的cursor只由自有taken事件数推导。当前宽度52、步长2，
reset、hold、taken和恢复自有checkpoint都保持偶数value；flag仍可跨两个相位。
本轮新增纯测试检查整个闭包，并拒绝复制、外来、旧reset epoch和已释放来源。
这仍是抽象逻辑history模型，不是逐个PHR寄存器复刻，也不证明任意旧checkpoint
在物理环形存储中仍然存活；完整FTQ生命周期仍缺。

该合同解释Phr的1417个缺键中的1404个，但必须显式假定复位后使用同epoch真实
检查点。另13个才是不依赖输入约束的局部矛盾。新只读工具默认仅分类13，显式
`--assume-owned-checkpoints`才另外分类1404；精确核对所有指针写者/循环offset
与实际native producer/arm/span。零计数、生成行号或模型不变量本身都不是整个
硬件无条件不可达的证明。现有raw覆盖和分母完全保留，不采样证明来填功能bin。

新增39项纯模型/源码/native证据负向契约；完整门禁2271PASS、真实DUT兼容16PASS，
原模型/用例/RTL/DUT/SDK文件未改，仅加四个诊断和测试文件。335个功能ID保持，
不因035–038已验证的恢复需求再造同义点；本轮原生增量0。详见
[完整归因、复验命令和证据](coverage-gap-triage-20261013.md#2026-10-15大缺口再归因phr余数约束与物理副本只读)。

### 相邻双owner学习085：两份旧读必须合成，而非丢失一次更新

新增`BPU-INT-085`针对集成TAGE写缓冲残差中尚未验证的**相邻、双owner、旧读
转发学习**组合，而不是按生成RTL的slot/bank复制功能点。旧025每轮等待更新并
捕获新metadata；旧026虽相邻接受，但每笔只更新一个不同owner，都不能证明两份
旧counter同时进入流水线后，每个owner的两次更新均得到保留。

[纯语义程序](../bpuverify/bpu/model/tage/forwarding.py)从正常Main分支发现、基础方向
学习和两次独立TAGE分配开始，建立同历史下较早NT counter2、较晚T counter5的
两个最长历史provider。准备过程中每个mispredict位置也与自有最终预测对照；不能
将较早实际已错的taken分支标成正确、再把错误随意记到较晚分支。NT前缀及T尾项
表达执行顺序；只在准备Main方向时有意暂停TAGE学习，目标burst时两者均真正开启。

[case](../bpuverify/bpu/case/direction_forwarding.py)随后捕获两个不同的真实S1/S3
来源。PC/history数值与读内容可以相同，但checkpoint/token对象必须不同，且两个
来源均在反馈前完成。环境先登记两份原始来源及完整反馈，再一次提交给生产
AsyncDriver；不在case中创建task/gather、操作边沿或写引脚，也不等待前一笔更新
提交后才发送后一笔。由monitor确认两笔实际接受相隔一个周期，而非把排队当接受。

每笔均为较早NT、较晚T的完整已跟踪路径：两份旧counter2/5必须合成到0/7，而非
错误地各用一次旧值只得到1/6。自主history/Main/TAGE/pipeline模型逐周期比较
所有定义输出，反馈metadata只作为待比较actual。新消费者必须保有原provider身份，
完整纠正窗口只允许S2较晚T、不得多出S3反转；再用新0/7来源提交饱和反馈，第二个
新消费者检查不回绕、不破坏另一owner，之后才完成全部六条checked义务。

六条义务为不同checkpoint的旧读、相邻完整路径反馈、对立双owner学习、负向转发
至零、正向转发至七、新鲜饱和保持。两组加入生产门禁，required schema94→96，
功能ID329→330；不改原生46541分母。相邻接受凭据由确切来源持有至显式释放，
不再依赖容量8的近期诊断deque，因此批量验证不会被诊断日志窗口截断；reset及
retire均释放凭据。这是语义事件回执，不导出逐周期JSON轨迹。

[最终隔离验收](../results/direction-forwarding-qualified-20261015-v1/summary.json)
为1PASS、12.28秒（刺激2.23秒），六条reached/checked各100%；
[兼容选测](../results/direction-forwarding-compatibility-20261015-v1/summary.json)
为42PASS、4进程56.36秒。纯模型与合成负向契约另有42项，覆盖错误source/旧读、
不相邻或不完整反馈、只保留一次/一侧学习、provider转移、多余repair、无接受/
旧饱和来源及提前结束；这些测试不计真实DUT覆盖。完整生产另行重跑，不将隔离
集合拼成新的完整分子。RTL、DUT、SDK均保持不变；完整FTQ epoch/nonce及其它
预测器组合仍不由本profile声称已完成。

[最终严格差分](../results/direction-forwarding-qualified-20261015-v1/qualified-line-delta.json)
相对历史正式完整基线新增53个DA键：`Tage.sv`1、`WriteBuffer_8.sv`52。与候选
增量集合逐键相同；其中Tage6805及10个写缓冲键已由近期合格场景命中，另外
**42个写缓冲键**在上一完整生产v2仍为零。52键包含条件头和伴随赋值，不能冒称
52个不同写入效果或53项功能；功能资格来自两个完整输入、双owner新结果及最终
consumer的独立比较。隔离25804/46541不是新的完整项目覆盖分子。

[完整框架/模型/负向门禁](../results/direction-forwarding-gates-20261015-v1/summary.json)
为1946PASS、4进程131.81秒，完整包含上一轮1897项，另加42项新纯契约、1项
超过诊断deque容量的归属回执契约及6项新增schema门禁；非用例枚举或DUT覆盖
数量。三轮终态evidence完整、integrity为空，最终源码epoch一致，根正式报告不变。

[随后完整生产](../results/production-direction-forwarding-20261015-v1/pytest-artifacts/evidence.json)
重新执行全部17498项：17474PASS、21FAIL、3XFAIL，64进程499.61秒。失败及
XFAIL集合逐项等同上一完整v2；330功能点全执行，313PASS、15FAIL、2XFAIL。
完整collection/JUnit/controller一致，64份收据和1477产物hash复核通过，最终
epoch一致。当轮BPU原生测量为
33558/46541，相对v2精确新增上述42键、无额外/缺失键，十DUT零旧键丢失。
因为保留21个既有RTL失败，这仍是未发布的失败全量诊断，不替换正式根报告。
当轮SDK功能诊断
保留失败标题，功能293组中274组满目标；新增004/085四组均满，原19个未满组仍保留。

### 读优先服务086：接受、保留、提交和可见性分开验证

本轮在085之后增加`BPU-INT-086`，计划330→331。其问题不是再访问一个bank，而是
同一bank中**不同历史、相同分支owner**的学习义务不能互相覆盖。030/031检查需要
SRAM重读的反馈被预测阻塞；085只在读空闲窗口完成相邻学习，都不能证明不需要
重读的强provider反馈在持续预测下被接受、延迟写回并保持正确版本。

[纯模型程序](../bpuverify/bpu/model/tage/service.py)通过原checkpoint直达PC与经过
另一个真实checkpoint返回PC的两条路径建立A/B历史，各自有较早NT counter2及
较晚T counter5。Main分支记录是共享的，TAGE状态/快照则由自己的历史决定。
四次不同来源按A/B/A/B真实查询顺序采集，全部在反馈前完成，不复制同一receipt。
独立学习出的直接跳转流随后占住同一SRAM bank；这不是按物理set遍历，而是两种
逻辑历史必须能同时保留的最小区分前提。

准备脚本也不能把A的输入标签照搬到B：A已经降低全局弱base selector，B的弱T
provider此时会直接取得资格，进一步增强它是**正确反馈**，不是mispredict。
纯测试逐次用自有最终决策核对错误位置，已经修正最初照搬导致的不真实错误标签；
最终DUT资格在修正后重跑，不沿用早期候选的PASS来证明当前程序。

[环境](../bpuverify/bpu/env/direction_service.py)一次提交四笔完整NT前缀/T尾项输入，
仅等发送接受及模型学习成熟，不调用committed drain提前停流。四笔均实际相邻
接受，且各接受时都有公开预测接受；整个持有窗口的实际读mask必须持续占用该bank，
训练读端口始终不请求reread。自主history/Main/TAGE/pipeline模型持续运行；实际
读mask、ready及write payload只作为actual，不决定golden学习、hash或成熟时间。

独立版本模型应留下四份(row,tag,owner)义务，分别已合成至0/7；实际两个写端口
的完整front payload必须与独立服务顺序相符，ready均0且连续保持。保持读取时再
在A、B各发一个新查询，二者均须消费旧SRAM值2/5；只看到pending或只检查一个
历史都不能关闭checked义务。只有这两个consumer成功后，才释放预测读取。

[monitor](../bpuverify/bpu/monitor/tage/service.py)复用SDK `ReadyValidMonitor`，
由其在驱动稳定阶段保存不可变写payload、在对应接受边沿确认`Transfer`。原
YAML已经具有这些memory-direct IO及bankMask投影，无需VPI、internal写入、DUT
重建或新的底层时序适配。每个owner必须按独立服务顺序接受A/B两份完整写回，
总共四次；漏、早到、重复、错row/tag/counter/valid都失败。最后在原A/B历史各有
一个提交后的新消费者，验证0/7、provider归属、完整S2/S3纠正窗口及没有多余pending。

六条reached/checked为不重读反馈接受、预测/反馈并发、四份历史/owner结果保留、
两历史旧值消费、逐义务真实退休、两历史新值消费。两组加入发布门禁，required
schema96→98；第一次旧consumer或第一次新consumer都不提前关闭需要两历史的义务。
case只表达准备、发送、旧值消费、释放、新值消费，采样/任务/异常清理在支持层，
没有固定settling等待或逐周期JSON导出。模型/合成负向测试不作为DUT命中证据。

初始单历史对照PASS但相对上一完整生产净增0；它只说明延迟服务，不证明历史
隔离。双历史最终资格和差分单独记录，不用前者替代后者，也不将生成条件头当成
独立功能。完整FTQ nonce/epoch与其它预测器组合仍未完成，RTL/DUT/SDK不改。

[最终真实DUT资格](../results/direction-service-qualified-20261015-v1/summary.json)
为1PASS、14.91秒（刺激4.88秒），六条reached/checked均100%。
[严格原生差分](../results/direction-service-qualified-20261015-v1/qualified-line-delta.json)
相对同一历史正式完整基线新增83个DA键：Tage1、WriteBuffer_8共82。其中53键已
在上一完整085生产诊断命中，另外**30个WriteBuffer_8键**仍为零；与候选v2增量
集合逐键相同，但最终证据来自修正错误标签后重新运行的源码。新增键包含保留
记录1的row/tag/counter与未写回命中的选择/伴随赋值，既有物理分母不变；不是30项
功能、30次真实写入或必须再遍历所有bank。四个完整提交与两组新旧consumer才是
功能资格，行计数本身不足以证明它。

[兼容选测](../results/direction-service-compatibility-20261015-v1/summary.json)
为47PASS、4进程61.58秒，除上一轮42项外，还包括086及旧030/031同bank重读
阻塞、跨历史和跨PC并发，保留“强provider无需reread”和“需要reread时必须阻塞”
两个相反合同。
[完整框架/模型/负向门禁](../results/direction-service-gates-20261015-v1/summary.json)
为2012PASS、4进程132.76秒，完整保留上一轮1946项，另有60项新纯契约及6项
schema门禁。新纯契约从语义程序独立建立四个pending版本，验证全局selector导致
的实际错误位置、两个历史的双向转发/可见性、错来源/不相邻接受/写载荷/漏多写/
顺序/早期回收/旧消费者/单历史假闭合及不重同步；monitor负向检查还覆盖SDK
Transfer快照不可变、取消、部分启动失败、清理失败不掩盖首异常和watcher释放。

三轮终态evidence完整、integrity为空、最终源码epoch一致，均无ERROR/SKIP/XFAIL。
RTL/DUT520个冻结文件及SDK与上一轮身份一致，正式五份根报告不替换。本轮没有
重新执行全量，不能把隔离30键简单加到33558而称新的完整分子；最近完整生产仍是
085的17474PASS/21FAIL/3XFAIL、330个功能点测量，当前计划则为331。已有普通
RTL失败与19个历史未满功能组继续保留，整体目标未完成。

### 满容量命中087：容量边界不能退化为多地址枚举

`BPU-INT-087`新增的是**容量已满时更新原逻辑项仍须保留其它义务**，不是再增加
两个物理坐标。复用086的自主历史/Main/TAGE模型和读服务环境，按配置的每owner
四条保留容量，建立四种真实历史A/B/C/D、各两个相反方向provider。五个原始来源
按A/B/C/D/A查询顺序捕获，均持有旧2/5，且每份checkpoint不同；正常反馈均为完整
NT前缀/T尾项，没有伪造metadata或从实际状态重新初始化模型。

不同地址不等于不同历史：最初选取的第四条路径`PC+0x180`经自有PHR折叠后与A
完全相同，纯模型在准备阶段就拒绝了这项前提。最终采用`PC+0x200`路径；独立
计算的四份context及T3 row均不同，之后再与真实DUT逐周期对照。选择来自模型
历史语义，不是枚举DUT地址直到行覆盖率上涨，也不将地址标签当成覆盖事件。

五笔不重读反馈在连续同bank预测中相邻接受。静态
[bundle](../bpuverify/bpu/bundle/tage_service.py)只在本场景增加八个dirty及两个完整
incoming payload的只读memory-direct绑定；原086默认不采这些字段。实际的每个
incoming row/tag/valid/counter均须符合原来源独立计算的顺序。第五笔到达时，实际
八个dirty必须都为1，且它必须命中A原来的两个逻辑键，不能偷偷变成第五个新键。
dirty仅是actual资格检查，不决定golden的容量、成熟、hash、内容或推进。

[checker](../bpuverify/bpu/checker/direction_capacity.py)必须保留八份待提交义务，
没有dirty义务被覆盖；闭式预期为A学习两次得到0/7，B/C/D各一次得到1/6。读取
不释放时，四种历史各有一个新consumer仍须看到旧2/5。只完成两种历史不能关闭
前四条checked。释放后SDK monitor确认每owner四个、总计八个完整写回，顺序及
row/tag/counter/valid逐一比较；之后四种历史分别消费自己的新值及完整repair窗口，
没有多余写回/pending才关闭最后两条checked，释放原来源凭据。

六条reached/checked分别是全部容量实际占用、满容量逻辑命中、八份结果保留、
四历史旧值消费、八份真实提交、四历史新值消费。公共driver接受本身不为前两条
记credit。两组加入发布门禁，required schema98→100，计划331→332。case只有
准备、发送、旧消费者、释放、新消费者；无边沿、固定等待、task/gather或私有框架。
无背压full miss可能覆盖dirty victim是另一个合同，本项**没有**覆盖或豁免该边界；
完整FTQ nonce/epoch和其它预测器自主组合仍未完成。

[最终隔离资格](../results/direction-capacity-qualified-20261015-v1/summary.json)
为1PASS、19.65秒（刺激9.66秒）；
[兼容选测](../results/direction-capacity-compatibility-20261015-v1/summary.json)
为48PASS、4进程67.88秒；
[完整模型/框架/负向门禁](../results/direction-capacity-gates-20261015-v1/summary.json)
为2057PASS、4进程138.26秒。新增35项容量纯契约、2项可选bundle绑定、2项monitor
选择契约和6项schema门禁，原2012项全部保留；纯测试不贡献真实DUT行覆盖。
三轮源码epoch一致、收据与产物hash完整，正式五份根报告保持不变。

[严格原生差分](../results/direction-capacity-qualified-20261015-v1/qualified-line-delta.json)
相对正式历史基线新增87键：Tage1、WriteBuffer_8共86，最终与候选集合逐键一致。
其中34键在上一完整085仍为零，但仅20键不在086的合格集合；086也有16键未被087
覆盖。两场景互补，不能以87替换83、重复累计34+30、或将物理记录2/3的20条伴随
赋值解释为20项功能。086与087合格增量相对085的并集为50键，是否全部进入当前
完整分子须由新的完整回归独立确认，不拼接历史数据发布。RTL、DUT和SDK未改动。

[后续完整生产复验](../results/production-direction-capacity-20261015-v1/exit.json)
已独立确认：全部17611项，64进程、442.33秒，17587PASS/21普通FAIL/3strict XFAIL，
失败与XFAIL集合均与085完全相同。332功能点全部执行，315PASS/15FAIL/2XFAIL；
64份收据及1484个产物hash、collection/JUnit/controller及终态源码epoch均一致。
BPU原生**33608/46541**，相对085恰新增上述去重50键，十DUT零旧命中丢失，其它
九DUT集合不变。SDK诊断HTML汇总297组、278组达到完整目标，原19个未满组集合
不变；086/087四组均100%。该原生诊断含失败刺激，不是正式发布；五份根报告仍为
历史合格基线。详见[逐模块完整结果](coverage-gap-triage-20261013.md#2026-10-15086与087后的完整生产复验未发布)。

### 满容量新键088：被替换义务与新键初始化的独立合同

087只证明满容量命中旧key；`BPU-INT-088`增加的是容量已满时的**第五个新逻辑
key**。写接口没有背压，这个配置允许替换dirty victim，并不保证无限保留所有
已接受更新。不能把允许的容量丢弃当RTL错误，也不能把任意丢失纳入golden。

[独立程序](../bpuverify/bpu/model/tage/service.py)建立五种真实历史A/B/C/D/E，
T3 row/context各异，同PC、同bank、每历史两个相反方向owner。Main先共享学习至
0/3，A的旧TAGE值为1/6，其余四种旧值为2/5。五个不同checkpoint均在反馈前捕获。
相邻完整NT前缀/T尾项反馈使A产生实际待写0/7，B/C/D产生1/6，E再以新key换入1/6。
不要预先把A学到0/7再拿饱和保持填容量：数值不变可能抑制写请求，达不到前提。

[checker](../bpuverify/bpu/checker/direction_replacement.py)要求E proposal到达时，
实际八个dirty全为1，且两个被阻塞的完整front仍是A的0/7；五个完整incoming
row/tag/valid/counter按原来源独立比较，E必须不同于之前四key。只有这些实际
前提都满足，才为满新键事件记reached。独立版本模型按已规定的服务rank/tree
replacement预测恰好替换A的两个待写义务，保留E/B/C/D；不得读取DUT victim、
replacer或dirty来决定自己的丢弃、计数或新key初值。

新key的1/6与victim的待写0/7刻意不同，错误继承旧counter不能蒙混通过。所有五种
历史在持续读取时仍必须消费各自旧SRAM值。释放后SDK确认恰好八个完整survivor
提交，顺序为每owner的E/B/C/D，不能混入A、漏邻居或多出写回。随后五种历史全部
有新consumer：A保持其未提交的旧1/6，其余四种变为1/6；相同数值不允许替代不同
请求的PC/history/provider归属和完整repair窗口。最后才释放十份原/旧消费者凭据。

本轮还收紧086/087/088共用checker的中间credit：所有旧值消费者通过后，只关闭
实际接受/容量前提、新键或命中资格、旧值消费这三条，checked仅50%。保留全部
结果或只替代指定victim的规则，必须等**全部真实提交及全部新消费者**之后才关闭，
与最后两条一起达到100%。仅看front不能证明后面的版本未丢失。上文086/087首次
验收的四条提前关闭时机是旧记账；当前按此更严格边界复验，完整功能合同未削弱。

六条reached/checked为实际满容量、新键用自身counter、仅两条victim义务被替代、
五历史旧值消费、八survivor提交、victim/新键/所有邻居消费。两组纳入生产门禁，
required schema100→102，计划332→333。保留型ServiceProgram仍拒绝超过容量的
历史数；独立FullReplacementProgram显式描述不同的容量丢弃合同，没有全局打开
“允许丢失”。case不操作边沿、引脚、task/gather或固定等待，仍复用生产driver、
SDK monitor和自主history/Main/TAGE/pipeline oracle。RTL/DUT/SDK均不改。

真实DUT资格与新旧契约负向检查单独记录；相对最近完整086/087的严格原生增量为
**0**。相对更早正式基线的45键也全部已在最近完整运行命中，不能叫新增行覆盖。
这补上功能缺口，却没有覆盖新的DA键，说明“缺功能”和“缺行”不是一一映射。
本轮没有新的完整生产分子；上面的17611项全量属于088之前的源码。

[最终隔离资格](../results/direction-replacement-qualified-20261015-v3/summary.json)
为1PASS、23.95秒（刺激12.04秒）；
[兼容选测](../results/direction-replacement-compatibility-20261015-v3/summary.json)
为49PASS、4进程69.40秒，保留前48项并检查更严格的086/087 credit时机；
[完整模型/框架/负向门禁](../results/direction-replacement-gates-20261015-v3/summary.json)
为2098PASS、4进程146.14秒，原2057项全保留，新增26条语义/合成负向契约、9条
源证明传递契约和6项schema门禁。拒绝第五key伪装旧hit、实际未满/无victim结果、
错误counter seed、错误或超额丢弃、保留错误key、漏邻居、遗漏victim/新key消费者、
缺第八次提交及假关闭；所有旧消费者完成时checked只能50%，缺最终效果不提前满。

[严格差分](../results/direction-replacement-qualified-20261015-v3/qualified-line-delta.json)
与初始候选的45键逐键相同，均已被最近完整086/087命中。第一次直接把A预学到
饱和的纯程序没有形成两个overflow，已按写资格修正；没有以该失败程序声称full
miss。最终资格还增加了第五proposal时实际A完整front=0/7的直接验证，以及上述
更严格checked时机，不用早期PASS替代当前源码证据。三轮最终epoch相同、收据及
产物hash完整；RTL/DUT520个冻结文件、SDK36个文件及正式五份根报告均未改变。
普通RTL失败不扩大XFAIL；其它预测器自主组合、完整FTQ和其它未满功能组仍开放。

### 跨owner旧来源089：原metadata不是当前保留版本

`BPU-INT-089`对应集成WriteBuffer_8中尚未闭合的跨输入port/保留owner路径。
它不是把独立TAGE的prepared实际shadow快照移植到BPU，而是从自主MainBTB/TAGE/
history程序正常建立两条所有权时间线：原预测provider=5、旧way；当前同逻辑key
provider=4、相反way。两份值都来自各自独立生成的读快照，actual metadata只被比较。

[程序](../bpuverify/bpu/model/tage/migration.py)使用三个真实两跳历史blocker/
original/newcomer。路径delta `0x648`和`0xad8`来自七位T3行fold的零空间：它们
保持三者同bank/同候选row，但tag不同，不是把同一个历史贴三个地址标签。共同
恢复源可以改变具体row，DUT用例不硬编码row122，也不搜索actual地址直到命中。
独立纯程序检查真实路径、唯一tag和每步手算counter/useful；所有mispredict位置
均与原语义最终决策对照。

20步正常学习只需三个逻辑key，不必先铺满四表八项再枚举bank/depth。用自有随机
状态的allocation admission选定合法T3机会：blocker学到7/useful0，原key学到5/
useful0并保存真实来源；原key弱化到4后被newcomer替换，newcomer学到5/useful1；
再次分配原key时，唯一可替换的另一way被占用，原key以4/useful0迁移到相反way。
只在准备共享Main方向时暂停TAGE，目标反馈时两者实际开启。每个准备输入都要由
新consumer确认后才回收，原强provider来源则一直保留到最终检查结束。

不能用“旧miss再分配到另一way”代替这个前提：mispredict触发的SRAM reread会
重新找到当前provider，未必发生分配。目标事件使用原强provider的正确T反馈，
确实不重读SRAM，才能保留旧way和旧counter。完整输入必须仍属原checkpoint；
原TAGE metadata的旧5提出counter6，而当前保留版本4必须转发成5，不是直接写6。

[monitor](../bpuverify/bpu/monitor/tage/service.py)复用现有memory-direct Bundle、
`@on`和SDK ReadyValidMonitor，比较actual原port proposal的row/tag/valid/6，并
确认恰好一个完整写回到相反的当前owner、counter5。新消费者分别检查原key的新
owner/result、newcomer的counter5/useful1不变，以及已被替换blocker仍miss；完整
history、Main、TAGE metadata和S2/S3 repair由自主pipeline oracle持续比较。
原反馈的provider/base方向同为T，故不触发useful学习；这不是豁免独立TAGE026
的普通useful错归属失败，也不声称已经验证陈旧来源的useful重定向。

六条reached/checked为真实key迁移、原强来源无重读接受、旧way/counter proposal、
当前owner/counter提交、新owner消费者、邻居useful及被替换key的miss。checked
全部等待实际输入、proposal、SDK提交及三个新消费者；只看模型状态或一个端口
不关闭。两个方向各有独立的两组，共四组进入生产门禁，required schema106组、
计划334点；一边PASS不能填满另一边的覆盖组。只有两个逻辑所有权方向，不做
bank×depth×slot枚举，case也没有边沿、get/set、task/gather或固定等待。

最终真实DUT资格[旧way0](../results/direction-migration-qualified-way0-20261015-v1/summary.json)
1PASS、16.31秒及[旧way1](../results/direction-migration-qualified-way1-20261015-v1/summary.json)
1PASS、16.29秒；[兼容选测](../results/direction-migration-compatibility-20261015-v1/summary.json)
51PASS、4进程75.99秒；[完整模型/框架门禁](../results/direction-migration-gates-20261015-v1/summary.json)
2160PASS、4进程153.29秒。新增50项纯模型/负向契约及12项schema门禁，原2098项
全部保留；纯测试不贡献DUT覆盖。四轮最终epoch一致，收据/产物hash完整，RTL/
DUT/SDK及正式根报告未改。

隔离严格差分两方向相对正式基线各新增8键，均为WriteBuffer_8；相对最近完整
086/087则分别是8、7键，互不重叠，共**15**。旧way1的804–812包括完整key赋值和
实际counter更新，不能把7条伴随条件/赋值夸称7个功能点。两方向的完整复验如下，
不是把隔离15直接拼成分子。整体FTQ合法性及其它预测器自主组合仍未完成，现有
普通RTL失败继续保留。

[最新完整生产复验](../results/production-direction-migration-20261015-v1/exit.json)
执行全部17717项、64进程、443.72秒，17693PASS/21普通FAIL/3strict XFAIL，无
ERROR/SKIP/XPASS，FAIL/XFAIL精确集合与前一完整086/087相同。334功能点全部
执行，317PASS/15FAIL/2XFAIL；303功能组中284组满目标，19个未满组集合不变。
64收据及1476个产物hash、collection/JUnit/controller身份和终态1988项源码epoch
均已核对。088及更严格credit已一起重跑，不只测089后拼接以前的PASS。

BPU诊断原生**33623/46541**，相对086/087恰新增15个WriteBuffer_8键，逐键等于
两个最终隔离合格集合的去重并集。十DUT零旧命中丢失，其余九DUT命中集合完全
相同，分母均不变。WriteBuffer_8缺314，其中120个局部矛盾的原生producer证明
在本轮重新通过，仍有194个未分类。失败刺激包含在原生诊断内，正式五份根报告
不替换。详见[逐模块完整结果](coverage-gap-triage-20261013.md#2026-10-15089旧来源跨owner更新后的完整生产复验未发布)。

### 跨owner旧来源突发090：原快照固定，当前版本逐笔饱和

089只验证一次旧反馈，无法排除后续重叠反馈丢失、旧值覆盖新值或饱和回退。
`BPU-INT-090`继续使用同一独立Main/TAGE/history/pipeline模型，不另造一个以
actual write/dirty为推进条件的信号级golden。四次真实预测分别拥有不同token和
checkpoint，均在原provider为5/旧way时完成；随后才正常替换、保护邻居并把同
逻辑key重分配为4/新way。四份原metadata保持不变，不重复发送同一receipt。

[环境](../bpuverify/bpu/env/direction_burst.py)通过生产AsyncDriver一次登记并发送
四个原来源的正确T反馈；monitor独立确认四个相邻的真实接受。每个原强provider
都独立满足无需SRAM重读的资格，故原way提案始终是5→6；当前保留版本则应把
四次学习合成到**5、6、7、7**，全部路由到迁移后的owner。最后一笔检验上界保持，
不是再学习成6，也不能回绕到0。四笔是从当前4达到上界7后再保持一次的最短程序，
不是queue深度、bank数量或“多发几笔刷行”的参数。

当前配置下读空闲，独立模型的每个在途版本都应逐周期退休；SDK monitor因此确认
四笔相邻完整写回。输入接受、原提案、当前版本提交是三层不同事件，不能把enqueue
当接受，不能把提案6当最终counter，也不能只看最终7掩盖第四笔输入或处理丢失。
`DirectionBurstChecks`要求每个提案晚于自己的公开接受、每个提交晚于自己的提案；
连续性和完整payload分别比较。语义模型自己维护待学习/待提交版本，实际观察不
改变它的状态。未来若换成允许合并写回的硬件配置，需要另行声明可见性合同，不能
悄悄放松本配置的逐版本义务来回避差异。

三个新消费者还须分别证明原key为7/新way、邻居仍5/useful1、被替换key仍miss；
所有原metadata不可变，完整S2/S3修复由自主pipeline oracle持续比较。六条checked
全部等到四个实际输入、四个原提案、四个SDK提交、三个新消费者比较后才关闭。
两个方向各有独立reached/checked组，共四组纳入门禁，required schema106→110，
功能计划334→335；不按四个来源拆四个同义功能点。case仍只有准备、突发、消费等
语义动作，没有边沿、get/set、task/gather、固定等待或prepared内存初始化。

新增60项纯模型/合成负向契约检查两方向真实历史和5/6/7/7、重复receipt、漏输入/
提案/提交、错误来源/owner/payload、饱和回退/回绕、非相邻接受/退休、旧消费者、
邻居破坏、错误repair、第四份metadata被重置和提前credit；原50项089契约一起
重跑110PASS。它们不计DUT功能覆盖或原生行覆盖。旧普通RTL失败及完整FTQ、其它
预测器自主组合的缺口仍保留，不因本场景通过而豁免。

最终隔离[旧way0](../results/direction-burst-qualified-way0-20261015-v1/summary.json)
1PASS、pytest17.17秒，[旧way1](../results/direction-burst-qualified-way1-20261015-v1/summary.json)
1PASS、17.15秒；[兼容选测](../results/direction-burst-compatibility-20261015-v1/summary.json)
53PASS、4进程80.66秒；[模型/框架/负向门禁](../results/direction-burst-gates-20261015-v1/summary.json)
2232PASS、4进程162.09秒，完整保留原2160项并增加60项语义契约及12项schema门禁。
四轮1995文件epoch相同，证据完整，未改RTL/DUT/SDK或正式根报告。

严格隔离差分相对历史正式基线为旧way0共21键、旧way1共24键；相对最近完整089
则分别只有**7、1**个新键，互不重叠。其中`WriteBuffer_8.sv:810`和`:1427`是跨
owner的当前counter饱和保持，1455/1456、1475/1476、1495/1496为其它保留rank的
同输入命中/未写路径的条件与伴随赋值。后六键不是六个不同功能点，也未为它们
增加rank/slot枚举。完整生产分子必须另行重测，不能将隔离并集直接当当前全量。

[随后完整生产复验](../results/production-direction-burst-20261015-v1/exit.json)重新执行
全部17791项、64进程、439.06秒，**17767PASS、21普通FAIL、3strict XFAIL**，无
ERROR/SKIP/XPASS。FAIL/XFAIL精确集合与完整089相同；335功能点全部执行，
318PASS/15FAIL/2XFAIL。collection/JUnit/controller、64收据及1494个产物hash与
终态1995文件epoch均一致。当轮完整原生测量中
BPU为**33631/46541**，精确新增上述8键；十DUT零旧命中丢失，其余九个命中集合、
所有分母与构建provenance不变。WriteBuffer_8缺306，其中120个局部矛盾证明
重新通过，186个仍未分类；独立SC336/TAGE120局部证明也重验，不缩分母或给
功能豁免。失败刺激包含在诊断内，正式根报告保持不变。

当轮完整SDK功能诊断
明确标记FAILED/NOT publication，1163份功能输入只合并一次；307组中288组满
目标，19个未满组精确集合不变，四个090组全部100%。完整FTQ及其它自主预测器
组合仍开放；不能把本profile的成功描述成整个BPU参考模型已完成。

## 十个 UT 的当前审计与缺口

此表描述源码范围，不代表所有功能已通过；最近完整生产结果为上面的091 useful
延后服务复验：18153项、18128PASS/22FAIL/3strict XFAIL，不能把失败全量称为合格发布。
以下17367项记录属于此前的模型迁移阶段，不是本次源码验收。
2026-10-15曾完成两轮全部17367项的真实生产执行；修正两条旧单测契约后的
最终v2为17343PASS、21普通FAIL、3strict XFAIL，仍不能发布为
合格全量；各模块测试数、329个功能点状态及含失败刺激的原生诊断，见
[完整生产测量与缺口重新分层](coverage-gap-triage-20261013.md#2026-10-15当前语义模型的完整生产测量未通过发布)。

| UT | 原有模型实际范围 | 完整语义模型仍需覆盖 |
| --- | --- | --- |
| UBTB | 原来只有用例预期值，没有独立状态模型 | 本轮补 `UbtbReference`：公开预测/快训/FTQ反馈，独立条目与PLRU、可信度、连续训练和替换冲突；当前配置已接真实DUT，发现一项连续反馈语义差异，见下节 |
| ABTB | 旧计数器、替换、写缓冲局部参考保留作辅助；部分输入是实现级写请求 | 新 `AbtbReference` 默认接入，独立维护四路条目、目标、方向学习、替换和读/更新版本。原1971项生产选测PASS；补目的地所有权功能点后当前选测58PASS、1普通FAIL，见下节。live S1 fastPositions与完整FTQ合法性不由该模型声称完整覆盖 |
| MBTB | 旧两路LRU和以prepared实际快照为起点的受限shadow/entry/counter检查保留作辅助，不当完整golden | 新 `MbtbReference` 默认维护条目、目标、方向、LRU、读快照与写入义务；当前完整生产选测833PASS、3普通FAIL，见下节。完整FTQ合法性、live S1 positions和任意溢出公平性不宣称已完成 |
| TAGE | 固定provider/alternate对子及shadow写参考保留作局部诊断 | 独立`TageReference`默认接入：自有表内容、hash/匹配、provider/alternate、counter/useful、selector、随机分配、aging和在途学习。新增分配规划后当前完整模块选测1091PASS、1普通FAIL；35个功能点PASS、026FAIL。不是全项目回归通过，见下节及078复验 |
| SC | 原来只有独立阈值模型；集成侧 SRAM/shadow 局部参考仍作辅助 | 已补 `ScReference` 并默认启用：从PC和公开历史特征独立计算五类权重、加权和、阈值及纠正结果，保存在途读快照；130项模块测试PASS，见下节。历史生成器本身属于上游UT，不由此声称完整BPU历史/恢复已验证 |
| ITTAGE | 原region目录与aging实现级审计仍作辅助 | 独立三表/两bank语义模型默认接真实UT；074组件cut-point仍按原边界报告。062/092新增自主Main/ITTAGE/history组合，独立推导S1读、S2区域解码/选择、15位PRNG、原来源学习和读优先目标服务，不使用实际组件metadata为golden。UT跨区域学习的两个普通FAIL保留；此profile不声称其它预测器/栈/完整FTQ同时组合已完成 |
| RAS | 原有有界提交栈及distinct推测/retirement局部模型保留作辅助 | 新 `RasReference` 默认维护调用帧、重复分组、检查点和提交状态；公开状态及全部八个保留组均独立比较。080也将此独立模型接入集成BPU，从真实检查点验证重复调用的恢复重放与真实返回退休。新增组合动作三入口普通FAIL，旧弱覆盖用例也暴露已有enable缺陷。原始TOSR/NOS、BOS及完整FTQ合法性仍须结合专门检查，不能宣称全部内部队列不变量已由本模型覆盖 |
| URAS | 原实现级pending寄存器诊断仍作辅助，不再当完整golden | 本轮补抽象栈规约模型、操作/纠正/恢复事件API与默认周期比较；主RAS top是UT公开输入。新PopAndPush功能点在三个入口有普通FAIL，见下节 |
| UTAGE | 原useful时序、地址/折叠历史与受限partial-wrap参考保留作辅助 | 新 `UtageReference` 默认维护两表条目、完整15位tag、counter/useful和在途版本；预测、反馈、aging及请求关联均独立比较。321项选测315PASS、6普通FAIL，见下节；不是全部功能已通过 |
| BPU | 许多子路径参考及断言，未有完整组合语义oracle | 自有历史/checkpoint、三级选择/repair和自主周期token engine已接通独立MicroBTB/MainBTB；004另增加MainBTB/TAGE自主组合，独立推导provider/alternate及原始/合格方向，不用实际组件输出作为golden。015/019新增Ahead/Main非条件双边循环、原S1来源fastTrain、S3重放消费者和禁用回退的独立组合。044另接条件Ahead/MicroTAGE自主profile；低tag正对照通过，高位tag保持普通FAIL，非条件profile仍明确拒绝conditional。066补NT-over-T选择较晚direct及T-over-NT选择较早conditional，两方向各自原来源拥有实际useful增加，完整1024 useful状态比较及下一actual边界确认；正向候选先声明，显式redirect关联不猜编码别名。076/077检查停顿、恢复、纠正与metadata归属。075及080的TAGE/RAS组件cut-point证据仍按其边界报告，不冒称完整组合。其它预测器、CommonHR及完整FTQ仍缺，不能声称完整BPU模型已完成；此前004强化见下节 |

091另在同一自主Main/TAGE/history profile上闭环普通useful学习的读优先保留、实际
服务及新消费者，原始来源与非零邻居保持；不把实现级queue指针作为算法输入。
这仍不关闭上表中完整FTQ与其它预测器组合的缺口。

062/092另接自主Main/ITTAGE/history，093另补独立Micro/Main的entry+direction
读优先服务；028的真实旧冷源counter所有权差异保持普通FAIL。共享service monitor
只消费已绑定端口，领域geometry不混入接收生命周期。上表中的完整FTQ和全预测器
同时组合仍未完成，详见本文对应章节。

### 最新004强化：MainBTB/TAGE自主组合，不以组件输出为oracle

本项晚于上面完整生产v2；完整生产的17343PASS/21FAIL/3XFAIL不能被称为本次源码的
全量验收。继续按用户要求只改模型、验证与必要的框架支持，RTL和DUT不改、不重建。

[DirectionSources](../bpuverify/bpu/model/direction_sources.py)组合已存在的独立
MainBTB/TAGE算法模型。每个请求拥有独立history checkpoint、Main读快照及TAGE读
快照；S2用自己的base/selector计算raw与qualified方向，S3消费S2冻结的qualified
决策。反馈由原请求的自有metadata推导；实际S3 metadata、公开来源及实际接受输入
的所有定义字段均先比较，不能用实际provider/way/counter重新初始化golden。
失效字段不比较，未知/已释放/相同编码但不同对象的checkpoint不能借用旧快照。

[场景](../bpuverify/bpu/case/direction_learning.py)只表达六步学习程序：Main弱正学习，
短历史T2学习NT并增强，长历史T3晋升为弱正provider，暂停TAGE学习后仅增强Main
至T，再由更短NT alternate纠正raw T方向，最后增强长provider使其保留并获得useful。
关键对照是Main自己预测T、短alternate预测NT：若错误地绕过alternate改选Main，
最终选择与S3 repair都必须失败。每一步必须有真实接受及后续新请求消费者；全部
因果窗口内的repair与精确owner比较，缺失或多出一次repair都不能算通过。

同一004的新增六条reached/checked义务纳入生产门禁，required schema由92增至94；
功能ID总数仍329。原生行是否增长另作严格差分，不将oracle强化折算成新增行覆盖率。

本轮也修正了两类采样边界：RiseWrite reset的新可见值与本拍已消费值不同，monitor
单独解码消费reset事件；TAGE随机分配仅由自己的复位种子和连续周期演进，不读实际
随机数、不调整seed补相位。分配机会判断必须与driver编码处于同一驱动时隙，不能
先等待条件、再跨一个驱动时隙发请求。xreactor的`drive_ready_valid`因此新增可选
同步`admit`回调：false时不写输入，true后不经await即编码；它只控制启动，不替代
ready/valid接受。环境负责有界预算，case不出现边沿或固定等待。

SDK在`dev/coverage-v2`本地提交`b130a3c`，依赖锁同步，未推送；SDK全量为1108PASS
及3个subtest。最初未提交改动被依赖门禁拒绝，未绕过门禁。仅Python层变化，不涉及
picker/xcomm ABI或系统原生库。旧普通RTL失败继续保留，不扩大XFAIL范围。

[最终隔离DUT验收](../results/autonomous-direction-learning-qualified-20261015-v1/summary.json)
为1PASS、13.08秒（场景本身1.15秒），六条reached/checked均100%。
[严格原生差分](../results/autonomous-direction-learning-qualified-20261015-v1/qualified-line-delta.json)
相对历史完整基线为**0新增键**，分母仍46541；隔离25599命中不是新的全量分子。
[兼容选测](../results/autonomous-direction-learning-compatibility-20261015-v1/summary.json)
为41PASS、4进程52.17秒，包括旧直接训练、独立Main学习、Micro容量/旁路、PHR、
自主pipeline、TAGE组件学习/多位置路由及RAS恢复/退休。两轮evidence完整、integrity为空；
正式根报告未替换，520个RTL/DUT受冻结文件与历史基线身份相同。

[框架、模型与负向门禁](../results/autonomous-direction-learning-gates-20261015-v1/pytest-artifacts/evidence.json)
为1897PASS、4进程pytest125.37秒。74条新增纯测试覆盖快照/反馈独立性、三处
metadata边界的每个定义字段、旧来源/错误消费者/多余repair、reset消费边界、
取消/排队/异常原样传播。作用域提前退出会取消未接受输入，不能让它后来无条件
发送。缺失、新增schema不符或checked不完整都被门禁拒绝。合成actual只用于
检查oracle能否抓错，不计真实DUT覆盖；中途停止的一轮串行局部门禁不作通过证据。

现有 `FullScReference` 的“Full”指 shadow 容量和状态范围，不是整个 SC 预测器。
`IttageContextModel.advance()` 在接受反馈时立即更新表，不能直接用于有在途写入的
并发场景。074此前的旧目标/新目标差异确认为oracle错误：它把发送反馈当成更新
已提交。现已改用独立模型维护在途更新与历史读取快照，074通过并形成31个严格
归因原生新行点，见[周期语义与覆盖增量](coverage-ittage-semantic-aging-20261015.md)。

## ABTB：分支目的地所有权与原生满覆盖漏检

[AbtbReference](../bpuverify/abtb/model/semantic.py)输入是预测/恢复和已接受分支反馈，
独立维护4 bank × 64 row × 4 way条目、方向计数器、替换recency以及不可变读快照。
半字PC和四位历史特征独立映射row/bank，24位partial tag匹配条目，22位目标在请求PC
区域重构；当前配置无carry fix。分支位置、kind、RAS动作及目标均由模型自己维护，
没有从实际SRAM、counter、replacer状态或写包初始化/修正expected。

学习语义与提交可见性分开：not-taken反馈降低所有命中的条件方向；taken反馈降低
更早的条件方向，仅提升同位置条件方向。taken miss分配弱正方向；indirect目标改变
才纠正目标，conditional/direct目标不因此改写。预测本身不touch替换；已接受的taken
hit及提交写入touch recency，同row提交写优先于训练touch。学习接受不等于entry可见：
单端口读服务优先，已有请求保有旧条目和counter快照，恢复重匹配已拥有的快照。

写入义务的身份是**目的地(row, way)和版本**。同目的地新版本可替代旧版本；不同
目的地不能只因tag相同而合并。模型表达的是独立更新合同，不导入旧WriteBuffer
slot/dirty-mask参考，也不按实际dirty/writeResp来安排golden的提交。有限容量、服务
优先级和无背压溢出的边界单独声明；本次丢失场景仅两条不同目的地义务，未达到
四条容量，不靠制造溢出。

[公开输入monitor](../bpuverify/abtb/monitor/semantic.py)负责信号解码和RiseWrite消费
边界；算法仅接受严格的纯语义值，拒绝信号包装和超出配置的输入。反馈metadata在
独立UT是上游输入；真实场景返回的是先经模型检查的原始metadata，不修改hit/way。
[默认checker](../bpuverify/abtb/checker/semantic.py)取代OBSERVE_ONLY，对预测结果、
有效metadata和`toMicroTage.result`的定义字段逐周期比较；流水返回另检查PC及独立
history路由。无效payload不拿来判断功能，actual.valid也不能决定是否检查预期命中。
异常包含tick、事件、独立状态和字段差异；之后不重同步。live S1 `fastPositions`仍由
既有专门断言检查，不将这宣称为新模型的完整独立采样检查；全BPU/FTQ合法性也未
因此完成。

### 2026-10-21：redirect 死开关、多命中 way 对与 65 个 arm 的结构证明

AheadBTB 是“行覆盖 100% 仍然漏行为”的典型：17854 行早已全命中，但
`io.redirect` **从未被驱动**。端口绑定了、monitor 解码了、独立模型在
`advance` 里用 `events.redirect` 清 `frame.valid`/`read_ticket`，可 agent 的
idle 编码与 `_encode_lookup` 都硬写 `"redirect": 0`。按 ICache 的“死开关”标准，
这是没有证据的覆盖承诺。本轮把 `AbtbLookup` 加上显式 `redirect` 字段、
`submit_predict` 校验其为 bool 并编码真实值，新增 `BPU-ABTB-054` 与
`test_redirect_flush.py`：在途窗口被重定向撤销时必须整体无效
（`meta_valid=0` 且四 way/`micro` valid 全 0），而随后同 PC 查询仍返回原
目标/位置/类型，证明撤销的是发布资格而不是学习状态；idle 重定向脉冲不制造
也不销毁记录。

检查器同步做一处**收窄**：模型没有有效 frame 时不再抛
`accepted ABTB request has no owned read transaction`，而是要求实际响应是完整
flush；只要 DUT 发布了任何预测字段仍然失败。旧写法会把机制上正确的 flush
报成假失败。

多命中清理此前只做一次重复分配，只到第一个 victim 对。新增
`test_multi_hit_cleanup_pairs.py` 连续 6 轮复用同一真实冷快照，读回重复集合、
排空写回再读，要求四组 way 对 (0,2)、(2,3)、(1,3)、(0,3) 都出现，每次清理后
**恰好保留新写入的一份**，并显式断言上层臂的 (2,3) 必须被观察到——这关闭了
`AbtbDut.v:21642`。

剩余 65 个 arm 用有界结构证明归因：64 个是每 set 的 PLRU 链尾，其外层守卫
已经 OR 了该 set 四个 `readWayMask` 位，fall-through 要求四位全 0 与守卫矛盾；
1 个是 `WriteBuffer` 的 `io_write_0_valid & ~hit ? victim : 2'h0` 生成在自己的
false 分支内。审计工具逐 set 校验“只引用本 set 的四个 mask”，并用布尔枚举复验
矛盾；删 mask、借用别的 set、加最终 else、去掉 if 守卫、让 else 可变六种变异
全部被拒绝，源码不变、分母保留、不授予功能信用。

最终选测 **76 项：75 PASS / 1 FAIL**，行仍 17854/17854、branch 4810→4811、
toggle 11982→11984。唯一 FAIL 与基线同节点（`BPU-ABTB-053` 写缓冲合并键缺
目的 way），未改名、未加 XFAIL。组合矩阵见
`docs/abtb-combination-matrix-20261021.md`，其中 `C×D`（恢复与重定向同拍）、
`A×F` 最强形式（同 set 读写与 PLRU 更新顺序）与同拍恢复组合显式登记未验证。

### 验收证据与新增普通FAIL

- [原完整生产选测](../results/abtb-semantic-dut-20261015-v1/summary.json)：
  **1971 PASS、52个已执行功能点全部PASS，8进程388.69秒**。该次结束时源码epoch
  核对一致，evidence完整且无integrity错误；原生仍17854/17854。它先于新053及后续
  输入验证/关联加固，是历史完整模块证据，不能称当前1985项源码已全绿。
- [当前语义/兼容选测](../results/abtb-semantic-ownership-20261015-v2/pytest-artifacts/evidence.json)：
  **58 PASS、1普通FAIL，4进程4.62秒，59项**。48项纯模型及负向测试全部PASS，
  包括独立list分区recency对照、两个方向端点、读快照不可变、同tag不同目的地保留、
  11类错误字段拒绝及不重同步、非法信号包装拒绝、同PC错误history关联拒绝。
  串行distinct纠正、pending same-destination、原流水/恢复/使能/读压力/目标区域均PASS。
  当前选测执行8个ABTB功能点，其中7PASS、新053FAIL；epoch核对一致，证据完整，
  无ERROR、SKIP或新增XFAIL。

`BPU-ABTB-053` 为两个真实resident indirect位置3和9各接受一个目标纠正，持续读让
写入保持在途。随后提供正常提交窗口，再由公开预测验证两个更新及邻居。它们是
独立UT的两条合法反馈输入，**不是声称同一FTQ块执行两个taken indirect**，也没有
声称全BPU产生这种反馈序列的完整可达性证明。同一目的地两条更新的正对照保留
最新版；distinct两条串行纠正也通过，排除了基础地址/类型规则或单次纠正不支持。

distinct pending场景在native tick202失败：位置3、way0期望目标`0x400009c0`，实际
仍旧`0x40000980`；位置9、way2已正确更新为`0x40000b00`。模型四个提交计数包括两次
分配和两次纠正，未读实际提交包来求这个状态。源码
[WriteBuffer.scala:164](../XiangShan/src/main/scala/xiangshan/frontend/bpu/WriteBuffer.scala#L164)
只用set/tag判断hit，不含目的way；`hasWayMask=false`时hitNotWritten以整条新请求
替换旧请求，覆盖了另一way的未提交纠正。这个解释与两种正对照和最终公开字段差异
一致；RTL未修改，普通FAIL保留，不能复刻该合并键把丢失纳入golden。

两个稳定rule的诊断合并为reached=2/2、checked=1/2；只取PASS来源则分别1/2、1/2。
串行正对照不贡献pending checked credit。两个group加入生产门禁，附加group数47→49；
[当前门禁选测](../results/semantic-publication-gates-20261015-v3/summary.json)
**217 PASS、4进程44.65秒**，current epoch一致。缺失、改变schema或不完整checked
均拒绝发布；失败worker退出码1仍让根回归失败，不因为诊断证据完整而变成成功。

ABTB此前已原生满覆盖，新场景不声称新增原生行点；当前59项选测
原生测量
11387/17854只反映有限且失败的选测，不替换此前模块/全量合格覆盖，也不与历史
集合拼接。新的功能点缺失走的恰是已覆盖写合并分支：行覆盖不能代替独立功能判断。

该ABTB选测时默认事件级独立模型已接入七个UT：UBTB、ABTB、URAS、ITTAGE、SC、RAS、
UTAGE；后续MBTB已接入，见下节。已发现的功能差异和全量回归验收仍未解决，目标未完成。

## MBTB：匹配资格、目的地所有权与生产回归范围

### 独立模型的输入和状态

[MbtbReference](../bpuverify/mbtb/model/semantic.py)从公开预测、resolved分支、上游metadata
和复位/使能事件出发，自行维护512个branch record、方向计数器、按alignment/replacement
index分组的两路LRU、不可变读快照和在途写入。算法仅依赖Python dataclasses；不导入
旧`prepared`快照参考，不拿实际SRAM、counter、shadow owner或内部write packet初始化/
修改golden。PC/target保留既有半字单位，窗口排列、tag、page/offset过滤、local target及
相邻区域carry均独立计算。当前配置的有限target编码不宣称能表示任意远距离target。

语义是branch ownership，不是寄存器逐位复刻：匹配conditional源才能学习方向；已
保留的同(row, tag, position)条目更新保留其owner，重置confidence也属于这个owner，
不能改另一条目的计数器；重复项无效化是指定目的way的操作，不是有效tag=0/pos=0
条目的身份。同位置属性改变重写条目，非return的indirect按ITTAGE base合同纠正目标；
普通direct/conditional不因相同属性下target变化重写。只有accepted taken反馈/entry
decision touch替换状态，普通预测和not-taken不touch。

周期准确描述可见性：S0的committed读快照保留到后续输出；接受反馈、产生学习patch、
进入entry buffer和退休不同步。Entry版本按逻辑身份/owner表达，counter则是depth-two
FIFO，读服务优先于写退休，空队列flow-through、满队列同边界退/进明确处理。无背压
溢出是当前配置的独立容量边界，不能由这里宣称无限容量/任意流量无丢失。方向学习
使用孤立UT的公开feedback counter snapshot；真实用例的原始metadata先由模型检查
预测来源，再未经修改返回。它是cut-point输入，不是完整BPU/FTQ reference的替代品。

[monitor](../bpuverify/mbtb/monitor/semantic.py)仅解码公开端口及RiseWrite消费边界；
[default checker](../bpuverify/mbtb/checker/semantic.py)替换OBSERVE_ONLY，逐周期检查
所有定义的result/metadata字段，filtered raw hit仍检查位置、属性和counter，raw miss
的无效payload不成为golden。使能关闭时注册prediction冻结、rawHit metadata门控，
请求关联使用历史边界资格，不使用后来时刻的使能值。错误立即记录且通过agent/
Scoreboard转成带tick、事件、独立状态和字段差异的pytest异常，不重同步。
live `s1_positions`和完整FTQ指针/epoch/resolve合法性未由该模型完整独立验证。

### 三个硬件事件缺失，而非更多bank坐标

新增三个功能点各有正对照，只使用一个代表坐标、正常IO、真实metadata和正常driver；
没有内部写入、没有bank/set枚举、没有新增skip/XFAIL。

| 功能点 | 缺失语义 | 独立预期/实际首个差异 | 正对照 |
| --- | --- | --- | --- |
| MBTB-027 | rawHit=false不能以同位置payload训练其他tag | tick176，resident counter应2/实际1，taken应1/实际0 | 同样tag miss但其他position反馈不改resident，PASS |
| MBTB-028 | stale cold反馈的retained owner重置不能落到nominated peer | tick226，earlier conditional counter应0/实际2，taken应0/实际1 | current metadata的indirect retarget，PASS |
| MBTB-029 | 高way无效化不得与有效零tag/零position identity合并 | tick242，way0应valid1/实际0，way1应valid0/实际1；错误survivor | 非零tag/position的相同清理/训练重叠，PASS |

027明确是no-entry-mispredict的正确not-taken反馈，未请求分配；只是其训练PC的tag
没命中另一条已占用record。[MainBtbAlignBank.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbAlignBank.scala)
的counter hitMask只检查valid conditional和position，没有rawHit/源类型资格。另一处
替换touch的actualTakenMask却明确检查rawHit，不能混淆这两种资格。
028准备真实earlier conditional的counter=0，然后由later indirect的correct taken反馈
将nomination指向peer；entry cache仍保留indirect owner。stale genuine cold metadata
只重写该indirect，实际entry owner保留但reset mask按nomination改变peer。此前弱邻居
用例两边都为2，重置到2不可区分，不能证明所有权保护。

029将旧计划中“jointly zero但未注册的只读diagnostic”升为正式P0要求；不复制旧
诊断plugin/框架patch。[WriteBuffer.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/WriteBuffer.scala)
用set/tag匹配，MBTB tag包含entry tag/local position；zero invalidation因此命中有效
零key的lower owner。模型的clear则保留明确目的地。原144-bin cleanup矩阵及三类原有
key schema不变，029单独验证联合零操作数，避免改物理分母掩盖缺口。

reached/checked每类两rule，六个group都纳入生产门禁。清理的reached必须观察到公开
S2-consume并关联模型自有duplicate快照，**仅prepare duplicate不给clear offered credit**；
checked须完成全部独立输出/状态比较。选测的diagnostic合并每类reached=2/2、checked=1/2；
只取PASS来源每类分别1/2、1/2，失败来源不贡献PASS覆盖。该次MBTB验收时仍缺TAGE和
BPU完整模型；后续TAGE本轮独立验收已发现同一useful所有权差异，完整组合BPU仍未实现。

### 当前验收与缩短迭代

- 原完整模块选测`results/mbtb-semantic-dut-20261015-v1`：791PASS、26功能点全部PASS，
  8进程388.61秒，结束时epoch一致；原生1056/1056。它先于新增三条要求及生产范围
  调整，是历史证据，不冒充当前完整通过。
- [最终完整生产选测](../results/mbtb-semantic-dut-20261015-v3/pytest-artifacts/evidence.json)：
  **833PASS、3普通FAIL，8进程88.67秒，836项**。65项新的纯语义/负向测试以及5项
  replacement分片schema/credit测试均PASS；11类错误字段拒绝、不重同步、错误PC关联、
  非法signal包装拒绝、不可变快照及未consume不给clear信用均验证。精确collection/
  JUnit/生命周期一致，evidence完整、integrity错误为空，冻结epoch结束后核对一致。
  当前MBTB功能点26PASS、027/028/029普通FAIL；没有ERROR或SKIP，没有发布失败回归。
- [最终门禁](../results/semantic-publication-gates-20261015-v7/summary.json)：**258PASS，
  4进程71.78秒**，epoch一致。required group数49→58，包括三类新事件、替换语义与
  保留的物理schema。无解释退出/崩溃/生命周期或artifact缺失仍拒绝；证据完整不把
  普通FAIL变成PASS。

旧MBTB-024一个test内串行运行1024个index/align/upper/mode子场景，单case384.62秒，
8进程无法拆它。现在[pytest case](../tests/mbtb/testcase/test_replacement_indices.py)每个
场景独立调度：production取index0/63、两个alignment和upper角色、四类touch，**32项**；
`--regression-profile=physical`保留全64indices，**1024项**。这是collection范围不同，
不是加skip。profile单元测试实际collect两种范围并核对唯一nodeid数量；初始384秒
索引单体已退出生产关键路径，当前较慢的是旧shadow61.9秒和entry-keys56.6秒场景。
这些剩余单体还可继续拆分，不能宣称全项目生产并行优化全部完成。

### 2026-10-20：RAS 提示位与 57 个剩余 arm 的归因

此前所有训练向量的 `ras_action` 都是0，因此“完整分支属性”功能点只验证了
branchType、target和position，RAS提示位从未被观察。新增两个用例补上这个
**缺失情况**：四个提示编码（none/call/return/return-and-call）在预测和原始
metadata中原样返回；以及仅提示位0→2变化时，`BranchAttribute.===`会触发原way
就地重写（`MainBtbAlignBank.scala:225-231`，属性相等包含rasAction），不消耗
新way、邻居保持。两者均PASS，关闭训练/元数据/预测/两个align bank响应路径上
共28个RAS提示toggle点。

剩余57个branch arm已全部归因，没有未定位项：
- 49个是`ReplacerState.sv`每个物理set的同一替换状态副本
  （`if (io_write_1_valid & setIdx==N) states_N <= ...`）。训练只触达代表set，
  逐set补满属物理副本枚举而非新功能；生产profile本来就只取代表坐标。
- 8个由生成层次常量证明不可达：flush wayMask bit0恒0使port-0的7个clear
  payload mux无法选择clear臂；计数队列RAM的`R0_en`恒1使读禁止臂不可达。
  `python3 -m bpuverify.mbtb.coverage.branch_audit`给出16组布尔穷举和4个源码
  变异负对照，原始分母不扣减。
对应49个“未覆盖行”就是上述49个set副本的if行，不是另一批缺口。

该轮**120项：110 PASS、10 FAIL**，10个FAIL与基线逐项相同：017四程序、025、
027、028共享“计数器按position匹配而未检查rawHit/owner”的首错；029是联合零
key清理的目的地归属；026是两真实来源共用服务时纠正被清理吞掉。行覆盖保持
1007/1056，branch保持385/442，toggle 7300→7328（+28）。功能组43个中32满；
未满组全部由上述普通FAIL或物理副本profile造成。行/branch饱和不能替代功能判断。

两个taken touch都有**会改变age的前置状态**：way0先用真实way1 correct feedback
建立相反age；way1原age本已相反。两者必须改变独立LRU victim；not-taken及lookup
控制必须保持。这样counter变化和下一次真实victim均能区分更新逻辑，而不只重复
观察本就相同的状态。4-rule的reached/checked都全满，alias sharing和独立邻居由
同一program及默认语义模型逐步核对。

原`kunminghu_v3.mbtb.indexed_replacement` **6144-bin schema/digest与历史完全相同**。
32项生产贡献只命中192/6144（3.125%），未访问bin全部保留；两个新semantic group
各4/4。production门禁要求完整schema和全满semantic，physical门禁另要求物理cross
全满。未对其他地址给出equivalence/formal证明，未把3.125%改写成物理100%。

### 原生行缺口的归因及范围警示

当轮原生测量
为**1004/1056**，带pytest退出码1；38/38 module v_line已命中但不能替代DA源行统计。
相对原全物理1056/1056，52未命中项全部位于`rtl/mbtb/ReplacerState.sv`，形式为
`states_i <= io_write_1_bits_state`，52个不同index各一个DA键。范围为8..31及33..60；
例如[line270](../rtl/mbtb/ReplacerState.sv#L270)在write-valid/index8的guard内，直接来自
`ReplacerState.scala:58`的向量写入展开。它们是本次生产范围未访问的物理写入副本，
**不是52项新的功能、也不是不可达行**。完整原生1056分母和6144物理cross分母均未删。

当前已覆盖替换的更新/不更新、alias与邻居合同；没证明所有physical indices正确。
全物理profile按需保留；上述两种Scope单独报告，不把历史并集冒充当前coverage。
本轮没有声称新增合格原生行点。三个新错误却均走原来已覆盖代码，说明行覆盖满也
无法替代这些事件合同。全项目当前source acceptance尚未闭合，目标仍未完成。

现在默认独立事件模型已接入八个UT：UBTB、ABTB、MBTB、URAS、ITTAGE、SC、RAS、
UTAGE；TAGE和完整BPU仍需建设。RTL及SDK未改，分支保持原状，未引入VPI/internal写入
或逐周期JSON导出，既有缺陷及新普通FAIL仍须处理。

## TAGE：历史条件化学习与branch identity，而非内部写包复刻

[TageReference](../bpuverify/tage/model/semantic.py)只依赖dataclasses和固定配置的历史
layout常量；预测/训练encoder、DUT、旧pair/shadow模型都不参与golden运算。它拥有
四表×四bank×128row×两way的entry/counter/useful、八个selector bucket、不可变读
快照、branch-owned在途版本与aging状态。从真实复位开始，15位分配随机状态按种子
和多项式独立推进，包括SRAM复位未完成的周期；不读取实际随机数或分配选择。
历史fold用逐bit parity独立求值，不复用driver的chunk-fold实现。

语义从匹配的conditional resolved事件出发：只选择最长/次长历史匹配；weak provider
由独立selector决定是否让位给alternate/base；反馈重新评价错误才请求更长历史分配。
方向学习按饱和增减，weak disagree聚合selector vote后一次限幅，useful学习属于该
branch保留的owner，不能因为反馈nominated way过时而落到peer。未匹配、非conditional
或disabled反馈不学习。分配候选分invalid、weak-and-unused、unused三层，由自有随机
状态过滤并使用原候选fallback；无候选才累积aging压力。aging只清useful，不改身份
和方向；在途队列flush与128row清理、读期间零useful可见性独立表达。

接受、学习成熟、进入pending和退休不混成一次写。所有读保有committed快照，单端口
读优先；保留的(row,tag)版本合成最新counter并保留owner。服务rank/有限容量/无背压
边界是显式当前配置合同，不消耗实际slot/dirty-mask来决定golden。完整FTQ执行轨迹
是否合法仍不由独立UT保证，不能把该合同推广成无限吞吐或完整BPU参考。

[公开monitor](../bpuverify/tage/monitor/semantic.py)只把IO转成Events、Feedback和Base。
[默认checker](../bpuverify/tage/checker/semantic.py)替代OBSERVE_ONLY，检查所有定义的
public correction、metadata、raw fast provider和SC provider counter。无效payload不
决定expected命中与否；实际错误valid不能关闭预期比较。异步返回额外检查原请求PC、
完整history context、有效base/type/confidence和S1位置关联；冻结首错、不重同步，
通过正常agent/SDK Scoreboard抛pytest异常，包含tick、事件、自有状态和字段差异。

独立UT中prediction metadata是上游反馈输入；正常case只返还已经由主模型验证的
genuine输出，不伪造provider/way/counter。整个BPU则必须由自己的预测/历史账本产生
这些期望，不能把实际组件metadata直接作为完整组合golden。当前完整BPU模型仍缺。

### 资格验证、功能点和原生缺口

- 49项纯语义/负向测试覆盖两个方向端点、独立fold/坐标、32767非零随机周期、接受
  与提交边界、immutable reads、counter forwarding/owner保留、FIFO容量/flush和
  useful aging。14类错误输出都必须失败且不改模型状态；PC/history/位置/base/valid
  五类错误关联即使payload自洽也必须失败。另有7项coverage资格测试，保证计划中的
  请求不给reached、实际未匹配不给learning credit、错误比较不给checked。
- [完整模块初次选测](../results/tage-semantic-dut-20261015-v1/pytest-artifacts/evidence.json)
  1011PASS、1普通FAIL，12进程266.89秒，1012项；35个TAGE功能点PASS、026FAIL。
  结束时epoch一致，evidence完整、integrity错误为空，无ERROR/SKIP或新增XFAIL。
  它先于history case的reached失败路径加固，是历史证据。
- [最终完整模块选测](../results/tage-semantic-dut-20261015-v2/pytest-artifacts/evidence.json)
  **1018PASS、1普通FAIL，16进程221.47秒，1019项**；35个TAGE功能点PASS、026FAIL。
  结束时epoch一致，evidence完整、integrity错误为空，无ERROR/SKIP或新增XFAIL。
  49项主模型/负向与7项coverage资格测试都PASS；默认模型已接九个组件UT，BPU组合
  模型仍缺。该模块失败回归没有发布成全项目报告，目标也没有因此完成。
- 新`BPU-TAGE-036`用同一PC/position的四个区分history，不枚举物理bank/set，检查
  context分配、局部学习、交错路由和恢复后的protected state。正/反顺序走同一个
  SDK asynchronous prediction Scoreboard，不在case暴露edge或asyncio.gather。
  两组reached/checked各4个rule，[当前独立选测](../results/tage-semantic-history-20261015-v2/summary.json)
  1PASS、3.58秒，两组均4/4；不靠重复发送刷coverage。rule进入生产门禁，完整schema
  不变；required group数58→60。[当前门禁选测](../results/semantic-publication-gates-20261015-v9/summary.json)
  197PASS、4进程73.56秒，结束时epoch一致。缺失reached/checked、改变schema和未满
  rule仍拒绝发布；普通FAIL不会因evidence完整而被放行。

026旧captured-way场景在native tick5808先由主模型拒绝：位置6的table3/way1 counter5
正确，但useful预期1、实际0。独立模型按retained logical branch owner维护这次学习；
实际useful仍按旧nominated way写入，而entry/counter路径已保留新owner。
[TageTable.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/tage/TageTable.scala)的
useful FIFO逐请求way入队，不能以entry WriteBuffer的owner迁移替代这项检查。既有
strict XFAIL只接受局部`MisassociatedProviderUseful`异常；主模型更早抛普通Mismatch，
不扩大XFAIL、不删除默认比较、不把错误路由复刻进golden。RTL未修改。

当轮最终原生测量
仍4467/4587，退出码1；相同DA分母/集合下无新增或丢失原有hit。120缺行都在
`rtl/tage/WriteBuffer.sv`，不是新history功能缺失的120个事件。
[036严格单场景归因](../results/tage-semantic-history-20261015-v2/qualified-line-delta.json)
新增原生行0，3841/4587是其单场景hit，不代替模块全量4467。既有112个局部guard
矛盾与8个控制header的分析仍是实现级线索，未完成完整可达性证明，不能统一标记
unreachable或删除原生分母。本轮提升的是独立语义检测与四个稳定功能rule，不虚报
原生行增长。

### 2026-10-20：误报 FAIL 修复与当前 epoch 的 120/64 分类

`BPU-TAGE-026` 的 strict XFAIL 在本轮一度被报成普通 FAIL：独立语义参考开始比较
useful 后，在场景收完自己的矩阵之前就以 `ScoreboardMismatch`（`0.useful`
expected 1、actual 0）抛出同一已知差异；marker 指定了
`raises=MisassociatedProviderUseful`，异常类型不匹配，pytest 因而不认预期。
修复只在适配层把**全部差异路径都以 `useful` 结尾**的 mismatch 重新标记为已声明
异常；混合、counter-only 与空差异集返回 None 并重新抛出原异常。两项纯负对照
覆盖这四种输入，marker 仍是 strict，未来修复会 XPASS 失败。最终选测
**226 PASS / 1 XFAIL / 0 FAIL**，原生 4467/4587、1513/1598、10711/15514 与
修复前完全相同；这是误报修复，不是 RTL 变化，也不冒充覆盖增长。

当前 epoch 的 120 个 TAGE 缺行全部在 `rtl/tage/WriteBuffer.sv`，按写缓冲槽位
（2 端口 × 4 entry）分组为 counter/setIdx/valid/tag 的重复发射臂；权威分类
**120/120、64 个 native producer、0 未知**，分母不变、`functional_pass_credit=false`。
85 个未覆盖 arm 的实际分布（本轮按原生报表重算）：`rtl/tage/WriteBuffer.sv` 50 个
（32 个 `else` + 16 个 `if` + 2 个 `cond_else`，槽位 hit/row 副本）、
`dut/tage/TageDut.v` 34 个（24 个 `cond_then` + 2 个 `cond_else`，其中 8 个是
`useAltOnNaVec_N_value` 的减到零钳位臂、9 个按 position 的 hitMask、5 个 tag-match）、
`rtl/tage/ram_4x9.sv` 1 个（恒使能 counter queue 的读禁止）。

`BPU-TAGE-020` 已用真实 weak provider 验证同拍两步 selector 贡献。
**31/0 端点已在集成路径验证**：`BPU-INT-072`（`tests/bpu/testcase/test_tage_selector.py`）
用 32 笔反馈把同一 `(table=3, altConf=1)` 桶从 15 推到 0、16 推到 31，越界那一拍仍有
真实 `decrements=1` / `increments=1` 投票而寄存器停在端点；八个选择器每帧与独立模型
逐项比较（见 `results/bpu-tage-endpoint-20261021-v1`）。
**独立 TAGE DUT 的桶 0–7 端点已全部实测命中**（`results/tage-selector-full-20261022-v3`）：
新增只读 `TageSelectorMonitor`（memory-direct 读 8 个 `useAltOnNaVec_N_value`）与纯 pull 的
`sample_selectors()`，用闭式算术逐步预测每次投票并对 DUT 8 个寄存器逐项比较。

`useAltOnNa` 按 `2 * providerTable + altConf` 索引，`altConf = !alternate.isWeak`。
三种稳定形态覆盖全部 8 个桶：

| 形态 | 桶 | 为什么 `altConf` 不再移动 |
|---|---|---|
| 无 provider，`base_conf` 直接当 `altConf` | 0、1 | 没有替代项，索引只由调用方给的基础置信度决定 |
| 饱和负向替代项（计数 0） | 3、5、7 | 计数 0 在继续 not-taken 训练下保持 0，`altConf=1`、`altPred=0` 恒定 |
| 直接分配到 table 2/3，无替代项 | 4、6 | `altConf` 取自 base 计数，而 base 由调用方每拍重给、不训练 |
| 冻结强替代项（计数 7） | 2 | bucket 0 的选择器先投到 10 使 `useProvider=1`，表项冻结 |

| 桶 | 表 / altConf | 锚定 | 上端 | 上行投票 | 下端 | 下行投票 | 越界钳位 |
|---|---|---:|---:|---:|---:|---:|---|
| 0 | 0 / 0 | 16 | 31 | 15 | 0 | 31 | 两端保持 |
| 1 | 0 / 1 | 16 | 31 | 15 | 0 | 31 | 两端保持 |
| 2 | 1 / 0 | 16 | 31 | 15 | 0 | 16 | 上下各再投 1 票仍保持 |
| 3 | 1 / 1 | 18 | 31 | 15 | 0 | 16 | 上下各再投 1 票仍保持 |
| 4 | 2 / 0 | 16 | 31 | 15 | 0 | 16 | 上下各再投 1 票仍保持 |
| 5 | 2 / 1 | 17 | 31 | 15 | 0 | 16 | 上下各再投 1 票仍保持 |
| 6 | 3 / 0 | 16 | 31 | 15 | 0 | 16 | 上下各再投 1 票仍保持 |
| 7 | 3 / 1 | 19 | 31 | 15 | 0 | 16 | 上下各再投 1 票仍保持 |

全量 TAGE 选测 branch 因此 **1513 → 1533（+20 arm）**、toggle **+40**，行与 FAIL 集合不变；
`useAltOnNa` 的未覆盖 arm **8 → 0**。bucket 7 另在集成 BPU 上由 `BPU-INT-072` 端到端覆盖。

**三条实现约束**（也是此前几轮判断错的地方，已更正）：

1. **索引必须取 DUT 自己的 metadata**，不能写死；`altConf` 在预测侧与训练侧分别重算，
   会合法移动，断言的是“8 个寄存器整体等于闭式模型”与“票全部落在同一寄存器”。
2. **分配表由 LFSR 决定**，所以用有界 tag 序列搜索；每个尝试都按同一套断言检查，
   找不到就失败 —— 这是准备搜索，不是放宽。
3. **两个方向要各用一次全新 reset 重放同一 tag 前缀**，否则第二次准备会落在另一张表上，
   实际驱动的是另一个桶（本轮踩到过，靠断言 `produced == bucket` 拦下）。

## SC：独立权重算法及事件可见性

算法模型：[model/semantic.py](../bpuverify/sc/model/semantic.py)。输入是PC、历史特征、
基础预测分支和已接受的反馈。状态为五类自有有符号权重（path/global/backward/loop/bias）、
四个自适应阈值、不可变读快照及延迟写入。该文件不依赖picker、xreactor或DUT对象；
debug索引、SRAM内容、实际权重和内部写缓冲包均不作为输入。

模型按统计纠正器的语义计算：历史特征与PC映射到权重行，分支位置选择权重列，
TAGE方向与可信度选择bias特征；每项证据为 `2 * weight + 1`，加权和的符号产生
纠正方向，绝对值严格超过可信度对应阈值才允许纠正。多个分支在同一权重上先合并
增减投票，再执行一次有符号饱和；阈值在同一周期按错误/低置信度反馈更新，越界
拒绝整次更新，不钳位到自定义端点。公共历史无效时，global/backward使用初始化权重
且不参与学习；path/loop/bias仍正常工作。

周期精确只规定因果可见性：预测捕获已提交权重的快照；下一次提交不得改变既发出
请求的预期结果。接受反馈、学习、入缓冲及提交是不同事件；bank上的读服务优先于
权重写入。逻辑写patch在有界缓冲中合并、退休，不逐位镜像RTL next-state寄存器。
容量满且没有背压时的替换属于当前配置可观察合同，不假定无限队列或无条件转发。

[公开输入monitor](../bpuverify/sc/monitor/semantic.py)只解码模块端口。SC UT的TAGE/
MainBTB基础预测及训练metadata是合法上游输入；预测输出metadata先经独立模型检查，
真实场景再将原始metadata不改动地返回训练端。不能把这种cut-point输入模型直接
宣称为完整BPU预测选择、全局历史生成或恢复的golden。SC原有API使用半字PC，本轮
显式保留该单位，没有悄悄改变已有用例的地址解释。

[默认checker](../bpuverify/sc/checker/semantic.py)替换仅采样的默认预期，比较所有定义
的公开预测/置信度/bias元数据及分量方向；debug索引是被比较的actual，不是expected
的来源。流水返回还核对请求PC与独立折叠历史。RiseWrite的pending值/消费边界转换
只在适配层处理，用例不等待边沿，不读取权重或指定表索引。失败通过Scoreboard抛出
带周期、事件、独立状态和差异字段的异常，不用实际结果重同步模型。

新增 `ScHistory` 传入原始path/global/backward/loop历史；driver负责编码，上述算法用
另一种位奇偶算法计算fold。`BPU-SC-023` 在三个代表上下文中学习相反方向，再连续
发出六次交错预测，要求读快照和请求上下文一致，不遍历bank/set。七项稳定语义事件
覆盖分为reached/checked两组，只有成功的独立公开输出比较才给checked记账；reset
撤销旧义务。两组均纳入生产发布schema/完整性门禁，失败测试不能贡献PASS覆盖。

本轮证据：

- [SC模块完整选测](../results/sc-semantic-dut-20261015-v1/summary.json)：**130 PASS，
  4进程，116.14秒，23个SC功能点PASS**。其中新增纯模型/负向比较测试52项；17种
  错误字段注入均被拒绝，另验证不重同步及失败/reset不给虚假checked覆盖。
  evidence完整、integrity错误为空；1822项源码/依赖/DUT文件的冻结epoch在结束后
  核对一致。功能覆盖51个当前输入、18个group；新增两组各100%。
- [历史场景独立选测](../results/sc-history-semantic-event-20261015-v1/summary.json)：
  单项PASS；[严格行增量归因](../results/sc-history-semantic-event-20261015-v1/qualified-line-delta.json)
  为**0**。SC模块本轮原生DA命中仍为 **3145/3481**，不能声称新增模型让行覆盖上涨。
- `results/sc-semantic-publication-gates-20261015-v1`：**126 PASS，37.35秒**，包括缺失/
  改写schema、partial矩阵和失败来源的拒绝；要求的附加group数从39增至41。

这些都是选测，不是十个UT的当前源码全量绿灯，未替换已发布报告。UBTB、URAS和
ITTAGE此前的新语义差异仍保持普通FAIL，未修改RTL、未新增skip/XFAIL。当前已默认
该SC选测当时接入独立语义模型的是这三个UT加SC；后续RAS已加入，见下一节。
ABTB、MBTB、TAGE及完整BPU仍需
继续建设。剩余336个SC行点须继续按硬件事件合同归因，不能仅以局部guard矛盾一概
视为不可达或补充遍历刷覆盖。

### 2026-10-20：当前 epoch 的 336/16 分类与全脏写缓冲开放候选

SC 当前选测 **51 PASS、23 个功能点 PASS、28/28 组满**，原生 3145/3481 行、
890/1038 branch、10518/15076 toggle。全 PASS 不作为闭合：336 个缺行全部在
`WriteBuffer.sv` / `WriteBuffer_8.sv`，是同一字段赋值在生成代码里的三个发射点
中的前两个（`if (hit)` 内的 `if (_GEN_15..18)`，而 `_GEN_15..18` 含 `~hit`），
第三个 `!hit` 发射点已覆盖。当前 epoch 的权威分类为 **336/336、16 个 native
producer、0 未知**，分母不变、不授予功能信用；不是靠行号文字猜的不可达。

148 个未覆盖 branch 分为 ScDut 128 与 WriteBuffer 20。ScDut 侧包括 4 个 bias
bank 副本、17 个 MainBTB-entry→SC-index 优先级、8 个阈值端点、6 个 path 权重
端点、29 个 bias 权重端点、46 个 correct/wrong slot→way 矩阵格、18 个 global
权重端点；其中阈值端点由外部 `[640,5040]` 资格和每拍至多 15 的增减证明不可达，
其余是同一饱和算术或选择在按行/按 way 副本上的未执行实例，行为由
SC-005/007/008/012/013/014/019 在已执行副本上验证，明确不声称每一行都被执行。
WriteBuffer 侧有 2 个四 entry 全 dirty 的 `victim = replacerWay_0`、2 个同守卫
三元 else 死臂和 16 个死守卫头。全 dirty 臂在 51 项中从未到达，而
`overwrite`/`full` 不是 SC 顶层端口，训练 agent 又按批等待 idle；公开协议下
四笔 pending 写能否共存尚未确认，因此既不能标成“缺用例可达”，也不能标成
“结构不可达”。它登记为开放语义候选，需要只读 monitor 或明确的合同排除，
不计 PASS，也不通过扫 bank/set/way 补数字。

## RAS：调用程序语义与当前原生缺口

### 模型边界

[RasReference](../bpuverify/ras/model/semantic.py)用不可变调用帧和程序前缀表达推测状态，
重复地址按八层分组；模型自行保存八个已提交保留组及有限推测来源。恢复使用模型
自己产生的检查点，不根据输入metadata的地址字段新建golden栈。提交关联到实际
已接受的推测操作，地址来自公开的指令请求，不读取specQueue/SRAM当答案。
resolved属性可以不同于较早的推测分类，这是独立UT的反馈输入合同。

动作按栈代数处理：neutral不改变程序，return弹出，call压入，return-and-call先弹出
再压入新返回地址。这个顺序也与[RISC-V RAS提示](https://docs.riscv.org/reference/isa/v20240411/unpriv/rv32.html)
以及本仓库`BranchAttribute.ReturnAndCall/PopAndPush`的定义一致，不把编码3当成neutral。
程序深度和重复层次投影到公开metadata；排队信用、恢复和提交的可见性单独维护。
同周期提交的保留地址可以已更新，而注册的top仍看到上一版本；模型不借实际top校准。

[默认checker](../bpuverify/ras/checker/semantic.py)比较公开top、压缩分组、重复层次和
分配序号，另核对commit metadata。模型自有已提交分组也与只读memory-direct观测
逐周期比较，包括提交head、全部保留地址和重复计数。这些观测只作为actual，既不
传入算法模型，也不修改它的状态。未使用VPI、internal写入或逐周期JSON导出。
信号采样/半字地址转换仍在[monitor](../bpuverify/ras/monitor/semantic.py)，testcase无边沿等待。

原始队列指针TOSR/NOS、BOS关系及完整FTQ跟踪合法性不是这个程序模型的完整声明，
原有专门检查器仍保留。源码中的128个来源/检查点历史上限也是模型服务边界，不是
额外硬件FTQ容量声明。不能仅凭这个部分状态投影声称全部内部队列关系已验证。

### 三个组合动作差异与旧假闭合

新增 `BPU-RAS-017` 用同一语义分别检查speculation、redirect重做及resolved退休。
准备A、B调用帧后，组合动作应替换B为C，而不增加净深度。全部metadata来自真实
已检查来源；退休场景先由真实推测call提供C地址，再送resolved组合属性，明确是
独立UT的属性纠正合同，不宣称完整FTQ轨迹合法。保留组比较能在提交时直接发现
错误；之后的return消费还保留在场景中，不能用仍活跃的推测C冒充提交正确。

最终诊断选测：[evidence](../results/ras-semantic-dut-20261015-v3/pytest-artifacts/evidence.json)
为**417 PASS、4个普通FAIL、1个原有严格XFAIL，4进程9.32秒**。422项精确collection/
JUnit/三阶段生命周期一致，1830项源码/依赖/DUT哈希epoch核对一致，完整性错误为空。
其中新增语义/负向测试116项、guard审计测试9项均PASS；64种三动作组合另用不压缩
的普通list栈交叉验证，错误公开字段及保留地址/计数都触发异常且不重同步。

三个新FAIL属于同一组合语义缺失：

| 入口 | 首个失败状态 | 预期 | 实际 |
| --- | --- | --- | --- |
| speculative | native tick34，top与分配序号 | C=`0x40003008`，分配序号3 | B=`0x40002008`，分配序号2 |
| redirect redo | native tick40，top与分配序号 | C=`0x40003008`，分配序号3 | B=`0x40002008`，分配序号2 |
| resolved retirement | native tick40，保留组2地址 | C=`0x40003008` | 仍为B=`0x40002008` |

表中地址是字节，实际端口为半字编码；tick不是cycle。退休失败时公开top/metadata
仍显示活跃的推测C，**仅检查预测地址会漏掉这个提交错误**。

### 2026-10-20：组合动作的覆盖指纹与启用门控

本轮补齐三个情况枚举后再次测量：`RasStack.sv` **569/585行、200/216 branch**。
剩余16行和16个branch arm全部是提交拍同时 push+pop 的组合写
（`commitStack_N_ctr <= commitTop.ctr - 1`，8个提交栈格×两种 nspUpdate 选择）。
公开提交口只有一个 `rasAction`，只有编码3会同时置起 pushValid/popValid；
`Ras.scala:109-110` 却只匹配2/1，因此组合动作落入 neutral。这16行不是缺测试，
而是同一组合语义缺失的源码级覆盖指纹；在没有公开 pushValid/popValid 引脚时
不能合法到达，也不应通过内部写入制造覆盖。

同轮补强的用例：相邻 call→neutral 仍消费刚压入的返回地址（命中
`RasStack.sv:854`，单次 `act` 的空拍会走 writeBypass 臂）、12层不同调用跨越
三比特 ssp 回绕后按 LIFO 展开、恢复九层且 ssp 已回绕的真实检查点。
三者均PASS，不新增功能点ID。另有一个测试期望写错的初版（把 pop 返回值当成
被弹出的帧）被独立参考否定，修正后PASS；未据此误报RTL缺陷。

启用门控的差异仍保留：`Ras.scala:71-72` 的 pushValid/popValid 不含 enable，
只有 `spec.fire` 含；禁用调用仍推进 ssp/sctr/tosw。严格XFAIL
`test_disable_gate_preserves_stack` 与普通FAIL的覆盖率闭合用例都在，未新增XFAIL。

另外一项普通FAIL是旧 `test_ras_functional_coverage_closes_defined_bins` 在disabled
操作后仅断言top保持。它的地址的确保持0，但group从0变1、分配序号从0变1，旧
覆盖曾因此假闭合。现在默认模型拒绝该状态，测试补完整metadata断言并关联已有
`BPU-RAS-008`，功能点状态变为FAIL；原严格XFAIL不变，未增加新的skip/XFAIL。

新增覆盖两组各三个稳定入口bin。31个诊断输入中，reached=3/3，checked=0/3；
只取PASS来源的26个输入时，两组均0/3。故不得报告“组合动作已覆盖且通过”。
生产门禁要求两个schema且全满，附加group数从41增至43。
`ras-semantic-publication-gates-20261015-v2` **184 PASS、43.14秒**，覆盖matrix拒绝策略
及并行证据完整性；提交观测增加之后的三个负向检查另包含在上述最终RAS选测中。

并行证据producer修复一个正交问题：pytest普通FAIL/ERROR/严格XPASS的worker退出码1，
若能由完整且同worker的失败报告解释，不再误称为“worker证据丢失”；退出码1但无
失败报告、退出2/3/4/5、崩溃、缺失/重复记录及artifact校验失败仍拒绝。根回归退出码
仍1，发布门禁仍失败。`tools.refresh_coverage`仍拒绝发布失败选测，当前原生汇总
明确命名为diagnostic且保留`pytest_exitstatus=1`，没有转成成功摘要或覆盖既有报告。

### 16个缺失原生行点不是缺少重复return场景

当轮原生测量
仍为 **569/585**，与此前合格基线相同。源级
[guard审计](../results/ras-semantic-dut-20261015-v3/guard-audit.json)覆盖全部16个未命中DA键：

- 8个递减副本位于increment优先分支的 `else if`，要求同一selector既false又true。
- 另8个副本在外层push路径内又要求pop；父[Ras.sv](../rtl/ras/Ras.sv)从同一个已注册
  rasAction分别产生`==2`的push与`==1`的pop，当前两态关系不允许二者同时为true。

审计检查精确父端口表达式、子块begin/end嵌套、即时优先条件和guard定义，绑定源
哈希及native原始文本；源码/未命中集合变化即拒绝，放松关键约束的负向对照存在
满足赋值。它只是**源绑定的两态局部guard/父输入关系证明，不是整RTL形式化证明**。
585原生分母及16未命中项全部保留，没有通过扣除它们宣布100%。

这说明不能把每个低行覆盖率都归因于少测了一个功能：这里普通重复提交递减已被
检查，缺口来自生成的冗余副本；反而重要的ReturnAndCall走已覆盖neutral路径，原生
行点不会提醒它缺失。提升验证质量须补语义功能点，而非遍历8个slot刷不可能的路径。
RTL未修改；此轮没有新增合格行点，先前BPU-INT-074的31点增量仍是独立历史证据，
不是当前全量回归的汇总。该RAS选测时默认语义模型为UBTB、URAS、ITTAGE、SC、RAS；
后续UTAGE已接入，见下一节。其余四个UT及全量验收仍未完成，目标保持未完成。

## UTAGE：历史条件化方向学习，不镜像内部寄存器

[UtageReference](../bpuverify/utage/model/semantic.py)独立维护两张512行方向表、完整15位tag、
饱和计数器和useful。输入为预测上下文、上游基础分支、已接受反馈及恢复事件；折叠历史
用逐位奇偶法计算，hash、provider选择和更新均由模型自行求出。算法文件不依赖DUT、
picker或xreactor；不读取实际条目、counter、useful、shadow槽位或dirty mask来生成预期。
配置承诺15位tag，不能为了匹配当前8位容器而截断golden的tag。

学习以分支事件为单位：最终位置之前的条件分支按not-taken学习；最终条件分支按resolved
方向学习；同位置的非条件分支不学习条件方向。最早错误位置产生分配义务，选择provider
之上首个useful为零的表；分配弱方向计数器，正确且与base意见不同才增加useful，错误
则减少，意见相同保持。128次失败分配后lower逐一递减、upper减半；全局aging与局部
学习同边界时的优先合同也明确验证，而不是用固定延时凑波形。

周期准确描述的是可见性：反馈接受、资格快照、学习生效和写入退休是不同事件；连续
反馈要转发前次counter版本，不能重复使用旧metadata；已发出的预测保存不可变读快照。
有界最近更新使用版本号和写入义务表达，同地址旧版本取消不允许误清新版本。调度与
容量属于配置的可观察合同，但算法不逐位复制RTL的dirty/priority next-state逻辑。

[monitor](../bpuverify/utage/monitor/semantic.py)只在适配层解码公开端口及RiseWrite消费
边界。AheadBTB的组合输入另在输出采样相位解码，不以DUT预测值校准模型。memory-direct
只读useful/tick是actual：复位后及aging后全体比较，其他时刻检查本次学习坐标，包括
应当保持的坐标。[默认checker](../bpuverify/utage/checker/semantic.py)比较所有定义的
公开字段，并核对流水请求的PC、tag历史和索引历史。未定义的idle/非条件payload只按
输入资格排除，不能按actual.hit排除；任何定义字段错误仍抛出pytest失败且不重同步。

### 2026-10-21：有界放行、文件系统假失败与 1099 行的按 cell 归因

本轮把 UTAGE 的**判定映射**和**基础设施**分开修，而不是改语义：

- 三个已登记缺陷（007 tag 截断、016 shadow 环同槽清 dirty、021 高地址 provider
  被 007 阻断）此前由独立参考先于场景自己的异常报出，strict marker 不匹配，
  于是被报成普通 FAIL 或在第一个差异处中止。新增
  `allow_known_miss(pc, position)` 与 `allow_known_counter_difference(table, index)`：
  放行绑定到**具体地址/单元**，只删除声明字段（hits/meta_valid/该槽的命中派生字段，
  或单个 counter），tag、position、base、其余槽位与单元继续比较；每次放行记录
  tick、地址/单元、期望/实际与原因。7 项纯负对照覆盖非声明地址、反向差异、混合
  命中差异、非 counter 字段、错误单元与非法声明。
- 首轮全量中三个 XFAIL 变成 FAIL，根因是 per-case 隔离目录未创建导致的
  `FileNotFoundError`，不是 RTL。harness 现在进入用例前建目录，新增
  `write_output()` 只创建路由父目录，5 处直接写文件改为该接口；
  `tests/framework/test_artifact_paths.py` 20 项 PASS。
- 补一个**有区分度**的缺失情况：007 之外的恢复用例此前只训练下表，快照
  `tableId=0` 无法区分“重放保存载荷”和“重新查到同值”。新增
  `test_override_upper.py`（S2/S3 × 位置 5/7，4 PASS）先在下表保护后训练上表，
  要求恢复后 `tableId=1/counter=4/direction` 原样重放；改 override PC 只改变
  tag 匹配（hit=0），方向仍来自保存快照。关闭 `UtageDut.v:1121`。

最终选测 **250 项：212 PASS / 35 FAIL / 3 XFAIL**，冻结 epoch 与 3042 文件一致。
35 个 FAIL 与基线**逐节点相同**；离开 FAIL 集合的 4 项恰是 3 个已知缺陷（回到
strict XFAIL）与 1 个被 007 阻断的分配矩阵（现在 PASS）。

原生测量 **9954/11053 行、3248/3746 branch、9144/13376 toggle**。增长的行
（+730）全部是 `usefulEntries_*_value <= 2'h1` 分配臂与其 `if` 头（各 365 个）：
021 之前在第 8 个高 tag 地址中止，现在完整跑完 512×2，这些 cell 真正完成分配。
这是“把已定义矩阵跑完”的按 cell 副本命中，不是新功能，也没有改分母。

剩余 1099 行全部在 `BypassShadowBuffer.sv`（另一表的 `BypassShadowBuffer_1.sv`
已满覆盖），模板审计为 367 奖励 + 366 惩罚 + 366 `else if` 头，即同一
(bank,set) useful 更新模板的按 cell 副本；剩余 497 个 branch arm 是低表 aging
`value==0 ? 0 : value-1` 的逐 cell else 臂（本轮 15 个 cell 到达，语义由
UTAGE-017 在 4 bank × 3 strength 上验证）。`UtageDut.v:1133`（上表恢复的 slot 2
方向）在位置 6/7/8 × base 0/1 × S2/S3 探针下仍未命中，登记为开放，不称不可达。

组合审计（`docs/utage-combination-matrix-20261020.md`）额外确认了三个不能算
“已覆盖”的格：`io.redirect` 是死开关（模型表达、RTL 有 `~io_redirect` 门控，
但 `UtagePorts` 从未绑定、无用例驱动）；单端口 SRAM 强制写回与读同 bank 冲突会
让合法读退化为 miss，而模型未表达该规则；反馈与 S2/S3 恢复同拍未构造。

### 2026-10-21：UTAGE `io.redirect` 死开关修复与 BPU-UTAGE-026

UTAGE 的 `io.redirect` 与 ABTB 同类：monitor 解码 `redirect`、独立模型在
`advance` 里用它清 `frame.valid`/`redirect_bubble`，RTL 也在 A2 用 `~io_redirect`
门控 `a2_abtbHitVec_*`，但 **ports 没绑定、fast-lookup Bundle 没字段、driver 从不驱动**。
本轮补上 `redirect=dut.io_redirect`、Bundle 字段、`UtageLookup.redirect`（显式 bool
校验）与 `BPU-UTAGE-026`，并新增 `test_redirect_flush.py`：在途查询遇到相邻拍
重定向时该窗口 `hit=0` 且四个 AheadBTB 槽 `valid=0`，随后同 PC 查询仍返回原
provider/位置/计数；同一程序**无重定向时必须保留命中**作为对照，idle 脉冲不
制造也不销毁记录。全量选测 **251 项：213 PASS / 35 FAIL / 3 XFAIL**，35 个 FAIL
与上一轮逐节点相同，行/branch 不变（9954/11053、3248/3746），toggle
+6（9144→9150）；`UtageDut.v:1133` 仍是唯一未命中的 DUT arm。

### 2026-10-21 补：写压力下同 bank 读的更正与 BPU-UTAGE-027

上一轮把“单端口 SRAM 强制写回与读冲突”写成“模型未表达”，**这是错的**。独立模型
已有 `RecentUpdates.pressured`（未完成义务 > 6，等同 RTL forceWrite 条件），并在
“写缓冲未命中 + 有可退休项 + pressured + 同 bank”时把该条目置无效。

新增 `BPU-UTAGE-027` 与 `test_write_pressure_bank.py`：固定 PC 的八个折叠历史
（表 0 tag 均在实现位宽内，刻意避开 007）在 bank 0 上相邻拍一次提交，先断言
`outstanding>6` 且 `pressured=True`（证明压力真的到达），再逐条回读要求各自命中、
方向与计数，最后断言积压量下降（证明强制写回推进而非无限保留）。

仍未构造的是最强形式：条目已被挤出写缓冲、只在 SRAM，同时同 bank 强制写回压掉
`srcalRealReadEntry.valid`——构造它必然跨越 ring 槽复用，与 `BPU-UTAGE-016` 重叠。
本轮没有制造第二个重叠场景，避免把两个缺陷混成一个结论。全量选测
**252 项：214 PASS / 35 FAIL / 3 XFAIL**，35 个 FAIL 与上一轮逐节点相同，
行/branch/toggle 均不变。

### 2026-10-21 补二：恢复与在途反馈的组合，以及一个被否定的控制假设

`test_override_with_inflight_feedback.py`（S2/S3，2 PASS）：先提交恢复请求，再让一笔
真实 not-taken 反馈落地。响应必须重放提交时刻的快照（`ctr 5 / taken 1 / table 0`），
而同一程序的 fresh 查询给出 `ctr 3 / taken 0`；**两者必须不同**才证明恢复没有重读
当前候选。若 fresh 查询没有变化，上面的断言就是空转，所以用例把这一点也断言了。

这里同时记录一个被实测否定的假设：最初想把“反馈先落地时恢复应等于 fresh 查询”
作为控制组，实测并非如此——override 的设计就是复用**更老的** A2/A3 快照，与最新
读相等并不是义务。把“相等”写进控制组只会制造假失败，因此只保留“重放提交时刻
快照”这一条独立义务。该格从“未验证”改为已覆盖。

### 2026-10-21 补三：上级组合的双预测器同拍比较见证（INT-108/109）

子模块闭环只证明“各预测器自己会撤销、自己会命中”，不证明**组合层**在同一拍
真的比较了两个窗口。本轮补两个见证功能点，都用继承默认 `PipelineChecker` 的
观察者，只统计比较事件与模型给出的仲裁值，不改任何比较逻辑：

- `BPU-INT-108`（`test_composition_shared_redirect.py`）：重定向拍上同时比较
  `ahead` 与 `early_direction`，实测 5 拍，其中 tick434 有真实 ABTB 命中。
- `BPU-INT-109`（`test_composition_main_ahead.py`）：正常服务拍上同时比较
  `ahead` 与 `main_metadata`，实测 **29** 拍同时比较、**13** 拍两边都有真实命中、
  **3** 拍（400/402/404）早级来源属于 AheadBTB 来源且存在 S2 选择。

三条断言是递进的，专门防两种空转：一是“空窗口对空期望”，二是“两边都命中但仲裁
静默退回 fallthrough”。两个见证互不替代：前者是重定向路径，后者是正常服务路径。

过程中两次踩到同一类错误：`records` 是有界 deque（且首次 capture 可能为空），
用“长度变化”或直接 `records[-1]` 都会失效——见证类检查器的边界条件必须单独测。
本轮同时新增 `tools/run_cost.py` 与 `docs/run-cost-analysis-20261021.md`，
把“先预览成本、按块运行、运行期冻结工作树”写成纪律：BPU 侧存在单例 1340s 的
`test_integrated_state.py` 与合计 1840s 的 `test_integrated_abtb_counters.py`，
一次不加选择的选测很容易演变成两小时空等，且运行中改文件会让整轮因 epoch 变化作废。

定向 14 项运行（`results/bpu-upstream-20261021-v4`）为 **13 PASS / 1 FAIL**、
47 秒；唯一 FAIL 是文档已记录的 `BPU-INT-044 full-tag-high-bits` 反例，未修改。

### 2026-10-21 补四：重定向与训练反馈同拍（INT-110）

既有程序从不把这两个事件放在同一拍：对 `early_direction` 程序采样 254 个被比较拍，
`redirect` 只有 5 拍，而 `redirect + training(valid&ready)` 是 **0 拍**。因此之前
所有"绿"的结果都不包含这一格。

`BPU-INT-110`（`test_composition_redirect_training.py`）在同一拍启动两个独立脉冲
驱动，用继承默认检查器的 `CollisionChecker` 记录该拍，并断言：该拍确实存在
（tick 520）、模型中**同时**构造出 `Redirect` 与 `Feedback`（二者均 `true`）、
且 `middle_repair=final_repair=0`（flush 归属于重定向而非训练）。

它只证明**事件被建模**，不证明碰撞后的学习状态一定正确；`evidence.coverage` 为空，
不授予覆盖率信用。定向 12 项运行（`results/bpu-upstream-20261021-v5`）为
**11 PASS / 1 FAIL**、47 秒，唯一 FAIL 仍是已记录的 `BPU-INT-044 full-tag-high-bits`。
行数从上一轮的 27404 降到 26169 是**选择集变小（14→12 项）**所致，不是覆盖率下降。

### 2026-10-21 补五：AheadBTB 重复副本在集成层的缓冲可见性（INT-111）

`test_conditional_prefix.py` 的压缩入口 profile 在集成 BPU 中曾稳定失败：同一比较拍里
参考模型认为 way1 已失效，DUT 仍报告 way1 命中（`ahead.1.valid/micro_valid/meta_hit`、
`early_direction.1.valid`，以及一个 fast S2 变体）。失败在 tick 940 首次出现，持续
15 个被比较拍（至 tick 970），8 个 profile 中只有 4 个 compressed-entry 失败，
conditional-entry 全过。

逐拍证据（`first_failure_context` + 记录全部差异的探针）：

- 参考帧 `row=1 bank=3` 的 way1 已无效，memory 中该 way 也为无效；
- 参考的 bank3 写缓冲中仍保留该 `(row=1, way=1)` 的失效版本（order 7，已退休），
  说明模型确实发出过这次清理，而不是从未检测到重复；
- DUT 的 way1 与 way3 内容完全相同：position=2、kind=1(conditional)、action=0、
  target_low=515；两者的命中只会产生同一个唯一 taken 分支，已发布的方向/目标/位置/
  修复字段在失败拍上逐字段相同；
- 单独用探针把全部 scoreboard 差异记录下来并让程序继续执行：除这四个 way 级命中标记
  外**没有任何其它差异**，8 个 profile 的程序级语义断言全部成立。

因此这不是“DUT 少清一次”的功能缺陷，而是单端口 bank 写回优先级的可见性差异：
AheadBTB 模块合同明确写回要等读空闲窗口（ABTB agent 的 `drain_bank_writes`
注释与用例），集成层的持续 S0 读取会把该写回推迟。参考模型在 memory 层提前可见，
检查器按逐拍 way 命中比较就产生了假阳性。

处理（`BPU-INT-111`，`bpuverify/bpu/checker/pipeline.py` 的
`buffered_duplicate_allowances`）：

1. 额外 way 必须与参考同一行的某个命中 way 内容逐字段相同（position/kind/action/
   target_low），否则失败；
2. 参考 memory 中该 way 必须已无效，且参考持有该 bank/row/way 的失效版本；
3. 只放行 absence 标记；`choice*`、`prediction`、`fast_*` 的 target/taken/position/
   kind/action 与 metadata 仍全部比较；
4. 每个放行记录 tick、bank、row、way、幸存 way 与字段，并对同一 bank/row/way 设
   64 拍有界窗口；超出即失败，避免把永久残留当成“延迟写回”；
5. 用例在 16 拍预测保持的空闲窗口后重读同一行，断言旧 way 的期望=实际=0
   （`duplicate_history`），证明清理没有丢失，只是被缓冲。

负对照（`tests/bpu/scoreboard/test_buffered_duplicate_allowance.py`，10 项纯检查）：
内容差异四类（position/kind/action/target_low）、参考仍认为副本有效、缺少失效版本、
失效版本指向另一 row 或另一 way、以及来源不是 AheadBTB，全部拒绝放行。正向格还断言
幸存 way 的 `valid` 与 `target_low` 仍在比较中，放行只删 absence 键。

结果：4 个 compressed-entry profile 各 15 拍/30 项放行；conditional-entry 为 0 放行；
8 个 profile 全部 PASS，且空闲窗口后旧副本消失。该放行不改变任何 XFAIL，也不把
连续读取期间的清理时延上界写成合同；ABTB 模块级的写缓冲/drain 验证继续独立保留。

### 2026-10-21 补六：UTAGE slot-2 上表恢复，最后一个未命中 DUT arm 归零

`UtageDut.v:1133`（`a2_abtbTakenVec_2` 在恢复时按 `overrideAbtbTableIDVec_2`
选表）长期是唯一未命中的 DUT arm。上一轮结论是“位置 6/7/8 × base 0/1 × S2/S3
探针仍未命中，登记为开放”。本轮找到**形状原因**，不是激励强度问题：

- 所有既有恢复用例只呈现**单分支** AheadBTB beat；
- 单分支 beat 的 slot 2 回退位置是 `position + 2`（`driver/encoding.py` 的
  `fastPositions` 填充），而在 `position` 上训练的表项永远不可能是 slot 2 的
  provider；
- 因此这一臂在单分支形状下**结构不可达**。

改用真实三分支 beat `(2,4,6,empty)`：先在位置 1 训练下表（该位置不出现在该 beat
中）保护下表该索引，再只对位置 6 提供真实结果——它既是唯一错误来源，下表又被保护，
分配必然落到上表。随后以 `s2`/`s3` 重新携带**同一 beat** 恢复，断言
`tableId=1、cfiPosition=6、takenCtr_value=4、predTaken=1`。

为此在 `bpuverify/utage/agent/main.py` 增加 `submit_predict_branches(override=...)`
与 `recover_prediction_branches(...)`，让恢复路径能重新携带多槽 beat；这是把已有
agent 能力接到恢复路径，不是新驱动语义。

**实测** `results/utage-slot2-upper-20261021-v1`：**218 PASS / 35 FAIL / 3 XFAIL**
（256 项，epoch 3055 changed=0），35 个 FAIL 与上一轮**逐节点相同**（`added=0`、
`left=0`）。覆盖率变化：

| 指标 | 上一轮 | 本轮 | 变化 |
|---|---:|---:|---:|
| RTL 行点 | 2364/3097 | 2364/3097 | 0 |
| RTL branch 点 | 3248/3746 | **3249/3746** | +1 |
| RTL toggle 点 | 9150/13376 | **9152/13376** | +2 |
| 源码行 | 9954/11053 | 9954/11053 | 0 |

**行覆盖不变是关键证据**：该行本身早已执行，缺的是该分支上的表选择取值。
所以“行 100%”不能推出这条语义已覆盖，这是一次典型的 branch 级缺口，而不是补行。

一条必须写明的边界：实测恢复拍 `slot["valid"]=0`、`hit=0`，但保存的
`tableId/cfiPosition/takenCtr_value/predTaken` 仍是原值。`valid` 来自上游 beat 的
当拍有效位，恢复请求在采样拍已不再携带该位。因此用例只断言**保存身份与方向**，
不断言重造的 `valid/hit`；后者仍由独立参考模型逐字段比较。这不是放宽，而是把
“原始方向来自保存表”与“当拍 beat 有效”分开。

**该区间的臂已全部命中**：全量选测中 1100–1200 行只剩 `1133 cond_then` 一项未命中，
本轮之后为空（`uncovered_rtl_branches` 的 497 项全部落在
`BypassShadowBuffer.sv`）。早期只跑 2 条用例的探针曾把 slot 1/slot 3 的同类臂也
列为未命中，那是选择集过小的假象，不作为结论。

### 2026-10-21 补七：共享重定向从“比较发生”推进到“撤销生效”（INT-108）

`BPU-INT-108` 原先只证明：存在 5 拍重定向且同拍比较了 `ahead` 与
`early_direction` 两个窗口，其中 1 拍 ABTB 有真实命中。这只排除“全 miss 空转”，
并不证明撤销真的发生。

本轮在同一 witness 内加入第二层：以重定向拍为锚，记录其**下一个无损比较拍**
（tick+2）的两个窗口，要求 `ahead.meta_valid == 0`、四个 `ahead.*.valid` 全 0、
四个 `early_direction.*.valid` 全 0、`raw_hits` 无 1；并要求至少一组配对的
**重定向前**一拍确有真实命中。

实测（`results/bpu-upstream-20261021-v6`，46 项全 PASS，epoch 3055 changed=0）：

| 项目 | 数值 |
|---|---:|
| 重定向比较拍 | 5 |
| 后续比较拍 | 5 |
| 后续拍 ahead valid 全 0 | 5/5 |
| 后续拍 early valid 全 0 | 5/5 |
| 后续拍 meta_valid = 0 | 5/5 |
| 重定向前有真实命中的配对 | 有（tick 434，`ahead_hits=[0,0,1,0]`） |

**为什么断言“后一拍”**：`AheadSources.advance` 把重定向的失效应用到下一状态，
重定向当拍呈现的仍是撤销前内容。若把“当拍即空”写成期望，就是凭空造一条 RTL
不满足的要求——那是假阳性，不是更严格的验证。

仍不证明“撤销后重新查询可恢复原 provider”；该义务由 `BPU-ABTB-054` 与
`BPU-UTAGE-026` 分别在子模块内承担，组合层不为它们重复授信。

### 2026-10-21 补八：SC 全脏写缓冲的可达性由只读 monitor 判定

`sc-module-qualification-20261020-v2` 把 `WriteBuffer` 的 `all_dirty_victim`（四槽全脏时按
`replacerWay` 覆盖）登记为开放项，理由是“四笔写能否在公开协议下共存未确定”，并认为需要读
`rtl/sc`/`dut/sc`——该读取超出授权，故阻塞。

本轮换一条已授权的观测路径：集成 `BpuDut` 通过 memory-direct 暴露每个 SC 写缓冲的
`shadowValid_0_{slot}`、`dirty_0_{slot}` 与 `io_read_0_ready`（`bpuverify/bpu/monitor/sc/observer.py`
本来就绑定）。新增只读见证 `tests/bpu/testcase/test_sc_full_dirty_reachability.py`，继承生产
`FullScChecker`，在 2 bank × 4 way 共 8 个物理排列上逐周期统计全部 **10 个** buffer（5 张表 × 2 bank）：

| 指标 | 实测 |
|---|---:|
| post-reset 比较周期 | 3500 |
| 每个 buffer 的最大 dirty 占用 | **1 槽**（全部 10 个） |
| `full_overwrite` 次数 | **0** |
| 排水被拒（`io_read_0_ready=0`） | 13900 buffer-cycle |

**必须排除 reset 当拍**：8 个程序都在 tick 1 出现 `dirty=4, valid=2`——上电未初始化的影子
寄存器，既不满足“dirty ⇒ valid”的模型不变量，也不是语义状态。把它计入会得到相反的
“可达”结论，这是典型的假阳性陷阱。

机制上：每个被接受的反馈之后训练事务都会等待流水线提交，写与写之间隔得远，排水总有机会
清掉前一个脏槽；要到四槽全脏，必须四笔不同 `set_index` 的 miss 在四个相邻拍进入同一 buffer、
且三个边沿的排水都被拒绝。排水被拒本身很常见（约占 39%），但两者在公开程序里从未叠加。

模型侧本来就能处理：`bpuverify/bpu/model/sc/full.py` 的 `full_advance` 已实现 `full_miss`
（按 `victim(plru)` 覆盖、`kind='full_overwrite'`），`FullScChecker` 每拍比较全部十个 PLRU
状态并在下一沿确认动作。因此这是**防御路径**，不是缺模型；两个 arm 保留在原生分母中，
不授予覆盖信用。

证据：`results/sc-full-dirty-reachability-20261021-v1`（`reachability.json` + README）。

### 当前真实DUT结果与功能缺失

[最终模块选测](../results/utage-semantic-dut-20261015-v3/pytest-artifacts/evidence.json)：
**315 PASS、6普通FAIL，4进程67.80秒，321项**。其中42项纯模型、负向比较和清理测试
全部PASS。collection、JUnit及生命周期证据完整，integrity错误为空；结束时冻结源码
epoch核对一致。原有狭义XFAIL标记未扩大；默认独立检查在它们声明的异常之前发现
前提错误时，pytest正确报告普通FAIL，不能通过拓宽XFAIL隐藏。

新增 `BPU-UTAGE-025` 的direct/indirect两个入口均普通FAIL：真实warm conditional
provider的counter=3、useful=1；同位置非条件反馈到达后，native tick296模型useful仍1，
实际为0。旧冷态用例只检查“不分配”，没有验证已命中的条件provider不能被非条件
反馈改写。其余失败涉及完整tag、shadow替换后的counter保存，以及分配/更新矩阵的
provider前提；没有把失败反馈纳入PASS功能覆盖。当轮完整选测原生测量为
**6987/11053**，带pytest退出码1；因部分大场景提前失败，不能当成覆盖率下降后的合格
基线，也不能替换此前9904/11053的已发布全量证据。

### 从缺行到语义事件：最大索引与独立上下文

旧基线的1149个UTAGE未命中DA键全部属于lower useful更新副本，383个物理坐标各三个
键（128..511，462已命中）。这不是383个独立语义功能点。它们也不能仅因相同PC/history
下的tag缺陷就宣称不可达：A0索引上下文和A1tag上下文是公开的独立流水输入。

新增 `BPU-UTAGE-024` 使用**单个最大九位索引511**，保持A0不变、切换A1长历史tag，
覆盖分配、正饱和、base一致保持、三个真实旧预测来源的连续负反馈、零保持、长provider
选择以及六次交错流水请求关联。没有遍历bank/set，没有手造provider或改写真实metadata。
两个稳定语义group分别记录reached/checked，各8/8；比较成功才给checked记账。

[独立选测](../results/utage-semantic-boundary-20261015-v3/summary.json)单项PASS；
[严格行增量](../results/utage-semantic-boundary-20261015-v3/qualified-line-delta.json)为
**+3**，定位到 `rtl/utage/BypassShadowBuffer.sv:7916`、7917、7919，即lower useful的
index=`3+4*127=511`更新。构建/信号哈希、SF/DA键及原生文本均核对；该场景自身原生
命中4215/11053，不将历史集合并集冒充当前全量9907/11053。

原物理allocation分母2048、update分母8192完整保留；本场景只给独立检查成立的
2个allocation和4个update坐标bin记账，其余地址仍未闭合。新增两类语义需求共四个
group纳入生产门禁，附加group数43→47；此前对应门禁选测196PASS。源码内旧全量
地址场景仍待按语义/物理两层进一步整理，不能用本场景替代完整地址证明。

该UTAGE选测时默认独立语义模型为六个UT：UBTB、URAS、ITTAGE、SC、RAS、UTAGE。
当时ABTB、MBTB、TAGE及完整BPU仍未完成；前三者后续结果见上文，当前默认九个组件
UT已接入，完整BPU仍缺。新缺陷未改RTL、未新增skip/XFAIL，全量验收与覆盖闭合目标
仍未达成。

## UBTB 样板

- 算法层：[model/semantic.py](../bpuverify/ubtb/model/semantic.py)，没有 xreactor、
  picker 或 DUT 对象。输入 `UbtbEvents`，状态为条目、逻辑recency树、在途学习和lookup。
- 适配层：[monitor/semantic.py](../bpuverify/ubtb/monitor/semantic.py)，只采公开端口；
  用 `@on()` 解码事件与观测响应，不生成 expected。
- 比较层：[checker/semantic.py](../bpuverify/ubtb/checker/semantic.py)，默认在 agent
  启动时启用；无显式 expected 的预测也必须与模型比较。无效响应只检查valid，命中
  响应比较全部有效字段。失败给出事件、周期、独立状态与字段差异，不自动重同步。

复位撤销未完成语义请求；该模块的lookup暂存不是全部reset寄存器，因而reset期间及
reset后第一个新请求之前的闲置输出不能当成响应比较。此资格由输入事件决定，不由
actual.valid 决定。RiseWrite待写值与真正消费边界的转换只在monitor适配层处理。

模型复刻配置的**可观察行为**而非理想无限容量 BTB：部分tag别名、PC区域目标重构、
可信度耗尽及无target-fix都在合同中明确。对于无效 payload 位、无效 metadata 域，
比较器忽略它们，不能由这些未定义位制造假错误。

### 当前资格验证与新发现

`results/ubtb-semantic-dut-20261015-v8/evidence.json`：**98 PASS、1普通FAIL、
0 ERROR/XFAIL/SKIP，证据完整且无integrity错误，8.03秒**。其中54项为新增纯模型/
负向比较测试，全部PASS；其余为实际模块组件和场景测试。它是UBTB选测，不是十个
UT的全量验收，也未替换已发布的覆盖率报告。

失败是合法条件分支的事件链：taken分配，然后四个连续not-taken反馈。语义参考的
可信度为 `3 → 2 → 1 → 0 → 0`，最终应miss；实际公开响应却是`valid=1,taken=1`。
同一反馈序列分隔发送通过，旧有连续恢复、taken重分配、流水预测及替换碰撞也通过。
失败周期为native tick34（不是34个周期）。此处没有读内部counter来确定expected。

源级原因与该差异一致：
[MicroBtb.scala:206](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ubtb/MicroBtb.scala#L206)
注释要求“已无用且实际taken时重新初始化”，但下一行只传入`notUseful`，缺少taken
限制；连续训练旁路还能将刚耗尽的条目作为hit转发，因此最后的not-taken可能把
可信度重置到3。参考模型按学习语义保持耗尽状态，没有把这个实现分支复制进去。

2026-10-20 复验补充：新增带**不同target**的连续fall-through用例，复活后的公开
响应为`valid=1,taken=1,target=0x80003650`，即把not-taken报告自带的target安装成
taken预测，危害不止是“旧target仍有效”。同轮新增三拍相邻taken用例验证可靠性在
上界保持，命中`UbtbDut.v:1793`的饱和保持臂，使branch从187/192升到188/192；
行覆盖保持794/794。剩余4个branch由生成代码的父守卫或互斥条件决定：
`UbtbDut.v:1785 else`被`t0_hitT1Update`中的`t1_fire_REG`合取排除，
`1790 else`与`770 cond_then`要求`!t1_hitNotUseful`与影子计数为0同时成立，
`MicroBtbReplacer.sv:283 else`与父守卫`predTouch|trainTouch`矛盾。
因此UBTB在行覆盖100%、功能覆盖组全部100%的情况下仍有1个普通FAIL，
不能把覆盖饱和当作功能通过。

复现：

```sh
python -m pytest -q tests/ubtb/testcase/test_semantic_reference.py
```

保持普通FAIL，未新增skip/XFAIL、未修改RTL、未把实际结果回填参考状态。最终硬件
修复仍需按模块学习合同处理；若合同有另一种解释，应先明确规范，而不是为绿灯改oracle。

## MicroRAS：抽象栈而非寄存器镜像

[UrasReference](../bpuverify/uras/model/semantic.py)接收`RasEvents`，其中包含接受操作、
较年轻/较老位置的纠正、推进、退休、redirect和reset。状态只有操作窗口、主顶部的
可知性及预测结果；模型不接收DUT的`hasPush/hasPop/retAddr`等内部状态。

预期按**较老→较新**的操作顺序规约：call压入自己的返回地址；return弹出；
`PopAndPush`先弹出再压入新返回地址。只有主RAS当前顶部是已知的，弹出它之后更深
的内容未知，不能编造返回地址；后续call又可建立已知顶部。纯测试另用**较新→较老**
的消去代数交叉验证，不以同一代码或实际输出计算expected。

cycle、pulse、stream都默认启用[公开事件monitor](../bpuverify/uras/monitor/semantic.py)
和[Scoreboard比较](../bpuverify/uras/checker/semantic.py)，用例没有边沿等待。RiseWrite
待写值转换仍限于adapter。usable=0的目标位未定义；usable=1比较精确地址。URAS不
拥有主RAS深层存储，也不由此声称已验证集成BPU的主RAS或其恢复。继承端口`enable`
在当前MicroRAS实现中没有门控，本模型未凭空给它添加门控规范。
2026-10-20 起改为显式采纳“关闭时不提供可用目标”的合同：`Bpu.scala:101` 把
`rasEnable && mbtbEnable` 接到 `uras.io.enable`，主 RAS 有对应门控，父级在
`Bpu.scala:284-285、321-322、551-558` 无条件消费 `specOut.isCanUse/retTarget`；
因此新增 `BPU-URAS-017` 并在模型中用 `RasEvents.enabled` 门控公开 result。
只声明公开使用资格，不宣称关闭期间内部流水线是否推进。

原有模块套件接入新模型后：`uras-semantic-dut-20261015-v1` **126PASS**。
补新功能点`BPU-URAS-016`及同时推进场景后：`uras-semantic-dut-20261015-v2`
**127PASS、3普通FAIL，3.86秒**，证据完整、无integrity错误、无ERROR/skip/XFAIL。
新增两个覆盖资格纯测试后的最终模型测试和复验结果另列于该轮结果目录。
最终`uras-semantic-dut-20261015-v3`为**129PASS、3普通FAIL，3.94秒**；其中新增
纯模型/负向覆盖资格测试**108项全部PASS**，真实场景的三个差异完全复现。

三个FAIL都属于同一个缺失语义：return-and-call来自S1、S2纠正、S3纠正时，expected
是CALL_B返回地址`0x4000100c`；S1/S2实际仍返回CALL_A地址`0x40000804`，S3实际
返回主顶部`0x40003456`。它们都是native tick20（不是20个周期）的公开输出差异。
`BranchAttribute.RasAction.PopAndPush`明确代表组合操作，但当前MicroRAS仅使用
`isCall/isReturn`，分别只匹配编码2/1，将编码3落入neutral路径。未为通过而复刻这种
解码遗漏；RTL没有修改，保留普通失败供合同/硬件修复。

### 对覆盖率归因的影响

此前URAS原生行覆盖已是91/91，旧`uras_paths.action`只列0/1/2三种动作。编码3进入
的是已经被neutral覆盖的else路径，故**没有新增行点，但确实有缺失功能点**。因此
“行点缺口→功能点”不是唯一入口；还必须从完整事件语义检查功能覆盖分母。

新增12个稳定事件义务，分`reached/checked`两组，不按循环序号或物理bank划分。
诊断合并包括失败记录时：reached **12/12**，checked **11/12**；组合操作已实际尝试
3次，但一次也没检查通过。仅合并PASS贡献时：两者均**11/12**。全部27个功能输入
中仅24个可作PASS贡献。两组都已纳入完整发布门禁，不能把缺失的第12项删掉或把
尝试信用当成完成信用。覆盖文件只保留计数及有界first/last来源，不导出逐周期JSON。

`uras-semantic-publication-gates-20261015-v1` **114PASS，131.36秒**，包含缺失schema/
缺失bin时的拒绝门禁。该门禁契约的纯测试通过不表示真实DUT功能全通过；失败选测
没有替换已发布全量报告，本轮没有原生行覆盖增长声明。

### 2026-10-20：最后一条branch与启用资格

本轮补一个三阶段缺失情况：S1 return、S2 call、S3 return同拍共存。S2 call抵消
S1 return，但较早的S3 return使深度未知，公开结果应为usable=0。该用例PASS，
命中`UrasDut.v:484`的内层`s3_hasPop`臂；同一行有两个branch point（外层
`s3_hasPush` n=28已覆盖、内层`s3_hasPop` n=58未覆盖），只看报告行号会把缺口
算错。MicroRAS因此达到**91/91行、24/24 branch**，但行/branch饱和不代表功能通过：
`BPU-URAS-016`三个入口仍普通FAIL，`semantic_events.checked`保持11/12。

新增`BPU-URAS-017`：MicroRAS已武装可用目标时，父级enable=0仍返回
`usable=1,target=0x40000804`。父级连接、主RAS门控和无条件消费构成合同依据；
模型新增`enabled`只门控公开result。该点普通FAIL，`enable-gate.reached=1/3`、
`checked=0`，未把第一个disable拍之后的重启用阶段算作尝试。控制toggle均已覆盖；
剩余3594个toggle点属于未使用训练元数据、地址/数据载荷或常量单向信号。

## ITTAGE：自有状态与读取/提交边界

[IttageReference](../bpuverify/ittage/model/semantic.py)独立维护三张表、两bank、计数器、
useful、目标编码与16项region目录，以及被接受反馈、待写更新、写缓存和读取快照。
模型没有DUT/picker/xreactor对象；slot状态是语义字段更新，不是采来的RAM位向量。
反馈经学习与排队后才对后续读取可见；同bank读取优先，另一bank仍可提交；预测使用
读取时保存的不可变条目，并在选取时通过自有目录重构完整目标。

Context既可来自公开折叠上下文，也能由recent history用独立逐位奇偶算法计算。
driver请求的PC和history在响应关联时再核验，不能让错编码输入与DUT共同一致而通过。
默认Scoreboard关联使用既有三周期接口合同，测试不写边沿/gather或提交等待常数。

随机分配不以实际随机位作为golden：模型先算合法候选集合，验证DUT的valid及选择
属于该集合。经过验证的选择随后可以是上游训练metadata输入，这不是把DUT存储
状态回填参考。provider/alternate、可信度、useful、完整目标和有效资格仍独立精确比较。
无效metadata字段和变化的debug计时不比较。

当前范围是固定MinimalConfig，以及guard位为0的正常50-bit字节PC/目标；越界地址
明确报错，未声称guard-overflow行为已经建模。初始化采用公开reset-done握手，不
复刻SRAM物理reset计数。四项写缓存的满miss替换来自其明确声明的非反压合同；
在途同地址字段更新按语义合成，useful-only清除不能消掉未提交目标更新。

原有ITTAGE模块套件接新模型后，`ittage-semantic-dut-20261015-v2` **114PASS、
24.86秒**，包含非零history、全region替换、四个在途索引并行读、反馈资格与长期aging。
补功能点`BPU-ITTAGE-019`后的`v4` **118PASS、2普通FAIL，26.66秒**；新增
reset覆盖资格和类型检查后的`v5` **123PASS、2普通FAIL，26.73秒**，其中79项
纯模型/负向资格检查全部PASS。均为选测且证据完整、无integrity错误/ERROR/skip/XFAIL。
最后的保留目标region绑定边界另有复验，不把早期绿灯当作后续源码的全量验收。
最终`ittage-semantic-dut-20261015-v6`：**124PASS、2普通FAIL，26.78秒**；其中80项
纯模型/负向资格检查全部PASS，原18个ITTAGE功能点PASS，新019为普通FAIL。计划
该次共310个唯一功能点，后续扩展见上文。目标错误及其覆盖缺口保持不变，没有重复
teardown ERROR。

两个FAIL分别覆盖“目标region已存在”和“需要新region”。genuine最高provider
confidence=0且没有新表分配，反馈要求学习`0x41001400`，DUT却输出
`providerTarget=0x40001400`。一个场景还把错误直接送入最终预测；另一个场景因
alternate选择，最终target仍与模型一致，但错误provider元数据没有被掩盖。

源级定位：[Ittage.scala:320](../XiangShan/src/main/scala/xiangshan/frontend/bpu/ittage/Ittage.scala#L320)
在没有表allocation时强制usePcRegion，下一行也只在表allocation时允许region写入。
这与零可信度学习完整新目标的语义冲突。模型未复制该回退，RTL没有修改，保留普通
失败；与既有集成侧发现一致，但不能因此声称整个BPU参考模型已完成。

新增两种稳定事件义务及reached/checked两组，只有完成提交后的完整目标消费者比较
通过才给checked信用；reset撤销前一epoch的未完成义务，同地址合并不伪造中间消费。
`v4`诊断合并：reached **2/2**，checked **0/2**；仅PASS贡献两者均**0/2**。
38个功能输入中36个是PASS贡献。已纳入完整发布门禁，未删掉失败分母、未用纯模型
填真实DUT覆盖。`ittage-semantic-publication-gates-20261015-v1` **120PASS、137.26秒**。

独立ITTAGE此前已是1398/1398原生行点；本轮未声明行覆盖增长，也未替换已发布全量
报告。集成`BPU-INT-074`随后已复用此模型解决在途写入oracle问题，资格结果见下节。

### 集成074的周期语义资格

`integrated-ittage-semantic-aging-20261015-v3`：**1PASS、30.91秒**，单场景source epoch
1816项、JUnit与收集结果精确验证。独立模型9054次检查全部通过，269个公共来源
按各自meta tick读取历史快照；每周期tick和维护游标还与已核实硬件的辅助审计交叉
比较。265个真实反馈、一个全局reset epoch、1024个清除写入，读阻塞21次、更新
阻塞1次，六组reached/checked覆盖全部100%。纯模型/诊断兼容与故障测试174PASS。

严格对既有发布基线比较，原生LCOV分母46541及DUT/signal构建哈希不变，唯一PASS
场景归因到功能点074，新增31行点：全局tick reset2、各表clear cursor共3、维护
写缓存slot1路径26。`reports_published=False`，不是新的全量报告，也未把历史与
候选命中并集冒充当前覆盖率。该074资格验证时UT的跨区域错误、UBTB/URAS错误及其他
七个UT模型缺口仍在；后续已推进SC/RAS/UTAGE/ABTB/MBTB，见前述各节。完整BPU语义
reference仍未完成。XiangShan处于detached HEAD，该次验证
没有改RTL，已询问是否另建本地修复分支。

该ITTAGE选测时UBTB、URAS、ITTAGE三套新事件级独立模型已接真实UT，均暴露待处理功能
差异。当前状态以前述模块表及最新MBTB验收为准：八个UT已接默认语义模型，TAGE及
完整BPU仍有缺口；集成BPU还需要独立的组合、历史和恢复模型。

## BPU：组合语义核心与稀疏多分支学习075

### 已补的组合依赖，不冒充完整组合golden

[PathHistoryReference](../bpuverify/bpu/model/path_history.py)维护完整52-bit逻辑path word，
每条taken边做两位推进并加入独立地址贡献；not-taken不插入path边。checkpoint是
模型自己生成的不可变版本，restore回到该版本再应用真实分支结果，不接收实际
`phrLowBits`来修正history。复制/伪造、其他实例、复位前和已retire的checkpoint都
不能成为golden恢复输入。完整19种fold由逐bit parity求值；物理循环存储寿命、
FTQ checkpoint的释放与周期调度尚未接通，因此它不是新的PHR寄存器镜像或完整
PHR物理实现证明。当前地址输入合同是普通49-bit半字PC/target，guard上界仍待组合。

[选择规则](../bpuverify/bpu/model/selection.py)以语义branch候选和可选方向纠正为输入：
ahead有任意有效记录即抑制micro，即使ahead全部NT；选择按branch位置而非way顺序；
S2 raw provider与S3合格纠正不同，S3的SC优先于TAGE；Return与ReturnAndCall不混淆，
ITTAGE只改无Pop的indirect。S2不因target-only差异纠正；S3根据是否已有S2纠正，
决定是否还需比较MainBTB local target，而RAS/ITTAGE仍比较完整目标。fallthrough
单独处理fetch alignment、页面末端与地址回绕。

这两部分22项纯测试PASS。075只在已资格验证的受控预测状态中消费这组选择规则。
随后076/077已将这些核心接入自主周期engine及独立MicroBTB source adapter，见下节；
尚未自动预测全部学习状态下的BPU事件。不能从“已有选择函数”和“各UT已有模型”
推出整个BPU参考已完成。

### 从缺行到条件学习事件

075针对原集成TAGE useful增加路径在非零resolve槽位的缺口。使用一个PC、一个
可重复的genuine history，不枚举bank/set。正常反馈先建立两个**没有alternate**的
强NT provider，再在关闭TAGE学习的窗口把对应MainBTB base训练为taken。最后
开启TAGE，两条provider都NT且base都taken，同一反馈包的resolve槽位1/6都真实
resolve为NT。完整轨迹/FTQ可达性不由这组孤立反馈前置程序声称证明；exercise本身
是两个conditional后fallthrough，不伪造prediction metadata。

准备时发现旧`prepare_two_tage_providers`会给较早分支留下同方向alternate：该条件下
即使provider正确，也**不应**增加useful。因此没有把[0,1]放宽成“验证通过”；改用
MainBTB先占位、首次NT错误分配单个负向provider的真实过程，并明确检查hasAlt=0。
预期仍要求两个counter都2→1、useful都0→1、两个原provider owner保持不变。

[component monitor](../bpuverify/bpu/monitor/tage/semantic.py)从真实TAGE公开IO读取
PC、fold、base和反馈；[checker](../bpuverify/bpu/checker/tage/semantic.py)复用完整
`TageReference`，从reset独立维护全部表、selector、随机分配、aging和在途更新，
不从实际SRAM/随机数/写包初始化或修正状态。所有定义的纠正、raw fast provider和
SC counter均比较；public BPU metadata再关联到确切的自有历史frame。此处普通
ReadyValidMonitor在edge前捕获S3、在下一edge记接受时间，故关联对应的TAGE S2
post-edge frame使用明确的两周期合同，不按相近PC或方便的tick搜索。disabled TAGE
保留旧frame，不能把它声称为当前请求的新source；但是其所有定义的component输出
仍继续检查。错PC/tick/position/counter/useful/way全部拒绝、冻结首错且不重同步。

生成的集成TAGE RTL只含实际消费的9个fold端口，以及base valid/taken/confidence；
未使用的base position/type、其他fold在RTL elaboration时已经没有端口，不是“没开
波形”。绑定只读真实memory-direct端口；未消费的fold只在Context数学适配中留零，
四表坐标等价由4种history测试验证，不伪装成观察了全部19个输入。位置来源是模型
自己保存的S1 context，不读实际SRAM。仍是**TAGE组件cut-point**：上游PC/PHR/base/
feedback路由被观察，不能标作完整独立BPU历史/路由golden。

### 当前证据及没有获得的信用

- [最终独立场景](../results/integrated-tage-semantic-learning-20261015-v8/summary.json)：
  **1PASS，14.07秒**；有效学习接受与比较各4/4规则，evidence完整、integrity为空，
  结束时源码epoch一致。没有ERROR/SKIP/新XFAIL，也未发布为全项目汇总。
- [严格单场景行增量](../results/integrated-tage-semantic-learning-20261015-v8/qualified-line-delta.json)：
  **+2 native DA源行**，`rtl/bpu/Tage.sv:6805`和7455，分别是resolve slot1/6的
  `providerOldUsefulCtr + 1`，来自`Tage.scala:411/487`。相同build/signals/源文本与
  完整SF/DA分母46541均核验。单场景命中25344/46541不是完整BPU覆盖率；不能把
  历史33257与+2直接拼成“当前全量33259”。这是集成BPU行点，不是独立TAGE UT
  4587分母上的增长。其他resolve槽位的相同副本仍保留，不把它们新增为多条功能。
- [当前门禁/纯模型选测](../results/semantic-publication-gates-20261015-v10/summary.json)：
  **356PASS，4进程74.90秒**。包括203项matrix/profile门禁、57项trace开关契约、
  22项组合核心、12项component/坏关联、13项学习资格、49项独立TAGE模型测试。
  075两组加入生产门禁，required group数60→62；源事件未接受、槽位错、MBTB miss、
  非conditional、weak、alternate/base同向、useful已饱和、同owner等均不给reached。
  比较失败不给checked，缺组/变schema/未满rule仍拒绝发布。
- [兼容复验](../results/phr-trace-off-regression-20261015-v1/summary.json)：**14PASS，
  4进程23.25秒**，覆盖10项真实PHR recovery/S2/S3 repair/wrap、4项独立TAGE
  cold/allocation/双向counter。三个旧PHR程序的逐周期JSON已改为现有`--dump-trace`
  按需gzip sink；默认实际产物中没有`phr-recovery/override/wrap-*.json[.gz]`。
  功能coverage与checker继续运行，不以停审计换绿灯。这不是十个UT当前源码全量验收。

075完成时计划共320个唯一功能点；新增076/077后为322个。九个组件UT独立模型仍默认接入，完整BPU组合仍缺；
已知普通FAIL和TAGE026 useful所有权错误未改RTL、未扩大XFAIL。目标保持未完成。

### 自主周期组合076/077与生产metadata接收

[PipelineReference](../bpuverify/bpu/model/pipeline.py)从reset和环境事件推进自己的三级
token：每个请求拥有PC、完整history checkpoint和预测候选快照；由自己的候选独立
决定阶段选择、middle/final repair、请求替换、年轻请求冲刷、next-PC与历史恢复。
模型自己生成occupancy/fire/flush，实际阶段信号只作为actual参与比较，不用于推进
golden。CSR控制有两周期无条件延迟，核心reset不擅自清除该延迟。

输入只有公开配置/ready、redirect与accepted resolve等语义事件；启动时各组件的
SRAM初始化完成状态明确作为**服务可用输入**，不声称独立验证各组件reset扫表长度。
[MicroOnlySources](../bpuverify/bpu/model/micro_sources.py)复用独立`UbtbReference`，
从正常反馈建立条目，模型自有的S3结果产生fast feedback；不读取实际预测表、分配
结果或metadata建立条目。其他预测表必须保持cold或disabled；其他已使能预测器的
学习、call/return学习及FTQ commit均明确报不支持，不能忽略后继续给checked信用。

076在prediction/meta ready同时关闭时检查老请求照常退休、年轻请求保持；用一个
真正已发布source的redirect替换held请求，再恢复预测流。077用正常反馈学习两个
MicroBTB条目，独立预测early跳转、middle NT纠正、年轻请求被冲刷、历史回退及原
请求metadata退休。不枚举bank/set，不伪造checkpoint。每周期还比较所有有效阶段
PC/选择、公开预测及metadata PC/PHR，并用完整逻辑history独立预测9个实际消费的
lookup folds。

这也验证了一个生产接收协议问题：生成的meta端口虽有ready引脚，`Bpu.scala`中
`meta.valid := s3_valid`，且S3不因meta.ready停顿。原先直接用ready/valid握手接收
会漏掉ready低时的metadata。[BpuMetadataPort](../bpuverify/bpu/bundle/ports.py)仅
通过SDK公开`fire`触发扩展改为valid-only，所有物理引脚绑定保持真实；现有SDK
monitor仍负责pre-edge快照、下一edge时间戳和数据流。没有复制队列、假ready、
修改SDK私有方法或改变原source配对周期。076要求原生产agent在meta.ready保持
低时收到正常配对transaction，不用另一条诊断流掩盖丢包。

source关联只允许模型已发布checkpoint；外部低位编码不能回填golden。同编码但
完整history不同必须报歧义，foreign/retired/unpublished/wrong-PC均拒绝。已发布
source保留完整owner，由`retire_source`显式释放，不按固定年龄猜测失效；完整FTQ
epoch/nonce和全部predictor metadata的绑定仍待实现。CommonHR/RAS、其他source-bank
adapter、guarded地址及PHR物理循环存储寿命也未因此完成。

本轮验收（2026-10-15，均为选测，不发布全项目通过）：

- [真实DUT](../results/bpu-owned-pipeline-20261015-v7/summary.json)：**3PASS、2进程
  13.83秒**，含076、077及绑定检查。两类各5条事件，reached/checked四组均100%。
  当前选测原生24646/46541；相对历史完整基线新增DA行数为**0**，不能将新增功能
  检查声称为行覆盖率增长，也不能用选测分子替换全量分子。
- [纯模型/检查器/发布门禁](../results/owned-pipeline-publication-gates-20261015-v1/summary.json)：
  **535PASS、4进程81.04秒**。包括167项流水线模型/反向检查，其中128项是有限
  语义控制组合真值表，不是硬件坐标遍历。错误阶段PC/choice、valid/fire/flush、
  repair、CSR、fold、metadata及丢周期全部冻结首错、不给checked，不改变独立
  预测状态。没有reset/服务/退休的vacuous检查不能成功。延后信用必须有确切的
  下一周期比较。四个新覆盖组加入后required group数62→66；缺组、变schema、
  缺reached或checked均拒绝发布。
- [兼容复验](../results/owned-pipeline-compatibility-20261015-v1/summary.json)：
  **15PASS、4进程23.53秒**，包括10项PHR恢复/纠正/wrap、075稀疏双分支学习、
  4项独立TAGE cold/allocation/counter。未引入默认逐周期JSON导出。

以上三轮均核验结束时source epoch一致、evidence完整、integrity为空；没有新增
skip/XFAIL。按用户选择，本轮不建RTL修复分支、不修改RTL、不重建DUT；已知普通
FAIL保留，完整BPU参考与全量验收仍未完成。

### 原始方向与合格方向078：让两个owner的方向真正有区分性

历史基线仍缺集成`Tage.sv:9951/9969`的fast provider路由。源码语义在
`Tage.scala:121–130`：fast方向按最长历史、同表最低命中way选取，不经过弱provider
的USE_ALT_ON_NA资格；最终方向另在173–176行决定是否允许provider参与。
不能把fast与qualified当作同一方向，也不能因为两条路径偶然都NT就认为owner路由
已得到有区分性的验证。

新增[078程序](../bpuverify/bpu/case/tage/fast_routing.py)只用一个PC/history和两条
正常conditional：先形成T2/way0的较早强NT，再形成同row T2/way1的较晚弱T。
初始counter分别2/4、没有alternate、两条base都NT：独立TAGE模型预期raw为NT/T，
因此S2选中较晚分支；弱T provider尚未取得最终使用资格，因此S3纠正为fallthrough。
只给较晚分支一个新的真实T反馈后counter为5，S2结果应保留到S3；较早分支的
完整定义metadata和owner必须不变。请求、反馈与公开返回均走原SDK driver/monitor，
不读内部条目、随机数或实际写包来构造expected，不伪造metadata，不做bank/set遍历。

为建立有区分性的owner，新增独立模型的`Read.allocation`和
`TageReference.allocation_at_next_accept`：invalid/weak/unused候选、历史表优先和
自有LFSR的学习流水时刻由模型计算。[环境](../bpuverify/bpu/env/tage_semantic.py)
在真实读/更新排空后等待**模型预测的机会**，随后交给原SDK driver接受；核对实际
接受恰在预测的下一输入边界，不能受背压后悄悄换一个时刻。等待有失败预算，
不是固定settling delay，也不根据DUT随机状态调节golden。73项纯分配预测测试
检查只读性、完整接受/学习流水、不同生成器状态、空way优先及非静止/维护时拒绝。

原先按expected target搜索单次override可能跳过多余的同目标纠正；新增agent
`corrections_for`保留整个原请求S1至S3窗口内**所有**override的顺序、PC和tick。
[checker](../bpuverify/bpu/checker/tage/fast_routing.py)由独立TAGE方向和语义选择函数
构造完整期望序列：weak应是S2跳转后S3回退，strong应只有S2。wrong-PC/target/tick、
丢失或多余的override均不能被搜索条件隐藏。case没有边沿等待、pin get/set或task编排。
21项反向/资格检查包括交换MainBTB结果槽位、坏raw方向只给reached不给checked、
strong情况下多余的同目标S3以及不能结束的返回窗口。首错冻结，不重同步。

五条规则分别测量对立owner方向、弱raw的S2消费、弱qualified的S3纠正、增强后的
保留及邻分支隔离，reached/checked两组独立计数。生产发布门禁现在要求68组，
缺组、缺任一规则或schema变化均拒绝发布；原物理分母不缩减。

当前已完成的同一源码epoch选测：

- [最终单场景](../results/tage-fast-routing-20261015-v4/summary.json)：**1PASS、
  10.59秒**，两组各5/5规则；独立TAGE从reset维护全部状态并比较每个定义输出。
- [严格行增量](../results/tage-fast-routing-20261015-v4/qualified-line-delta.json)：
  相对历史完整基线**+1 native DA源行**，`rtl/bpu/Tage.sv:9951`，即预测slot0选取
  T2/way1方向。相同build/signals及完整46541分母核验通过；原生单场景25737/46541
  不是当前全量。另一slot的9969仍保留未命中，不为复制路由再增加物理枚举，也
  不把历史33257直接拼接为“当前全量33258”。
- [模型、负向检查及门禁](../results/tage-fast-routing-gates-20261015-v1/summary.json)：
  **670PASS、4进程85.02秒**，新增分配、返回窗口及覆盖资格检查均包含其中。
- [兼容选测](../results/tage-fast-routing-compatibility-20261015-v1/summary.json)：
  **16PASS、4进程24.62秒**，包括PHR恢复/纠正/wrap、075稀疏学习、076/077自主
  流水线、绑定、嵌套call/return与ITTAGE目标选择。
- [独立TAGE完整模块选测](../results/tage-semantic-dut-20261015-v3/pytest-artifacts/evidence.json)：
  **1091PASS、1普通FAIL、16进程221.73秒**，包括新增73项纯分配规划测试。
  唯一失败仍为026的captured-feedback useful所有权：tick5808、T3/way1，counter5
  正确，但useful期望1、实际0。首错、请求和自有状态均保留，没有新增失败、skip或
  XFAIL。根进程退出1，不能发布完整通过；
  当轮仅供诊断的原生测量
  仍为4467/4587，120个未命中键全部在WriteBuffer，不将失败raw混入合格汇总。

以上证据完整、integrity为空，均非完整全项目发布。078完成时计划323个唯一功能点；
新增的是一项有独立正误判断的raw/qualified路由需求，不是把一个新原生键解释成
整个TAGE已验收。各组件已知普通FAIL保留，不改RTL、不重建DUT，完整BPU组合仍缺。

### 078补强：较晚分支先被发现，方向仍按逻辑分支而非记录顺序归属

剩余`Tage.sv:9969`不是另一个bank需求，而是旧078只运行“较早分支先入MainBTB”
的发现历史。硬件中branch position、MainBTB记录位置、TAGE provider way是不同
身份；较晚分支可以已经resident，随后才发现较早分支。新场景在同一个PC/history
先正常学习较晚conditional，再学习较早conditional；TAGE仍先学习较早强NT、再
学习较晚弱T。这样两种结构的分配顺序不同，不能靠相同方向掩盖错路由。

两种程序历史各自从reset运行，不扫描bank/set，不靠读取实际分配随机数挑时刻。
独立TAGE模型保留全部表、方向、useful、selector及读/学习快照，仍检查所有定义
component输出和公开metadata；完整S2/T、S3/NT纠正，再增强provider仅保留S2的
consumer契约不变。较早邻分支须保持。比较/准备资格移到checker，case不含
assert、edge、get/set、固定settling delay或asyncio编排。

新发现历史不能只由参数标签建立：[checker](../bpuverify/bpu/checker/tage/fast_routing.py)
要求两个真实接受的taken conditional miss（MainBTB raw metadata未匹配），位置按
指定历史且接受tick严格递增。重复、同周期、倒序、非conditional、NT、非错误预测、
已知分支或未ready都不能建立发现资格。新的consumer还须晚于两个实际接受；
reset清除发现和consumer证据，坏输出仍不能重同步golden。
MainBTB输入/上游PHR仍是此TAGE component场景的显式cut point，**没有**将它
宣传成上一节自主Micro/Main pipeline已完整接入TAGE或完整FTQ合法性已证明。

强化同一`BPU-INT-078`，计划仍328，不因多一个原生键再造功能ID。两种发现历史
各保留五条reached/checked规则，共四组要求全满；新增两组进入生产门禁，
required schema88→90。旧顺序不能替代新顺序的覆盖证据。

[最终两场景资格](../results/tage-discovery-qualified-20261015-v1/summary.json)为
2PASS、2进程11.24秒，刺激各0.65秒；四组各5/5规则。
[较晚先发现的隔离差分](../results/tage-later-discovery-isolated-20261015-v1/qualified-line-delta.json)
严格新增**1个原生DA键：Tage.sv:9969**；
[原顺序的隔离复验](../results/tage-earlier-discovery-isolated-20261015-v1/qualified-line-delta.json)
仍严格新增9951，与旧078增量逐键一致。两者相对同一历史完整基线，build/signals、
RTL文本及46541分母均相同；增量不相交，不能合并冒充新的当前全量分子。

[兼容选测](../results/tage-discovery-compatibility-20261015-v1/summary.json)为39PASS、
4进程47.51秒，包括自主Micro/Main组合004、082/083、两种078历史、079、PHR、
RAS恢复/退休及现有pipeline场景。
[完整框架及模型/负向/门禁](../results/tage-discovery-gates-20261015-v1/summary.json)
1767PASS、4进程120.34秒；覆盖错误发现顺序/重复/同周期/倒序、缺失实际接受、
错准备状态、reset失效、过早来源、错phase标签和case分层约束，以及旧078/079
全部错字段/错override检查。缺任一新规则、缺组或schema变化均拒绝发布。
五轮最终epoch核对一致，evidence完整、integrity为空，无ERROR/SKIP/XFAIL。
正式四份根报告与同一历史完整基线哈希一致，未发布选测冒充全量；没有RTL/DUT/
SDK改动或重建，既有普通RTL FAIL及完整BPU组合缺口继续保留。

### Provider/alternate层级079：局部guard不等于原生行点不可达

079将剩余的`Tage.sv:619/621`缺口归因为**更短历史alternate的有区分性选择**，
不是再遍历物理坐标。[程序](../bpuverify/bpu/case/tage/alternate.py)在同一PC/history
用正常反馈建立T2的强NT，随后一次真正的T误预测反馈分配T3弱T，保留T2为NT
alternate。关闭TAGE学习、把MainBTB base训练成T，再恢复TAGE；此时T3和base
都T，只有T2 alternate为NT，错误选择无法靠同方向巧合隐藏。

独立模型预期S2的raw provider使较晚分支跳转，S3的合格alternate将其纠正为
fallthrough。再给该分支一次真实T反馈，T3从4增强到5、T2从2更新到3，provider
重新取得选择资格，完整返回窗口只应剩S2纠正。较早的NT sentinel仍保持base0且
无TAGE provider。准备、保留、方向及全部定义metadata从reset独立推导；不使用
实际SRAM、随机数、分配/写包作为golden，不伪造metadata，也不扫描bank/set。

[环境分配入口](../bpuverify/bpu/env/tage_semantic.py)现支持已有provider上的更长
历史分配；Hint由已经独立验证的source期望值构造，并核对真实接受的PC、history、
base、branch及精确时刻。不合格或无更长历史的分配明确失败，不以固定空等或
观察实际随机状态改变预期。[共用选择检查](../bpuverify/bpu/checker/tage/selection.py)
由独立TAGE frame和语义选择函数生成S1/S2/S3完整预期；078与079共用它，不在
case复制时序匹配/比较算法。MainBTB base和上游PHR仍明确是component cut point，
这些证据不是完整BPU/FTQ oracle或任意反馈轨迹合法性的证明。

六条真实事件规则为：promotion保留短历史alternate、alternate压过相反base、raw
方向的S2消费、alternate的S3消费、增强provider重新取得资格、sentinel未被修改。
新增两组reached/checked进入发布门禁，受管矩阵schema数68→70，不改变既有物理
分母。078和079的component预测事件都增加**真实请求advance**资格：停顿保留
的旧frame仍继续接受正确性检查，但不能重复挣新的预测事件信用。两项专门负测
验证这一点。错输出只给reached不给checked，错关联/丢失或多余纠正冻结首错，
错误消息保留tick、请求及自有状态。

本轮对行点的归因还纠正了一个容易混淆的边界：`_alt_T_21`确实不可能成立，因为
T3命中就已经是最高provider，不能再把它选为自己的alternate。16种table-presence
组合结合当前生成RTL表达式检查了这一**局部两态条件**，不声称全RTL formal，
也不排除任何原生分母。然而这不能推出DA619不可能命中：它位于外层alternate
选择表达式，T2 alternate就能到达。实际同一分母中，历史619/620/621计数为
0/372977/0，本轮初验为3/331/3。620源文本含T3分支却原本已有计数，也说明
native DA与该局部语义分支不是一一对应。归因必须同时核对真实功能事件和原生
插桩边界，不能单看某一行文字把行点标成unreachable。

当前最终独立场景[验收](../results/tage-alternate-hierarchy-20261015-v4/summary.json)：
**1PASS、12.03秒**，两组各6/6；
[严格单场景增量](../results/tage-alternate-hierarchy-20261015-v4/qualified-line-delta.json)
相对同一历史完整基线新增**2个native DA键：Tage.sv:619、621**。完整46541分母、
build/signals身份和源文本保持一致；不把它拼接成当前全量分子，不把两个行点当作
两项功能。新功能点079使计划数为324，已知普通FAIL及完整BPU组合缺口仍保留。

兼容[复验](../results/tage-alternate-compatibility-20261015-v2/summary.json)为
**21PASS、4进程29.50秒**，包含075、076/077、收紧事件资格后的078、PHR恢复/
纠正/wrap、嵌套call/return、ITTAGE目标选择以及独立TAGE cold/allocation/counter。
这些结果不替代上一节独立TAGE全模块的1091PASS/1普通FAIL，也不是全项目已绿。

最终[纯模型/反向检查/门禁选测](../results/tage-alternate-gates-20261015-v2/summary.json)
为**715PASS、4进程85.31秒**。包含层级学习的独立重放、交换结果槽位、坏alternate
方向、错误metadata/PC/target/tick/stage、丢失与多余纠正、strong时同目标额外S3、
sentinel被改动、无区分性条件不给信用、旧frame不给新事件信用，以及上述16项
编译guard局部复核。六条规则缺任一reached或checked、缺组或schema改变都拒绝
发布。最终场景、兼容及门禁三轮source epoch一致，evidence完整、integrity为空，
没有ERROR/SKIP/新增XFAIL；只有按需功能coverage与原生覆盖产物，无逐周期JSON。
RTL、DUT及SDK均未修改/重建，完整目标继续保持未完成。

### SC/TAGE写缓冲残差：源码条件与原生覆盖点关联复核

本轮没有新增功能点或行命中。依据079的反例，重新复核了两个独立UT全部残差，
避免把源行文字或局部条件直接当作native DA的语义。当前结果是：

| 独立UT | 当前原生覆盖 | 缺失DA键的局部分类 | 真实模块回归 |
| --- | --- | --- | --- |
| SC | 3145/3481 | WriteBuffer 72、WriteBuffer_8 264；336个赋值键对应16个互斥guard producer | 130PASS、23个功能点PASS，4进程116.01秒 |
| TAGE | 4467/4587 | counter40、priority-copy48、key-copy24、else块头8；120个键对应64个guard producer | 1091PASS、1普通FAIL，16进程221.61秒 |

这些不是通过新分母计算的“满覆盖”，更不意味着模块功能已全部正确。TAGE026
仍是同一个captured-feedback useful所有权错误，普通FAIL保持，根进程退出1。
已命中行中的错误不可能靠这份残差分类豁免。此结论限定于当前独立SC/TAGE的
生成变体，不能套用到集成BPU的不同WriteBuffer变体或其他模块。

[源码校验与native映射](../bpuverify/common/coverage/local_guards.py)要求：guard
定义和词法嵌套仍与当前编译源码一致；相应两态条件无解；每个声称分类的缺失键
的全部native `l/arm/S` producer都属于已证明的那个arm。缺失producer不当作零，
toggle不混入行计数，额外/错误producer及非零矛盾计数均拒绝分类；未知行完整保留。
输入源码哈希还必须匹配指定冻结回归epoch。原生分母与命中数原样返回，明确
`functional_pass_credit=false`、`whole_design_formal_claim=false`。

TAGE此前未分类的8个块头已得到明确关联：例如871来自
`l=849/arm=else/S=871-875`，1550来自`l=1548/arm=else/S=1550-1553`。
同anchor的非零if计数不属于这些else。SC则例如366–374来自
`l=365/arm=if/S=365-374`，并被外层hit与内层not-hit同时约束。这与079的619
外层alternate表达式是不同映射，不能只根据相近行或一个矛盾信号作统一判断。

[审阅坐标目录](../bpuverify/tage/coverage/guard_catalog.py)不是golden行为或证明；
它只选择当前变体需要复核的范围，每次仍执行源码、条件及native关联检查。旧
审计依赖的可删除历史JSON不再是单测输入；单测的合成native fixture明确不作为
真实验证证据。没有RTL/internal/VPI写入，没有DUT/SDK修改或重建。

本轮同一源码epoch证据：

- [SC完整模块选测](../results/sc-guard-review-20261015-v1/summary.json)与
  [本轮原生数据分类](../results/sc-guard-review-20261015-v1/guard-classification.json)：
  130PASS、336/336局部分类，无未知键；原生3145/3481不变。
- [TAGE完整模块终态](../results/tage-guard-review-20261015-v1/pytest-artifacts/evidence.json)、
  当轮仅供诊断的原生测量
  与[本轮分类](../results/tage-guard-review-20261015-v1/guard-classification.json)：
  1091PASS/1普通FAIL，120/120局部分类，原生4467/4587不变。分类记录明确携带
  `native_pytest_exitstatus=1`，失败raw不进入合格全量汇总。
- [纯模型/负向检查/门禁](../results/local-guard-gates-20261015-v1/summary.json)：
  746PASS、4进程87.34秒，含新增31项guard/映射契约。覆盖源码条件削弱、错误
  目的地/来源、错误或缺失/额外producer、span不完整、toggle混入、陈旧epoch、
  未知键保留、显式导出及拒绝覆盖已有文件、失败数据不得获取功能PASS信用。

三轮均核验epoch一致、evidence完整且integrity为空；没有ERROR/SKIP/新增XFAIL。
四份正式根报告的哈希在复核前后相同，没有发布新的完整项目通过或覆盖率数字。
工具默认只输出摘要，只有显式`--output`才保存约40KiB级聚合分类，不生成逐周期
审计/trace。这批缺口不应再靠bank/set枚举追数字；计划仍324个功能点，完整BPU
组合、其他模块的真实语义缺口与已知普通FAIL继续保持未完成。

### 集成RAS：真实检查点的重复调用恢复重放与返回退休（080）

按用户授权，本轮只改参考模型、验证适配与用例，没有修改RTL、创建RTL修复分支或
重建DUT。XiangShan继续detached HEAD；SDK仍为`dev/coverage-v2`。已有普通FAIL及
旧strict XFAIL均未放宽，不能用这一轮选测的PASS替代它们。

原集成重复调用场景只提交9/10次call，未验证“恢复较老检查点、重放那次call、
舍弃真实年轻后缀、随后退休重复return”的组合。这是操作及所有权缺口，不是
缺少更多物理槽位。新增[080场景](../bpuverify/bpu/case/ras/redo_unwind.py)用正常
反馈学到self-call和一个base目标故意不同的return；取得真实S3来源，先提交幸存
前缀，再恢复第8/9次call的真实pre-operation检查点并通过公开`ras_action=CALL`
重放，最后消费并提交真实返回。两种上下文仅区分压缩组末项与新组首项。

[语义检查器](../bpuverify/bpu/checker/ras/semantic.py)复用独立UT的
[RasReference](../bpuverify/ras/model/semantic.py)，不是复刻TOSR/NOS/队列寄存器。
从reset起自有调用帧、重复分组、检查点和提交操作；所有实际保留存储只作actual，
不用于初始化/修正golden。组件IO已是本周期事件，不套用独立顶层的引脚launch
延迟：[monitor](../bpuverify/bpu/monitor/ras/semantic.py)在SDK `DriveStable`解码
动作，在`RisingEdge`比较公开top/redirectMeta/commitMeta及全部8个保留组。
恢复/退休效果按组件的一拍注册合同比较；事件tick差3是该合同的reactor相位，
不是发给测试的固定settling等待。

每个后端来源还按**唯一coherent S3 tick**与自有快照关联，核对公开RAS检查点的
group/repeat/calls后才用于恢复或提交；不搜索附近同PC帧。FTQ redirectMeta本来
不导出topRetAddr，该地址另在组件及S3返回consumer检查，不能编造一个不存在的
metadata字段。返回consumer的valid、taken、PC和目标都要匹配自有栈顶；保留栈
最终状态再由“调用数−已返回数”闭式结果交叉检查，不只让一个模型与自身比较。

`BpuRetirement`移除了提交后的固定两拍等待。环境现在等待计划全部接受、注册
提交排空、**最后的保留栈效果已实际比较成功**，不是只看reference已经应用了
更新；summary也拒绝尚未比较的最后效果。128/512周期仅为失败预算，不是必须
消耗的运行周期。病例层不出现edge、get/set或asyncio调度细节。

独立两种上下文分别有6/7条事件规则：恢复重复计数/新分组、年轻后缀丢弃、重放
调用只退休一次、跨组返回、重复返回递减、自有目标消费和幸存帧完整性。各有
reached/checked组，四组已加入生产门禁。checked要求注册效果确实被模型接受且
对应actual比较成功；仅观察到输入、关闭enable导致忽略恢复、晚到比较、错误
actual或重复退休都不能获得信用。全项目管理schema数70→74，功能点计划324→325。

最终同一源码epoch的证据：

- [重复组末项隔离验证](../results/ras-redo-repeat-20261015-v1/summary.json)：
  1PASS，真实DUT；6条规则reached/checked均100%。
  [严格差分](../results/ras-redo-repeat-20261015-v1/qualified-line-delta.json)
  相对同一历史完整基线新增2个原生DA键：`RasStack.sv:325,580`。
- [新组首项隔离验证](../results/ras-redo-split-20261015-v1/summary.json)：
  1PASS，真实DUT；7条规则reached/checked均100%。
  [严格差分](../results/ras-redo-split-20261015-v1/qualified-line-delta.json)
  新增4键：`RasStack.sv:325,330,580,748`，与前者去重后仍是**4键**，不是6。
- [兼容选测](../results/ras-semantic-compatibility-20261015-v1/summary.json)：
  27PASS、4进程35.94秒；包含原6个提交栈场景、早期RAS/中性纠正/嵌套call-return、
  PHR恢复/修复/wrap，以及075—079和公开binding。
- [模型/负向检查/发布门禁](../results/ras-semantic-gates-20261015-v1/summary.json)：
  945PASS、4进程92.10秒。新增适配测试为**合成actual故障测试，不是DUT覆盖**；
  检查坏目标/valid/taken/PC、坏公开metadata、非目标保留单元、错误/晚到tick、
  ignored恢复、重复重放退休、最后效果未比较及不重同步。管理门禁继续拒绝缺组、
  缺reached/checked规则或schema变化；物理完整分母原样保留。

四轮evidence均完整、integrity为空、退出0，无ERROR/SKIP/XFAIL；epoch与最终源码
一致。正式根四份报告与历史基线的哈希完全相同，没有发布新全量结果。隔离BPU
原生覆盖分别25155/46541和25171/46541；不能把它们或历史分子加4冒充当前全量。
这仍是RAS组件输入cut-point及目标consumer的独立验证，不是完整FTQ nonce/epoch
合法性证明，也未完成所有预测器与自主pipeline engine的组合，整体目标继续未完成。

### 集成RAS：恢复真实return，先回滚再弹栈（081）

080只恢复call，不能替代return恢复。081正常学习同一call/return程序，接受至少
三笔真实return后，恢复第一笔的pre-operation检查点并重放一次RETURN。预期回到
“仅返回一次”，不是在当前栈上再弹一次。8/9次重复调用区分同组repeat递减和跨组
pop；调用在恢复前/后退休，区分前驱的retained/speculative寿命，不枚举物理槽位。

新场景还暴露并修复了参考模型错误：恢复调用帧时，旧模型没有取消年轻未退休
操作。重复return的(group,calls)提交键可能相同，导致后续错误匹配旧操作。
现在独立模型为语义操作维护逻辑序号及检查点操作前沿；恢复生效时取消年轻owner，
然后只创建一个重放owner。没有读取DUT队列指针，也不声称完整FTQ nonce/epoch
合法性。旧首次试跑失败证据保留，没有将oracle错误冒称RTL缺陷。

四种上下文各六条事件义务：恢复pop、撤销年轻return、前驱所有权、重放只退休
一次、恢复后的真实目标消费和幸存帧完整性。八个reached/checked组全部100%，
已加入两类发布门禁；预测消费在恢复效果比较成功前不给信用。计划325→326点，
管理schema74→82；功能点、事件bin和原生行点不是同一个指标。

严格单场景PASS差分相对同一历史完整基线分别3/5/5/8键：
[spec-repeat](../results/ras-return-spec-repeat-20261015-v1/qualified-line-delta.json)、
[spec-group](../results/ras-return-spec-group-20261015-v1/qualified-line-delta.json)、
[ret-repeat](../results/ras-return-ret-repeat-20261015-v1/qualified-line-delta.json)、
[ret-group](../results/ras-return-ret-group-20261015-v1/qualified-line-delta.json)。
去重8键为`RasStack.sv:580,749,752,755,756,827,831,832`，其中580已由080命中，
其余7键才是call恢复场景未触及的return路径。相同46541分母、DUT/signals/源码
身份均已核对；不将3+5+5+8相加，也不把跨轮并集当作当前全量分子。

[兼容选测](../results/ras-return-compatibility-20261015-v1/summary.json)为29PASS、
4进程39.17秒；[模型/负向/门禁](../results/ras-return-gates-20261015-v1/summary.json)
为1003PASS、4进程101.73秒。负向测试检查旧owner取消、后续重复return归属、坏
actual/寿命标签、重复事件、ignored/晚到效果、reset及不重同步；合成actual测试
不是DUT覆盖证据。[独立RAS完整模块](../results/ras-recovery-ownership-ut-20261015-v1/pytest-artifacts/evidence.json)
仍为15PASS、原4普通FAIL、原1strict XFAIL、8.90秒；
当轮原生测量
仍569/585，退出1，不作为成功报告发布。

四个隔离场景、兼容、门禁、完整RAS及先前6场景合并复验共八轮evidence均完整、
integrity为空，epoch与最终源码一致。RTL/DUT/SDK未改或重建，正式根报告未替换。
完整BPU组合oracle、已知普通FAIL及全量验收仍未完成。

### 集成MicroBTB：容量、近期访问保护与替换的真实消费者（082）

独立UBTB满原生覆盖并不等于集成BPU已验证容量/替换。历史完整基线在集成
MicroBtb仍缺169个DA键，MicroBtbReplacer缺28键。082只运行一个配置容量生命周期：
正常FTQ反馈建立32个不同逻辑分支，公开读回全部32项；再触碰自有PLRU预期的victim，
使它成为应保留的近期项，最后发送第33项的真实反馈并检查新的victim。32是配置
容量前提，不是bank/set枚举；整个场景只有一项pytest case、99个真实来源。

全过程复用`PipelineObservation`的自主token/三级选择/repair/history模型和
`MicroOnlySources`中的独立`UbtbReference`。条目、confidence和替换recency从reset
自行维护，没有采样DUT表内容、hit或victim线来修正预期。另由
[领域checker](../bpuverify/bpu/checker/micro_capacity.py)将每笔公开来源关联到唯一
已比较的prediction tick，比较程序指定的目标/位置/taken及同源metadata；旧tick、
错误来源和已复用输出均拒绝。其他预测器关闭，S2合法地把早期命中纠正为fallthrough，
该快训导致的confidence下降仍由模型负责；幸存项是在各自消费时检查，不声称之后
所有条目仍永久保有原confidence。不是全预测器组合或完整FTQ程序合法性证明。

初次普通流接收在停流重开时出现prediction/meta时间戳不一致。本场景复用已有
`agent.observe_phr`一致性观测，以真实S1接受及同源S3形成来源；PHR也独立检查。
没有将延迟4放宽成6、模糊匹配同PC、改RTL/SDK或复制框架补丁，也没有声称通用
普通接收器在所有停流时序下已修复；旧试跑失败证据保留。

六条硬件事件义务为：容量内全部记录读回、近期预测项受保护、满容量替换、victim
失效、新项消费和其他所有记录保持。仅计划分配没有信用；reached取实际接受的
完整反馈，checked还要等victim公开miss、新项hit及全部31个幸存者的完整payload
均比较成功。近期项也不能只因发过lookup就算保护成功。两个reached/checked组
均100%，已纳入发布门禁，schema82→84，功能点326→327。

[最终单场景](../results/micro-capacity-20261015-v4/summary.json)为1PASS、14.01秒，
其中刺激4.15秒；[严格差分](../results/micro-capacity-20261015-v4/qualified-line-delta.json)
相对同一历史完整基线新增**196个原生DA键**，MicroBtb168、MicroBtbReplacer28。
相同46541分母、DUT/signals及原始源码文本均通过核验。选测24942/46541不与历史
全量33257/46541作涨跌比较，不把二者的并集冒称当前全量覆盖率。

[兼容选测](../results/micro-capacity-compatibility-20261015-v1/summary.json)为33PASS、
4进程42.11秒，包含081四个真实恢复场景及既有080、PHR、075—079等；
[模型/负向/门禁](../results/micro-capacity-gates-20261015-v1/summary.json)为1041PASS、
4进程103.56秒。新增负向检查包括九类坏来源、重复来源、错误/未接受反馈、假保护、
缺失victim/new/protected/neighbor消费、reset及失败后不重同步；合成actual只用于
检查适配契约，不计真实DUT覆盖。三轮最终epoch一致，证据完整且integrity为空，
无ERROR/SKIP/XFAIL；正式根报告未替换，RTL/DUT/SDK未改或重建。

相对历史缺失集合，唯一未被082场景触及的MicroBtb键是1486，对应相邻同key更新
转发中的confidence加一。容量/替换没有验证这一正向转发义务：需用真实相邻反馈，
再通过后续消费/衰减区分正确合成与丢失一次更新，不能仅命中加法或读取actual计数
填golden。后续083已补此义务，见下节；已知耗尽后连续NT复活缺陷仍不能豁免。

### 集成MicroBTB：相邻正向学习必须能被后续消费者区分（083）

1486不是缺少一个cache地址，而是同key的两笔相邻正向更新需要使用前一笔的新
confidence。083正常学习一个owner，再收集两笔真实预测；其他预测器关闭产生的
真实S3 NT快训将confidence降到1。保留两笔来源各自的原始metadata，交由已有
driver在相邻接受周期发送T反馈，预期1→2→3。之后必须公开看到三次T命中，再看到
一次miss；若丢失一次增强，从2开始会在第三次probe提前miss，不能以“最终仍命中”
或“跑到了加法行”蒙混过关。此场景只需一个PC，不增加物理矩阵。

预期仍由`UbtbReference`从reset和真实语义事件推导。新增32个confidence的只读
memory-direct actual比较，限定在**模型自行确定无在途学习的静稳点**；不是用
actual挑选相近采样相位，更不把actual写回模型。公开token、选择、repair和history
仍逐周期比较；原生存储与公开IO的更新边界不同，没有假称所有raw counter中间态
都已由同一采样相位精确验证。弱态必须在真实来源之后比较为1，组合效果必须在
两次接受之后比较为3，非目标confidence保持，最终消费后比较为0。

新增五条事件义务：合格弱owner、真实相邻同owner接受、两个正向效果合成、三个
真实存活消费者、三次下降之后才耗尽。reached/checked两个组均100%，已加入生产
门禁；schema84→86，功能点327→328。相邻性同时核对driver接受及独立观测的实际
反馈事件，完整PC/target/position/kind/action/taken/mispredict均比较，不是发了两个
任务就登记并行完成。共享的停流、来源捕获和完成条件移入
[micro环境](../bpuverify/bpu/env/micro.py)，case不见edge、get/set或asyncio编排。

本轮还修复等待辅助函数的错误传播：Python predicate在仿真pump内运行，不能
直接抛出checker异常，否则同一失配会同时成为call FAIL和teardown ERROR。
现在保存原异常、正常唤醒等待者并清理触发器，再在等待任务中抛出同一个异常。
未修改SDK、backend或RTL；测试检查异常对象身份、取消后不再回调、Execution仍能
继续推进及timeout诊断保留。旧错误相位的候选保留为FAIL诊断，不计功能或覆盖信用。

[最终独立DUT资格](../results/micro-positive-forwarding-qualified-20261015-v1/summary.json)
为1PASS、10.73秒（刺激0.67秒）；
[严格单场景差分](../results/micro-positive-forwarding-qualified-20261015-v1/qualified-line-delta.json)
相对同一历史完整基线精确新增**1个原生DA键：MicroBtb.sv:1486**，46541分母、
DUT/signals/RTL文本身份不变。选测24671/46541不是新的全量分子。
[兼容](../results/micro-forwarding-compatibility-20261015-v1/summary.json)34PASS、
4进程42.62秒；[完整框架及模型/负向/门禁](../results/micro-forwarding-gates-20261015-v1/summary.json)
1602PASS、4进程115.62秒。包括错误来源/复用、假弱态、非相邻/错误实际反馈、缺失
一次增强、错误owner/neighbor实际计数、提前结束probe、失败不重同步及所有memory-direct
DUT绑定；合成actual测试不是DUT覆盖证据。

另以当前强化检查和共享环境对082作了[独立复验](../results/micro-capacity-confidence-qualified-20261015-v1/summary.json)：
1PASS、14.38秒；[严格差分](../results/micro-capacity-confidence-qualified-20261015-v1/qualified-line-delta.json)
的196键与旧082资格集合逐键相同，无旧增量丢失。两场景增量不相交，隔离合格
并集197键恰为历史MicroBtb169及替换器28个残差；这不是当前完整项目的覆盖分子，
也不等于所有分支/功能已通过，尤其不能豁免已覆盖路径上的连续NT复活错误。

四轮最终epoch一致，evidence完整且integrity为空，无ERROR/SKIP/XFAIL；正式根报告
没有替换，RTL、DUT与SDK未改或重建。MicroBTB学习profile仍不声称完整FTQ nonce/
epoch合法性或所有预测器组合，已有普通RTL FAIL保持，整体目标仍未完成。

### 集成MainBTB：独立查询快照、精确反馈归属与方向纠正（强化004）

本轮强化已有`BPU-INT-004`，没有因增加模型文件或两个窗口布局另增功能点，计划仍
为328。问题不是缺一个bank坐标，而是集成反馈里的MainBTB metadata本来由DUT
产生：若直接作为golden输入，即使训练、响应都来自错误请求，局部模型也可能自洽。

[BranchTargetSources](../bpuverify/bpu/model/main_sources.py)在自主周期engine中组合
独立的`UbtbReference`与`MbtbReference`。MainBTB内容、方向、替换及在途写义务
均从reset维护；每次issue保存自己的不可变查询快照。S2/S3的四路候选、方向、
target、选择、repair、后续PC与history都由这些自有状态推导，实际stage信号、
SRAM状态及MainBTB metadata只作为actual。复用独立UT模型新增的纯
`lookup_snapshot`接口，不另抄一套信号级算法。共享MicroBTB算法抽成`MicroSources`，
Micro-only与Micro/Main两种profile是并列组合，不将“只支持Micro学习”的限制
误用到组合profile。

`Resolution.origin`显式引用模型已经发布的确切`Token`对象。相同PC与低位history
可能对应冷查询、学习后查询两个不同快照，不能用相等数值搜索替代请求身份。
[检查器](../bpuverify/bpu/checker/pipeline.py)将真实S1接受和S3 metadata时间戳
关联到该owner，比较公开PC、预测payload、独立history及MainBTB所有有效metadata
字段。rawHit为0时payload未定义，不强行比较；命中时position/kind/action/counter
均比较。driver发送前登记已检查来源及冻结的反馈副本，实际输入被接受时再比较
完整分支向量和来源metadata，之后才向模型提交语义反馈。planned任务不是接受
证据，修改原transaction也不能改写expected。完成后显式释放验证owner；这不是
伪造RTL FTQ commit。复制对象、跨模型owner、已释放来源、错时间戳或错字段均报错，
失败保持原异常，不搜索附近同PC帧或重同步状态。

[场景](../bpuverify/bpu/case/main_learning.py)只表达语义程序：冷态真实来源接受
T反馈，后续消费MainBTB弱正counter2；同来源NT反馈降至1，MicroBTB仍预测T但
MainBTB应纠正为NT；再由新真实来源接受T反馈，原物理owner恢复counter2并重新
一致。既比较逐周期choices/fire/flush/history与MainBTB metadata，也在自有静稳
条件下比较MicroBTB confidence。停流、训练排空和来源捕获放在
[环境](../bpuverify/bpu/env/branch_targets.py)，case不含edge、固定等待或get/set。
两种窗口布局为aligned及rotated-unaligned，检验同一逻辑事件在窗口变换后仍能成立，
不乘bank/set笛卡尔积。

五条事件义务为冷态真实学习、MainBTB结果消费、同owner方向减弱、MainBTB纠正
MicroBTB、同owner恢复。reached取真实接受，checked必须等新查询及消费者均比较
成功；发了反馈、读到相同counter或命中了RTL行都不足以关闭义务。两组加入生产
发布门禁，required schema由86增至88，原生分母及功能点通过率分母不裁剪。

[最终真实DUT资格](../results/owned-main-learning-qualified-20261015-v1/summary.json)
为2PASS、2进程11.37秒，两布局刺激分别0.66/0.65秒；五条规则的reached/checked
均100%，每布局分别有完整证据。
[兼容选测](../results/owned-main-learning-compatibility-20261015-v1/summary.json)
36PASS、4进程45.82秒，包含原004直接训练、082/083、PHR、自主pipeline及既有
RAS/TAGE学习场景。
[完整框架及模型/负向/门禁](../results/owned-main-learning-gates-20261015-v1/summary.json)
1738PASS、4进程117.85秒，包括独立MainBTB UT模型及新查询归属、接受输入、生命周期、
wrong-owner/错误消费者/不重同步反向检查。合成actual只检验适配与覆盖资格，
不算真实DUT命中；call/return与live trained enable越界也有显式拒绝测试。

[单布局隔离复验](../results/owned-main-learning-isolated-20261015-v1/summary.json)
为1PASS，[严格原生差分](../results/owned-main-learning-isolated-20261015-v1/qualified-line-delta.json)
相对同一历史完整基线新增**0键**。因此本轮是已有004的oracle与因果义务加强，
不是行覆盖率上涨；隔离24801/46541及两布局合并24803/46541都不是新的全量分子。
四轮最终源码epoch一致，evidence完整、integrity为空，无ERROR/SKIP/XFAIL。
四份正式根报告与历史完整基线哈希一致，没有用选测或历史并集替换正式全量数据。

范围仍有边界：其他训练过的预测器、自主pipeline内call/return及FTQ commit、
训练后仍在途时切换MainBTB enable均明确拒绝；完整FTQ nonce/epoch合法性和guarded
地址仍未完成。本轮组合DUT资格采用逐笔学习后排空；尚未取得集成侧相邻反馈burst
及预测读/学习写重叠的完整资格，独立MainBTB UT并发证据不能自动转移给此组合。
初始化/排空服务状态只决定何时提供服务，不生成分支golden；PHR
独立检查继续启用，不能将尚未完整独立解码的所有resolveMeta都宣传为已验证。
本轮没有修改RTL、SDK或DUT，已有普通RTL FAIL仍保留。

### 集成TAGE：有效但未跟踪的分支不能挤占或获得匹配owner的学习（084）

075的空槽是invalid，不能代替**valid但没有MainBTB记录**的条件分支。084在一个
真实32字节取指窗口的8条条件分支（半字位置0、2、4、6、8、10、12、14）中，
只正常建立位置4、6、10、14的四个MainBTB/TAGE owner，其他四条保持未跟踪。
四个owner横跨两个fetch子窗口和两张历史表，分配由独立模型机会预测，不观察
实际随机状态。随后保留TAGE强NT、正常把MainBTB base训练为T，再一次完整resolve
全部8条NT；这是一条真实完整的未跳转路径，不是换几个空槽编号。

[语义程序](../bpuverify/bpu/model/tage/interleaved.py)只描述分支位置、目标与已解析
结果；不是新的寄存器镜像或替代oracle。
[环境](../bpuverify/bpu/env/tage_interleaved.py)复用已有SDK driver、monitor和有
真实完成条件的训练排空。base准备逆分支顺序进行，较早已执行分支均NT、最后一条T；
两次T对应2位counter的0→1→2，不是等两拍。case不含assert、edge、get/set、
固定settling delay或asyncio编排，不展开bank/set矩阵。

[checker](../bpuverify/bpu/checker/tage/interleaved.py)继续使用从reset维护全部
TAGE表/计数器/useful/selector/在途学习的`TageReference`，保存各来源的自有查询
快照。真实接受时逐项比较全部8条分支、完整history、MainBTB position匹配、原始
独立预期hint及resolve槽向量。四条matched与四条unmatched不能压缩后再按槽号
索引metadata；所有原owner应counter2→1、useful0→1、MainBTB base2→1，之后
公开metadata及完整S1/S2/S3 consumer窗口都必须比较成功。没有实际接受不登记
reached，有坏输出或缺任一owner不登记批次checked。

单看这四个结果还不足以排除“为未跟踪分支意外学出provider”。所以之后按正常反馈
把每一条原untracked分支引入MainBTB：完整较早conditional前缀均NT、新发现尾项T且
真正mispredict，当前MainBTB中仍未匹配。checker独立维护这些分支的逻辑base counter
结果，原metadata不改写；每次实际接受以后才更新记账，等待正常commit，再公开
消费新branch的`hasProvider=0`及MainBTB counter2。既检验mixed beat后的保持，
也检验后续**未匹配但真正错误预测**的反馈不会获得TAGE分配资格。不用实际SRAM
初始化/修正golden，也不能只probe三条就登记四条均过滤。

新功能点084对应“有效未跟踪分支与匹配分支的学习资格/归属隔离”，不是把4个
useful行点拆成4个功能；计划328→329。六条事件义务是完整交错有效反馈、按位置
匹配owner、正确且反base的学习、四个结果均消费、未跟踪反馈被过滤、后来发现时
没有意外provider。reached/checked两组各6/6，最后两项必须等四个延后consumer
全部成功才关闭。两组进入生产门禁，required schema90→92；原生分母不裁剪。

[最终单场景](../results/tage-interleaved-qualified-20261015-v1/summary.json)为1PASS、
11.43秒，刺激1.43秒；
[严格差分](../results/tage-interleaved-qualified-20261015-v1/qualified-line-delta.json)
相对同一历史完整基线新增15个DA键，其中Tage5、WriteBuffer_8共10；
Tage的4个新useful键是6935、7065、7325、7585，9951已由078独立覆盖。逐键对照
前文16份同基线BPU隔离资格，重合仅9951，因此相对此前已证明的隔离增量又新增
**14个不同键**。10个写缓存键是场景伴随的entry/计数更新路径，不将其声称为10项
新增功能；真实有效学习由四个最终owner及全部consumer比较证明。完整46541分母、
RTL文本及build/signals保持一致，隔离25502/46541不是当前全量分子。

[兼容选测](../results/tage-interleaved-compatibility-20261015-v1/summary.json)40PASS、
4进程47.99秒；[框架/模型/负向门禁](../results/tage-interleaved-gates-20261015-v1/summary.json)
1785PASS、4进程123.28秒；另有[退休/恢复契约](../results/tage-interleaved-retirement-contracts-20261015-v1/summary.json)
32PASS、0.78秒。后两组选测nodeid无重合，共1817项，逐项包含上轮1767项门禁
的全部nodeid，没有漏掉退休契约。新增44项纯测试从语义事件程序建立四个
owner，检查完整mixed输入及每个owner效果、全部延后consumer、错误接受/关联、
缺失或多余repair、reset与旧来源、未接受与过早结束、程序前缀及case分层；合成
actual只测检查器契约，不计DUT覆盖。缺组/缺规则/schema变化均拒绝生产发布。
四轮最终源码epoch核对一致，证据完整、integrity为空，无ERROR/SKIP/XFAIL；
正式四份根报告与历史完整基线哈希一致，均未被选测结果替换。

相对该历史基线，`Tage.sv`当时缺失的10个DA键，现分别由075、078两种历史、079
及084的独立合格场景触及；这只是相同源文件残差的逐键证据，不等于当前全量
TAGE功能/原生分支已满，更不豁免独立TAGE的026普通FAIL。

范围仍明确：MainBTB结果/上游history是这个TAGE component场景的cut point，
不是自主Micro/Main pipeline已经完整组合TAGE，也不证明全部FTQ nonce/epoch及任意
程序前置轨迹合法。reset使旧来源、部分义务及逻辑counter记账失效；坏accepted输入、
坏state/consumer保持首异常，不重同步。没有RTL/DUT/SDK改动、重建或新增XFAIL。

### 其他缺行不能直接变成新功能点

以下是对相同生成源码的局部归因，不是新的全设计formal证书，也不删除任何原生分母。

| 缺行 | 源码约束 | 处理 |
| --- | --- | --- |
| CommonHR 869–871共3行 | `CommonHR.sv:850`外层先处理r1_valid，内层869再次要求r1_valid；进入外层else后该条件不成立 | 局部互斥guard，不再添加“更多redirect”刷同一分支 |
| 集成MicroRAS 133–134共2行 | `Bpu.scala:254/264/265`使S3总可退休，因此S2 fire等于S2 valid；S2 override已经要求valid。`MicroRas.scala:145`再要求override且不fire | 当前集成连接下不成立；独立URAS UT允许独立控制，不能把此归因推广到该UT |
| PHR历史基线1417项 | 包含大量按物理cell/index展开的写入与优先guard；正常genuine checkpoint的两位推进有parity约束，但外部任意metadata能提供odd-pointer反例 | 还需逐类证明，不能把1417全部标unreachable，也不伪造checkpoint遍历来追数字 |

## 每个模型的最低验收

1. 明确配置、语义输入/输出、状态来源、时间合同和不支持的范围；越界明确报错。
2. 纯模型测试覆盖手算边界、相邻事件、reset/stall/flush与同周期冲突。
3. 实际 DUT 的 driver/monitor 流接入比较；不只用一两个最终状态断言。
4. 修改 actual 的关键字段/状态时检查必须失败，expected 不随之改变；失败带上下文。
5. 全量通过情况和已知缺陷单独报告；纯模型测试通过不等于真实 DUT 资格验证通过。

局部模型可以分阶段建设，但不能以补文件/空基类、signal级检查或覆盖率全绿替代
上述验收。公共基础设施继续复用 xreactor，领域模型留在 `bpuverify/<dut>/model/`。
