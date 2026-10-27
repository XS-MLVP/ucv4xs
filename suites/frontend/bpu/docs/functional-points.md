# Kunminghu-v3 BPU 功能点清单

最新完整诊断20209项：20169 PASS／37普通FAIL／3 XFAIL，原20156节点判定保持。
本批6个DUT程序、47项纯检查，定向稳定后只跑一次全量。四个程序完整通过，
两个taken长来源在训练历史重建处首先失败，不直接计为TAGE算术或架构缺陷。
INT-086原十条要求保留并补三条，仍为FAIL；其余344点定义及判定映射不变。
硬件335点仍311 PASS／22 FAIL／2 XFAIL，环境10 PASS。

459组／411满，旧447组比例保持；新增114项义务到达92、checked76。四通过
程序完成19次SDK服务、48个消费者、68笔Main更新和46次训练历史比较。
BPU新增1个既有Main替换状态副本行，单个PASS用例独立复现；无旧命中损失，
仍17287零键及137个集成TAGE缓冲开放键。见
[完整诊断](../results/production-confidence-boundary-20261017-v1/README.md)及
[饱和往返与来源存活](tage-confidence-boundaries-20261017.md)。合同、覆盖组和
功能点通过率分开，不能把新增义务当作已通过或把物理副本当新功能。

## 前一轮相反方向测量

最新完整诊断20156项：20118 PASS／35普通FAIL／3 XFAIL，原20100节点判定
保持。本批6个DUT场景为3 PASS／3 FAIL，50项纯检查全PASS，仅跑一次全量。
INT-086原七条要求保留并追加相反方向迟到学习的三条要求，原六字段合同
不变；三个原饱和来源缺少提案，使该点由PASS转FAIL，原有测试仍PASS。
其余344点定义、分域及节点判定映射不变。硬件335点为311 PASS／22 FAIL／
2 XFAIL，环境10 PASS。

447组／403满，旧435组比例保持；新增90项义务reached72、checked45，
三个失败场景checked均0，不为被阻断的最终服务及消费者计功。十DUT原生
集合不变，仍17288零键及137集成缓冲开放键。见
[完整诊断](../results/production-direction-turnaround-20261017-v1/README.md)及
[语义要求与首错状态](tage-direction-turnaround-20261017.md)。全部335份合同
存在不等于全部已证明，完整FTQ来源资格及其他未闭合范围继续保留。

## 前一轮循环迭代测量

最新完整诊断20100项：20065 PASS／32普通FAIL／3 XFAIL。本批6个真实DUT
场景、59项纯检查全部PASS，定向之后只执行一次全量；原20035项判定保持。
新增独立INT-099明确旧预测的循环迭代上下文所有权，不继承原043/094排除
IMLI的证据。335硬件点为312 PASS／21 FAIL／2 XFAIL，环境10 PASS；原344点
定义和合同保持。45项新配对义务完成，435组／397满，旧423组比例保持。
十DUT原生键和命中集合不变，17288零键及137集成写缓冲开放键保留，不称
原生行增长。见[完整诊断](../results/production-loop-iteration-20261017-v1/README.md)
及[六场景语义](loop-iteration-source-ownership-20261017.md)。任意延迟GHR/BW
查找、SC组合和完整FTQ资格仍未闭合。

## 前一轮混合版本测量

当前完整诊断20035项：20000 PASS／32普通 FAIL／3 XFAIL。本批4个真实DUT
场景、44项纯检查全部PASS，622项定向之后仅执行一次全量；两处旧纯断言
修复已在完整轮通过，其他19985判定保持，原硬件判定不变。INT-086追加部分
服务后混合来源、重新激活／饱和抑制及不等长服务要求，原344点身份、分域
和合同保持。硬件311 PASS／21 FAIL／2 XFAIL（334点），环境10 PASS。
423组／385满，48项新配对义务完成；BPU原生新增7键，十DUT旧命中无损失，
17288零键和137个集成写缓冲开放键保留。见
[完整诊断](../results/production-mixed-visibility-20261017-v1/README.md)及
[四场景语义](tage-mixed-visibility-learning-20261017.md)。334份合同并非全部模型或规格已闭合。

## 前一批次完整测量

最新完整测量19987项：19950 PASS／34 FAIL／3 XFAIL，本批5个DUT语义场景和
80项纯检查全PASS，仅执行一次全量。原32失败保持，另2处纯检查写死全仓
总数343，已在随后291 PASS专项中修复，不伪造修复后的当前源码全量。
新增INT-098后为344点：334硬件合同、10环境；原343点判定与合同保持，硬件
311 PASS／21 FAIL／2 XFAIL，环境10 PASS。415组／377满，41项新配对义务闭合；
BPU新增5个原生行键，其他九DUT集合保持，十DUT无旧命中损失，17295零键与
144个集成写缓冲开放键保留。见[完整诊断及版本边界](../results/production-residency-batch-20261017-v1/README.md)
和[五场景合同](tage-partial-residency-cases-20261017.md)。

## 以下保留阶段历史

最新完整复验19902项：19867 PASS／32普通FAIL／3 XFAIL，旧19813测试及343点
判定保持。INT-043补恢复的实际方向、非条件转移及已执行前缀三项细化要求，
4个真实DUT场景及85项纯检查全PASS，成对24项义务闭合；原六字段合同和
其他342定义保持，不新增功能ID。405组／367满，旧397组比例保持；硬件仍
310 PASS／21 FAIL／2 XFAIL，环境10 PASS。十DUT原生命中无增无损，17300
零键和149个集成写缓冲开放键保留；本批一次全量611秒，不把判错增强称为
行增长。IMLI和任意查询来源未独立验证，094两项原FAIL继续保留。见
[完整诊断](../results/production-common-recovery-20261017-v1/README.md)及
[四种语义场景](common-history-recovery-batch-20261017.md)。下方保留历史轮次。

最新完整复验19563项：19528 PASS／32普通FAIL／3 XFAIL，旧19496测试及343点
判定保持。INT-090细化双迁移、双路退休与后继同时出现的要求；66新纯检查
和1DUT程序PASS，实际8次SDK服务、3次同拍交叠和2个新消费者完成成对8项
义务。原合同、其他342定义及旧389组比例保持；391组／353满，硬件仍310
PASS／21 FAIL／2 XFAIL，环境10 PASS。十DUT原生键和命中集合不变，17330
零键仍保留，不把并发检查补证说成行覆盖或功能点通过率上涨。见
[完整诊断](../results/production-bpu-dual-retirement-20261017-v1/README.md)和
[语义义务](bpu-dual-retirement-20261017.md)。下方为历史轮次。

最新完整复验19496项：19461 PASS／32普通FAIL／3 XFAIL，旧19452项及全部
343点判定逐一保持。INT-089补两条原分支同时迁移、相反反馈独立累计、读
阻挡可见性及干净再激活要求；新增43纯检查和1DUT程序PASS，8项reached与
checked均完成。原合同及其他342定义不变，不新增功能ID。389组／351满，
旧387组比例保持；硬件310 PASS／21 FAIL／2 XFAIL，环境10点PASS。BPU
原生DA增加7，十DUT无旧命中损失，17330零键仍保留。见
[当前完整诊断](../results/production-bpu-dual-migration-20261017-v1/README.md)及
[人类可读要求](bpu-dual-provider-migration-20261017.md)。下方保留历史轮次。

最新完整复验为19452项：19417 PASS／32普通FAIL／3 XFAIL，旧19429项判定逐一
保持，新增19项纯检查和4DUT场景全PASS。MBTB-017补不同旧位置关系下的两向
年龄隔离证据，但其原四个串改反例仍FAIL，343点状态不变。原合同不放宽，
两组成对覆盖显式升级36→72项义务，原36个bin名称保留；reached48/72、
checked36/72，原位置关系仍0 checked。387组／349满，其余385组比例保持；
十DUT原生键及命中集合不变，17337零键仍保留。硬件仍310 PASS／21 FAIL／
2 XFAIL，环境10点全PASS。见
[完整诊断](../results/production-mbtb-full-capacity-age-20261017-v2/README.md)。下方保留历史轮次。

最新完整复验为19429项：19394 PASS／32普通FAIL／3 XFAIL，原19390项判定
逐一保持。MBTB-017补满组连续分配、独立方向与后续竞争要求；新增35纯检查
PASS、4项DUT普通FAIL，首个新分支计数应2实1、方向应taken实not-taken。
该点由PASS转FAIL，不继承旧空组证据；其他342点不变。硬件310 PASS／21 FAIL／
2 XFAIL，环境10点全PASS。387组／349满，旧385组比例保持；新增reached12/36、
checked0/36。十DUT原生分母、键和命中集合保持，17337零键未减少。见
[完整诊断](../results/production-mbtb-full-capacity-learning-20261017-v1/README.md)与
[语义义务](mbtb-full-capacity-learning-20261017.md)。下方保留原阶段统计。

最新完整复验为19390项：19359 PASS／28普通FAIL／3 XFAIL，旧19358节点判定
逐一保持。UTAGE-018补独立原来源交错学习、两端保持及反向恢复，30项纯检查
和2项DUT全PASS，成对20项义务全满；旧非成对矩阵证据保留，不增加功能ID。
343点判定保持：硬件311 PASS／20 FAIL／2 XFAIL，环境10点全PASS。385组／
349满，MicroTAGE6997→7007／11053，其余九DUT集合不变、十DUT无旧命中损失。
17337零键、49职责组保留；见[完整诊断](../results/production-utage-long-history-learning-20261017-v1/README.md)。

当前逐点语义审查为**333项硬件合同、0项旧硬件点待审查**，343个ID不变。
最后64项[BPU集成定义](bpu-integrated-functional-definition-review-20261016.md)采用后，
所有旧硬件点均明确事件、归属、效果、观察、保持与范围，但未证明全部规格
或模型完备。新增子义务不继承旧PASS；输入切点、状态服务和真实消费者分别看待。
完整目标oracle低位盲点、013的宽XFAIL前提以及前轮地址/辅助参考问题先处理，
再按[用例设计顺序](semantic-gap-test-design-20261016.md)补证，不扩大物理遍历。
其中[完整目标参考与013分类已修复](../results/full-target-oracle-repair-20261016-v1/README.md)：
真实DUT专项9 PASS/2 XFAIL，已知RTL高位缺陷保留。
随后[MicroBTB地址域成套修复](../results/ubtb-byte-address-repair-20261016-v1/README.md)：
六类真实消费者及两组成对事件全满，344项纯检查PASS；64进程18983项全仓复验
为18955 PASS/25普通FAIL/3 XFAIL，旧18910节点及343功能点判定精确保持。
该阶段Main旧depth辅助参考尚待修复；后续已修复参考并暴露第二深度RTL普通
FAIL，见[原身份修复与证据](mbtb-depth-owner-repair-20261016.md)，不豁免旧失败。

此前逐点语义审查为**269项合同、64项待审查**。新增50项
AheadBTB合同后，九个独立UT的236点均有合同；还剩BPU64点。见
[AheadBTB审查](ahead-btb-functional-definition-review-20261016.md)：保存快照选择年龄、
S1快速位置与S2旁带各自关联、已接纳训练跨禁用完成等仍须补证，053继续普通FAIL。
旧“4 MiB”文案是半字/字节混淆，22位半字偏移对应8MiB字节区域。
此前新增41项MicroBTB/MainBTB合同，
本轮发现MicroBTB字节API与原始PrunedAddr绑定/模型单位不一致，以及MainBTB
禁用保持前态不够区分、旧depth期望不能证明计数owner。它们不是新增PASS，
也不能用纯模型兼容通过关闭。见[MicroBTB](micro-btb-functional-definition-review-20261016.md)
和[MainBTB](main-btb-functional-definition-review-20261016.md)。

此前178合同阶段，TAGE36项、SC23项、
MicroTAGE25项、ITTAGE19项、MicroRAS16项、RAS17项均有六字段合同。最新采用
45项目标/调用合同，区分codec与真实硬件闭环、推测年龄/主栈深度、信用回收
与提交操作。见[ITTAGE](ittage-functional-definition-review-20261016.md)、
[MicroRAS](micro-ras-functional-definition-review-20261016.md)、[RAS](ras-functional-definition-review-20261016.md)。
当时剩余为BPU64项、AheadBTB50项、MainBTB25项、MicroBTB16项。

此前采用53项TAGE/SC定义，区分方向、保护、
选择偏好、权重和阈值；SC-005旧稳定方向不足以证明权重饱和，边界及聚合义务
保留证据缺口。见[TAGE审查](tage-functional-definition-review-20261016.md)与
[SC审查](sc-functional-definition-review-20261016.md)。没有新增DUT刺激或改参考算法。

上一阶段补入33项
BPU/SC/TAGE/RAS合同，纠正INT-044的S3指导来源，并明确同拍老化与学习、保护
边界恢复义务；这些新义务尚未获得新增DUT证据，不用旧PASS自动关闭。
见[MicroTAGE](bpu-microtage-functional-review-20261016.md)与
[保留状态](retained-state-functional-review-20261016.md)及
[BPU剩余来源](bpu-gap-owner-functional-review-20261016.md)审查。当前全部43个
零行关联ID均有明确合同，不代表所有硬件功能或缺口原因已闭合。

此前地址域修复阶段完整测量18983项：18955 PASS/25 FAIL/3 XFAIL，旧节点和343点判定保持；
365组/334满，新增两字节域事件组、旧363组全保持。十DUT原生集合精确不变、
剩17372零键；本轮冻结333份合同/2163源码，6新增DUT与67纯检查全PASS。
下方“正在运行”和47合同等均为前期记录，见
[完整资格](../results/production-byte-address-20261016-v1/qualification.json)。

## 以下保留阶段历史

最新定义阶段已正式采用18项旧UTAGE语义，当前**47项合同、286项待逐项审查**，
UTAGE全部25点均有合同，343个ID和历史配方保持。006/008/009已新增11项DUT
场景及47项纯检查，262项专项全PASS、六个新成对组全满；原生行增量为0，不
将来源判错能力增强说成行覆盖上涨。完整复验正在运行，最新完整测量仍为下方
18852项的上一阶段结果，冻结的29/304不能当作当前定义数量。见
[定义后设计与证据](../results/utage-source-ownership-20261016-v1/README.md)。

最新UTAGE证据补强完整复验：18852项，**18824 PASS /25 FAIL /3 XFAIL**；
旧18754节点及343点判定保持，新增98项全PASS（38 DUT场景、60纯模型/检查）。
原020/021各增加2/36项PASS证据，但整体仍FAIL。四个新语义组全满，旧353组
比例保持；UTAGE原生**6990/11053（+3）**，其余九DUT集合不变，无旧命中损失。
当前计划333硬件、10环境、29合同、304待审查；18项旧UTAGE定义提案另见
[来源与语义审查](utage-functional-definition-review-20261016.md)，未采用为冻结计划。
详见[完整复验](../results/production-utage-usefulness-events-20261016-v1/qualification.json)。
以下为前一阶段记录。

最新缺口补全：保留旧341个ID，先登记相邻 MainBTB 替换的 **MBTB-030 / INT-097**
两项合同，再实现单元/集成各7场景。当前共**333个硬件功能点、10个环境契约**，
29项显式事件合同，仍有304个旧硬件点待逐项语义审查。完整18754项诊断为
18726 PASS /25 FAIL /3 XFAIL，旧节点及旧功能点判定不变；硬件314 PASS /
17 FAIL /2 XFAIL，环境10 PASS。四个新增reached/checked组全满，旧349组比例
不变；MBTB原生1006/1056，其余九DUT集合不变，不枚举bank、不豁免RTL失败。
见[定义、场景和最终资格](coverage-gap-completion-20261016.md)。以下为前期记录，
静态旧表的“已有”及当时点数不替代当前计划与pytest判定。

前一阶段定义整理：计划与新报告分开统计**331个硬件功能点、10个环境契约**，
保留341个原ID。主summary改为硬件域，完整计划统计保留在summaries.all。
152项缺失description此前从下方对应ID的要求说明恢复；后续缺口审查已修订29项
名称/描述，显式事件合同由19项增至27项，涵盖全部17个失败点，另304个硬件点
仍待逐项语义审查。旧配方及恢复来源保留在计划metadata中。不能将文档补齐当作新PASS
或覆盖率提升。`ENV-IF-*`仅为Binding契约，不是Interface实现。
详见[定义、证据边界和审查入口](verification-point-semantics.md)。
当前缺口驱动的语义定义与逐行关联见[功能事件审查](functional-event-review-20261016.md)
及[可读事件目录](functional-events.json)。下方旧表尚未全部逐项重审，不应把表的
登记数量或“全bank/全槽位”配方当作独立语义需求数量。
下方历史段落中的合并341点统计与旧保留策略均按当时记录理解；静态表的“已有”
不替代最新pytest判定，历史载荷是否仍在以`results/RETENTION.md`为准。

分域后的完整复验`production-feature-domains-20261016-v2`共18708项：
**18680PASS/25FAIL/3XFAIL**，64进程、owner595.91秒，2123文件epoch不变。
原18642用例及全部341点判定保持，新增66普通测试全PASS；硬件331点为
312PASS/17FAIL/2XFAIL，环境10点全PASS。十DUT最终DAT逐字节相等，349组比例
全部不变、318满。这是定义与统计修正，不是覆盖率提升或RTL验收；正式报告不覆盖。
见[复验资格](../results/production-feature-domains-20261016-v2/definition-qualification.json)。

此前框架生产迁移完整复验：仍为**341点全部执行，322PASS/17FAIL/2XFAIL**，
所有旧节点/功能点判定精确保持；新增22项框架/诊断合同，不新增功能ID。
18642项/64worker完整执行18614PASS/25普通FAIL/3strict XFAIL，coverage提交和
worker回收完成，不改RTL或发布正式报告。十DUT原生集合不变，BPU33754/46541。
自动采集349组/318满，4个旧流程未导出的未满组及两项UTAGE异常前有效样本被
恢复；功能点通过率并未提高。详见[生产迁移资格](xreactor-managed-runner-20261016.md)。

此前093补强完整复验：**341点全部执行，322PASS/17FAIL/2XFAIL**，
全部旧点判定精确保持，不新建097。两条不同较早conditional完整纠正为indirect，
真实双来源/完整entry与独立direction保留、实际SDK服务、旧/新消费者闭合。
另发fresh offset请求，让较晚sibling真正被选择后比较原target及修正窗口；
不以模型内隐藏entry自洽代替DUT证明，不枚举bank/way，不豁免覆盖/丢弃。

[完整生产诊断](../results/production-main-reclassification-20261016-v1/diagnostic-summary.json)
18620项，64进程440.46秒：**18592PASS/25普通FAIL/3strict XFAIL**，无ERROR/
SKIP/XPASS。新增41重分类、25归因、6schema及1DUT共73项全PASS，所有旧节点
精确保持。门禁3139PASS（37.89秒）、兼容71PASS（56.98秒）、单093 PASS
（case1.46秒，pytest11.36秒）同2107文件epoch；64收据与1501产物hash核验。

BPU原生DA33745→**33754/46541（72.53%）**，严格新增9键恰好等于单093 PASS；
十DUT零旧键损失，其余九个精确集合、分母/构建不变。v_line仍2392/8236。
1182功能输入仅合并一次（137.28秒）：**345组/318满**，新增两组各6义务全满，
旧343组比例及27未满实例精确保持；required schemas146→148。新增FC维度不是
新增功能点，功能点通过率仍94.43%。原生Main125→116：74跨owner、42仲裁候选；
其13个producer都有历史独立UT PASS聚合见证，仍不是集成FTQ合法性或功能PASS。
原016闭合及其余九模块覆盖率保持，已知RTL差异不改FAIL，也未改RTL/DUT/SDK。
旧096 raw经新授权删除，汇总证据保留；当前与上一轮016完整输入保留，正式报告
不覆盖。见[语义与范围](semantic-reference-models.md#093补强两个独立较早分支的完整类型纠正)。

以下RAS016及更早段落均为当轮历史记录，不作为当前源码的单独全量验收。

2026-10-16上一轮RAS016集成补强完整复验：仍为**341点全部执行，322PASS/17FAIL/2XFAIL**，
全部旧点状态逐项保持，不新增097同义ID。原独立UT六个call/return丢通知上下文
保留；新增集成neutral direct来源检查距离2不回收、满容量下注册BOS回收后才解除
guard，随后不同身份call复用及fresh return正确消费。全部8个提交组不得变化，
neutral不能伪造已提交call；普通call/return的source顺序与SSP检查不放宽。

[完整生产诊断](../results/production-ras-neutral-gap-20261016-v1/exit.json)18547项，
64进程449.54秒：**18519PASS/25普通FAIL/3strict XFAIL**，无ERROR/SKIP/XPASS。
新增43纯/负向、6schema、1DUT共50项全PASS，所有旧节点精确保持；门禁3067PASS、
兼容70PASS、单016 PASS同2103文件epoch，64收据及1504产物hash核验。BPU DA
33741→**33745/46541（72.51%）**，恰好是单场景独立资格的四个gap键；十DUT
零旧键损失，其余九个精确集合、所有分母/构建不变。v_line仍2392/8236，不混算。

1181功能输入只合并一次（135.24秒），343组/316满；新增两个8-bin reached/checked
组全满，旧341组比例和27个未满实例全部精确保持。required schemas144→146；
FC组数增加不意味着功能点分母或通过率增加。RAS016有两个pytest节点；原六个
独立上下文是在一个节点内运行，不误算七个节点。集成RasStack35→31缺键，余16
局部guard与15物理组副本，保留分母，不自动授予功能PASS或枚举这些槽。仍是明确
漏通知防御profile，不声称正常FTQ合法性或全预测器独立性；已知RTL问题继续FAIL。
详见[语义与端点](semantic-reference-models.md#016集成补强中性提交回收版本寿命但不提交调用栈)
及[完整原生分类](../results/production-ras-neutral-gap-20261016-v1/diagnostic-integrated-ras-residue.json)。

以下096及更早段落均为当轮历史记录，不作为当前源码的全量验收。

2026-10-16历史096完整复验：**341点全部执行，322PASS/17FAIL/2XFAIL**，旧340点
状态逐项不变。096是“guard恢复后取消/回收版本可被新call身份安全复用”的一个
生命周期，不按slot14/15、call数量或13个原生键拆功能。独立持久程序栈比较真实
16版本满速边界、guard拒绝call/return和同当前source恢复、较老14-call来源释放
guard、存活旧操作提交、新返回地址跨容量wrap、撤销年轻新call及fresh新return。
该RAS语义cut-point不冒称自主Main/Micro全预测器或完整FTQ；旧010浅层guard恢复
不是新身份复用的完整证据。Main-only15版本是初次recipe节拍预期错误，不是RTL差异。

[完整生产诊断](../results/production-ras-reclaimed-versions-20261016-v1/exit.json)
18497项，64进程443.45秒：**18469PASS/25普通FAIL/3strict XFAIL**，无ERROR/
SKIP/XPASS。新增31纯/负向、6schema、1DUT共38项全部PASS，所有旧节点保持。
门禁3018PASS、兼容69PASS及单096 PASS同2096文件epoch；64收据、1496产物hash
核验，不改RTL/DUT/SDK及五份正式报告，不新增XFAIL。

BPU原生DA33728→**33741/46541（72.50%）**，严格13键等于单096 PASS：RasStack12
键，另1键是正常准备新PC的LRU物理副本，不算新Main-LRU功能。十DUT零旧键损失，
其他九个精确集合及所有分母/构建不变；v_line另2391→2392/8236。1180功能输入仅
合并一次（135.57秒）：341组/314满，新两组满，旧339比例及27未满实例全部保持。
required schemas142→144，不以合成schema通过代替真实功能闭合。

集成RasStack剩35键：16个源码/native完全对应的局部guard、15个物理组副本、
4个**尚未闭合**的non-push提交gap回收键。它们不是35个新功能；四个gap键关联
现有RAS016语义但缺集成来源/消费者证明，不能用096的正常call提交回收替代。
详见[096模型、范围与剩余需求](semantic-reference-models.md#096guard回滚后的调用版本回收与新身份复用)。

以下095及更早段落均为当轮历史测量，不作为本次源码全量验收。

2026-10-16最新095完整复验：**340点全部执行，321PASS/17FAIL/2XFAIL**，旧339点
状态逐项不变。新095归纳一个完整分支记录的版本生命周期：同PC两个真实旧来源
并行纠正类型/目标，pending只保留最新完整entry，但独立direction FIFO保留两次
接纳；fresh旧读先于释放，实际服务只含最新entry；fresh新来源再次修改clean
记录，重新服务并由fresh消费者读出前一region目标。完整sibling、另一PC和原始
metadata均保留。八个事件义务不是八个功能，四条新增DA也不是四个功能ID。

[完整生产诊断](../results/production-owned-main-rewrite-20261016-v1/exit.json)
18459项，64进程469.06秒：**18431PASS/25普通FAIL/3strict XFAIL**，无ERROR/
SKIP/XPASS。新增32纯/负向、6schema契约和1DUT场景，39项全部PASS，所有旧
节点状态保持。门禁2981PASS、兼容68PASS及单095 PASS与全量同2088文件epoch；
64收据、1496产物hash核验，不改RTL/DUT/SDK及五份正式报告，不新增XFAIL。

BPU原生DA33724→**33728/46541（72.47%）**，四键逐项等于单095 PASS，十DUT
零旧命中损失，其余九个精确命中集合及全部分母/构建不变。v_line另增2388→2391。
1179功能输入只合并一次（134.35秒）：339组/312满目标，新两组满；旧337组比例
及27个未满实例完全保留，required schemas140→142。初次负向carry试跑的问题是
验证协议projection的enum编码，已由原始声明和三项纯契约修正，不能记为RTL缺陷。
MBTB52缺行是同一个已执行train-state事件的未命中物理set副本，保留024物理分母
和按需深度回归，不再拆52个功能点或默认枚举。剩余Main125键、其它缺口、已知
RTL问题及全预测器/FTQ组合继续开放。
详见[095语义及验收边界](semantic-reference-models.md#095完整分支记录的pending版本取代与clean重激活)。

以下094/043及更早段落均为当轮历史测量，不作为本次源码全量验收。

2026-10-16最新094/043完整复验：**339点全部执行，320PASS/17FAIL/2XFAIL**，
旧338点状态逐项不变。094是“NT恢复只能追加已执行条件前缀，不能预计较晚未执行
conditional”这一语义要求，不按GHR/BW、内部/公开endpoint或原生行数拆点。
later-direct两种正对照通过，强化既有043；later-conditional两种端点均普通FAIL。
恢复应254/14，实际252/12；不绑定内部GHR/BW的公开profile先检查新source的
resolve.valid=1，再比较后续应253/12、实际249/8。模型expected只来自自有事件
序列和确切原owner，不读取实际metadata作为golden；不是nonconditional资格缺失。

[完整生产诊断](../results/production-owned-common-history-20261016-v1/exit.json)
18420项，64进程455.81秒：**18392PASS/25普通FAIL/3strict XFAIL**，无ERROR/
SKIP/XPASS。所有旧节点逐项状态保留，仅新增上述两个FAIL。新增60纯/负向、
2Bundle+2采样、24schema契约和4DUT场景；门禁2943PASS（214.16秒）、兼容
67PASS（113.18秒）、两个单PASS和两个隔离普通FAIL均同2081文件epoch。
64收据、1502产物hash核验；不改RTL/DUT/SDK及正式报告，不新增XFAIL。

十DUT原生DA精确命中集合、分母、构建来源和v_line完全不变：BPU33724/46541，
v_line2388/8236。通过的两个单场景均零增量；不能把补强oracle和发现错误说成
行覆盖率增长。任意S0历史队列选择、IMLI、自主SC历史组合和完整FTQ仍未完成。
1178功能输入只合并一次（133.48秒）：337组/310满目标。旧329组比例及23未满
实例逐项保留；direct新增四组满，conditional reached的state/public为50%/66.67%，
两个checked为0，共27未满。required schemas132→140；功能点通过率、FC组闭合
和原生DA不互换。SC336/TAGE120/BPU缓存120局部guard、PHR13局部+1404条件键
复核不变，不删分母、不填PASS。
详见[语义边界与源码原因](semantic-reference-models.md#094与043条件事件序列而不是commonhr信号方程)。

以下093/028及更早段落均为当轮历史测量，不作为本次源码全量验收。

最新093/028复验：**338点全部执行，320PASS/16FAIL/2XFAIL**。093新增容量内
MainBTB entry+方向FIFO完整服务闭环这一需求族，不按11条缺行或两个PC拆点。
028只加强原有所有权要求：真实BPU旧冷源提出的counter reset须跟随保留owner，
不得重置负向peer；仍普通FAIL，不新增同义功能点，不以093的通过替代028。

[完整生产](../results/production-owned-main-service-20261015-v1/exit.json)18328项、
64进程446.97秒：**18302PASS/23普通FAIL/3strict XFAIL**，无ERROR/SKIP/XPASS。
旧节点和逐项状态全保留，唯一新增失败是028集成资格。45语义纯/负向、1Bundle、
12schema契约与2DUT场景新增；门禁2855PASS、兼容65PASS、093单PASS及028单FAIL
均与全量同2071文件epoch，64收据和1495产物hash核验，RTL/DUT/SDK及正式报告不改。

BPU诊断33724/46541（72.46%），净增11个DA键，逐键等于093单PASS；十DUT
零旧命中丢失，其余九个精确命中集合、全部分母/构建不变。v_line另为2388/8236，
不与DA混用。1174份功能输入只合并一次（133.85秒），329组/306满目标；新增
服务两组满，旧源两组因失败为0，原325组比例和21个未满实例完全保留，总未满23。
required schema128→132；框架合成门禁通过不代表这些真实组全通过。
详见[093与028语义范围](semantic-reference-models.md#093与028mainbtb完整目标服务与旧冷源的真实owner资格)。

以下062/092及更早段落是当轮历史测量，不作为本次源码全量验收。

最新062/092复验：**337点全部执行，319PASS/16FAIL/2XFAIL**，旧336点逐点状态
不变。062只增强自主Main/ITTAGE/history oracle，不新增同义功能点；092归纳普通
正确间接学习在读压力下保留完整目标、释放后实际服务、提交前后新读可见性的一个
需求族。四个真实历史/foreign-region身份不是bank/set遍历，六条事件义务也不是
六个新功能ID。短/长历史两类各自完整闭环。

[完整生产诊断](../results/production-owned-indirect-service-20261015-v1/exit.json)
18268项、64进程505.72秒：18243PASS/22普通FAIL/3strict XFAIL，无ERROR/SKIP/
XPASS，旧节点与失败集合完整保留。三场景隔离资格均PASS；兼容64PASS、门禁
2797PASS，六轮同2062文件epoch，64收据及1485产物hash逐份复核。新增89语义
纯/负向、5个Bundle/Monitor、18schema契约与3个真实DUT场景。

BPU诊断33713/46541（72.44%），净增52个DA键，逐键等于短/长两项单PASS的
各26键；这是完整目标效果的slot2/3赋值展开，不按行拆点。十DUT零旧命中丢失，
其余九个精确命中集合、所有原生分母和provenance不变。1172份功能输入只合并
一次（134.03秒），325组中304满目标；六个新增组全满，全部旧组比例和21个
未满实例不变。required schema122→128，不把group数量当成功能点通过数。
RTL/DUT/SDK及正式根报告不改，已知FAIL不豁免，全量不发布为通过。详见
[独立语义与服务边界](semantic-reference-models.md#062与092自主间接目标学习与读压力下的完整目标服务)。

以下091及更早段落是当轮历史测量，不是本次源码全量验收。

新增091是一个真正缺失的硬件事件需求族，不按两条缺行拆两个点：正确provider与原
base分歧时，useful学习须在持续预测读压力下保留，释放后按序服务，两个原历史的
新消费者才能看到提交值。它不同于086的entry counter保留/合并，也不同于073维护
清零。四个语义要求归入一个功能点，六条reached/checked采样义务全部闭合；准备
好来源本身不计reached，必须等实际反馈接受。无bank/set遍历或实际状态golden种子。

[最终完整复验v2](../results/production-owned-direction-useful-20261015-v2/exit.json)
18153项、64进程444.96秒：**18128PASS/22普通FAIL/3strict XFAIL**，失败精确集合
和所有旧用例保留，无ERROR/SKIP/XPASS。计划现**336**点，全部执行，
**318PASS/16FAIL/2XFAIL**；原335点逐点状态不变，只增加091一个合格PASS。
75纯/负向契约、2个Bundle/Monitor契约、6schema契约和1DUT场景新增；最终门禁
2588PASS、旧兼容60PASS、隔离资格1PASS，四轮同2042文件epoch，64收据及1492
产物hash复核。required schema120→122。

BPU诊断**33661/46541（72.33%）**，净增queue入队/出队两个原生DA键，逐键等于
单PASS增量，`v_line`仍2387/8236；十DUT零旧键损失，其余九个命中集合不变。
1169份功能输入只合并一次（135.92秒），为319组、298满目标；所有旧组比例及原
21未满实例不变。已知失败不豁免，RTL/DUT/SDK及正式根报告不变，完整FTQ和其它
组合仍开放。详见[091语义与证据](semantic-reference-models.md#091-useful延后服务原来源学习旧值读取与实际写回分开证明)。

以下066及更早段落保留当轮测量，不是本次源码的全量验收。

066现完成双方向自主资格：NT-over-T选择较晚direct，T-over-NT选择较早conditional。
正向候选必须在返回驱动之前独立学习、实际确认并声明；同一base在另一历史下改变
方向时，所有声明的entry/useful保持。独立最高provider决定选择，命名consumer
自己的原S3来源必须引起useful增加，在下一完整actual比较后才确认，不能借同key的
另一task凑效果。来源归属与比较正交，不读取实际provider来初始化或修复golden。
新增20条义务包含原14条NT前提，两个reached/checked组均20/20，required schema
118→120；不是20个新功能点，也不替换原高索引066及NT-only场景。

[最新完整复验](../results/production-owned-early-positive-20261015-v1/exit.json)18069项、
64进程446.51秒：**18044PASS/22普通FAIL/3strict XFAIL**，精确失败集合不变，
无ERROR/SKIP/XPASS。335点全部执行，**317PASS/16FAIL/2XFAIL**，没有重复增加
功能点通过数。45纯/负向契约、6schema契约及1DUT场景新增；门禁2505PASS、旧兼容
59PASS、单场景1PASS，四轮同2035文件epoch，64收据/1485产物hash复核。
BPU诊断33659/46541（72.32%），净增8键逐键等于独立PASS资格；十DUT零旧键损失，
其余九个命中集合不变。1168功能输入只合并一次为317组、296满目标；旧组比例及
21未满实例不变。高位tag普通失败保留，不改RTL/DUT/SDK或正式根报告；完整FTQ和
其它组合仍开放。详见[双向语义与边界](semantic-reference-models.md#066双向反基预测先声明来源再验证实际选择和学习效果)。

以下保留前几轮资格记录，不作为当前源码的全量验收。

前一轮066新增自主反base资格，不新增同义功能ID，计划仍**335**点。真实NT provider必须
推翻强T Ahead base，S1选择较晚direct分支，与独立Main一致且不靠repair补救；其
原S3来源必须导致useful增加，并等下一完整actual状态比较通过后才确认效果。
同一Ahead owner用两条真实短历史保护原provider，不做物理坐标遍历。原066高
索引程序及其所有检查保留；新增14条因果义务的reached/checked两组均完整，
required schema116→118。新增33项纯/负向契约、完整门禁2454PASS、旧兼容58PASS，
单场景1PASS；四轮相同2027文件epoch。

最终完整18017项、64进程501.44秒：17992PASS/22普通FAIL/3strict XFAIL，失败
精确集合不变，无ERROR/SKIP/XPASS。335点全执行，317PASS/16FAIL/2XFAIL；本轮
加强066的判断资格，不把它重复计为新增通过点。BPU诊断33651/46541，净增11键
逐键等于独立PASS资格；十DUT零旧键损失，其余九命中集合完全相同。1167功能
输入合并为315组、294满目标，旧组比例及原21未满实例完全不变。失败全量未发布。
该轮尚缺T provider对NT base；后续双方向资格见上。完整FTQ物理寿命及其它组合仍缺。
详见[066独立语义与资格](semantic-reference-models.md#066自主反基预测原来源选择较晚分支并确认useful效果)。

044现增加条件Ahead/MicroTAGE的自主组合oracle，仍保持**335**个功能点，不新增
同义ID。正常Main发现、原Ahead消费者、单独NT resolve、新来源的later direct发现、
原来源fastTrain、独立分配的负向provider及新消费者均比较；checked等新receipt及
原快照保持完成才关闭。两种tag-width语义类各八条规则，required schema112→116。
最终选测低tag类PASS、完整tag高位类普通FAIL；低tag reached/checked各8/8，高位
reached5/8、checked0/8。不得用低tag结果宣称完整044已通过。

高位失败明确为独立tag `0x4000`与DUT八位容器`0x00`、hit预期1/实际0；完整15位
oracle不截断，不新增XFAIL，也不删失败类。新增55项纯契约通过，最终模型/框架
门禁2415PASS（171.16秒），旧DUT兼容56PASS（80.54秒）。最终全量17977项、64进程
453.73秒：17952PASS/22普通FAIL/3strict XFAIL，仅新增高位tag的普通失败；335点
全执行，317PASS/16FAIL/2XFAIL。BPU诊断33640/46541，新增8键，其中6键有单独
PASS低tag类资格，另2键不记合格提升；十DUT零旧命中损失，正式根报告不变。
当轮1166功能输入合并为313组、292满目标；旧组比例均不变，原19个未满组保留，
另有高tag两组未满。功能组分母、功能点分母与原生分母不混用。
下段015/019数据是此前完整测量。NT provider当前可能与Ahead base同方向，本
范围不冒称已证明base方向反转、全部预测器组合或完整FTQ合法性。
详见[044语义边界和差异证据](semantic-reference-models.md#044条件aheadmicrotage自主组合独立标签与原始路径训练资格)。

当前015/019加入自主Ahead/Main组合oracle，不新增同义ID，计划仍335点。正常双边
间接循环必须产生两个真实Ahead S1消费者，原S1快照供S3 fastTrain，后续Main目标
更新必须触发自主S3纠正、原读重放和新目标miss消费；禁用Ahead还要验证Main S2
回退。七条义务分别记录reached/checked，checked等到全部完成，required schema112组。MicroBTB在
该程序关闭，条件MicroTAGE和完整FTQ仍不由本profile声称完成。

最终隔离1PASS、兼容56PASS、模型/框架2348PASS；完整17908项为17884PASS、
21普通FAIL、3strict XFAIL，64进程445.10秒，失败集合不变。全部335功能点执行，
318PASS/15FAIL/2XFAIL，旧015/019通过点不重复计数。BPU原生33632/46541，净增
1个MainBTB替换状态物理写入键；十DUT零旧命中损失。失败全量不替换正式根报告。
309功能组中290满目标，两个新组完整；原19个未满组精确集合不变，不折算为通过点。
详见[自主组合及资格](semantic-reference-models.md#015019自主aheadmain组合提前读原来源学习与纠正重放)。

090之后的只读归因**不增加功能ID或覆盖分数**：PHR缺1417键中13为局部矛盾，
1404仅在复位及同epoch自有checkpoint约束下不可达。034原已定义合法偶数orbit，
035–038已定义两级方向/指针修复，不重复造点。raw PHR两组仍75%，保留奇数编码
bin，不用证明填PASS。ABTB4926和两块shadow4805的缺键均映射到少数计数器事件
的物理展开，也不能拆成数千功能点。新增39项诊断/不变量测试，完整门禁2271PASS、
DUT兼容16PASS；当时原模型、用例、RTL/DUT/SDK均未改，最新全量为下述090。
详见[分层归因和边界](coverage-gap-triage-20261013.md#2026-10-15大缺口再归因phr余数约束与物理副本只读)。

当前计划**335**点，新增`BPU-INT-090`：四份不同真实旧预测在逻辑key迁移后相邻
反馈，原metadata都提出6/旧way，当前版本必须以5/6/7/7提交到新owner。三个新
消费者检查饱和结果、邻居counter/useful和被替换key的miss，四份原metadata均
不可变。四笔是从4达到7后保持一次的最短事件程序，不是queue或bank枚举。
两方向四组reached/checked独立门禁，required schema110组。隔离每方向1PASS、
兼容53PASS、模型/框架2232PASS；纯模型测试不计DUT覆盖。

最新完整17791项为17767PASS、21普通FAIL、3strict XFAIL，64进程439.06秒，失败
集合与上一完整089相同。335功能点全部执行，318PASS/15FAIL/2XFAIL；307功能组
中288组满目标，19个未满组集合不变。这三类统计不混用。BPU诊断原生净增8键
到33631/46541，恰等于合格隔离增量；十DUT零旧命中丢失，失败全量不替换历史
正式根报告。详见[090语义及验收](semantic-reference-models.md#跨owner旧来源突发090原快照固定当前版本逐笔饱和)。

此前计划**334**点时新增`BPU-INT-089`：保留真实旧强provider来源，正常替换/保护/
重分配让同逻辑key迁移到相反way；旧metadata提出counter6，当前保留版本必须以
counter5提交到新owner。邻居counter/useful和被替换key的miss也必须由新消费者
确认。两方向独立四组门禁，required schema106组，不枚举bank/depth。
隔离每方向1PASS、兼容51PASS、模型/框架2160PASS；最新完整17717项为17693PASS、
21普通FAIL、3strict XFAIL，失败集合不变。334功能点全部执行，317PASS/15FAIL/
2XFAIL；303功能组中284组满目标，19个未满组集合不变。这三个统计不混用。
完整BPU诊断原生净增15键到33623/46541，十DUT零旧命中丢失；失败全量未替换
历史正式根报告。详见[089语义及验收](semantic-reference-models.md#跨owner旧来源089原metadata不是当前保留版本)。

此前计划**333**点时新增`BPU-INT-088`：五种真实历史在同一bank触及capacity+1。
实际满后新key只替代指定victim的两份pending，新counter不能继承victim的0/7；
五历史旧消费者、八份真实survivor提交、五历史新消费者全部比较后才关闭六条规则。
required schema为102组；088隔离1PASS、兼容49PASS、模型/框架门禁2098PASS。
相对最近完整生产原生新增0，不能把补功能点等同新增行覆盖。最近完整仍是下方
332点/17611项的086/087源码，未把当前333点拼成合格全量。
见[088模型及更严格checked时机](semantic-reference-models.md#满容量新键088被替换义务与新键初始化的独立合同)。

此前计划**332**点时新增`BPU-INT-087`：同bank四种真实历史、每历史两个owner，
五份A/B/C/D/A旧读反馈在连续预测中相邻接受；实际八个dirty全部占用后，A的
逻辑命中必须保留八份结果。四历史旧值消费后才释放读取，确认八次SDK完整写回，
再分别消费A的0/7与其它历史的1/6。不是第五新键溢出，也不是bank/set枚举。
新增两组门禁，required schema100组；隔离1PASS、兼容48PASS、模型/框架2057PASS。
本轮完整生产17611项为17587PASS、21普通FAIL、3strict XFAIL；所有332功能点执行，
315PASS、15FAIL、2XFAIL。普通失败集合不变，失败全量不替换历史正式根报告。
见[087语义及验收边界](semantic-reference-models.md#满容量命中087容量边界不能退化为多地址枚举)。

此前新增`BPU-INT-086`时计划331点：相同bank、两种真实历史、每历史两个
逻辑owner的四笔不重读反馈在连续预测中相邻接受。读取期间必须保有四份pending，
两个新查询仍看到旧2/5；释放后确认四次完整SDK写回，再分别消费新0/7。六条
reached/checked加入门禁，不枚举bank/set。它的最初资格是隔离选测，现已与087一起
进入上面的完整生产复验；旧正式报告不冒称当前全量；见
[086语义及验收边界](semantic-reference-models.md#读优先服务086接受保留提交和可见性分开验证)。

2026-10-15后续增量：计划现为330点。新增`BPU-INT-085`不是再枚举一个bank，
而是两份不同真实预测来源都持有同一旧counter2/5，完整双分支反馈相邻接受，
每个逻辑owner均须学习两次并由新请求读到0/7；再以新metadata验证饱和保持。
这不同于025每轮取新metadata的串行闭环，也不同于026每笔只更新一个不同owner。
六条硬件事件义务分别有reached/checked；新增两组纳入生产门禁。
最新隔离验收与完整生产测量见
[085自主并行学习](semantic-reference-models.md#相邻双owner学习085两份旧读必须合成而非丢失一次更新)。
该增量不替换下面的历史正式发布边界，普通RTL失败不因新场景通过而被豁免。

2026-10-15 发布边界：根 `results/feature-points.json` 对应完整生产回归
`production-ittage-directory-events-20261015-v1`，307 点全部执行，300 PASS、7 strict XFAIL；
pytest 为 15,595 PASS、7 strict XFAIL、0 SKIP。231个功能组中219个达到完整目标。
生产回归使用三类 ABTB 代表坐标，
完整 768 项物理遍历改为显式按需运行；两种范围的基线和完整物理分母分别保留。
见 [回归范围](regression-profiles.md) 和 [最新报告](../REPORT.md)。

067现已改为目录分配/预测消费两个事件族，各自reached/checked。分配五种规则，
消费三种规则，四组均100%；21真实分配事件、20目录写、231新鲜consumer逐一
对应。原单capacity case增加一次8项占用时的真实reuse，证明已有项优先于空项，
无bank扫描或新增DUT case。reset/全状态/全部resident/PHR/完整S3/drain合同保留，
不在case结尾批填十标签。完整生产十DUT原生分母和命中集合不变，BPU33257/46541，
新增原生0；是功能输入和测量补强，不是通过率或行覆盖上涨。见
[目录事件与正式证据](ittage-region-lifecycle-20261013.md#2026-10-15事件化分配提交和预测消费分别测量)。

072补强真实provider表/alternate置信度到八个逻辑selector的路由义务，不新增同义
功能点。复用073必需的八个容量对象、每表一个弱base和一个强base；每场景各路
训练一次，实际T3投票及完整八寄存器提交后才给checked。两组reached/checked均
8/8，原072饱和/消费和073六组检查保留。完整生产精确新增8键、十DUT零回退，
BPU33257/46541；八键在旧全物理范围也未见。不是bank/set遍历或再加老化case；
功能点通过率仍300/307，新增两组路由覆盖不能冒称多了两个通过功能点。见
[路由语义和正式证据](integrated-tage-selector-events-20261014.md#八个逻辑selector的输入路由加强原072不增加物理枚举)。

073已完成真实合格分配失败累计、饱和后的两种T3清理触发、清理写优先级/全范围
完成、新分配与保留tag消费。每场景255次增量、4128清理写握手、7项最终保持；
六组reached/checked完整。完整生产精确新增92键、十DUT零回退，BPU33249/46541；
88键旧全物理范围也未见，4键恢复旧路径。源码/64收据/985功能输入/根报告均核验。
不是92个功能点，也不因此豁免全部分配优先级或queue状态需求。见
[073语义与发布](hardware-event-functional-points-20261013.md#tage-useful老化073的真实事件资格与完整发布)。

071与修订070已通过完整生产刷新。SC旧64格属于历史检查清单，现为真实反馈
来源/T1更新/提交关联的52格事件覆盖，reached与checked分开且完整；原生新增0，
不以分母改变宣称上涨。068/069的MicroRAS在途事件迁移及年轻RETURN被中性S2
更正取消已完整生产发布，4/4 reached与checked均完整，原生同样新增0。
新增072检查合格TAGE selector训练提交与真实预测消费，现已完整生产发布，
精确新增11个原生键、十DUT零回退，BPU至33157/46541。更新/消费的reached与
checked四组在定义范围内均完整；8键直接对应selector更新，3键为伴随路径。
见 [TAGE事件证据](integrated-tage-selector-events-20261014.md)。
其他模块仍有同类清单式条目，尚未全部迁移。见
[事件语义定义和实现边界](hardware-event-functional-points-20261013.md)。

已发布070补整个阈值增量的范围拒绝与恢复，BPU精确新增17原生键至33146/46541，
十DUT零旧键回退。SC3键直接对应拒绝路径；TAGE14键仅是候选算术路径，不能等同
有效训练功能完成。见 [冻结场景和结果](integrated-sc-threshold-bounds-20261013.md)。

此前 BPU-INT-069 用真实热call/冷中性跳转构造S2 correction、较老S3 push与较年轻
错误路径CALL的三方重叠。完整MicroRAS/PHR、实际S2修正与每笔最终S3目标均比较，
哨兵不得产生最终metadata或进入主RASspec端口；六笔真实退休和全部提交单元/排空
也检查。10/10语义格、70项新增纯契约通过。完整生产精确新增10键，BPU至33129/46541，
集成MicroRAS87→89/91，十DUT零回退；7个MicroBTB和1个替换器键是哨兵带出的自然
路径，不是8项新功能。只用一组输入，不枚举bank、不伪造metadata或声明完整FTQ模型。
见 [准备门禁、前递/冲刷与发布](neutral-micro-ras-correction-20261013.md)。

此前 BPU-INT-068 补连续S1 call/return的在途操作前递/抵消需求。三次不同call与
三次LIFO return之间直接相邻或仅隔一条普通跳转，必须实际形成S1-pop/S2-push/
S3-push和S1-pop/S3-push，而非靠S2修正串行推进。全部9个MicroRAS寄存器、完整
公开目标/精确S3关联、6笔真实退休/全部提交单元、完整PHR及排空均比较后，16/16
语义格通过；新增67项纯契约、2个DUT case。完整生产精确重现隔离并集46原生键，
十DUT零回退，BPU至33119/46541；集成MicroRAS83→87/91。其余增量是自然程序
带出的MicroBTB/替换器/RasStack路径，不是46个新功能点或bank/set遍历。
main speculative RAS top仅是模块输入，不冒称其完整独立状态模型或FTQ合法性。
见 [输入、比较、剩余行分类及完整发布](early-micro-ras-pipeline-20261013.md)。

此前 BPU-INT-067 用20个输入context验证集成ITTAGE的PC-region控制、16项目录容量、
满表已有region复用及两次PLRU替换；每次写后比较所有resident、完整公开metadata、
精确关联S3目标，以及reset-derived目录/PHR、真实接受反馈及最终排空。
10/10语义格、54项新增纯契约通过；完整生产精确新增46原生键，十DUT零旧键丢失，
BPU至33073/46541，RegionWays116→162/162。46键旧全物理范围也均未命中，
不是46个功能点，也不是bank/set枚举。
另一个已存在foreign region的零置信度target重写诊断仍普通FAIL，直接暴露
providerTarget/altDiffers契约违例；alternate可遮蔽即时跳转错误。它不计覆盖、
不新增XFAIL，既有7项XFAIL不是全部未完成需求。见
[目录生命周期、发布复核及独立失败](ittage-region-lifecycle-20261013.md)。

此前 BPU-INT-066 通过真实四节点程序及一个 base-alias 返回节点，分离 index/tag
祖先并保留同一 ABTB base，实际检查 lower index462/tag208 的 allocation、
agreement-hold、useful增长/减少。10/10语义格通过，64项纯契约通过，完整生产
精确重现隔离70键增量、十DUT零回退，BPU至33027/46541。66键恢复旧物理范围，
4键为旧范围也未见的 useful 更新行；不枚举其余 high index 或宣称完整FTQ合法性。
见 [场景、负向检查和精确增量](integrated-high-index-useful-20261013.md)。

新增 BPU-RAS-016 显式丢弃少量call退休通知，再使用独立比较过的真实pre-operation
metadata检查距离2保持、距离3回收、push优先级及同代/跨代指针。6上下文、36语义
格、870周期的完整公开状态/BOS/8个提交单元比较均通过，后续call/return保持也检查。
独立资格与完整生产精确新增 `RasStack.sv:598,600,601,602`，RAS565→569/585，
十DUT零回退。该证据为独立模块公开端口故障注入，不冒称正常FTQ合法性，
不使用neutral commit或内部写入。107项新增纯契约检查错误状态与漏格会失败。
见 [故障边界与分层实现](ras-retirement-gap-20261013.md)。

新增 BPU-INT-063 部分回绕保留旧项已在上述完整回归中 PASS；已有 BPU-INT-017
补充相邻 resolve retarget、恢复流动后的双源仲裁与最终 MicroBTB target 读回。
上述场景的25个新行键全部保留。新增 BPU-INT-064 稀疏四节点 negative payload
返回通过独立 index/tag 历史关联，选择真实较后 CFI；9项功能契约全命中，
再补 lower1/2/7与upper6四格，使 shadow response-selection cross 达26/30。
该步相对上一生产基线净增192个原生 BPU 行键、十DUT零回退。

新增 BPU-INT-065 使用同一输入程序、不同回绕边界，环境按实际已接受写入的退休
调整停止位置；完整比较upper3/4/5旧负向payload与关联公开预测，27/27语义格通过。
该次完整生产shadow cross达29/30，BPU32957/46541，精确新增10键、十DUT零回退。
三个独立场景的0/10/3行增量去重只有10，不能相加；upper1完整consumer契约仍未通过。
新诊断已真实达到upper1读响应，但后续dirty/写回契约普通FAIL、不计覆盖。
见 [slot1因果证据](shadow-slot1-dirty-collision-20261013.md)。
见 [停流、已接受任务和精确回读](shadow-wrap-boundary-retirement-20261013.md)。
登记或行命中不能代替功能PASS，既有缺陷需求也没有被新场景豁免。

新增 BPU-UTAGE-023 在独立 index/tag PC及history 下检查真实高地址provider，
两种反馈节奏的20项语义契约全部通过；1024 useful单元、完整元数据及不同PC的
相邻请求均比较。原8192格useful更新cross只新增index462的8格，至5128/8192；
MicroTAGE原生9901→9904/11053，十DUT零回退，不枚举其余高地址。
原same-PC位宽缺陷需求及strict XFAIL不变，也不冒称完整FTQ合法性。
见 [场景与证据边界](utage-split-context-useful-20261013.md)。

新增需求：BPU-INT-059为200种合法双对齐几何×10 counter阶段（2000 bins）；
BPU-INT-060为两bank/四way/两profile的16种零历史SC-used场景（24 bins）；
BPU-INT-061为增加正/反向CommonHR的32种场景（48 bins）。比较通过之后
才导出功能覆盖，三组完整分母已纳入发布门禁；登记需求不等于登记PASS。

本文是目标验证范围。状态以 pytest 生成的 results/feature-points.json 为准；本表中的
“现状”在 2026-10-08 按最新完整回归复核，但不代替自动化 verdict。

以下为2026-10-08历史回归：1911 PASS、6 strict XFAIL、0 SKIP，255/255 功能点执行、249 PASS。
十个 DUT 已用未改动的 RTL 重建以修复旧覆盖率插桩错拍。
编译器与原生处理器改变了行映射范围；下表中的行增量数字保留原 5.026
场景基线语境，当前 5.052 行指标见 [rtl-coverage-analysis.md](rtl-coverage-analysis.md)。
工具修复不是新增功能点的替代证据。MicroBTB resolve 向量、同拍源仲裁和连续
useful 转发已由新场景关闭 34 个原生行缺口；新登记的 BPU-UBTB-016/017 均 PASS。
见 `results/coverage-ubtb-resolve-refresh-audit.json`。
ITTAGE 满 region 表的 tree-PLRU 替换已由 BPU-ITTAGE-018 的独立模型及
流水线比较检查，关闭两行而不要求超容量无损，见
`results/coverage-ittage-region-refresh-audit.json`。
MicroRAS 中性 S2/S3 override、主 RAS 回退及 redirect 恢复已由
BPU-URAS-015 关闭两行，三个 encoder 负对照均检出；该轮完整审计见
`results/coverage-uras-neutral-refresh-audit.json`。仅收集测试不再改写正式报告。
TAGE alternate/selector 及七个 ITTAGE 剩余分支点
仍需按有效资格继续分析和补测，
尚未因一条零计数就自动登记为已完成的新功能点。
SC threshold 已由 BPU-SC-021/022 正式覆盖四-way 上下界、资格门控、混合
贡献、邻 way 保持、相邻反馈及多分支越界整笔拒绝；88 个新 cross bin 闭合，
三负对照均检出。原生行 3142/3481→3145/3481，分支 866/1038→875/1038。
该轮完整审计见 `results/coverage-sc-threshold-refresh-audit.json`，仍不宣称
精确 signed table-counter 或全 SC 功能闭环。
后部 resolve 槽位诊断之后，BPU-TAGE-027/028 正式交叉八槽的 provider 深度／
饱和／保持、资格与邻项状态；独立冻结的输入预期及被动 monitor 检查实际
槽位和预测 metadata 关联，异步 prediction Scoreboard 检查输出。376 个新
cross bin 闭合，四负对照普通 FAIL。TAGE 原生行 4311/4587→4331/4587，
分支 1319/1598→1411/1598，其他九 DUT 及六项 XFAIL 不变。该阶段完整审计见
`results/coverage-tage-sparse-refresh-audit.json`。
正常分配／只读观测诊断先证明四个顶层 alternate-table2 mux 行可达，其
probe raw 始终不计主表，见 `results/coverage-tage-alternate-slots-readonly.json`。
随后 BPU-TAGE-029/030 正式化精确 alternate/provider 状态与混合槽重叠关联：
独立配对模型冻结预期，同事件 Bundle／Monitor 检查完整 metadata、两表
counter/useful/way 身份与选中 alternate；236 个 cross bin 闭合，四负对照
普通失败，27 项纯模型／能力／清理测试通过。TAGE 4331→4335/4587，
分支 1411→1421/1598，其他九 DUT 和六项 XFAIL 不变；该阶段完整审计见
`results/coverage-tage-alternate-refresh-audit.json`。模型不冒充完整分配／
aging／历史／陈旧 metadata／FTQ 参考。后续 key-copy 守卫复核追加分类 24 个
局部矛盾赋值，不增加 PASS 功能点也不删行分母；证据见
`results/coverage-tage-key-copy-unreachable.json`。该阶段 WriteBuffer 140 个未分类行和
其他功能组合仍需继续分析，不能由算术行命中推断功能完成。
再以真实非饱和 counter 1→0 与新 tag 分配的同笔反馈证明四个 WriteBuffer
路径可达，临时合并 4335→4339；饱和保持会省写，不能当作并发证据。
该单次 probe 的原始数据未登记功能点 PASS、未计主表；
见 `results/coverage-tage-mixed-hit-miss-readonly.json`。
随后 BPU-TAGE-031/032 正式覆盖四上下文 × 双 way × counter 1/2 的同拍双写，
以及 counter 饱和／无 MainBTB 命中／无效 slot／全局关闭的单写或零写。
144 个 cross bin 均在输入、完整全 bank 写端口、四周期延迟与全 resident
正反顺序流水线回读检查后闭合；23 项纯模型／能力／清理测试通过。
漏目标、漏后槽、将同拍双写伪装为单写、错 set 参考四负对照均普通失败。
完整回归使 TAGE 4335→4341/4587、分支 1421→1424/1598、v_line 95→96/132，
其他九 DUT、六项 XFAIL、工具及分母不变；剩余 246 行中 112 行局部分类、
134 行未分类。该阶段完整审计见 `results/coverage-tage-mixed-writes-refresh-audit.json`；
模型仍仅覆盖已准备的最高表、零折叠历史，不宣称完整 shadow 容量／FTQ 参考。
后续 BPU-TAGE-033 的相邻／间隔反馈矩阵正式通过：26 项纯检查与硬件矩阵
共 27 个新增 PASS，96 个 cross bin 闭合，四负对照均普通失败。
完整回归 TAGE 4341→4344/4587、分支 1424→1426/1598、v_line 不变；其他九 DUT
和六项 XFAIL 不变，恰关闭 WriteBuffer 844/845/888。剩余 243 行中 112 行
局部分类、131 行未分类，原始分母保留。该阶段完整审计见
`results/coverage-tage-overlapped-saturation-refresh-audit.json`；586-item 收集保护见
`results/coverage-tage-overlapped-saturation-collection-protection.json`。

随后剩余行分析发现另一项需求：旧 metadata 的 physical way 不是 retained
shadow owner；深层 counter 必须从最新保留值转发，而不是复制反馈中的旧值。
四 bank、双向 owner、depth 0–3、pending/clean 共 64 组正常驱动诊断全部
通过，临时原生行 4344→4397/4587，恰关闭 53 行；原生分母和 112 个局部
分类行保持。这份隔离诊断自身不计功能 PASS 或新 XFAIL，随后正式结果见下文。
新 `observe_shadows()`、读压力驱动封装及独立单写/drain/counter 模型已通过
四个 depth-3 硬件代表场景和 115 项纯检查；完整输入、全 shadow 周期及
正反流水线回读均检查。证据见 `results/coverage-tage-retained-owner-readonly.json`。
已登记并正式通过 BPU-TAGE-034，计划现有 254 点。
正式测试代码的隔离完整矩阵已通过：64 组合、192 个 cross bin、3360 个
shadow 周期和正反完整 profile；最新纯检查为 117 项，另有八个普通 FAIL
负对照，均保留 transfer 身份及接受/观察时刻。证据见
`results/coverage-progress-tage-retained-owner.json` 和
`results/coverage-tage-retained-owner-negative-controls.json`。
全仓刷新与审计已完成：1401 PASS、6 strict XFAIL、0 SKIP，254/254 功能点
执行、248 PASS。TAGE 正式 4397/4587，关闭同样 53 行；其他九 DUT 指标和
缺口集合、六项 XFAIL 不变。333 raw、146 功能 JSON、147 组及十份原生报告
同源/时效一致，刷新后 1407-item 收集保护通过。见
`results/coverage-tage-retained-owner-refresh-audit.json` 和
`results/coverage-tage-retained-owner-collection-protection.json`。
八个额外局部矛盾块头仅分类，剩余 120 个局部分类行、70 行未分类，原始
分母不扣除；FTQ 资格及原 useful 缺陷仍未闭合。

后续只读分析已验证另一项状态交叉：同一批真实 NT/T metadata 的双请求
way 与两个 retained owner 交叉，仍同时保留独立 counter 更新和上下界饱和。
32 组合通过并在 4397 行正式基线上临时再关闭 21 行；普通 owner 的六个深层双写
代表场景再关闭 24 行，候选达到 4442/4587。这批诊断尚未登记功能 ID，
也不属于 BPU-TAGE-034 的正式刷新。证据分别见
`results/coverage-tage-dual-cross-owner-readonly.json` 和
`results/coverage-tage-own-port-retained-readonly.json`。它们说明有必要将
双写的 hit/miss 与 companion dirty/clean 状态组合提炼为正式需求，而不是
只追加相同单写用例。剩余候选 25 行的四类待验证组合见
`results/coverage-tage-dual-write-gap-review-readonly.json`。
十个 companion dirty-hit/clean-hit/miss 代表场景随后通过，候选再关闭 22 行至
4464/4587；但 port0 已饱和 × companion 首次 miss 的三行尚未命中，不能
将其算作已覆盖。见 `results/coverage-tage-mixed-companion-representatives-readonly.json`。
随后 68 组合全 bank 矩阵通过，2148 个 shadow 周期及 416 项双写见证检查后，
候选精确关闭全部 25 行至 4467/4587；剩余 120 行与局部分类集合逐项一致，
不删原始分母。见 `results/coverage-tage-mixed-companion-full-readonly.json`。
双写 BPU-TAGE-035 已正式通过，最新完整报告已审计为 255 点。
新独立 bounded reference、八模式公共场景、384 个 cross bin 和简短 pytest
入口已实现；509 项纯检查和八个 depth3 代表通过。1917-item 正常收集不改
四份报告；十项负对照已全部产生有上下文的普通 FAIL。完整 128 组合隔离 pytest
及独立增量审计已通过：5336 个 shadow 周期、832 项双写见证、384 个 bin、
输入与正反 profile 一致，精确关闭 70 行且没有新缺口。完整全仓刷新随后通过
独立审计：1911 PASS/6 strict XFAIL/0 SKIP，255 点执行、249 PASS，TAGE 正式
4467/4587；其他九 DUT、源码/工具/分母与原六项缺陷不变。见
`results/coverage-tage-dual-shadow-refresh-audit.json`；1917-item 收集保护见
`results/coverage-tage-dual-shadow-collection-protection.json`。不宣称 FTQ、slot
碰撞或 full-row PLRU 已验证。

RAS 的源守卫审查将 65 个未命中行中的 16 个赋值分类为局部优先级矛盾或实际
父模块 action 互斥；九项源条件变异对照通过，不增加 PASS、不扣行分母。
此前条件头 515 的不可达分类已撤回：可达 false-arm 映射到该行并有 63 次原生
计数，即使 true-arm 的赋值 516 不可达。剩余 49 行提示八 SSP 索引的 committed repeat/saturation/wrap、非 push 有效提交的 bos
回收以及 redirect-call/return/bypass 等状态交叉。redirect 恢复返回地址实际
由 `cfiPc` 生成，现有 restore 封装尚未驱动该字段；先补驱动，不把测试里的
裸 IO 写入当能力。见 `results/coverage-ras-commit-gap-review-readonly.json`。
八 SSP × 普通/饱和的 16 组诊断已通过；两个不同结构的有界模型/重放器检查
1063 次公开操作及 5715 项比较，候选精确关闭 34 行至 554/585，16 个局部
矛盾赋值仍保留，15 行未分类。见 `results/coverage-ras-indexed-commit-readonly.json`。
首轮仅验证 top/SSP/SCTR 投影，未登记新功能 PASS/XFAIL；达到八格容量时的
底部淘汰是模型边界，不要求无限深保留。随后临时原型补齐完整 committed
八槽存储、公开输入和提交级被动观测；56 项纯检查、16 组合真实 pytest、
1063 次操作/5315 个周期/33353 项比较的独立重放及八项有上下文的普通 FAIL
负对照通过。见 `results/coverage-ras-committed-cells-prototype-readonly.json`。
该原型尚未进入当前冻结的仓库运行代码或正式功能计划；其原生行增量尚未审计，
必须等待完整正式刷新通过后再核对，不能直接套用首轮投影诊断的 34 行结论。

实际 FTQ 提交资格已进一步源审查：action=None 不进入 CommitQueue，因此不能
伪造 neutral commit 来关闭 bos 四行；必须用 Pop/PopAndPush 的真实退休 metadata
和距离条件验证，不能据此宣布不可达。八项源条件变异对照通过，见
`results/coverage-ras-commit-qualification-source-readonly.json`。action=3 的 coroutine
虽可进入 FTQ，却不满足当前 RAS 父级的 `== Push/Pop`，其预测栈效果仍待动态
验证；已有属性回传或训练资格功能点不是该项证据，不增加 PASS/XFAIL。

真正相邻的 push→pop 另用既有 `PulseDriver.send_many()` 完成隔离真实 pytest：
27 组逻辑序列覆盖 nested/alternate/turnaround 与重复计数跨饱和边界；独立
展开调用栈重放检查 198 次操作、225 周期、1431 项比较，完整输入与八槽
committed 邻项保持通过，原生 `RasStack.sv:801` 命中 47 次。八项错误观察
负对照均普通 FAIL。见 `results/coverage-ras-adjacent-bypass-prototype-readonly.json`。
尚未登记功能点，正式 RAS 仍 520/585；不声称全 speculative metadata/FTQ，
原生增量审计等待正式刷新通过，不把临时 raw 当正式结果。

redirect 隔离 agent 原型随后补齐公开 cfiPc：24 组 inflight/committed ×
SCTR=0/3/7 × 四类恢复重做全部通过真实 pytest。独立重放检查 524 次操作、
1160 周期、1528 项比较及 24 次恢复，核对真实 checkpoint 来源、完整输入、
正/负地址 signGuard、提交/恢复延迟、旧调用链退栈与 committed 邻项保持。
八项观察错误负对照均普通 FAIL，十个原缺失 redirect 源行在 raw 中均命中；
见 `results/coverage-ras-redirect-redo-prototype-readonly.json`。同样尚未登记功能点
或合并正式行增量，不推广为完整 queue recovery/FTQ 参考模型。

三套隔离场景现已整合成候选公共 agent API：`RasOperation`、`act_many()`、
`observe_committed()` 与兼容旧形状的 `restore(cfi_pc=...)`。170 项真实 pytest
通过（167 纯检查、三项硬件矩阵），67 个合法场景格闭合；25 项新 API 错误
注入均普通 FAIL。6700 周期、36339 项比较的完整记录与独立重放一致，实际
raw 命中 45 个原缺口，但尚未计正式增量。见
`results/coverage-ras-integration-candidate-readonly.json`。字节相同的旧 RAS
测试在新 agent 下另得 15 PASS/1 原 strict XFAIL/0 SKIP，见
`results/coverage-ras-candidate-legacy-readonly.json`。候选尚未迁入冻结仓库，
不增加计划或正式 PASS。完成 TAGE-035 正式刷新审计后，候选用16份新鲜
正式 RAS raw 加三份正向 pytest raw 通过原生增量门禁，精确关闭45行至
565/585、无新缺口；仍待迁入仓库、正式注册及完整刷新，不直接计正式覆盖。

随后 BPU-MBTB-020 正式交叉四物理 bank、双目标 way、双向 counter 更新、
低/高索引上下文与同 bank 阻塞/跨 bank 直通，共 64 组合。独立输入语义和
全 bank queue 请求/写回预期在驱动前冻结，被动 monitor 检查相邻反馈、
两项实际保留/排空与 flow 对照，异步 prediction Scoreboard 检查哨兵及
正反顺序完整 resident 回读。192 个 phase cross bin 断言后闭合，51 项纯
检查和四个普通失败负对照通过。完整回归 MainBTB 840→851/1056、分支
317→332/442、v_line 不变；其他九 DUT、六项 XFAIL、源码与分母不变。
该阶段完整审计见 `results/coverage-mbtb-counter-pending-refresh-audit.json`；
638-item 收集保护见 `results/coverage-mbtb-counter-pending-collection-protection.json`。
随后 BPU-MBTB-021 将 entry WriteBuffer 同 key 连续间接目标改写正式化：
低/高 set、四 bank、两 way、阻塞/直通和三种 carry 变化，共 96 组合。
公开输入、完整 entry 请求/写回及完整目标/metadata/邻项回读均独立比较；
288 个 phase cross bin 断言后闭合，93 项纯检查和五个普通失败负对照通过。
完整回归 MainBTB 851→857/1056（81.16%），v_line 29→31/38、分支
332→348/442；源码、工具、分母、其他九 DUT 和六项 XFAIL 保持不变。
该阶段审计见 `results/coverage-mbtb-entry-retarget-refresh-audit.json`；732-item
收集保护见 `results/coverage-mbtb-entry-retarget-collection-protection.json`。
该阶段剩余 199 行；不同 key 双 pending entry 的 32 组隔离候选，见
`results/coverage-mbtb-entry-two-keys-readonly.json`，随后由下述正式场景替代。

BPU-MBTB-022 正式交叉两个不同 set/tag 的间接分支、两种反馈顺序、三种目标
region 配对，以及低/高 set、四 bank、双 way 和阻塞/直通，共 192 组合。
每个目标始终属于自己的 PC；阻塞后两项按提交顺序写回，不按同 key 合并。
独立冻结的完整输入、全 bank 请求/写回及完整 resident/metadata 正反顺序回读
通过后，576 个 phase cross bin 闭合。145 项纯检查及六个带上下文的普通 FAIL
负对照通过。正式 MainBTB 857→877/1056（83.05%），v_line 31→32/38、
分支 348→351/442，关闭 20 行，其他九 DUT 和六项 XFAIL 不变。该阶段审计见
`results/coverage-mbtb-entry-keys-refresh-audit.json`；878-item 收集保护见
`results/coverage-mbtb-entry-keys-collection-protection.json`。
该阶段剩余 179 行为 WriteBuffer 126、ReplacerState 53。跨 way shadow 的
32 组探针另关闭 44 行，见 `results/coverage-mbtb-crossway-shadow-readonly.json`，
随后由下述有界正式矩阵替代；原探针 raw 本身不进入正式 manifest。

BPU-MBTB-023 将 captured-cold 请求的 LRU victim 与原 shadow owner 分开比较：
低/高 set、四 bank、双 owner way、clean-first/pending-second、阻塞/直通及
三种 carry 转换，共 192 组合。正常分配及正确 taken touch 不强制内部状态，
独立 LRU/端口/节拍预期与完整目标/meta/counter/邻项回读通过后采样，576 个
phase/status cross bin 闭合。251 项纯检查及六个普通 FAIL 负对照通过。
正式 MainBTB 877→921/1056（87.22%），v_line 32→36/38、分支 351→365/442，
关闭 44 行；源码、分母、其他九 DUT 和六项 XFAIL 不变。该阶段审计见
`results/coverage-mbtb-shadow-refresh-audit.json`；1130-item 收集保护见
`results/coverage-mbtb-shadow-collection-protection.json`。
这个 PASS 只覆盖初始 counter=2 的居民，不证明任意邻项或完整 FTQ 安全。

BPU-MBTB-024 将替换索引 PC[9:4] 与 SRAM set PC[10:5] 分开：目标、
set+32 alias、邻接独立索引及另一 align bank 在同一次复位后共同驻留。
覆盖 64 索引 × 两 align × 两 SRAM set 高位 × 四种 touch，共 1024 组合。
conditional 正确 taken 使 counter 2→3 并触碰 LRU；真实 not-taken 误预测使
2→1 而不触碰 LRU；预测读取不触碰；新分配将选中 counter 重置为 2。
独立 indexed LRU 在 DUT 反馈前选择 victim，完整 profile 正反流水线回读
通过后采样 6144 个 phase cross bin。112 项纯检查及七个普通 FAIL 负对照
通过。正式 MainBTB 921→974/1056（92.23%），分支 365→418/442，v_line
仍 36/38；恰关闭剩余 53 个 ReplacerState 行，其他九 DUT、原生分母及六项
XFAIL 不变。该阶段证据见 `results/coverage-mbtb-replacement-refresh-audit.json`；
1243-item 收集保护见 `results/coverage-mbtb-replacement-collection-protection.json`。
这是一个索引共享/隔离功能点，不把复制赋值拆成 53 个功能 ID。

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

独立有序诊断以不同 tag 的条件邻项 counter=3 为前提，16 组全部观察到其
counter 3→2，而 entry payload/owner/时序均正确，只有两处公开 metadata
counter 字段改变。诊断普通 FAIL 未登记功能 PASS 或 blanket XFAIL；完整 FTQ
epoch/redirect/资格仍需审查，见 `results/coverage-mbtb-shadow-counter-side-effect-readonly.json`。
024 阶段剩余 82 个 WriteBuffer 行（025 再关闭 42 行）。先前 128 组索引探针已由上述正式矩阵
替代；旧探针 raw 仍不进主表，见 `results/coverage-mbtb-replacer-index-readonly.json`。
FTQ 源码确认 MainBTB 在 resolve 路径训练，redirect 会过滤年轻训练；仅有
捕获/反馈顺序不证明 epoch 资格，见 `results/coverage-mbtb-ftq-qualification-source-readonly.json`。
40 个复制赋值需要双写有效，但 flush 可以补出第二路，不能仅凭训练 one-hot
将其划为不可达；见 `results/coverage-mbtb-flush-overlap-source-readonly.json`。
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

BPU-MBTB-026 随后将非联合零 key 的清理/训练重叠正式化：四物理 bank ×
training depth 0/1 × dirty/clean 清理 shadow × 三种 key，共 48 组合。
持续 S2 multi-hit 清理保持 dirty；单拍清理后暂停并排空，才能准备 clean。
这些阶段控制封装在 agent 内，用例仅提交训练并等待周期。独立冻结的输入、
两写端口 payload/read 资格、全 shadow 前后状态及四周期延迟均比较；
两 set 完整 profile 再按正反顺序流水线回读，144 个 cross bin 断言后闭合。
21 项纯模型/scope 检查通过，八项有身份/tick/status 的负对照均普通 FAIL。
完整回归 MainBTB 1016→1056/1056（100%），v_line 38/38、分支
426→434/442，恰关闭最后 40 个原生映射行；其他九 DUT 和六项 XFAIL 不变。
1283 PASS、6 strict XFAIL、0 SKIP；253/253 功能点执行、247 PASS；332 raw、
145 功能 JSON、146 组聚合 99.47%，十份 LCOV/JSON/HTML 同源/时效一致。
见 `results/coverage-mbtb-cleanup-overlap-refresh-audit.json`；1289-item 收集保护见
`results/coverage-mbtb-cleanup-overlap-collection-protection.json`。
八个剩余分支已由实际父模块常量连接及四项源码变异负对照分类，证据见
`results/coverage-mbtb-branch-unreachable.json`；原生分支分母 442 不扣除。
更早启动训练的隔离诊断还观察到联合零 key 下另一 set 更新被清理覆盖，
不同于旧 delay 0/1 诊断的 pending 首读；见
`results/coverage-mbtb-cleanup-routing-readonly.json`。该诊断只在一个物理 bank
验证这一新偏移，未登记正式 PASS/XFAIL，完整 FTQ 资格及整体目标仍未闭合。

现状取值：

- **已有**：已有独立或接近独立的自动化证据；
- **部分**：在聚合场景中被触及，但没有独立 verdict；
- **缺失**：没有足够自动化证据；
- **缺陷**：已有稳定复现并登记为 strict XFAIL。

## 1. 验证环境契约

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| ENV-IF-001 | P0 | picker signal_tree 的层次化 Bundle/Pulse 绑定正确 | 已有 |
| ENV-IF-002 | P0 | clock immediate、普通输入 RiseWrite，DUT 首拍前 reset=1；测试无边沿细节 | 已有 |
| ENV-DRV-001 | P0 | driver 独占信号，重复 claim 失败，close 后释放 | 已有 |
| ENV-DRV-002 | P0 | pulse valid 恰好覆盖一个 DUT 接受周期 | 已有 |
| ENV-DRV-003 | P0 | 异步单周期 Driver 连续周期接受多个请求并发布事件 | 已有 |
| ENV-DRV-004 | P1 | queue 满、cancel、close、idle 恢复的失败语义 合法旧来源允许晚于年轻来源解析；失效或被篡改输入在写入前拒绝。取消未发射任务后可继续工作，驱动期异常保持终止并保留原异常。 | 已有 |
| ENV-MON-001 | P0 | monitor 产生带 event 的不可变 snapshot | 已有 |
| ENV-MON-002 | P1 | monitor start/close/rearm 和 lossless overflow | 已有 |
| ENV-SCB-001 | P0 | 固定延迟/FIFO/tag/custom association 正确 | 已有 |
| ENV-SCB-002 | P0 | mismatch/incomplete/association error 到达 pytest | 已有 |

## 2. MicroBTB

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-UBTB-001 | P0 | reset 后 sramResetDone 与 trainReady 就绪 | 已有 |
| BPU-UBTB-002 | P0 | cold lookup miss，disable 时不产生有效预测 | 已有 |
| BPU-UBTB-003 | P0 | taken 条件/直接/间接分支可分配并返回完整 payload | 已有 |
| BPU-UBTB-004 | P0 | not-taken miss 不分配新 entry | 已通过；独立用例断言不分配；汇总功能覆盖的 `trained`×`miss` bin 现也在真实 not-taken 训练及后续 miss 断言后采样，原先仅用冷态查询采样的前提错误已修正 |
| BPU-UBTB-005 | P1 | hit entry 的 target/position/type 可更新且时序明确 | 已有 |
| BPU-UBTB-006 | P1 | 全相联容量替换后 survivor payload 保持隔离 | 已有 |
| BPU-UBTB-007 | P0 | back-to-back lookup 固定一周期延迟并正确关联 | 已有 |
| BPU-UBTB-008 | P2 | partial-tag alias、position 和 target 边界 | 已有 |
| BPU-UBTB-009 | P1 | not-taken 命中令 useful counter 从强正逐级下降：前两次保持原预测，第三次变成 miss；再训练 not-taken 不重分配，随后 taken 训练重新分配并返回新 payload | 已有 |
| BPU-UBTB-010 | P1 | 一次 not-taken 老化后，精确 taken 命中恢复 useful counter；重复精确命中在正饱和保持有效，不回绕 | 已有 |
| BPU-UBTB-011 | P1 | 两笔相邻训练分别分配、老化同一个 PC；第二笔通过 t0/t1 bypass 看到尚未写回的 entry，后续老化次数可由预测 hit/miss 验证 | 已有 |
| BPU-UBTB-012 | P1 | 连续训练将 useful counter 从 3 降到 0 后紧接不同 target 的 taken 训练，须重新初始化 payload/useful counter，并经三次后续 not-taken 才失效 | 已有 |
| BPU-UBTB-013 | P0 | 条件、直接、间接三种不同 PC 连续交错查询时，每周期接受一笔且逐笔返回完整有效位／方向／位置／类型／目标 payload | 已有 |
| BPU-UBTB-014 | P0 | 全局 disable 阻止 fastTrain 分配和已有 entry 的 payload 更新，并隐藏已有命中；重新 enable 后原 entry 保留，启用时同一更新可生效 | 已有 |
| BPU-UBTB-015 | P1 | 32 项表填满后，在替换写回周期查询被驱逐的旧 PC，必须返回 miss，不能用旧 hit mask 误读新 victim payload；同样的填充／访问历史下，查询一个非 victim PC 仍须返回完整原 payload。写回后新项命中、旧 victim 消失、其余 resident 保留 | 已有；agent 封装训练写回与查询重叠，四格功能覆盖在结果断言后采样 |
| BPU-UBTB-016 | P0 | resolve 向量全部八个 slot 的唯一有效误预测须返回其精确 target／position／type／RAS action；较早正确 not-taken 分支不得误选。每个 slot 的条件项还须按三次选中 not-taken 反馈老化至 miss，其他 resident 保持 | 已通过；八 slot × 两种场景的 16 格断言后闭合，monitor 补齐 RAS 属性，不再只驱动 fastTrain |
| BPU-UBTB-017 | P0 | resolve 与 fastTrain 同拍到达时有效 resolve 优先；正确反馈、无效误预测和被门控的 t0 由 fastTrain 更新；无资格 resolve 不修改 resident，全局 disable 阻止两个源且保留旧项，重新启用后可分配 | 已通过；agent 核对两源事件同 tick，八格在架构断言后闭合；关闭 resolve 的负对照被检出 |

BPU-UBTB-010/011/012 的连续反馈证据另补上“恢复／重初始化之后还要送下一拍”的
转发交叉：两组 burst 均用三次后续 not-taken 的失效边界检查持久 useful=3。
四格覆盖断言后闭合，原生四个 forward-counter 行实际命中。
MicroBTB 当前 794/794 行、187/192 分支；不把满行当作所有功能组合已验证。

## 3. AheadBTB

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-ABTB-001 | P0 | SRAM reset 完成后 cold miss 和 meta 有效 | 已有 |
| BPU-ABTB-002 | P0 | 三种 branch type 分配到正确 entry/bank | 已有 |
| BPU-ABTB-003 | P0 | not-taken miss 不分配 | 已有 |
| BPU-ABTB-004 | P1 | indirect hit 的 target 修正 | 已有 |
| BPU-ABTB-005 | P1 | set/bank mask、冲突和 replacement | 已有 |
| BPU-ABTB-006 | P0 | back-to-back lookup 接受后两周期采样并关联（含驱动 launch 共三周期） | 已有 |
| BPU-ABTB-007 | P1 | meta 与 toMicroTage sideband 一致 | 已有 |
| BPU-ABTB-008 | P1 | 不同冷查询 PC 的 meta.setIdx 与 RTL 哈希索引对应，避免用错预测事务的训练 metadata | 已有 |
| BPU-ABTB-009 | P1 | fastTrain valid 所在接受周期的 PC、target、taken 与 meta 同周期有效 | 已有 |
| BPU-ABTB-010 | P1 | 条件分支方向计数器可向不跳转／跳转两侧收敛并饱和，训练目标 set 不影响相邻 set 的预测 payload | 已有 |
| BPU-ABTB-011 | P1 | 同一 bank/set 的四个条件分支分别占用不同 way；逐一训练方向时仅命中 way 的 counter 改变，其余 tag/方向/target 保持 | 已有 |
| BPU-ABTB-012 | P1 | 相同 PC 在不同折叠路径历史下选中四个独立 bank，训练其中一处不造成其他 bank 的 tag/target 混淆 | 已有 |
| BPU-ABTB-013 | P1 | 同一 PC 的较晚位置 taken 分支训练降低较早条件分支方向计数器，反向训练只恢复较早分支，不改变较晚分支的方向和 target | 已有 |
| BPU-ABTB-014 | P1 | 四个同 bank/set 条件 entry 老化到 not-taken 后，第五个 taken entry 替换其中一 way 时 counter 必须重置为可预测 taken；其余三 way 的方向及 target 保持 | 已有 |
| BPU-ABTB-015 | P1 | 同一 bank/set 持续分配超过容量时，replacement 逐步访问所有 way；每次只驱逐一项，最终四个驻留 entry 的方向和 target 正确 | 已有 |
| BPU-ABTB-016 | P1 | S2 override 提前恢复已保存的预测；同 PC 命中，改变 overrideStartPc 后重新匹配为 miss，metadata 保持有效 | 已有 |
| BPU-ABTB-017 | P1 | S3 override 提前恢复已保存的预测；同 PC 命中，改变 overrideStartPc 后重新匹配为 miss，metadata 保持有效 | 已有 |
| BPU-ABTB-018 | P1 | 最高 setIdx=63 的四个 bank 分别训练不同 target，索引边界下回读不混淆 | 已有 |
| BPU-ABTB-019 | P1 | 最高 setIdx=63 的四个 bank 各自满组后持续替换，访问所有 victim way，检查新项、保留项与跨 bank 隔离 | 已有 |
| BPU-ABTB-020 | P1 | 最高 setIdx=63 的每个 bank/way 条件方向计数器先收敛到 not-taken 饱和，再恢复到 taken 饱和；其余 entry 的方向与 target 不变 | 已有 |
| BPU-ABTB-021 | P1 | 最高 setIdx=63 的四个 bank 各 way 老化至 not-taken 后被替换，新 entry 的方向计数器须重置为 taken，其他 entry 仍保持 not-taken | 已有 |
| BPU-ABTB-022 | P0 | 不同 PC 的背靠背请求各自返回匹配的分支 position/type/target，不能只检查某个 entry 有效 | 已有 |
| BPU-ABTB-023 | P1 | 相同 PC 的四种路径历史交错进入流水线时，各自选择正确 bank 并返回该 bank 的 target | 已有 |
| BPU-ABTB-024 | P1 | 内部 bank 3/set 16 与 bank 1/set 34 的四个 way 条件计数器分别向负饱和、再向正饱和恢复；另让同 bank 相邻 set 34 四路保持 not-taken，逐路翻转 set 35 的计数器并回读两组方向、target 与路由，排除跨 set/way 串扰 | 已有；set 35 的 8 个原缺失 RTL 行点由新场景命中 |
| BPU-ABTB-025 | P1 | 相同 PC／同一 bank 使用折叠历史哈希高两位访问四个独立 set，分别训练不同 target 后回读不混淆 | 已有 |
| BPU-ABTB-026 | P1 | 哈希选中的内部 set 1 在四路条件 entry 老化至不跳转后逐路替换，新 entry 计数器重置为跳转，幸存 entry 的方向与 target 不变 | 已有 |
| BPU-ABTB-027 | P1 | 物理 set 31/32 的索引位边界 × 四个 bank × 四个 way：32 个 resident 同时驻留；每项独立老化至 not-taken、恢复 taken，持续回读其他 resident 的方向、target 和路由元数据 | 已有；按未命中格子扩充 bank 1/3 |
| BPU-ABTB-028 | P1 | 同一份真实 cold 预测 metadata 被后续训练复用，在同一 bank/set 不同 way 产生同 PC/position 双命中；S2 检测后，单端口 bank 获得无读窗口并清理为唯一命中，方向与 target 保持；bank 0/2 分别验证 | 已有 |
| BPU-ABTB-029 | P1 | 持续查询同一单端口 bank 时，两笔指向不同 set 的 fastTrain 写入应保存在写缓冲中；读压期间仍 miss，停止读取后两处各自命中且 target/set/bank 正确 | 已有 |
| BPU-ABTB-030 | P1 | bank 1/set 34 的四路条件 entry 老化到 not-taken 后逐路替换：新项立即 taken、旧 tag 消失、其他 resident 的方向/target 不变，bank 3/set 16 哨兵不受影响 | 已有；原始 needReset 分支受插桩相位影响 |
| BPU-ABTB-031 | P0 | 全局 disable 阻止 fastTrain 分配和已有间接目标更新，并隐藏已有命中；重新 enable 后旧条目保留，启用时相同目标更新可生效 | 已有 |
| BPU-ABTB-032 | P1 | 目标区域边界：同区域目标完整返回；跨 4 MiB 上溢／下溢时，因 `EnableTargetFix=false`，AheadBTB 单模块将查询 PC 的 `[49:22]` 与目标低 22 位拼接，必须明确断言两种 wrap 结果 | 已有；这是早级局部编码契约，不豁免集成 BPU 对错误高位的最终修正义务 |
| BPU-ABTB-033 | P1 | 物理 setIdx 63→0 的相邻 PC 在 history 选中的 bank 1/2 各驻留一项 set 63 哨兵与四项 set 0 条件 entry；两个哨兵保持 not-taken，set 0 的八个 way 逐路老化、恢复，每步回读十项方向、target、way 与 set/bank 路由 | 已有；按未命中格子扩充 bank 1/set 0，交叉验证跨 bank 与回绕隔离 |
| BPU-ABTB-034 | P1 | 同 PC 四路不同位置的条件分支填满 bank 1/set 36；训练第五个更后位置的 taken 分支时，恰好替换一项，三个幸存的前位置方向计数器应减至 not-taken；再训练最早幸存项，仅其恢复 taken，其他方向、target、way 不变 | 已有；交叉验证位置优先级与满组替换 |
| BPU-ABTB-035 | P1 | 在 bank 1/set 36 预置不同数量的旧 tag，分别引导满组替换选中四个 victim way；每次都用同 PC 四路不同位置的条件分支和第五个更后位置的 taken 分支，检查恰好驱逐一项、三个幸存项均被抑制且 target/way 不变，以及旧 tag 不再命中 | 已有；覆盖 victim way 0–3 与位置优先级抑制的交叉场景 |
| BPU-ABTB-036 | P1 | bank 0/set 0 同 PC 四个条件位置均命中时，一笔 not-taken 反馈使全部四路方向转为不跳转，随后 taken 反馈仅恢复位置相同项、降低更早项、不影响更晚项；依次训练四个位置，用恢复次数区分隐藏的弱负／强负计数状态，始终检查 target 和 way | 已有；补齐“多命中 not-taken × 位置选择性 taken”的行为交叉 |
| BPU-ABTB-037 | P1 | bank 3/set 0 同 PC 的四个位置分别存放两个条件分支、一个直接分支、一个间接分支；重复 not-taken 反馈只能降低条件项，taken 恢复只影响匹配条件位置；间接目标修正只改变自身 target，同时按位置优先级降低前面的条件项，持续检查全部 type、way、target | 已有；补齐“混合分支类型 × 共享反馈 × 间接目标修正”的交叉 |
| BPU-ABTB-038 | P1 | bank 3/set 0 混合条件／直接／间接的四路满组在不同替换历史下被较晚条件分支替换：四个 victim way 和三种旧类型均要出现；新条件计数器从弱正老化为不跳转并恢复，幸存项的类型、位置、way、target 不变 | 已有；交叉检查非条件 way 被条件分支复用时的计数器重置 |
| BPU-ABTB-039 | P1 | 同 PC 在 path hash 3/7 下分别选择 bank 3 的 set 0/1：前者保留混合分支类型四路，后者四个条件位置从一次 not-taken 共同老化后逐路恢复；每一步检查两个 set 的方向、位置、类型、target、way 和路由互不串扰 | 已有；交叉“历史哈希选 set × 同 PC 多位置计数更新” |
| BPU-ABTB-040 | P1 | 同 PC 在 path hash 3/7 下选择四路弱正混合类型与强负条件分支配置；相邻周期交错查询时，送往 MicroTAGE 的每路 S2 result 必须与对应预测的 valid、position、type、RAS action、taken 和 strong bias 一致 | 已有；五格断言后采样；S1 fastPositions 与 S2 result 的阶段语义分别说明 |
| BPU-ABTB-041 | P1 | 同一 PC 在物理 set 1 由四种历史哈希分别选择 bank 0/1/2/3，各 bank 四个条件位置及不同 target 同时驻留；逐 bank 老化全部方向、再按位置恢复全部四个物理 way，每次检查其他三个 bank 的路由、方向、way 与 target 不变 | 已有；交叉“历史选 bank × 同 PC 四路计数更新”，20 格输出断言后采样 |
| BPU-ABTB-042 | P1 | 同一 PC 在物理 set 2 的四个历史 bank 各自填满四路条件位置；逐 bank 训练第五个更后位置，只允许选中 bank 替换一个 way 并抑制三个幸存条件项。再老化、逐位置恢复全部四路，持续核对被驱逐项不存在、其余三个 bank 的方向、target、way 和路由不变 | 已有；交叉“历史选 bank × 满组替换 × 同 PC 位置优先级”，24 格输出断言后采样 |
| BPU-ABTB-043 | P1 | 四个历史 bank 中同时填充物理 set 2/3/4：set 3 各四路条件项，前后相邻 set 各留一个老化为 not-taken 的哨兵。逐 bank/way 老化并恢复 set 3 计数器；每次核对全部 24 个条目的方向、唯一目标、物理 way 和 bank/set 路由，证明两侧相邻 set 与其他 bank 均不受干扰 | 已有；32 个 bank×way×方向 bin 及双侧哨兵保持 bin 在断言后闭合；set 3 的计数器行点缺口全部关闭 |
| BPU-ABTB-044 | P1 | 四个历史 bank 同时填满物理 set 4 四路，并各在 set 3/5 放置 not-taken 哨兵；原四路也老化为 not-taken。逐 bank 以第五个不同 tag 替换一个物理 way，要求旧 tag 消失、新项从 taken 起步，其他三路及双侧邻 set、其他 bank 的方向、target、way、路由保持不变 | 已通过；四 bank 与双侧隔离 bin 在输出断言后闭合；set 4 的 10 个减向选择行点新命中，正向臂仍有 16 个缺口 |
| BPU-ABTB-045 | P1 | 在 BPU-ABTB-044 的 set 3/4/5 双侧老化邻域中，四个 bank 各替换一个 set-4 victim；将新项再次老化到 not-taken，再让 12 个幸存旧项与 4 个替换新项逐路恢复 taken。每次更新后检查 24 项的方向、目标、物理 way 和 bank/set 路由，双侧哨兵与其他 bank 不变 | 已通过；16 个 bank×way 恢复 bin 和替换／幸存类型 bin 在断言后闭合；set 4 剩余 16 个正向更新行点全部命中 |
| BPU-ABTB-046 | P1 | 同一 PC 的高物理 set 48–51 与 4 个 bank 构成 16 格折叠历史索引：每格存不同条件目标，逐格老化／恢复方向并持续检查其余 15 格的路由、目标、way 与方向不串扰 | 已通过；16 个 route 和 32 个方向转换 bin 在全格读回断言后闭合；固定种子全量 AheadBTB 新命中 24 个 `v_line` 点（16 个正向、8 个减向），均是原先未触达的高 set 复制实例，不把每格计为独立功能点 |
| BPU-ABTB-047 | P1 | 在同一 PC 的高 set 48–51 × 四 bank 哈希网格中，每格同时驻留四个条件位置及独立目标配置；逐格一次负向反馈使四路变为 not-taken，再依位置逐路恢复，每次检查全部 16 格的路由、物理 way、目标和方向 | 已通过；64 个 route×way 功能 bin 在全网格断言后闭合；固定种子全量 AheadBTB 新命中 73 个 `v_line` 点（48 个正向、25 个减向）和 90 个分支点，高 set 网格的 64 个计数器格子无剩余行点缺口；复制格子数不等于功能点数 |
| BPU-ABTB-048 | P1 | 同一 PC 在高 set 48–51 × 四 bank 的 16 个历史路由各驻留四路及不同 target；逐格训练第五个更后位置，只允许该格一个物理 way 被替换、三个幸存项变为 not-taken，其他 15 格的目标、方向、way 和路由保持不变 | 已通过；16 个替换路由 bin 与隔离 bin 在全网格断言后闭合；固定种子全量 AheadBTB 行/分支计数不变，说明此行为交叉不能由复制 RTL 点增量代替 |

## 4. MainBTB

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-MBTB-001 | P0 | reset 后 cold lookup 返回全 miss | 已有 |
| BPU-MBTB-002 | P0 | 同 fetch block 多 entry 按 position 共存 | 已有 |
| BPU-MBTB-003 | P0 | branch type、target、position payload 正确 | 已有 |
| BPU-MBTB-004 | P1 | taken counter 双向收敛且不溢出 | 已有 |
| BPU-MBTB-005 | P1 | 已有 entry 更新不误分配其他 entry | 已有 |
| BPU-MBTB-006 | P1 | 同 set 冲突、replacement 与无关 set 隔离 | 已有 |
| BPU-MBTB-007 | P0 | back-to-back lookup 接受后两周期采样并关联（含驱动 launch 共三周期） | 已有 |
| BPU-MBTB-008 | P1 | 页末 fetch 屏蔽下一页的 raw-hit entry；从下一页起点查询仍可返回该 entry，position 正确重映射 | 已有 |
| BPU-MBTB-009 | P1 | fetch 起点越过已有分支位置时屏蔽该 raw-hit entry；从原 block 起点查询仍命中 | 已有 |
| BPU-MBTB-010 | P1 | disable 时 lookup 流水级保持，禁用期间的新 PC 不替换旧输出；重新 enable 后训练过的 entry 可见 | 已有 |
| BPU-MBTB-011 | P1 | disable 时训练不更新已有 indirect target；重新 enable 后同一训练可生效 | 已有 |
| BPU-MBTB-012 | P0 | 不同 PC 的背靠背请求逐笔返回各自的 position/type/target，不能以重复同一 PC 的命中代替关联验证 | 已有 |
| BPU-MBTB-013 | P1 | 部分目标地址按 TargetWidth=20 保存时，同一区域、向相邻区域上溢、从相邻区域下溢三种目标均能还原完整地址；三格均在预测回读后采样 | 已有 |
| BPU-MBTB-014 | P1 | 同一位置的条件 entry 先老化至计数器 0，再按“条件→直接→间接→条件”改变分支属性；每次必须原位改写、旧类型消失、方向计数器重置为弱跳转，且同一 fetch block 的邻项 target/way 不变；改回条件后再次 not-taken 训练可生效 | 已有；补齐属性改写与计数器重置交叉，原 2/2 行覆盖未反映该需求 |
| BPU-MBTB-015 | P1 | 有效条件 entry 的反馈即使 `mispredict=0` 仍须更新方向计数器：正确 taken 从弱正到正饱和；经真实 not-taken 误预测转负后，正确 not-taken 继续老化至负饱和。同 align bank 邻项的方向、target、way 全程不变 | 已有；补齐“非误预测训练 × 条件方向计数器”交叉 |
| BPU-MBTB-016 | P1 | 同一 FTQ 反馈包含同 align bank 的两个已驻留条件分支：较早分支正确 not-taken 后才能到达较晚分支，后者唯一误预测 not-taken；两项计数器同拍更新。随后较早正确 not-taken、较晚正确 taken 的反馈让两项再次同时更新并饱和，位置、way、target 不变 | 已有；补齐单分支 agent 无法表达的并行训练向量 |
| BPU-MBTB-017 | P1 | 两个不同 tag、同物理 set 和 align bank 的 FTQ 反馈在相邻接受周期到达，无空拍；两种先后顺序均须保留两个 entry，分别返回正确 target 且占不同 way。这检验 replacer 的同组前递，不等于 multi-hit 清理 | 已通过；此前每笔训练后均等待 6 周期，未覆盖连续反馈交接 |
| BPU-MBTB-018 | P1 | 相邻 16 字节对齐起点分别训练直接分支：前一起点应同时看见位置 5／13 的两个不同 align-bank entry；后一起点只看见后者重映射到位置 5；返回前一起点仍看见两个精确目标 | 已通过；补齐普通页内重叠窗口的地址轮转与位置高位映射 |
| BPU-MBTB-019 | P1 | 真实 cold metadata 分配原条目并排空 SRAM 写入，再训练另一个物理 set 使原 write-buffer shadow 退出；以原 cold metadata 和不同 target 重放，暂缓 S2 清理时必须在公开预测及 metadata 中同时看到两个同位置 way。恢复清理后只保留低 way，另一 set 的 entry 不变 | 已通过；四个输出断言后功能 bin 闭合；补齐此前 2/2 RTL 行、4/4 分支无法证明的同位置 multi-hit 检测与 flush |
| BPU-MBTB-020 | P1 | 四物理 bank、双目标 way、双向更新及 set 1/2、31/32 上下文；24 笔同 bank 哨兵预测期间相邻送入两个目标的真实反馈，要求队列保留两项、有序写回；跨 bank 哨兵对照必须直通。独立输入、队列端口/占用与全 resident 正反顺序流水线回读保持相反 way 和两个哨兵 | 已通过完整回归；64 组合、192 个 phase cross bin、51 项纯检查和四个普通 FAIL 负对照；关闭 11 原生行。该阶段剩余 205 行，不声称 overflow/entry-buffer 参考 |
| BPU-MBTB-021 | P1 | 低/高 set、四 bank、两 way 的同 key 间接分支命中，24 笔哨兵预测期间相邻两笔真实反馈改写目标；阻塞时只写回最新目标，跨 bank 直通时两笔有序写回。交叉 Fit→Overflow、Overflow→Underflow、Underflow→Fit，检查 carry、完整目标、请求/写回节拍及所有 counter/邻项保持 | 已通过完整回归；96 组合、288 个 phase cross bin、93 项纯检查和五个普通 FAIL 负对照；关闭六原生行。该阶段剩余 199 行，不声称满 dirty 覆写、跨 row/way 迁移、flush 或完整 FTQ 参考 |
| BPU-MBTB-022 | P1 | 两个不同 set/tag 的真实间接 hit 反馈在 24 笔哨兵预测期间相邻提交；交叉低/高 set、四 bank、双 way、两种输入顺序及三种独立目标 region 配对。阻塞时两项均保留并按提交顺序写回，跨 bank 对照有序直通；完整目标、counter/metadata、相反 way 与两个哨兵保持 | 已通过完整回归；192 组合、576 个 phase cross bin、145 项纯检查和六个普通 FAIL 负对照；关闭 20 原生行。该阶段剩余 179 行，不声称 full-miss overflow、跨 way shadow 迁移、flush 或完整 FTQ 参考 |
| BPU-MBTB-023 | P1 | 分配前捕获真实 all-miss metadata，正常分配及正确 taken touch 后相邻重放；独立 LRU 选请求 way，命中 retained shadow 的写回必须留在原 owner。交叉低/高 set、四 bank、双 owner、clean-first/pending-second、阻塞/直通和三种 carry 转换，检查完整端口/节拍与初始 counter-2 居民的正反流水线回读 | 已通过完整回归；192 组合、576 个 phase/status cross bin、251 项纯检查和六个普通 FAIL 负对照；关闭 44 原生行。非弱条件邻项已有独立有序诊断 counter 3→2，未计 PASS/XFAIL；不推广为任意邻项、完整 FTQ、跨 row、flush 或 overflow 验证 |
| BPU-MBTB-024 | P1 | 目标 SRAM set 与 set+32 alias 共享 PC[9:4] 的替换状态，而邻接索引、另一 align bank 独立；真实 conditional taken/NT 反馈分别改变 counter 和 LRU 资格，读取不触碰；独立 LRU 选择 victim，新分配重置 counter，全部 profile 正反流水线回读保持 | 已通过完整回归；1024 组合、6144 个 phase cross bin、112 项纯检查和七个普通 FAIL 负对照；关闭全部 53 个剩余 ReplacerState 行。该阶段仍缺 82 个 WriteBuffer 行，不声称 flush/overflow、stale-key shadow 或完整 FTQ 验证 |
| BPU-MBTB-025 | P1 | 读压力真实填充双 key 的 depth 0/1；请求 way 跨 retained owner，entry 写回保留 owner、counter 独立初始化 request way，填充与改写 IO/节拍及双 key 正反完整 profile 回读正确 | 已通过完整回归；32 组合、96 个 phase cross bin、23 项纯检查、六个普通 FAIL 负对照；关闭 42 行，该阶段剩余 40 个 WriteBuffer 行。仅有界两 way/两 depth，不声称任意饱和邻项、flush/overflow 或完整 FTQ |
| BPU-MBTB-026 | P1 | 四物理 bank、training depth 0/1、dirty/clean 清理 shadow，交叉零 tag／非零 position、非零 tag／零 position、全非零 key；同拍训练另一 set，独立输入／两端口 payload／全 shadow 前后状态检查，双 set 完整 profile 正反流水线回读保持 | 正式通过 48 组合和 144 个 cross bin；21 项纯模型／scope 检查及八项普通 FAIL 负对照有效。完整审计 coverage-mbtb-cleanup-overlap-refresh-audit.json 确认最后 40 个映射行闭合，MainBTB 1056/1056。联合零 tag/position 错 owner 及更早偏移的邻项更新丢失仍为隔离诊断，不声称完整 FTQ 资格 |

## 5. TAGE

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-TAGE-001 | P0 | cold lookup 无 provider，并使用 base prediction | 已有 |
| BPU-TAGE-002 | P0 | mispredict 训练分配 provider | 已有 |
| BPU-TAGE-003 | P1 | taken counter 向 taken 收敛并饱和 | 已有 |
| BPU-TAGE-004 | P1 | taken counter 向 not-taken 收敛并饱和 | 已有 |
| BPU-TAGE-005 | P1 | 弱 provider 回退 base，强化后改选 provider | 已有 |
| BPU-TAGE-006 | P1 | provider 提供额外价值时 useful counter 更新 | 已有 |
| BPU-TAGE-007 | P2 | 其他 PC 查询不破坏原 PC provider/tag | 已有 |
| BPU-TAGE-008 | P1 | 最高历史表 provider 无更长表可分配时仍可双向训练计数器，且 provider 不丢失 | 已有 |
| BPU-TAGE-009 | P1 | 四张表同一索引的两个 way 均有 useful entry 时，新分支分配失败且原有 entry 保留 | 已有 |
| BPU-TAGE-010 | P1 | 连续分配失败使 8 位 useful-reset 计数器饱和；清零后新分支可分配，恰好替换一个旧 tag，其他 provider 保持 | 已有 |
| BPU-TAGE-011 | P0 | 相同 PC 的已训练位置与冷位置交错进入流水线时，provider 只对应已训练位置 | 已有 |
| BPU-TAGE-012 | P1 | 高置信度 base 与弱 provider 方向相反时，预测 metadata 的 `altConf=1`；正确结果训练后仍检查 provider counter 与 fallback 结果 | 已有 |
| BPU-TAGE-013 | P1 | 同一 selector 桶的两个弱 provider 中，只训练一方且不再分配；另一方 counter/way 不变，但预测从 base fallback 切换为 provider | 已有 |
| BPU-TAGE-014 | P1 | 同一 set 的有限分支流自然分配到四张 tagged table；各深度均以高置信度 base 回退开始，正确结果训练后 provider counter 4→3→2 且 entry 不丢失；逐用例命中奇数 selector 更新臂 1/3/5 | 已有 |
| BPU-TAGE-015 | P0 | 全局关闭时同一 cold metadata 的训练不能分配 provider，开启后相同训练可以分配；再次关闭时预测端隐藏 provider，恢复后原 table/way 仍在 | 已有 |
| BPU-TAGE-016 | P1 | 直接／间接跳转即使因目标错误而误预测，也不能给 TAGE 分配 provider；已有条件 provider 时，同 PC/位置的非条件反馈不改动 table、way、counter，而合格条件反馈可继续训练计数器 | 已有；补齐原 agent 硬编码条件类型所遮蔽的训练资格门控 |
| BPU-TAGE-017 | P1 | 同一笔 FTQ 反馈中，较早正确 not-taken 条件分支与较晚正确 taken 条件分支隔一个空槽；两者各有 MainBTB 命中及独立 TAGE metadata，两个 provider counter 同拍朝相反方向更新，第二笔还能分别继续更新 | 已有；agent 绑定完整训练分支向量和 TAGE metadata 向量 |
| BPU-TAGE-018 | P1 | 有效条件分支若在 MainBTB 训练 metadata 中没有匹配的 rawHit/position，冷态不得分配，已有 provider 不得更新；同笔反馈中较早 miss 也不能挡住较晚匹配分支更新 | 已有；agent 训练事务显式表达 MainBTB hit/miss |
| BPU-TAGE-019 | P1 | MainBTB 四路预测的非 0 slot 可独立分配 TAGE provider：第 1／2／3 路轮流作为较晚条件位置，中间允许空槽；连续异质向量需保持每路 provider、方向、metadata、SC counter valid 与 S2 baseConf 关联 | 已有；S1 positions 和 S2 result/baseConf 分阶段驱动，保留单路 API，五格断言后采样 |
| BPU-TAGE-020 | P1 | 同一 FTQ 反馈中，较早实际不跳转与较晚实际跳转的条件分支分别命中同表不同 way，两个弱 provider 均与各自高置信度 base 相反；两路正确 base 反馈应使共享 `useAltOnNa` selector 一拍增加两步，同时独立更新两个 provider counter。随后用两次反向反馈仍不越过选择阈值、第三次才切回 provider，区分漏计、只计一路和多计一路 | 已有；六格功能覆盖在 provider/选择结果断言后采样 |
| BPU-TAGE-021 | P1 | 同一 FTQ 反馈中较早不跳转、较晚跳转的两个条件分支命中同表不同 way、同一 `useAltOnNa` 桶：前者弱 provider 错而 base 对，后者弱 provider 对而 base 错。正负两票须在本拍抵消，但两个 provider counter 各自更新；恢复弱态后仍回退 base，再给一票反向反馈才切换 provider | 已有；与 TAGE-020 共用真实分配辅助函数，四格功能覆盖在断言后采样 |
| BPU-TAGE-022 | P1 | resident tagged provider 的计数器为 5 时，相邻八拍合格正确 taken 反馈须经写缓冲转发将其饱和到 7，且 table/way 与 taken 预测保持 | 已有；provider-only 正确反馈不读 SRAM，不证明不同索引同时 pending；历史 TAGE 全 RTL 行点 38/132→55/132 |
| BPU-TAGE-023 | P1 | 同 bank、同最高 table/way 的四个不同索引接收相反方向的真实误预测反馈，32 拍连续训练后原 provider counter 各自达到 0/7；单独重训第一项仅使其变成 1，其他三项保持 | 已有；四项不超 buffer 容量，复位串行作对照，24 格 cross 在断言后闭合；原生行 5208/5653→5224/5653 |
| BPU-TAGE-024 | P1 | 四个同 bank 索引都先占满四表两 way；最高表的较早分支实际不跳、较晚分支实际跳，一拍只含一个真实误预测却更新两个写端口。32 拍连续训练后 pipeline 回读要求原 counter 0/7、后分支 useful 增加、前分支 useful 保持，其他六个分支 tag 完整保留；单独重训第一项只使其 counter 变成 1 | 已通过；复位串行对照比较 counter／方向，不要求 useful 逐拍串行等效；48 格 cross 断言后闭合；漏 way、漏第四索引、损坏 useful 条件三负对照均检出；原生行 5224/5653→5336/5653；每端口四个不同 key 不超 entry-buffer 容量，不承诺 useful 队列保留全部重复 beat |
| BPU-TAGE-025 | P1 | 四个同 bank 索引 × 最高表 way 0→1／1→0：真实 strong provider 被弱化并合法替换，原 tag 重分配至另一 way；用新鲜 metadata 正确反馈后，原 counter 4→5、useful 0→1，无关 tag counter 7／useful 3 和其他六邻项完整保持；重复正反顺序流水线读回仍一致 | 已通过；120/120 cross bin 断言后闭合，被动 monitor 核对实际反馈身份／metadata，捕获后无 reset，七拍有效反馈；不改 RTL，原生行计数未增加 |
| BPU-TAGE-026 | P1 | 相同四索引／双向迁移，重放原 tag 的真实捕获 strong metadata；原 counter 更新仍需与 tag 关联，迟到 useful 更新允许丢弃或重定向，但必须保留旧物理 way 上无关 tag 的 useful 与全部其他状态 | 已复现 strict XFAIL；八例原 counter 均 4→5，却使无关 tag useful 3→1（counter 保持 7），两次读回共 16 项失败，104/120 cross bin 命中且保留 16 个失败 bin；仅特定异常触发 XFAIL，错 metadata／丢反馈／串行读回三负对照均普通 FAIL；只证明单模块反馈契约，不宣称集成 FTQ 调度可达 |
| BPU-TAGE-027 | P1 | 八个 resolve 槽 × 双向 × 四 provider 深度，逐项检查真实分配、强化、近饱和、饱和及保持的 taken/useful counter、身份与全部先前 resident；独立输入检查稀疏槽位和完整真实 metadata，流水线回读保持接受／完成节拍 | 已通过完整回归；320 个 cross bin 闭合，21 项纯语义测试支撑输入契约；漏 slot7、压缩槽位、错 provider 参考均普通 ScoreboardMismatch；与 028 合计关闭 20 原生行、增加 92 branch hit，原生分母及 v_line 不变；不宣称精确 alternate 写回或全程序 FTQ 轨迹 |
| BPU-TAGE-028 | P1 | 每个 resolve 槽检查 MBTB miss、direct、indirect、inactive 和 disable 不更新真实 highest provider；合格目标须穿过 unmatched／非条件邻项正确关联预测 metadata 并更新，邻项保持 | 已通过完整回归；56 个 cross bin 闭合，输入预期不复用 encoder、驱动前冻结；交换 metadata 普通 ScoreboardMismatch，完整输出由异步 prediction Scoreboard 检查；resolve 槽不等同扁平 MBTB/metadata 槽 |
| BPU-TAGE-029 | P1 | 正常分配准备真实 table2 alternate／table3 provider；双向、四预测槽、两 baseConf 的十四阶段检查 alternate 更新／保持、provider-only、上下饱和、弱区、selector 再进入、跨方向及资格门控；两表 way 身份、counter、useful 与完整 metadata 必须精确关联 | 已通过完整回归；224 个 cross bin 断言后闭合，独立配对模型在驱动前冻结，原 prediction monitor 同事件捕获只读内部 Bundle；与 030 合计关闭四顶层行、增加十 branch hit，v_line 和分母不变；不宣称完整分配／aging／FTQ 模型 |
| BPU-TAGE-030 | P1 | 相反方向的既有 resident 与 alternate/provider 配对目标混合于预测槽 0 和后部槽 1/2/3；正反顺序先提交多笔再统一 drain，完整状态与接受间距／完成延迟不得错配，退出状态观测后恢复基本 monitor | 已通过完整回归；12 个 cross bin 闭合；保持错误 alternate、交换 way、使用上一事件内部状态、漏后部反馈四负对照均带事务／差异／状态普通失败，无额外 teardown／悬空任务异常；三项清理纯测试检查 owned failure、独立错误与取消 |
| BPU-TAGE-031 | P1 | 四个同 bank 索引 × 双最高表 way × counter 1/2：较早 not-taken provider 更新与较晚 cold tag 分配须在同一事件写两个端口，精确核对 bank/set/tag/counter/outcome 和四周期延迟；旧 victim 消失、六邻项保持，全状态正反顺序流水线回读 | 已通过完整回归；48 cross bin；独立写活动参考在提交前冻结，完整全 bank 被动 Bundle/Monitor 区分同时双写和两拍串行写；与 032 合计关闭六个原生行 |
| BPU-TAGE-032 | P1 | 同一混合 hit/allocation 在 counter 已饱和、早槽无 MainBTB 命中、早槽无效及全局关闭时，只允许新 tag 单写或完全零写；省写不得伪装为双端口活动，目标和全部无关 resident 保持 | 已通过完整回归；96 cross bin；与 031 共 23 项纯模型／能力／清理测试、四个普通 FAIL 负对照；WriteBuffer 尚余 246 原生行，不以局部矩阵宣称全部 shadow/FTQ 已验证 |
| BPU-TAGE-033 | P1 | 四上下文 × 双最高表 way × counter 1/2：两笔 genuine 旧快照下，相邻混合反馈必须转发并在 0 饱和；间隔反馈必须重新读 SRAM、正确再次递减或省写。逐事件完整写 payload/延迟、输入节拍、两 victim 消失、六邻项及恢复阶段原 baseline 均保持 | 已通过完整回归；96 cross bin、26 项纯检查和四个普通 FAIL 负对照；关闭 WriteBuffer 844/845/888，完整输入和写活动参考在驱动前冻结；不宣称全 FTQ／shadow 容量模型 |
| BPU-TAGE-034 | P1 | 四 bank × 双向 owner × depth 0–3 × pending/clean：真实旧 way metadata 经迁移后反馈，retained counter 从 5→6→7 并保持，而请求 counter 始终为 6；逐周期完整 shadow、输入／全写端口及正反流水线完整居民状态检查 | 已正式通过；64 组合、192 个 phase cross bin、3360 个 shadow 周期，117 项纯检查及八个有上下文的普通 FAIL 负对照通过。全仓 1401 PASS/6 XFAIL/0 SKIP 审计完成，正式关闭 53 行；不声称 FTQ 资格或 useful 缺陷修复 |
| BPU-TAGE-035 | P1 | 四 bank × depth0–3 × 八种双写状态：普通/交叉 owner 的 pending/clean、port0 miss × companion dirty/clean hit、port0 hit 或饱和 hit × companion 首次 miss；同一 prestate 独立解析两写，检查上下界饱和、miss 初始化、完整输入及 shadow、正反流水线居民状态 | 已正式通过；509 项纯检查、八模式 depth3 硬件代表和十项有上下文的普通 FAIL 负对照通过。128 组合、384 个 phase cross bin 的完整隔离矩阵和独立增量审计已通过；全仓 1911 PASS/6 XFAIL/0 SKIP 审计完成，正式关闭 70 行；不声称 FTQ 或碰撞/full-row PLRU |

## 6. Statistical Corrector

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-SC-001 | P0 | provider invalid 时 SC 不覆盖 TAGE | 已有 |
| BPU-SC-002 | P0 | 累积分数越过阈值后 used 生效 | 已有 |
| BPU-SC-003 | P1 | taken 方向训练收敛 | 已有 |
| BPU-SC-004 | P1 | not-taken 方向训练收敛 | 已有 |
| BPU-SC-005 | P1 | SC counter 饱和且不回绕 | 已有 |
| BPU-SC-006 | P2 | PC/position index 之间互不污染 | 已有 |
| BPU-SC-007 | P1 | 已训练 SC 在 MBTB miss 时不使用校正，恢复有效条件分支后仍可使用 | 已有 |
| BPU-SC-008 | P1 | 已训练 SC 在 MBTB 命中非条件分支时不使用校正，恢复条件分支后仍可使用 | 已有 |
| BPU-SC-009 | P0 | MBTB 有效性、provider 有效性和分支类型交错进入 SC 流水线时，S2 的 used 判定与次周期注册 metadata 都逐笔对应 | 已有 |
| BPU-SC-010 | P0 | 全局关闭后已训练的 SC 不参与预测，关闭期间的反向训练不起作用；重新开启后原方向仍在，同一训练 payload 在启用状态下可改变方向 | 已有 |
| BPU-SC-011 | P1 | 已学成 not-taken 的 SC 分别接收三类 taken 反馈：MBTB 无命中、非条件分支、TAGE provider metadata 无效；每类反馈都不应改动校正状态，随后同一位置的合格条件反馈须能重新学成 taken | 已有；补齐预测资格检查之外的训练资格门控矩阵 |
| BPU-SC-012 | P1 | 已学成的条件分支轮流放在 MainBTB slot 1/2/3，较早直接分支和空槽不得使用 SC；相邻周期交错的 provider 有效/无效向量需保持各路 SC 方向、use 位与次周期注册 metadata 对齐 | 已有；多阶段 driver 提交四路 S2 事务，monitor 返回完整向量，五格断言后采样 |
| BPU-SC-013 | P1 | 同一 FTQ 反馈中，resolved slot 0 的条件分支未 taken、隔空槽后的 slot 2 条件分支 taken；它们分别关联 MainBTB 预测 slot 1/3 的 metadata，在一笔训练中独立学成相反 SC 方向 | 已有；batch 事务驱动完整 resolve 向量与四路 MainBTB meta，对两路收敛断言后采样 |
| BPU-SC-014 | P1 | 同一 fetch block 的两个条件位置落到相同 SC way、但占不同 MainBTB 预测槽；冷态下较早分支 not-taken、较晚分支 taken 的同拍合格反馈必须按 way 汇总增减并相互抵消，单分支对照仍能学成校正且两个预测槽都看到该共享 way | 已有；64 笔取消反馈逐笔检查方向/use，随后单分支学习作正对照，四格断言后采样 |
| BPU-SC-015 | P1 | 同一 SC way 的两个条件位置都 not-taken 时，同拍反馈应聚合两次减向更新；从相同冷态开始，双分支反馈比只训练较早分支用更少训练拍学成 not-taken，两个预测槽都看到同一校正 | 已有；第三次复位重复单分支学习拍数，排除残留状态，四格断言后采样 |
| BPU-SC-016 | P1 | 相邻八拍交替反馈同 fetch block 中不同 SC way 的两个条件位置，pending 写缓冲合并后两路均应最终学成 not-taken | 已有；agent 封装连续反馈，复位后以串行反馈作正对照；SC `.v/.sv` 行点 25/33→27/33，不要求与串行等速收敛 |
| BPU-SC-017 | P1 | 同 bank 四个不同索引以相邻反馈学习交替的 not-taken/taken 校正；五类表的公开索引 metadata 与各 PC 保持关联，排空后四项均使用各自方向的 SC | 已有；不超 buffer 容量，复位串行作对照，不要求逐拍等效；12 格 cross 闭合；原生行 2052/3068→2568/3068 |
| BPU-SC-018 | P1 | 四个 pending 索引分别使用 counter 0/7/3/4 对应的四种真实 bias selector；positions 4/5/6/7 覆盖四 way，逐 way 连续反馈后既有学习状态和未选冷态邻 way 均须保留，流水线回读关联与复位串行各阶段对照 | 已通过；48+16 个 cross bin 闭合；漏 way、漏第四 row、错写邻 way 三负对照均检出；原生行 2568/3068→2642/3068 |
| BPU-SC-019 | P1 | 四个 pending PC 行各自交叉四 bias selector／四 base way：逐 selector 训练全部为负，再只将 row／selector 棋盘格两 way 反转为正，所有未选 way／selector 均保持；用公开 bias 方向 metadata 隔离共享非 bias 总和的影响，核对五类索引、provider、SC decision/meta 和流水线时间；feedback monitor 验证实际身份与相邻／复位串行节拍 | 已通过完整回归；1280 个 cross bin 断言后闭合；漏 selector 即使总 SC 仍正确也被 bias 断言检出，错 selector／串行化也普通 FAIL。原生行 2642/3068→2724/3068，新增 dirty 45／clean 37 行；该阶段剩余原始 344 行保留分母，不承诺精确 signed counter 或逐拍串行等效 |
| BPU-SC-020 | P1 | 四行分别用相邻／复位串行准备到真实 taken/used 全 1，排空更新并回读后用捕获正向 metadata 间隔式逐 way 反向重激活；全部未选 way／selector 保持，再用真实负向 metadata 恢复每行棋盘格两 way；流水线读回核对身份、时间与重复 snapshot，feedback monitor 核对实际节拍 | 已通过完整回归；1024 个 cross bin 断言后闭合；漏第四行、错捕获预测、串行化准备三负对照均普通 FAIL。原生行 2724/3068→2732/3068，关闭八个 clean-shadow 赋值；剩余 336 原始行与复核的局部矛盾赋值一致并保留分母，不宣称精确 signed counter 饱和或全 SC 功能闭环 |
| BPU-SC-021 | P1 | 四-way 单步到 640/5040 后拒绝四次并向内恢复；每个 way 的四个不同同-way 条件位置到 642/5038，越界候选 638/5042 须保留旧值而非钳到边界；其余三-way 保持，完整向量逐笔与驱动前参考比较 | 已通过完整回归；两组各 24 个 cross bin 闭合；独立模型及 agent 内只读 Bundle/Monitor，testcase 无边沿或 VPI；错误饱和负对照普通 FAIL；关闭三个原生 threshold 行，保留 3481 行分母 |
| BPU-SC-022 | P1 | 四-way 检查 wrong-SC 资格、MBTB miss、非条件、provider invalid、关闭、真实高置信度一致正确反馈、同-way 净零／净正／净负及四笔相邻反馈；比较完整向量、资格槽位、增减数和真实 beat 节拍 | 已通过完整回归；40 个 cross bin 闭合；漏 way3／漏后续分支负对照普通 FAIL；40 项纯模型及三项能力错误测试通过；分支增至 875/1038，其他九 DUT 指标及六项 XFAIL 不变，不以预测方向代替阈值状态 |

## 7. ITTAGE

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-ITTAGE-001 | P0 | cold miss 提供合法 allocate metadata | 已有 |
| BPU-ITTAGE-002 | P0 | 首次训练分配 target provider 并命中 | 已有 |
| BPU-ITTAGE-003 | P1 | provider target 更新及 confidence 变化 | 已有 |
| BPU-ITTAGE-004 | P0 | enable gate 禁止有效命中 | 已有 |
| BPU-ITTAGE-005 | P1 | provider 失去置信度后选择 alternate target | 已有 |
| BPU-ITTAGE-006 | P2 | 背靠背请求在接受事件后三周期采样并正确关联（含驱动 launch 共四周期） | 已有 |
| BPU-ITTAGE-007 | P1 | primary 置信度降至 0 且 alternate 有效后继续训练，alternate target 保持正确 | 已有 |
| BPU-ITTAGE-008 | P1 | 基于真实 metadata 持续误预测至 allocate 无候选并使 8 位 tick 达到正饱和；useful 衰老启动后 provider/target 不丢失 | 已有 |
| BPU-ITTAGE-009 | P1 | 相同 PC 在零／非零折叠路径历史下分别分配不同 target；交替查询时各自命中，不发生索引或 tag 混淆 | 已有 |
| BPU-ITTAGE-010 | P1 | 训练分支位于非 0 slot 时，选择唯一有效的间接跳转并写入该 slot 的 target | 已有 |
| BPU-ITTAGE-011 | P0 | 全局关闭时使用同一 cold metadata 的训练不能分配 provider，开启后相同训练可分配；关闭查询隐藏命中，重新开启仍返回原 target | 已有 |
| BPU-ITTAGE-012 | P1 | 训练反馈必须 valid、taken、间接、且无 RAS pop 才允许进入 ITTAGE：invalid、未 taken、条件／直接分支、return、return-and-call 不得分配或改写 provider；普通间接跳转及间接调用可以分配 | 已有；补齐训练资格门控矩阵 |
| BPU-ITTAGE-013 | P1 | 同一笔 FTQ 反馈里四个较早有效条件分支均 not-taken、较晚有效间接跳转 taken 时，ITTAGE 必须选后者目标；两条件分支落空后较晚间接调用 taken 也可分配。仅有不合格 return 的向量保持 cold，随后合格向量可以分配 | 已有；补齐多有效 slot 的筛选与优先级 |
| BPU-ITTAGE-014 | P1 | 同一 PC 在三种折叠路径历史下，分别学习低 20 位完全相同、却位于 PC 同区、上邻 1 MiB 区及下邻 1 MiB 区的三个目标；每个 context 必须冷态分配并精确回读完整 target/metadata，随后交错查询仍不能串用 region 指针或历史 tag | 已有；ITTAGE-017 修正 byte／Pc.addr 编解码后才真正满足上述物理区域边界；四格覆盖在断言后采样 |
| BPU-ITTAGE-015 | P1 | 16 个不同非 PC region 目标低位相同，逐项插入后全部旧指针仍正确；满表复用已有 region 的相邻 folded-SRAM lane 不破坏驻留目标，反序交错预测仍逐笔关联 | 已通过；48 个 phase × region cross bin；不要求第 17 个新 region 无损 |
| BPU-ITTAGE-016 | P1 | 两个 SRAM bank 分别交叉首表强化／最高表零置信目标改写；八拍连续反馈重复访问四个不同索引，与 16 笔流水线读真实重叠；pending 读、排空和逐项 clean-shadow 更新均检查邻项隔离，复位串行对照 | 已通过；96 个 phase × mode × bank × context cross bin；串行化和丢第四 PC 反馈的负对照均被检出 |
| BPU-ITTAGE-017 | P0 | transaction PC／target 使用字节地址；输入及两项 provider target metadata 正确编码 Pc.addr，输出均解码回字节；拒绝负数／未对齐地址，整个 burst 驱动前验证避免后续非法 beat 部分提交 | 已通过；codec、monitor、encoder 独立断言；回退 identity 编解码的负对照失败 |
| BPU-ITTAGE-018 | P1 | 满 16-region 表后分别通过真实分配复用 region 0／15，连续插入两个不同的新 region；独立 PLRU 模型预测 victim，流水线回读核对旧 victim 指针以原 offset 解码新 region、所有其他 resident 的 target／provider／置信状态保持，预测读不改变替换策略 | 已通过；八个 touch × step × observation cross bin；关闭两个原生行，三个参考负对照被异步 Scoreboard 检出；不要求超容量无损 |

## 8. RAS

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-RAS-001 | P0 | reset 后空栈状态确定 | 已有 |
| BPU-RAS-002 | P0 | call push 生成正确 return address | 已有 |
| BPU-RAS-003 | P0 | return pop 严格 LIFO | 已有 |
| BPU-RAS-004 | P1 | 连续相同地址使用重复计数并正确弹出 | 已有 |
| BPU-RAS-005 | P1 | 空栈 pop/underflow 不破坏状态 | 已有 |
| BPU-RAS-006 | P2 | speculative queue near-overflow guard | 已有 |
| BPU-RAS-007 | P0 | redirect metadata 精确恢复栈状态 | 已有 |
| BPU-RAS-008 | P0 | disable gate 不改变栈 | strict XFAIL：top 保持但指针元数据仍更新；独立 `enable_integrity` 功能组仅 `top_preserved` 命中，`metadata_preserved` 保留未命中。汇总操作组只采样经断言的 `disabled_top_held`，不代表完整门控通过 |
| BPU-RAS-009 | P1 | 三层不同返回地址的调用链在 redirect 回滚到中间层后，连续 return 依次得到较老调用的返回地址和初始空栈 top | 已有 |
| BPU-RAS-010 | P1 | speculative queue 逼近溢出后，连续被门控的 push 与 pop 都不能改变栈顶及完整 redirect metadata；回滚到较早调用帧释放容量后，新的 push/pop 必须恢复工作且旧栈顶保留 | 已通过；五个阶段的功能 bin 在断言后闭合；RAS RTL 行点仍为 2/2、分支仍为 6/6，与仅观察栈顶的 RAS-006 和浅层回滚的 RAS-007 不同 |

RAS 原生行覆盖缺口另驱动补充了两个提交侧功能点：

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-RAS-011 | P0 | 三层不同地址调用被提交后，跨越一轮推测队列容量的临时提交 call/return 不得丢失旧帧；最后逐层恢复旧返回地址与初始空栈 | 完整回归通过；七格功能 bin 在断言后采样；保持时序但禁用提交的负对照能被检出 |
| BPU-RAS-012 | P1 | 3 次正常重复及 9 次超过三位计数上限的同返回地址提交，在推测队列复用后逐次返回；饱和后必须分帧，不能计数回绕或丢失调用 | 完整回归通过；六格功能 bin 在断言后采样；跳过重复 call 提交的负对照能被检出；两项场景共同使 RAS 原生行覆盖 457/563→503/563 |
| BPU-RAS-013 | P1 | 八个 committed SSP × 普通/饱和 repeat，跨推测队列复用和逐层退栈；有界独立模型保留已弹出物理格的存储值，被动观测每拍完整输入、八格地址/counter、head 与公开状态 | 已登记，仓库实际代码隔离通过 16 组合；待完整全仓刷新，不先计正式 PASS |
| BPU-RAS-014 | P1 | 无空拍相邻 speculative push/pop，depth 1–4、不同/重复地址、嵌套/交替/转向及 9/10/12 次饱和重复；同时检查逐拍观测和 act_many 有序返回数组 | 已登记，27 个场景 bin 隔离通过；单轴使用 coverpoint 而非虚构 cross；待正式刷新 |
| BPU-RAS-015 | P1 | 真实 inflight/committed checkpoint × SCTR 0/3/7 × 同地址 call/正负地址 call/return，先制造 wrong-path 再恢复重做并完整退栈 | 已登记，24 组合隔离通过；cfiPc 保留符号位，只去掉固定对齐位；待正式刷新 |

三项的实际仓库测试共 170 PASS（167 项纯模型/能力/缺 bin 检查及三项硬件
入口），6700 个观测周期、36339 项比较与独立重放证据一致；25 项错误注入
均触发带请求/观测时刻/状态的普通失败，旧用例保持 15 PASS/1 原 strict XFAIL。
冻结正式 raw 与三个正向 raw 的隔离合并恰关闭 45 行至候选 565/585，
不增加新缺口、不扣分母。见 `results/coverage-progress-ras-state-scenarios.json`。
当前正式基线仍 255 个功能点、RAS 520/585；计划增加到 258 点不表示已经正式
执行通过。剩余四个 bos 行需要真实非 push 提交与 FTQ 资格，不能伪造 actionNone
提交补覆盖；组合 action3 语义、完整 FTQ 路径和原 disable 缺陷仍未闭合。

## 9. MicroRAS

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-URAS-001 | P0 | main RAS 输入可初始化 speculative top | 已有 |
| BPU-URAS-002 | P0 | s1 push/pop 更新 usable 与 top | 已有 |
| BPU-URAS-003 | P1 | s2 override 的 push/pop 优先级 | 已有 |
| BPU-URAS-004 | P1 | s3 override 的 push/pop 优先级 | 已有 |
| BPU-URAS-005 | P1 | s1/s2/s3 同周期有效时的优先级 | 已有 |
| BPU-URAS-006 | P0 | redirect 后 invalid bubble 与恢复周期 | 已有 |
| BPU-URAS-007 | P2 | position/地址边界的 return address 计算 | 已有 |
| BPU-URAS-008 | P1 | 无 override 的 S1→S2→S3 正常推进：s2_fire 迁移 pending push，s3_fire 清除后回到 main RAS top | 已有 |
| BPU-URAS-009 | P1 | 中性 S2 override 不应遮蔽较老 S3 中待处理的 push | 已有 |
| BPU-URAS-010 | P1 | S2 override pop 在较老 S3 有 push 时与其配对，和没有 S3 push 时的 invalid 结果形成对照 | 已有 |
| BPU-URAS-011 | P1 | 相邻周期的普通 S1 pop→中性 S1 与较老 S3 push 配对：pending S2 pop 选 main RAS top，消退后回到 S3 return address | 已有 |
| BPU-URAS-012 | P1 | 较老的 S3 pending pop 遇到中性 S1 或中性 S2 override 时都使预测无效；S3 fire 清除后 main RAS top 重新可用 | 已有 |
| BPU-URAS-013 | P1 | 较新的 S2 pending push 优先于较老的 S3 pending pop；S2 消退后 S3 pop 再次使预测无效，S3 清除后恢复 | 已有 |
| BPU-URAS-014 | P1 | S1 pop／中性操作分别与 S2 pending push／pop 构成 2×2 相邻周期对照；验证配对后的返回地址、有效性及下一周期状态 | 已有 |
| BPU-URAS-015 | P1 | 中性 S2/S3 修正选当前主 RAS 新地址而非旧 top／call，取消年轻 call 且优先于同时到来的年轻输入；redirect 优先于修正，随后 S2 保留一拍恢复 invalid、S3 直接选主 RAS；撤回修正后被取消 call 不得重现 | 已通过；十个 stage × phase cross bin；关闭两个原生行，丢 S2／丢 S3／旧 main 地址三负对照均普通 FAIL；三个分支点仍需审查 |

## 10. MicroTAGE

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-UTAGE-001 | P0 | cold miss 和 allocate metadata 一致 | 已有 |
| BPU-UTAGE-002 | P0 | 首次训练分配后 lookup 命中 | 已有 |
| BPU-UTAGE-003 | P1 | taken counter 向 taken 收敛并饱和 | 已有 |
| BPU-UTAGE-004 | P1 | taken counter 向 not-taken 收敛并饱和 | 已有 |
| BPU-UTAGE-005 | P1 | miss 不产生 correction，meta 保留 base bias | 已有 |
| BPU-UTAGE-006 | P0 | back-to-back lookup 在接受事件后两周期采样并正确关联（含驱动 launch 共三周期） | 已有 |
| BPU-UTAGE-007 | P0 | prediction/training tag/index 宽度一致 | 缺陷 |
| BPU-UTAGE-008 | P1 | S2 override 在提前恢复周期复用 A2 预测，并按 overrideStartPc 重算 tag | 已有 |
| BPU-UTAGE-009 | P1 | S3 override 在提前恢复周期复用 A3 预测，并按 overrideStartPc 重算 tag | 已有 |
| BPU-UTAGE-010 | P1 | 相同 PC／position 在两种折叠路径历史下各自分配；训练其中一侧至 not-taken 不改变另一侧 taken 计数器 | 已有 |
| BPU-UTAGE-011 | P1 | 两表均不可分配时持续真实误预测至低表 useful tick 高位；同索引新分支 aging 前受阻、后分配至低表，原高表 provider 保留 | 已有 |
| BPU-UTAGE-012 | P0 | 全局关闭阻止延迟一拍的 fastTrain 分配；开启后同一训练可分配。关闭查询保持原输出而非强制 miss，恢复后另一折叠历史仍 miss、原历史仍 hit | 已有 |
| BPU-UTAGE-013 | P1 | AheadBTB 中较早条件分支与最终执行的分支位置／类型分离：同位置解析为直接／间接跳转时不产生伪条件校正；较晚直接／间接跳转在较早 base 正确 not-taken 时不分配，而在较早 base 错误 taken 时为较早条件位置分配 not-taken 修正 | 已有；训练事务显式携带最终分支类型，六格对照均检查输出 |
| BPU-UTAGE-014 | P1 | 同一查询包含四路 AheadBTB 输入：第 0 路较早条件分支保持 not-taken，第 1／2／3 路之一作为实际 taken 条件分支；检查空槽、位置及训练 metadata 对齐，训练后仅后续出错路命中 taken；再交错提交不同向量和折叠历史，逐笔核对结果关联 | 已有；agent 区分 A1 fastPositions 与 A2 result 的驱动阶段，标量兼容且五格断言后采样 |
| BPU-UTAGE-015 | P1 | 两表 × 四 bank × 八索引：同项连续反馈即时 bypass、全容量索引交错回绕；保留原 provider、counter 饱和、七个未选邻项与 history 关联，复位串行对照一致 | 已通过；被动 feedback monitor 检查拍数、PC／index 和相邻拍间距，流水线 readback 先提交八笔再配对；384 个 cross bin 在断言后闭合。串行化、丢一索引、错改最终位置三种负对照均检出 |
| BPU-UTAGE-016 | P1 | 完成 UTAGE-015 前提后用邻 bank 八个新索引完全替换 shadow，原 SRAM provider 的饱和 counter 必须仍在；新邻项保持弱态，两表／四 bank／两反馈模式全部检查 | strict XFAIL：完整 16-case 矩阵中 112/128 项丢失最后更新，低表 7→5、高表 0→2；前提或节拍错误仍普通 FAIL。384 个 cross bin 仅命中 272 个，失败 112 格保留未命中；VPI 只读诊断确认同槽 enqueue 的 dirty 被 cleanId 清理覆盖，不修改 RTL |
| BPU-UTAGE-017 | P1 | 四 bank 的低表 useful=1/2/3 与高表 useful=3，经恰好两轮全局 aging 后分别验证低表减一、高表右移：第一轮仅低强度项可重新分配，第二轮中等项先低后高、强项直接分配高表并保留原低表；每次操作后全网格回读检查邻项、counter、provider、position 和 history | 已通过完整回归；60 个 cross bin 断言后闭合，新增 4 个原生源码行。先用两次错误仍阻止分配、第三次才开放的硬前提证明高表 useful 更新。少一拍 tick、少一次低表强化、只破坏高表 useful 资格而保持 counter 更新，三负对照均普通 FAIL；原 SRAM 持久化缺陷不变 |
| BPU-UTAGE-018 | P1 | 四 bank × 较老历史 bit 6/7/8：相同 PC／position 与六位短历史共享低表，十二位长历史的不同索引保有相反高表 provider；分别饱和至 0/7，每次更新后全网格回读保持邻 bank、对侧历史和未训练 bit-11 高表上下文的低表 counter 4；正反顺序重叠预测核实 A0/A1 和完整 metadata | 已通过完整回归；144 个 cross bin 断言后闭合，新增 14 个原生行。编码器按 PHR 的真实窗口做 XOR 折叠，保留低四位旧行为并检查绑定位宽；截旧历史位／A1 错用当前历史两负对照均普通 FAIL。其他九个 DUT 汇总不变，已有 tag-width／SRAM 持久化缺陷不变 |
| BPU-UTAGE-019 | P1 | 四 bank × PHR bit 对 (0,9)/(1,10)/(2,11)：A/B 高表 hash 同索引而 tag／低表索引不同。先证明 useful=2/1 阻止替换，第二次高表错误才允许 B 替换 A；A 回退低表。B 饱和 7 后重放真实捕获 A counter-3 metadata 重建 A=4，再重放 B counter-7 metadata 重建 B=6；所有阶段流水线回读 A/B/邻项及完整 history／时间关联，相邻和复位串行反馈由 monitor 核验 | 已通过完整回归；720 个 cross bin 断言后闭合，新增 5 个原生 useful 行。错 snapshot counter、错 tag、强制串行化三个负对照均普通 FAIL；八次低表写入不超过 shadow 容量，不作为替换后 SRAM 持久化证据，已知缺陷不变 |

## 11. 集成 BPU

| ID | P | 功能点 | 现状 |
| --- | --- | --- | --- |
| BPU-INT-001 | P0 | reset vector、SRAM 初始化和首个预测可达 | 已有 |
| BPU-INT-002 | P0 | cold prediction stream 默认不 taken | 已有 |
| BPU-INT-003 | P1 | prediction 背压期间保持 valid 与 payload；meta 为 RTL valid-only 通道 | 已有 |
| BPU-INT-004 | P0 | FTQ training 被接受并改变后续预测 | 已有 |
| BPU-INT-005 | P0 | redirect 后从指定目标 PC 重新开始预测 | 已有 |
| BPU-INT-006 | P0 | 全局 disable 时回退为不 taken | 已有 |
| BPU-INT-007 | P1 | s1 prediction 与两周期后 s3 meta 精确关联；S3 perf echo 的 PC、target、方向、位置及来源与同笔 S1 输出一致 | 已有 |
| BPU-INT-008 | P1 | direct call、indirect return 与 RAS s3 override 协作 | 已有 |
| BPU-INT-009 | P2 | 持续 prediction stream 与训练并发，monitor 不丢 transaction | 已有 |
| BPU-INT-010 | P1 | prediction 背压期间 redirect 冲刷旧预测，恢复 ready 后首先接受新 PC | 已有 |
| BPU-INT-011 | P1 | 单独关闭 S1 的 MicroBTB/AheadBTB 后，已训练的 MainBTB 命中应在 S2 修正原 miss，并返回对应 target | 已有 |
| BPU-INT-012 | P1 | 跨早级部分目标区域的向上／向下分支，关闭 MicroBTB/AheadBTB 后应由 MainBTB 在 S2 给出完整 target；两个方向独立回读 | 已有 |
| BPU-INT-013 | P1 | MicroBTB 作为唯一早级来源时，部分目标地址跨界造成的错误高位应由 BPU 后续阶段修正，不能沿截断目标继续取指 | 缺陷：S3 仅比较目标低位，未触发修正 |
| BPU-INT-014 | P1 | MicroBTB 保留旧间接目标而 MainBTB 更新为同区域新目标时，S1 可先返回旧目标，但 S3 必须发现低位差异并覆盖为新目标 | 已有；作为 BPU-INT-013 的低位对照 |
| BPU-INT-015 | P1 | 关闭 S1 预测器时 MainBTB 在 S2 修正自循环分支；仅开启 AheadBTB 后，S3 fastTrain 及写回使同一分支提前在 S1 命中；再次关闭 AheadBTB 后回到 S2 修正 | 已有 |
| BPU-INT-016 | P1 | MicroBTB 先学目标 A，关闭 MicroBTB 后 MainBTB/AheadBTB 学不同目标 B；再次只开启 MicroBTB 时原目标 A 仍在，三阶段均核对公开的 S1 来源回显 | 已有；不代表双有效仲裁已验证 |
| BPU-INT-017 | P1 | 同一 S0 请求上 MicroBTB 与 AheadBTB 均有效且保留不同目标时，S1 必须选择 AheadBTB；先用 metadata 确认 AheadBTB 条目有效，再在双使能的新 S0 查询后背压保持同一 S1，关闭 AheadBTB 后应从目标 B 切换到 MicroBTB 保留的目标 A | 已有；同一背压 S1 的双源优先级已断言，三格功能覆盖闭合 |
| BPU-INT-018 | P1 | AheadBTB 已产生错误高位的跨 4 MiB S1 命中时，后续 BPU 阶段须以 MainBTB 完整 target 修正；必须先证明 ABTB 来源及局部 wrap，再判定 S2/S3 输出 | 缺陷／strict XFAIL：双分支循环使 MainBTB 双向完整目标先通过，真实 ABTB 返回方向 S1 却将 `0x407fffe0` 包装成 `0x40bfffe0`，同笔来源回显为 ABTB；低 22 位相同而后级未修正 |
| BPU-INT-019 | P1 | 已确认 ABTB 来源的 S1 自循环旧目标；背压停止读取后把 MainBTB 间接目标更新至跨 4 MiB 区域，恢复时同拍 S3 override 与 metadata 来源回显应给出完整新目标和 ABTB 旧目标 | 已有；证明低位差异的 S3 修正，作为 BPU-INT-018 仅高位差异 strict XFAIL 的对照 |
| BPU-INT-020 | P1 | 集成 FTQ 同笔反馈在 resolved slot 0/2 放入较早正确 not-taken 条件分支与较晚 taken 误预测，中间留空槽；MainBTB 的两个计数器须分别 2→1 并分配为 2，再在无误预测反馈中 1→0、2→3，同时 S2 返回较晚分支的目标 | 已有；完整训练向量经 BPU 转发，公开 resolve metadata 与 S2 target 断言后采样 |
| BPU-INT-021 | P1 | 集成 FTQ 对两个不同 TAGE provider 的逐分支反馈：先建立两个 MainBTB 条目和各自的 TAGE provider，确认公开 metadata 按 MainBTB raw-hit 位置配对且 table/way 不同；同笔 slot 0/2 正确 not-taken 反馈后，两 provider 计数分别 2→1、3→2，MainBTB 计数同时 0/1→0/0 | 已有；有界无预测读取训练窗口释放 tagged SRAM bank，单 provider 正对照与双 provider 更新均在断言后采样 |
| BPU-INT-022 | P1 | 集成 FTQ 的双分支 SC 训练：先使两个条件位置各有有效 TAGE provider，按 MainBTB raw-hit 位置确认 SC metadata 资格；相同冷态下，重复仅第一分支的反馈只使第一路 `useScPred=1, scPred=0`，重复同笔 slot 0/2 反馈则两路均学成 not-taken，中间 slot 1 无效 | 已有；训练期间冻结 TAGE provider 状态以隔离 SC，两次复位初态及训练后 provider table/way/counter 均核对，四格覆盖在断言后采样 |
| BPU-INT-023 | P1 | 集成 FTQ 中位置 1/4 两条条件分支映射到同一个 SC way，且对应不同 TAGE provider、相同 provider 计数 2 和 bias 选择。相同冷态下，第一分支单独反馈 4 笔未越过 SC 使用阈值、累计 8 笔越过；slot 0/2 同笔双分支反馈 4 笔便使两槽同时使用 not-taken SC 校正 | 已有；每阶段确认 TAGE provider table/way/counter 不变，单分支正对照排除训练整体无效，五格覆盖在输出断言后采样 |
| BPU-INT-024 | P1 | 集成 FTQ 中共享 SC way 的较早位置 1 正确 not-taken、较晚位置 4 taken，两路反馈方向相反。相同 provider 资格下持续 64 笔同笔反馈，SC 方向与使用阈值保持冷态；随后单分支 8 笔可学成 not-taken。再次复位后先复现抵消，再把较晚分支改为 not-taken，同笔双分支 4 笔即学成 | 已有；每段均确认 TAGE provider table/way/counter 不变，单分支与同槽位双分支对照排除向量被忽略的伪通过，六格覆盖在断言后采样 |
| BPU-INT-025 | P1 | 集成 TAGE 与 SC 同时使能，连续 8 笔 slot 0/2 双 not-taken 反馈每次都使用上一笔新配对的 S1/S3 resolve metadata；两路 TAGE provider 在原 table/way 从 2→1→0 后饱和，SC 两槽始终具备有效 provider，并于第 7 笔起共同启用 not-taken 校正、第 8 笔保持 | 已有；每笔断言 metadata tick 晚于上笔、同笔 S1/S3 固定延迟、MainBTB 条目及逐位置 provider 身份与计数，五格覆盖在行为断言后采样；这是新 metadata 的串行闭环，不证明多笔反馈在流水线中重叠 |
| BPU-INT-026 | P1 | 集成 FTQ 从先后两次已配对的 S1/S3 快照各取一笔反馈，分别更新两个不同位置的 TAGE provider；两笔连续进入同一训练通道，不等待前笔写回 | 已有；driver 先提交两笔、返回的接受 tick 相差一个完整周期，回读确认原 table/way 中 provider 计数 2/3→1/2，MainBTB 对应计数 0/1→0/0；同 PC/历史场景，不宣称已覆盖不同 PC/历史交错或训练与预测同时活跃 |
| BPU-INT-027 | P1 | 集成 FTQ 从两个不同 PC 的已配对 S1/S3 快照连续提交反馈：第一条件分支 not-taken，第二 taken；保持 prediction ready，monitor 必须在两笔训练接受窗口中实际观察到预测接受事件 | 已有；两笔训练接受相隔一个周期，两个 PC 的原 MainBTB 位置分别从 counter 2→1 与 2→3；五格功能覆盖在断言后采样。证明跨 PC 的 MainBTB 反馈隔离及预测／训练并发，不外推到折叠历史不同的 TAGE provider 关联 |
| BPU-INT-028 | P1 | 同一 PC／条件位置从两条真实 redirect 路径得到不同 PHR metadata；第二上下文先证实无法命中第一上下文的 TAGE provider，再分配自身 provider。两笔不同历史的 S1/S3 resolve 快照在相邻周期反馈 | 已有；原上下文 provider counter 2、新上下文独立 provider counter 4，连续两个正确 not-taken 反馈后各自保持原 table/way、分别变为 1／3；MainBTB 仍为共享条目且计数 1→0。TAGE 分配使用运行中的 LFSR，第二 provider 的绝对 table 号不是功能不变量。五格功能覆盖在断言后采样；训练时有界暂停预测读取 |
| BPU-INT-029 | P1 | 复用同一 PC／位置、不同真实 PHR 历史的两个 TAGE provider；让另一 bank 的非条件自循环持续预测，同时连续提交两份历史反馈 | 已有；训练 PC 使用 TAGE bank 0，预测 PC 使用 bank 1；两笔反馈在相邻上升沿接受，prediction monitor 在对应两拍均收到 bank 1 自循环 PC，回读各自原 table/way 的 provider 计数分别 2→1／4→3。五格功能覆盖在断言后采样；仅证明跨 bank 并发 |
| BPU-INT-030 | P1 | 同 bank 的持续预测读取与需要 tagged SRAM 读取的条件反馈相撞时，训练必须保持 valid/payload 等待 `trainReady`，停止预测读取后只接受一次并生效 | 已有；在同 bank 非条件自循环的 8 周期预测窗口内，prediction monitor 连续观察到该 PC、训练 transfer 保持 pending；停止读取后才接受，回读 MainBTB 计数 1→2 和更长历史 TAGE provider 的分配。五格功能覆盖在断言后采样 |
| BPU-INT-031 | P1 | 同一 PC／位置的两个真实 PHR 历史反馈在同 bank 预测读取阻塞期间同时排队；解除冲突后相邻周期接受且分别更新正确的 TAGE 历史单元 | 已有；两笔 transfer 在持续预测的 8 周期窗口均保持 pending，释放后接受 tick 相差一个周期；第一历史分配更长历史表的 provider，第二历史原 provider 计数 4→5。六格功能覆盖在断言后采样；共享 MainBTB 的旧 metadata 计数不充当两笔接受的证明 |
| BPU-INT-032 | P1 | 集成 ITTAGE 通过真实 FTQ 反馈为非零位置的间接分支建立 provider；暂时关闭 ITTAGE 后只把 MainBTB 更新为不同目标，再恢复 ITTAGE，同一 redirect／历史上下文应在 S2 返回 MainBTB 新目标、在 S3 选择 ITTAGE 原目标 | 已有；公开 provider metadata、S2 目标与配对的 S3 override 逐项断言，四格功能覆盖在断言后采样；独立 ITTAGE 满行覆盖不能证明顶层目标选择优先级 |
| BPU-INT-033 | P1 | 两层 direct call 依次进入不同 PC，两个 indirect return 的 MainBTB 静态目标均故意错误；集成 RAS 必须在两笔各自配对的 S3 修正中依次给出内层、外层的不同返回地址 | 已有；训练时关闭 RAS 并选取不相互驱逐的 MainBTB 地址，运行时重新开启。分别断言两次 call 的 S2 目标、两次 return 的错误静态 S2 目标和 LIFO S3 目标，时间戳严格递增；六格功能覆盖在输出断言后采样 |

## 12. 覆盖率驱动的候选与结论

原 TAGE 奇数 selector 候选已由 `BPU-TAGE-013/014` 分拆成可观察的
跨 tag 选择变化和逐深度训练场景。AheadBTB 的 multi-hit 候选现已转为
`BPU-ABTB-028`：真实查询 metadata 被两次训练复用，输出先出现双命中，
释放单端口 bank 的读占用后恢复唯一命中；对应生成 RTL 分支也已命中。
MainBTB 的同位置 multi-hit 清理现由 `BPU-MBTB-019` 独立验证：先将原条目
写入 SRAM，再训练另一物理 set 替换同 way 的 write-buffer shadow，随后重放
原 cold metadata 并改变 target。暂缓 S2 清理时，公开预测及 metadata 同时
显示两个同位置 way；恢复后只留下低 way，另一 set 不变。此前仅重放 cold
metadata、同组占位或属性改写得到单命中，是 write buffer 同 set/tag 合并
与持续 S2 清理共同遮蔽了该路径；具体证据见
[RTL 覆盖率分析](rtl-coverage-analysis.md)。
剩余 AheadBTB、MicroRAS 原始 RTL 覆盖缺口仍需按
[RTL 覆盖率分析](rtl-coverage-analysis.md) 分类；不能把每个未命中复制点
直接当作独立功能点。`BPU-INT-020` 证明 MainBTB 的集成多分支反馈；
`BPU-INT-021` 进一步证明两个不同 TAGE provider 的同笔反馈；
`BPU-INT-022` 在两 provider 有效的前提下，用单分支训练对照证明集成 SC 的
不同 way 逐分支反馈；`BPU-INT-023` 再对相同 SC way 的两次同向更新做
阈值速度对照；`BPU-INT-024` 再证明同 way 的反向票在同笔反馈中抵消，
并以同槽位双 not-taken 正对照排除向量被忽略。所有动态 metadata 反馈组合
仍不能由此推断。`BPU-INT-025` 进一步让 TAGE 与 SC 同时保持使能、
每笔使用新配对的 S3 metadata，证明两路 provider 计数与共享 SC 校正
顺序演进；它仍是串行反馈闭环。`BPU-INT-026` 在同一 PC/历史下先捕获
两次不同接受时刻的 S1/S3 快照，再经异步训练 driver 一次提交两个不同
位置的 FTQ beat：两个硬件接受事件相隔一个周期，读回的 TAGE provider
和 MainBTB counter 分别留下可区分的更新。这证明连续反馈进入流水线，
`BPU-INT-027` 再使用两个不同 PC 的真实 S1/S3 快照，预测 monitor
确认训练接受窗口中仍有预测被接受；两笔相邻 FTQ 反馈分别让原
MainBTB counter 2→1 与 2→3，排除反馈丢失或串到同一条目。
`BPU-INT-028` 进一步固定同一 PC 和位置，先用真实 redirect 路径改变
PHR metadata，并观察原 provider 在新上下文中 miss；随后分配新 provider，
确认旧上下文仍保留原 provider/counter 2、新上下文命中独立 provider/
counter 4。两个历史各取一份配对 metadata，FTQ 相邻反馈后分别读到 1／3，
证明历史上下文不能被错误合并。为隔离 tagged SRAM 单端口读写争用，
`BPU-INT-029` 进一步用另一个 TAGE bank 的非条件自循环让预测持续
进行；两笔历史反馈仍在相邻拍接受，prediction monitor 恰在这两拍均
收到自循环 PC，回读两个 provider 仍分别为 1／3。这证明不同历史反馈
能与跨 bank 的活跃预测并发。`BPU-INT-030` 则让非条件自循环与条件反馈
访问同一 bank，确认预测活跃期间训练保持 pending，停止预测读取后才被
接受，并通过 MainBTB 与 TAGE 回读确认输入未丢失、未误报接受。
`BPU-INT-031` 在同样的读冲突下先排入两个不同 PHR 的反馈，预测窗口内
两者都保持 pending，释放后相邻接受。分历史回读确认第一笔分配新
provider、第二笔把自己的原 provider 从 4 更新到 5；这补上了单笔
背压与跨 bank 双笔并发之间的交叉场景。两份快照共享 MainBTB 旧计数，
最终 MainBTB 值不能用来计数反馈笔数。
`BPU-INT-032` 将独立 ITTAGE 的 provider 行为推进到顶层目标仲裁：
先通过真实 FTQ 反馈分配 ITTAGE，关闭它时仅改变 MainBTB 的间接目标，
再在相同 redirect／历史上下文恢复查询。用公开 metadata 确认 provider
驻留，要求 S2 给出 MainBTB 新目标、配对的 S3 correction 给出 ITTAGE
旧目标。覆盖四格均在这些断言后采样，不以单模块 ITTAGE 命中推断集成
优先级。
`BPU-INT-033` 将独立 RAS 的 LIFO 行为推进到两层真实 BPU 控制流：
预先训练两个 direct call 和两个 indirect return，并令两个 MainBTB return
静态目标与正确返回地址不同；重新启用 RAS 后沿外层 call、内层 call、
内层 return、外层 return 的预测路径前进。两次 return 的 S2 仍公开给出
错误静态目标，各自配对的 S3 则按栈后进先出顺序给出两个不同返回地址。
这比 `BPU-INT-008` 的单层 call／return 更能检查跨帧状态和逐笔目标关联。
集成 BPU 中两个早级预测器同时有效且目标不同时的
S1 来源优先级现由 `BPU-INT-017` 验证。`BPU-INT-015` 证明 AheadBTB
可独立学习并提供 S1 命中，`BPU-INT-016` 证明两张表可分别保留不同目标；
新用例再用条件分支 metadata 与来源回显确认 AheadBTB 的目标 B，打开
MicroBTB 后由 agent 短暂恢复接受，让两张表在新的 S0 查询中同时读取。
随即背压保持该 S1，目标仍为 B；不接受下一笔请求，仅关闭 AheadBTB
和 MainBTB 后，同一 S1 显示 MicroBTB 保留的目标 A。A/B 不同，故不能
把目标已由 S3 fastTrain 收敛的输出误当成优先级证据。早先离开自循环再
重定向回 PC 的探针改变了折叠历史，AheadBTB 当笔无效，不计入本验证。
`BPU-ABTB-032` 又从未翻转的目标高位发现单模块目标区域边界未明确入表：
局部 4 MiB wrap 已用 fit／上溢／下溢三格验证。它本身不能证明集成 BPU
能纠正 ABTB 提供的错误高位。`BPU-INT-018` 现用 PC↔跨区目标的双分支
循环建立真实 fastTrain：先分别断言 MainBTB 双向完整目标，再断言返回
方向 S1 的局部 wrap 和同笔 ABTB 来源回显。后级没有输出完整 target，
因此严格预期失败；四格前提覆盖命中，修正结果 bin 保持 0。
`BPU-INT-019` 则已验证 ABTB 自循环旧目标到 MainBTB 跨区新目标的
S3 修正：agent 按同拍时间戳配对 S3 override 与 perf echo，公开来源仍
为 ABTB。由于新旧目标低位也不同，这与 `BPU-INT-018` 的高位独有
差异是两个独立对照。

## 13. 完成定义

本计划的功能点总数以 `verification_plan.json` 为准，其中：

- P0 必须全部有 testcase，并明确暴露FAIL/ERROR；不能为达到通过率而转换成XFAIL；
- P1 必须全部执行，strict XFAIL仅用于已明确登记且获准的特定缺陷，普通FAIL继续保留；
- P2 在完整回归中执行，可另设 smoke 选择集；
- 一个聚合 testcase 不得作为多个无关功能点的唯一证据；
- 功能点拆分完成后，旧的聚合定义应由上表粒度取代，而不是重复计数。
- 环境契约不进入硬件功能点分母，但失败仍使pytest失败，完整计划不能漏点。
- 描述非空不等于事件定义完备；模型文件存在不等于参考模型独立、比较完整。

功能点通过率由 pytest 判定，功能覆盖率只衡量已声明 coverpoint/bin 的采样闭环；
两者不能相互替代。即使现有 bin 均命中，仍需结合
[RTL 行/分支缺口分析](rtl-coverage-analysis.md)扩充尚未声明的功能场景。
