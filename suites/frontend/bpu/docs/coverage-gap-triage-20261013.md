# 2026-10-13：原生行缺口到功能需求的归因

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


## 2026-10-16：managed执行迁移不改变原生缺口

新完整生产18642项/64worker：18614PASS/25普通FAIL/3strict XFAIL，所有旧节点及
功能点判定精确保持。十DUT全部原生DA/v_line集合、分母、构建不变，因此下文
Main116、RAS31、SC336/TAGE120/BPU-buffer120和PHR13局部/1404条件归因仍适用，
没有借框架升级缩减分母或把分类变成PASS。1277原生输入完整，最终每build一份
DAT共约61.1MiB，worker输入提交后回收；新4个未满功能组和两项UTAGE样本恢复
来自自动采集异常前的有效观察，不是新硬件场景或RTL修复。
见[完整迁移差分](../results/production-xreactor-managed-20261016-v2/migration-qualification.json)。

## 2026-10-16：093完整重分类闭合Main本owner双记录保留（完整复验，未发布）

先基于上一轮完整RAS-neutral-gap原生LCOV逐项核对125个缺键及编译源码文本，
按源路径分组。本轮闭合其中9键，当前剩116；以下候选分类本身不是局部guard
证明、全设计可达性结论或功能PASS：

| 原生缺键数 | 源路径候选 | 既有语义需求与缺少的证据 |
| --- | --- | --- |
| 74 | 另一写入口命中原owner的pending/clean逻辑记录 | 关联028的保留owner、029的clear身份；不能因此断言全部74条都被已有FAIL阻塞，或全部是正常训练可达 |
| 42 | 一入口命中时另一入口仍有完整记录更新 | 关联026/029的训练与duplicate clear仲裁；独立UT覆盖不能自动转为集成公开来源证明 |
| 9→0 | 本owner的第二保留槽更新 | rank1本身不能证明两个pending逻辑记录；本轮093重分类已有实际双来源/效果/消费者证据，9键严格命中 |

编译位置为`rtl/bpu/WriteBuffer_4.sv`：跨owner430–440、454–464、494–504、520–530、
583–592、628–637、642–651；仲裁442–452、466–476、482–491、508–517；本owner
第二槽549–557。以上只是当前编译结果的位置索引，新[源/native关联器](../bpu/coverage/main_gaps.py)
实际按完整七字段payload复制、来源端口、保留owner及父分支关系提取，不靠固定
行号范围赋予语义。源行与原生报告文本逐条相等；所有125键对应14个native producer，
其中12个对应完整payload块，另2个是442/466的control-only else。它们不能被描述
为14次已执行的payload效果，更不能把125条拆成125功能点或删分母。当前116键
对应13个producer（11payload块、2control-only else），归因方式及分母未改变。

对照独立UT：`rtl/mbtb/WriteBuffer.sv`与集成child的**完整字节体仅模块声明不同**，
Scala输入key/字段一致。前轮缺125个DA键在独立UT原生DA中均有命中；更严格的
page-kind/anchor/arm/S-span逐项匹配，也确认全部14个签名已有同构建历史命中。
历史成功回归`production-ittage-directory-events-20261015-v1`的22份MBTB原生输入
逐份检查了controller→worker收据→artifact hash，归属34个PASS DUT用例。
这只是独立UT执行路径证据，不能自动授予当前工作树功能PASS、归给一个孤立case
或推论集成FTQ合法性。因此不能将这125键直接判为“缺失UT功能点”或局部不可达。

进一步核实026的agent：clean profile本来就先清理并排空，再重放清理与训练重叠；
并非只覆盖一次清理。此前把“重复清理”当成新UT候选的判断已撤回，不新增同义
功能。缺少的是集成公开来源与消费者资格，尚不能用这些UT命中代替它。
只读复核命令（默认不导出）：

```sh
python -B -m tools.review_main_gaps --baseline results/production-main-reclassification-20261016-v1 --standalone-baseline results/production-ittage-directory-events-20261015-v1
```

已实现093第二种**语义**profile：两个真实旧来源分别把较早负向conditional纠正
为taken indirect；独立模型拥有两份完整新kind/position/tag/carry/target，保持较晚
indirect sibling不变。连续真实读阻塞服务时，完整记录和两个方向重置不得合并或
丢弃。真实SDK服务、旧/新消费者和独立S2/S3修正窗口都必须比较，最终才闭合FC。
另补fresh offset请求：从较早指令之后开始，让被遮蔽的较晚sibling真正被选择，
再比较其原target和修正窗口。仅断言模型内未选中entry保持不变，不是DUT证据。
这不是将原case的way从1枚举到0；纠正了分支类型及顺序，选中的分支和修正窗口
也会变化。不新增097，不豁免FIFO溢出，不依赖stale nomination缺陷通过。

41项新增重分类、25项source/native关联、6项schema及1DUT，共73项全部通过。
既有Main service/rewrite77项纯合同及148组synthetic full gate纳入真实门禁；
合成actual不给DUT覆盖率信用。新单场景PASS（case1.46秒，pytest11.36秒），
门禁3139PASS（37.89秒）、兼容71PASS（56.98秒）及全量同2107文件epoch。

[完整生产诊断](../results/production-main-reclassification-20261016-v1/diagnostic-summary.json)
18620项/64进程440.46秒：**18592PASS/25普通FAIL/3strict XFAIL**，无ERROR/
SKIP/XPASS。旧节点和全部341功能点判定精确保持，仍322PASS/17FAIL/2XFAIL；
093现在有两个PASS节点，不新增097，也不把9条DA拆新功能。64收据、1501产物
hash核验；1182功能输入仅合并一次（137.28秒），345组/318满，新增两个6义务组
全满；旧343组比例、27个未满实例精确保持，required schemas146→148。

BPU原生DA33745→**33754/46541（72.53%）**，严格净增WriteBuffer_4.sv549–557
共9键，等于唯一独立PASS增量且孤立各计数1。十DUT零旧键损失、其他九个精确
集合和所有分母/构建不变；v_line仍2392/8236。BPU模块测试12334PASS/4FAIL/
2XFAIL，framework1126PASS，其余模块状态与下方前轮表完全相同。aging仍411.54秒，
不宣称运行速度优化。Main116剩余分类74/42仍是候选，13个精确producer签名均有
历史UT PASS聚合命中，不转移为集成FTQ合法性或正确性证明。SC336/TAGE120/
BPU-buffer120局部、PHR13局部/1404条件及RAS31（16局部/15物理副本）复核不变。

用户新授权后删除旧096原始worker目录1869文件、4113980965逻辑字节，汇总
LCOV/报告/日志保留；raw只能重跑生成。当前轮及上一轮016完整输入保留，RTL/
DUT/SDK、detached HEAD、xreactor分支及五份正式报告不变；入场线未降低或绕过。
本轮仍为失败诊断、不发布，未闭合其它预测器/完整FTQ或全部行缺口。
见[模型与证据边界](semantic-reference-models.md#093补强两个独立较早分支的完整类型纠正)、
[精确增量](../results/production-main-reclassification-20261016-v1/diagnostic-qualified-line-increment.json)、
[当前Main分类](../results/production-main-reclassification-20261016-v1/diagnostic-main-copy-residue.json)。

## 2026-10-16：016集成neutral来源闭合非push容量回收（完整复验，未发布）

096剩余35个集成RasStack缺键中，598、600–602对应真正未闭合的非push退休事件，
不是更多物理组。其语义是“真实source携带forward版本间隔时，退休回收旧信用，
但neutral不得提交任何调用栈数据”。补强现有RAS016，不按四条DA或两个端点新建
同义功能。旧独立UT六个同/跨代call/return上下文保留；新增一个集成profile。

自主持久Program/Frame从实际reset和语义事件拥有前驱、重复组、调用版本和退休；
先从真正2-call checkpoint切到neutral direct，真实neutral退休不回收。再次填满16
版本后，同当前source切换不能解除guard；真实neutral退休跨注册边界BOS→15，
下一拍guard才解除，期间不得靠另一次恢复解除。不同地址的新调用复用回收版本，
撤销年轻尾部后fresh S3 returns必须消费新地址；8个提交组始终保持复位数据，
旧metadata不变。源动作/PC/resolve/redirect/唯一tick/严格顺序及注册payload均检查，
只为neutral提供无栈操作路径，普通call/return的stale SSP仍拒绝。不改RTL，不读
实际BOS/top来修golden，不使用VPI/内部写入，也不声称正常FTQ允许漏通知。

[完整生产](../results/production-ras-neutral-gap-20261016-v1/exit.json)18547项，64进程
449.54秒：**18519PASS/25普通FAIL/3strict XFAIL**，无ERROR/SKIP/XPASS。
新增43纯/负向、6schema、1DUT共50项全部PASS，旧节点/全部341点状态精确保持；
341点322PASS/17FAIL/2XFAIL。门禁3067PASS（37.90秒）、兼容70PASS（61.23秒）、
单016 PASS（case0.97秒，pytest10.73秒）同2103文件epoch。64收据、1504产物hash
核验；原六上下文只有一个pytest节点，现016是两个PASS节点，不是七个节点。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 12292/4/2 | **33745/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1095framework PASS。BPU严格增4键恰好等于单016 PASS，孤立计数各1；十DUT
零旧键损失，其他九个精确命中集合、所有分母/构建不变。v_line仍2392/8236，
不能把四个DA键写成四个v_line或四个功能。1181功能输入仅合并一次（135.24秒）：
343组/316满，新增两组全满；旧341比例及27未满实例完全保持，required schema
144→146。功能点分母与PASS数未增长，这是既有合同的验证质量补强。

RasStack35→31缺键，全部分为16个精确源码/native局部guard键与15个committed-group
物理副本；旧四个OPEN gap键已获本有界集成来源/效果/消费者证明。分类本身不
排除分母、不授予功能PASS、不证明任意组路由，更不应默认枚举15副本。
SC336/TAGE120/BPU buffer120局部、PHR13局部+1404条件键复验保持不变。其它
Main125等未归因区、完整FTQ/全预测器及已知RTL差异继续开放；aging418.29秒仍在。
按既有授权删除被替代095原始worker输入约3.9GiB，汇总LCOV/报告/日志保留并
标记不能原地恢复raw，当时096对照与本轮完整输入保留；096 raw后来依用户新
授权清理，见本页最新节。RTL/DUT/SDK、detached
HEAD和五份正式报告不变，失败全量不发布。详见[语义与边界](semantic-reference-models.md#016集成补强中性提交回收版本寿命但不提交调用栈)、
[精确差分](../results/production-ras-neutral-gap-20261016-v1/diagnostic-native-delta.json)、
[当前剩余分类](../results/production-ras-neutral-gap-20261016-v1/diagnostic-integrated-ras-residue.json)。

## 2026-10-16：096 guard恢复后的调用版本寿命与复用（完整复验，未发布）

集成RasStack此前47个缺键不能靠枚举栈槽解释。现有8/9-call redo/return程序未到
真实满速容量及新身份复用边界；096复用独立持久Program/Frame语义模型，正常
学习两种不同返回地址。Main-only存在修正气泡，15版本后guard生效；初次把它当
16容量的recipe预期错误不得记为RTL缺陷。正常MicroBTB早期调用流达到16版本后，
额外call/return与同当前source恢复不得改变prefix；真实较老14-call来源解除guard，
只提交存活旧操作，再使不同地址的新版本跨wrap复用已取消/提交位置。撤销其
年轻尾部、提交保留新call并由fresh S3 return消费新地址后才闭合，保护旧groups。
不是写到尾槽就采样PASS，也不是读取实际top/计数/地址反灌golden。

[完整生产](../results/production-ras-reclaimed-versions-20261016-v1/exit.json)18497项，
64进程443.45秒：**18469PASS/25普通FAIL/3strict XFAIL**，无ERROR/SKIP/XPASS。
新增31纯/负向、6schema、1DUT共38项全PASS，旧节点/旧340点状态逐项保留；
341点全执行，322PASS/17FAIL/2XFAIL。门禁3018PASS、兼容69PASS、单096 PASS均
同2096文件epoch，64收据及1496产物hash核验。单case0.95秒，含setup pytest10.91秒。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 12248/4/2 | **33741/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1089framework PASS。BPU严格净增13键恰好等于单096 PASS：RasStack517–518、
582、584、718–721、724–727共12键，及ReplacerState_4:320一个正常准备PC的
物理副本；后者不授予新的Main-LRU功能PASS。十DUT零旧键损失，其余九个精确
命中集合、所有分母/构建不变。v_line另2391→2392/8236，不把13 DA写成13个
v_line或功能。1180功能输入只合并一次（135.57秒），341组/314满，新两组满；
旧339组比例及27个未满实例完全保持，required schema142→144。

RasStack原47键减12，剩35键逐项分为：

| 剩余键 | 源级/原生证据与后续动作 |
| --- | --- |
| 16局部guard键 | child body与独立UT逐字节相等；集成parent不同，单独核验189/190的push/pop互斥连接；全部native producer的anchor/arm/S span都与局部证明一致，不删分母 |
| 15物理committed-group副本 | 同一repeat增/减操作在group0/4–7的展开；group1/2/3已有真实命中和独立数据比较；不推论任意group路由都已证明，也不新增15功能或默认遍历 |
| 598、600–602四个gap键 | non-push retirement且forward version gap>2才重定位BOS；当前集成场景与有序call/return adapter未覆盖这一来源/效果/consumer合同。关联已有UT016，但集成证明仍OPEN |

详见[当前完整分类](../results/production-ras-reclaimed-versions-20261016-v1/diagnostic-integrated-ras-residue.json)。
四个gap键是下一步真实缺失的事件，不应由更多调用深度或正常push提交替代；
096不声称已闭合该需求。其它未归因区、全预测器/FTQ和RTL差异仍开放。既有
SC336/TAGE120/BPU缓存120局部guard及PHR13局部+1404条件键重验不变，不授予
功能PASS。RTL/DUT/SDK与五份正式报告不改，失败全量不发布；aging414.67秒仍在。
按此前授权清理已被替代094的原始worker输入约3.9GiB，汇总LCOV/结果/日志/HTML
保留并标记不能原地重验旧raw hash，当前095基线及本轮完整原始证据保留。
详见[096语义与边界](semantic-reference-models.md#096guard回滚后的调用版本回收与新身份复用)。

## 2026-10-16：095完整记录版本生命周期与物理展开的不同归因（完整复验，未发布）

Main缓存的129条缺行不能解释成129个功能。093保存两个不同记录，未闭合的是
同一logical branch的完整版本在pending/clean之间变化的因果链。095用正常学习
的较早negative conditional和较晚indirect sibling建立两个PC，再取同PC两个
真正不同的旧source。连续实际预测读下相邻纠正较早branch类型和两个完整target：
entry应只服务最新B，独立direction FIFO保留两次reset；fresh旧读必须发生在
释放前。SDK确认一次完整B entry+两次方向服务，再检查fresh消费者；用它的新
来源把clean记录改为前一region C，实际重新服务后再读，并保护sibling/另一PC。
不是沿dirty寄存器推golden，也不是只看S1 receipt或valid pulse。

| 缺口证据 | 归因与动作 |
| --- | --- |
| Main WriteBuffer_4的4个新DA键 | 补齐095完整record version事件链，单PASS与全量严格同四键；不是4个功能 |
| 独立MBTB剩余52个DA键 | 同一train-state写操作的未命中物理set副本；已有12副本命中，关联既有024，保留分母和按需physical回归 |
| CommonHR原3条缺行 | 已有局部r1 guard矛盾，不靠重复redirect补齐、不删分母 |
| 094错误发生在已有命中行内 | 功能错误仍普通FAIL；原生命中不代表语义正确，不能用覆盖率替代独立oracle |

MBTB52键与生成源码中的`states_i <= io_write_1_bits_state`逐项完全相等，64个
直接set选择中12个有原生命中，52个为零；all-ones的63选择使用reduce-and简化，
并未误按字符串模板遗漏。源码为
[ReplacerState.scala:66](../XiangShan/src/main/scala/xiangshan/frontend/bpu/replacer/ReplacerState.scala#L66)，
详见[当前原生点分类](../results/production-owned-main-rewrite-20261016-v1/diagnostic-mbtb-physical-residue.json)。
这不是不可达证明，也不证明任意地址路由正确；不应新增52个同义功能或默认set
遍历来制造进展。Main其它125键、BPU其它大块以及已知RTL阻碍仍未全部归因。

[完整生产](../results/production-owned-main-rewrite-20261016-v1/exit.json)18459项，
64进程469.06秒：**18431PASS/25普通FAIL/3strict XFAIL**，无ERROR/SKIP/XPASS。
新增32纯/负向、6schema与1DUT共39项全PASS，旧节点和旧339功能点状态全部保留；
当前340点全执行，321PASS/17FAIL/2XFAIL。门禁2981PASS（217.38秒）、兼容68PASS
（123.39秒）、单095 PASS与全量同2088文件epoch；64收据、1496产物hash核验。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 12216/4/2 | **33728/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1083framework PASS。BPU净增4键为WriteBuffer_4.sv:581–582、626–627，单资格
各计数1，严格等于唯一单095 PASS的差分；v_line另2388→2391/8236。十DUT零旧
命中丢失，其他九个精确集合、所有分母/构建不变。原Main129键剩125，仍需归因。
1179功能输入只合并一次（134.35秒），339组/312满，新两组满；旧337比例和27个
未满实例完全保留，required schemas140→142。SC336/TAGE120、BPU缓存120局部
guard及PHR13局部+1404条件键重验不变，不删分母、不填功能PASS。
第一次负carry试跑发现的是验证projection将逻辑-1误作二补码3；主源码规定enum
Underflow2，已修projection并加三项纯测试，不作为RTL FAIL。实际RTL/DUT/SDK、
detached HEAD和五份正式报告均未改；失败全量不发布，剩余目标继续开放。
详见[095语义、端点与源码](semantic-reference-models.md#095完整分支记录的pending版本取代与clean重激活)。

## 2026-10-16：094条件前缀恢复暴露额外未来事件（完整复验，未发布）

原生行被执行不等于功能正确。新的自主conditional-event history模型没有为了
补行复制CommonHR信号方程：普通block完成与较早conditional的backend NT恢复
是两种不同事件；后者只能追加截止被纠正指令的执行前缀。独立Micro/Main/path
正常学习早期后向taken分支及较晚branch，自有历史自然达到255/15，完整稳定
window独立认证lookup source，再从确切原公开owner恢复。较晚direct对照不追加
条件bit并通过；较晚conditional尚未执行，实际却多追加一个零。

state端点应254/14，actual252/12；另一profile完全不绑定内部GHR/BW，后续较晚
conditional真正执行一次后，新公开resolve.valid=1的history应253/12，实际249/8。
094归纳这一因果要求，不拆成两个端点功能；两个direct对照只增强既有043。
[CommonHR.scala:204](../XiangShan/src/main/scala/xiangshan/frontend/bpu/history/commonhr/CommonHR.scala#L204)
原全部hit计数与[Helpers.scala:33](../XiangShan/src/main/scala/xiangshan/frontend/bpu/history/commonhr/Helpers.scala#L33)
NT选择numHit解释额外零；BPU公开mask本来已conditional-only，不能误归因为direct
资格过滤。详见[独立模型、采样与范围](semantic-reference-models.md#094与043条件事件序列而不是commonhr信号方程)。

[完整生产](../results/production-owned-common-history-20261016-v1/exit.json)18420项，
64进程455.81秒，18392PASS/25普通FAIL/3strict XFAIL，无ERROR/SKIP/XPASS。
所有旧节点逐项状态保留，只有两个新conditional profile FAIL；339功能点全部
执行，320PASS/17FAIL/2XFAIL，旧338点状态不变。新增60纯/负向、2Bundle+2采样、
24schema契约和4DUT场景。门禁2943PASS、兼容67PASS、两个单PASS及两个隔离
普通FAIL均同2081文件epoch；64收据、1502产物hash核验，RTL/DUT/SDK未改。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 12183/4/2 | **33724/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1077framework PASS。十DUT精确native DA命中集合、分母、provenance及v_line
完全不变，BPU2388/8236；两个单PASS均零原生增量。本轮提高验证质量但**没有
行覆盖率上涨**；不能为了上涨去枚举bank，也不能用普通FAIL刺激授予合格信用。
任意S0队列选择、IMLI及自主SC历史组合仍未实现，不能称完整CommonHR或BPU。
1178功能输入只合并一次（133.48秒），337组/310满目标；旧329组比例及23未满
实例全部保留。direct新增四组满；conditional的state/public reached为50%/66.67%，
checked均0，总未满27。schema门禁132→140不替代真实组闭合。SC336/TAGE120、
BPU缓存120局部guard及PHR13局部+1404条件键同原生点重验不变，不删分母、
不记功能PASS。当前CommonHR仍缺的3条DA属于原已定位的局部r1 guard矛盾，
不能靠重复本次redirect补齐；本次094揭示的是已执行行内的语义错误。
五份正式报告保持原样，失败全量不发布，剩余缺口和RTL问题继续开放。

## 2026-10-15：093 MainBTB两类义务的真实服务，028旧源差异（完整复验，未发布）

WriteBuffer_4此前140个缺失DA键不能机械解释成140个功能。独立Micro/Main/history
程序先正常建立早期自循环、两个PC各自的negative peer0和indirect owner2；两个
current-hit原来源的目标纠正并行接受，在持续同bank预测读下保留完整entry和
独立masked direction效果。entry缓存每way两槽，不等于方向FIFO也有四项容量；
容量内程序只送两项并要求零覆盖/丢弃。两个fresh旧读后才能释放，SDK确认两次
entry和两次方向服务，再检查两个fresh新目标、0/2邻居、原metadata及精确S3
target-only修正。Main-only循环会产生真正读空档，故使用正常Micro预测，不伪造忙。
方向t1 offer和公开接纳同采样边界，entry额外RegNext晚一周期，均不是commit。

另将既有028接到真实BPU来源：保留学习前发布的cold source，独立证明key仍在
way1、旧nomination为peer0。真实counter enqueue却mask1/way0=2，而期望mask2/
way1=2，tick714立即普通FAIL。不是metadata手工伪造、失去key后强要旧owner，
也不声称失败后已检查到新的错误消费者。与UT同源的差异不另造功能ID或XFAIL。

[完整生产](../results/production-owned-main-service-20261015-v1/exit.json)18328项、
64进程446.97秒：**18302PASS/23普通FAIL/3strict XFAIL**，无ERROR/SKIP/XPASS。
所有旧节点逐项状态保留，唯一新增FAIL是028集成来源。338点全执行，320PASS/
16FAIL/2XFAIL，旧337点状态不变。45语义纯/负向、1Bundle、12schema契约及2DUT
场景新增；门禁2855PASS（203.42秒）、兼容65PASS（112.82秒）、单093 PASS与
单028普通FAIL均同2071文件epoch，64收据及1495产物hash核验。RTL/DUT/SDK未改。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 12117/2/2 | **33724/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1053framework PASS。BPU净增11键，WriteBuffer_4的609、614–623，单PASS均计数1，
逐键等于该资格，不给失败刺激额外合格信用；v_line另从2387增至2388/8236。
十DUT零旧命中丢失，其余九个精确集合、所有分母及provenance不变。该Main缓存
仍缺129键，不能未经分析归为其它功能或全部RTL缺陷。SC336/TAGE120、BPU其它
写缓存120局部guard及PHR13局部+1404条件键重验不变，不删分母、不填PASS。
1174功能输入只合并一次（133.85秒），329组/306满目标；新增服务两组满、旧源
两组0，原325组比例和21个未满实例保留，现未满23；required schema128→132。
五份正式报告不改，失败全量不发布。完整FTQ、全预测器组合、剩余缺口与已知RTL
问题仍开放。详见[语义、原始来源与差异](semantic-reference-models.md#093与028mainbtb完整目标服务与旧冷源的真实owner资格)。

## 2026-10-15：092完整间接目标效果的读优先服务（完整复验，未发布）

此前WriteBuffer_24/28各26个缺失DA键集中在slot2/3完整payload保存，不是26个
独立功能，也不是需要更多bank。缺的是四个原始历史来源的正确间接反馈已经接受，
但持续预测读阻止SRAM服务时，目标效果仍须被保存；新请求在提交前看旧值，之后
看新值。062的provider/target学习和074组件cut-point都不足以独立证明该组合因果。

新增自主MainBTB/ITTAGE/history适配器，不以实际provider/allocate/target为期望。
四个真实历史拥有四个row和四个foreign-region身份；短/长索引宽度两类独立资格，
不展开bank/set/中间表物理矩阵。驱动前声明完整confidence3目标patch；四次正确
反馈须与真实预测并行接受，输入、blocked完整payload与四slot保留均比较。四个
fresh旧读仍为confidence2后才释放压力；SDK确认四个完整有序提交，四个fresh新读
为confidence3，目标、原metadata、region与完整repair窗口保持后才给checked。
输入常量折叠的valid不伪造观测，service输出仍检查；mask保留36位，padding
DontCare不变造功能要求。无内部写入、VPI、case边沿等待或框架hack。

[完整生产](../results/production-owned-indirect-service-20261015-v1/exit.json)18268项、
64进程505.72秒：**18243PASS/22普通FAIL/3strict XFAIL**，无ERROR/SKIP/XPASS；
旧节点与每项状态精确保留。337点全执行，319PASS/16FAIL/2XFAIL，旧336点逐点
不变，只新增092一族。三项隔离PASS、兼容64PASS、门禁2797PASS均同2062文件
epoch；64收据、1485产物hash已复核。新增89语义、5Bundle/Monitor、18schema
契约与3DUT场景；062自主增强没有另造功能ID或行增量。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 12070/1/2 | **33713/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1041framework PASS。BPU净增52键：WriteBuffer_24/28的401–413、420–432各26，
单场景计数均为1，逐键等于两项隔离PASS并集；原生分母46541不变，v_line仍
2387/8236。十DUT零旧命中丢失，其余九个命中集合/全部构建provenance相同。
SC336/TAGE120、BPU写缓存120局部guard及PHR13局部+1404条件键重验不变，不删
原生分母或填功能PASS。RTL/DUT/SDK和五份正式根报告不变。1172份功能输入只
合并一次（134.03秒），325组/304满目标；六个新增组全满，原319组比例及21个
未满实例精确保留，required schema122→128。完整FTQ、全预测器组合、已知RTL
失败及其余物理展开仍开放。详见
[独立模型边界](semantic-reference-models.md#062与092自主间接目标学习与读压力下的完整目标服务)与
[原生逐键比较](../results/production-owned-indirect-service-20261015-v1/diagnostic-native-delta.json)。

## 2026-10-15：091 useful读优先延后服务是真缺失事件（完整复验，未发布）

`Queue4_UsefulCtrSramWriteReq.sv:83/85`此前缺的不是更多物理坐标，而是普通学习
在读压力下真正入队、之后出队的服务事件。原086的provider与base一致，不产生
useful增益，entry counter写缓存闭环不能证明独立useful通道。091用独立Main/TAGE/
history模型正常建立两个历史，令原negative provider正确而base错误；四个不同
旧来源A/B/A/B提出四个useful-one效果，完整输入在预测旁相邻接受，没有训练重读。
核对全部实际enqueue、满pending、blocked front与零ready；两个新读须仍见旧0。
释放后SDK确认四个有序完整提交，再由两个新consumer看到1且非零邻居保持。
TAGE counter合成0/7、Main旧快照各提2/3、useful旧0各提1三种语义分别检查。
不是从实际队列或表内容初始化golden；reached不提前放在准备阶段。

[最终完整生产v2](../results/production-owned-direction-useful-20261015-v2/exit.json)
18153项、64进程444.96秒：**18128PASS、22普通FAIL、3strict XFAIL**，无ERROR/
SKIP/XPASS，精确失败集合及所有旧node ID不变。新增75纯/负向契约、2个Bundle/
Monitor契约、6schema契约及1真实DUT场景。336点全执行，318PASS/16FAIL/2XFAIL；
原335点状态逐点不变，只新增091一个需求族，不按两条缺行或六条义务制造更多点。
最终隔离1PASS（5.45秒刺激），旧兼容60PASS（117.42秒），模型/框架2588PASS
（189.71秒），四轮同2042文件epoch；64worker收据、1492产物hash复核。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11973/1/2 | **33661/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1023项framework PASS。BPU净增两个DA键，逐键等于
[单PASS资格](../results/owned-direction-useful-qualified-20261015-v2/qualified-line-delta.json)，
各命中4次，`v_line`仍2387/8236。十DUT零旧键损失，其余九个命中集合、所有分母
和构建provenance不变。SC336/TAGE120、BPU写缓存120局部分类及PHR13局部+
1404条件键不变，不因此删分母或填功能PASS。RTL/DUT/SDK和五份正式根报告未改。

1169功能输入只合并一次（135.92秒），
[FAILED / NOT acceptance HTML](../results/production-owned-direction-useful-20261015-v2/diagnostic-coverage-report.html)
为319组、298满目标；旧组比例及原21未满实例完全不变。required schema120→122。
v1因修正reached事件过早而中断，其8.1GiB原生临时dat已回收、日志保留；不把该轮
部分结果或历史覆盖拼进v2。大块物理展开和局部guard不意味着更多新功能；其它
预测器组合、FTQ物理寿命和已知RTL差异仍开放。
详见[独立语义、来源和实际服务](semantic-reference-models.md#091-useful延后服务原来源学习旧值读取与实际写回分开证明)。

## 2026-10-15：066双向来源选择与学习因果闭环（完整复验，未发布）

既有NT-over-T证据不能替代T-over-NT：前者选择较晚direct，后者必须选较早
conditional。新增程序先独立学习并在actual边界确认T seeds，**驱动返回前**冻结
候选；通过另一历史把相同Ahead owner改成NT而保留每个seed，关闭fast learners
后只把Main改T。最高provider按独立算法选择，新命名公开consumer自己的原S3
反馈必须导致useful增加，并等下一完整actual比较后才确认。不是按实际输出选期望，
也不要求某个低表seed忽视高表优先级必胜。066不新增同义ID或重复计PASS。

[最终完整执行](../results/production-owned-early-positive-20261015-v1/exit.json)18069项、
64进程446.51秒：**18044PASS、22普通FAIL、3strict XFAIL**，无ERROR/SKIP/XPASS。
精确FAIL/XFAIL集合与全部旧node ID保留，新增45纯/负向契约、6schema契约、1DUT
场景。335点全执行，317PASS/16FAIL/2XFAIL。单场景1PASS（5.17秒刺激）、旧兼容
59PASS（108.46秒）、模型/框架2505PASS（186.32秒），四轮同2035文件epoch；
64worker收据、1485份产物hash复核，RTL/DUT/SDK及五份正式根报告未改。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11895/1/2 | **33659/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1017项framework PASS。BPU净增8键，逐键等于
[单PASS增量](../results/owned-early-positive-qualified-20261015-v1/qualified-line-delta.json)：
`BypassShadowBuffer_1.sv:4658/4659`为一个分配副本；4732/4735、4924/4927、
5692/5695为三个真实候选useful的更新条件/算术路径。不解释成8个新功能，不沿
这些坐标继续枚举。十DUT零旧键损失，其余九个精确命中集合、全部分母和构建
provenance不变。SC336/TAGE120、BPU写缓存120局部证明，PHR13局部+1404个
有owned-checkpoint前提的键均未变，不因此删原生分母或填功能PASS。

新两组各20条事件义务均完整，required schema118→120；1168份功能输入只合并
一次（135.28秒），[FAILED / NOT acceptance HTML](../results/production-owned-early-positive-20261015-v1/diagnostic-coverage-report.html)
为317组、296满目标，旧组比例及原21未满实例不变。PHR编码别名新增精确redirect
来源关联，不猜历史，15项归属契约通过；这不是FTQ物理寿命/容量或epoch合法性
证明。高位tag和其它已知普通FAIL保留；其它branch组合、全预测器和完整FTQ仍缺。
详见[语义模型和负向资格](semantic-reference-models.md#066双向反基预测先声明来源再验证实际选择和学习效果)。

## 2026-10-15：066自主反base选择及原来源useful学习（完整复验，未发布）

本轮不是新造功能ID，而是为原066补独立组合oracle。前一轮044能验证NT provider
被消费，但Ahead base也可能同为NT。现在要求NT provider真正推翻T base，S1从
位置2条件分支改选位置4 direct fallback，与独立Main一致且没有后续repair掩盖。
同一个Ahead owner通过另一真实短历史变强T，受保护MicroTAGE entry/useful保持；
Main-only改变方向后再恢复原历史。只有对应已检查S3来源的useful增加，并在下一
actual完整状态边界确认，才能给分。不是更多bank/set或实际组件写包驱动的golden。

[完整运行](../results/production-owned-early-opposition-20261015-v1/exit.json)18017项、
64进程501.44秒：**17992PASS、22普通FAIL、3strict XFAIL**，无ERROR/SKIP/XPASS。
原22FAIL、三XF和所有旧node ID精确保留。新增33纯/负向契约、6schema契约及1个
DUT场景。335点全部执行，317PASS/16FAIL/2XFAIL；066没有重复增加通过点。64
收据、1493产物hash及终态2027文件epoch均复核，四轮最终epoch相同。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11849/1/2 | **33651/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1011项framework PASS。BPU净增11键，逐键等于
[独立PASS资格](../results/owned-early-opposition-qualified-20261015-v1/qualified-line-delta.json)：
下层`BypassShadowBuffer.sv:3890/3891`；上层
`BypassShadowBuffer_1.sv:4730/4731/4922/4923/5690/5691/6004/6005/6007`。
八键是准备/学习过程中少量cell的分配选择与初始化，三键是既有useful cell的
更新/保持路径，不是11项新功能。十DUT零旧键损失，其余九个命中集合、全部分母
和构建provenance完全相同。隔离分子不冒充全量，也不拼接历史覆盖发布。

最终资格1PASS、场景4.03秒；旧DUT兼容58PASS（109.39秒），含原高索引066和
044低tag；模型/框架门禁2454PASS（175.25秒）。原高位15bit tag普通失败保留，
不截断oracle、不扩XFAIL、不改RTL/DUT/SDK。独立有资格的Ahead beat才定义裸
预测字段；valid和全部1024 useful cell始终检查。源身份、短历史固定点及旧读/
当前驻留tag相符是前提，counter0不能独自证明准备完成。

新增14条因果义务不是14个同层功能需求；两组reached/checked均14/14，生产
required schema116→118。1167份当前功能输入只合并一次（135.10秒），
[FAILED / NOT acceptance HTML](../results/production-owned-early-opposition-20261015-v1/diagnostic-coverage-report.html)
为315组、294满目标。所有旧组比例及原21个未满实例完全不变，正式五份根报告
不被本失败全量覆盖。功能点通过率、事件覆盖率和原生行比例分别报告。

该轮尚缺T provider推翻NT base的自主资格，后续双向资格见上；其它预测器和完整FTQ物理寿命/
epoch组合仍缺。SC336/TAGE120、BPU写缓存120局部证明重验不变；PHR仍是13局部键
和1404个有自有checkpoint前提的键，不豁免原生分母或填功能PASS。
详见[语义模型、时序合同和负向检查](semantic-reference-models.md#066自主反基预测原来源选择较晚分支并确认useful效果)。

## 2026-10-15：044条件Ahead/MicroTAGE自主组合后的完整复验（未发布）

[完整运行](../results/production-owned-early-direction-20261015-v1/exit.json)17977项、
64进程453.73秒：**17952PASS、22普通FAIL、3strict XFAIL**，无ERROR/SKIP/XPASS。
原21FAIL和三XF的精确集合不变，只新增高位tag消费者的普通失败。此前全部node ID
保留；新增55纯契约、12schema契约和2真实DUT场景。335点全部执行，317PASS/
16FAIL/2XFAIL；既有044被加强，不重复造ID，也不因旧三个子场景通过而忽略新FAIL。
64收据、1487产物hash和终态2020文件epoch均复核；五轮最终epoch相同，RTL/DUT/
SDK及五份正式根报告未改。新失败是更强oracle揭示的已有tag-width差异，不修RTL。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11815/1/2 | **33640/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另1005项framework PASS。原生十DUT零旧键损失，其余九个命中集合、全部分母及
构建provenance完全不变。BPU比此前完整多8键，全部是
`BypassShadowBuffer_1.sv`上层useful分配选择/初始化的物理展开，不是8个新功能。
[独立PASS低tag类](../results/owned-early-direction-control-qualified-20261015-v1/qualified-class-line-delta.json)
证明其中6键：4986/4987（bank1,row81）、6002/6003（bank2,row80）、6010/6011
（bank2,row81）。其余7034/7035（bank3,row81）只有全量诊断命中，未获PASS类
资格，不计合格提升。隔离25218/46541不冒充新全量分子，不把失败刺激的键拼成
验收结果，也不沿这四个cell扩展物理遍历。

真正补的质量缺口是“从自主history/Main/Ahead状态产生MicroTAGE学习和消费者”，
而非从实际上游写包推导shadow变化。读索引、标签历史、原始匹配位置、呈现位置
与原S1可训练路径分别保留；期望provider/counter/metadata不以实际hit/valid取值。
正常发现位置2条件分支，单独resolve为NT，再从新owner发现位置4 direct fallback。
新消费者才证明分配效果，最后关闭checked。provider可能与Ahead base同为NT，
不把这个证据夸大为已证明base方向被反转。两类地址区分tag-width，不枚举bank/set。

低tag reached/checked各8/8，高tag reached5/8、checked0/8。高tag失败tick500：
完整独立tag0x4000与实际读tag0x00，counter3、索引(0,320)、history及位置相同，
hit预期1/实际0；MinimalConfig15位与MaxTagLen8的源码/生成RTL证据已保留。
新增55纯模型/负向契约、最终2415项门禁和56个旧DUT兼容全部PASS，不能据此
豁免真实高位失败。详细
[模型、时序合同及边界](semantic-reference-models.md#044条件aheadmicrotage自主组合独立标签与原始路径训练资格)。

[FAILED / NOT acceptance HTML](../results/production-owned-early-direction-20261015-v1/diagnostic-coverage-report.html)
当轮1166功能输入只合并一次，134.07秒；313组292满目标。所有旧组覆盖比例完全
不变、原19个未满实例保持，仅新增高tag两组未满；required schema112→116。
SC336/TAGE120、BPU写缓冲120局部矛盾证明重验不变，不改原生分母或功能PASS。
PHR1404仍有自有checkpoint前提；完整FTQ寿命和全部预测器组合仍未完成。

## 2026-10-15：015/019独立Ahead/Main组合后的完整生产复验（未发布）

[完整运行](../results/production-owned-ahead-20261015-v1/exit.json)17908项、64进程、
pytest445.10秒：**17884PASS、21普通FAIL、3strict XFAIL**，无ERROR/SKIP/XPASS。
FAIL/XFAIL精确集合与完整090相同。335功能点全部执行，318PASS/15FAIL/2XFAIL；
015/019强化oracle，不重复加ID或通过点。collection/JUnit/controller、64份收据、
1478个产物hash及终态2010文件epoch均复核，RTL/DUT/SDK及正式五份根报告未改。
已有普通RTL差异仍导致全量失败，不作为验收发布。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11759/0/2 | **33632/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另有993项framework PASS。[原生诊断](../results/production-owned-ahead-20261015-v1/diagnostic-rtl-line-coverage.json)
包含失败刺激。相对完整090恰新增**1**个键，逐键等于最终合格隔离：MainBTB
`ReplacerState_4.sv:322`的set33状态写入。它是自然双边分支程序的伴随物理副本，
不是新的替换功能，不因此枚举其它set。十DUT零旧命中丢失，其余九个命中集合、
全部分母和构建provenance完全不变；独立模型强化与原生上涨分别评价。

真正补的质量缺口是：旧场景验证“实际组件结果与若干断言一致”，没有完整自主
Ahead/Main的请求/读取/学习/纠正链。现在使用独立算法和自有history，从正常
FTQ发现建立两条间接分支，Ahead对提前读的内容匹配新目标；S1原metadata冻结到
S3 fastTrain，S3目标纠正还必须保留其原replay read。两个真实Ahead消费者、新
目标miss消费者及禁用Ahead后的Main S2回退均比较，所有七条checked最后才给分。
不读取实际index/hit/SRAM来初始化或推进golden；没有bank/set/depth扫描。

原015/019场景（包括跨区域旧目标纠正）仍保留。本新增程序关闭MicroBTB，限定
非条件早期路径；遇到条件预测/学习明确报缺独立MicroTAGE组合，不用always-miss
stub隐藏它。其它预测器和完整FTQ合法性仍开放，不冒称完整BPU模型已经完成。
详见[模型边界、负向契约与资格](semantic-reference-models.md#015019自主aheadmain组合提前读原来源学习与纠正重放)。

隔离1PASS、兼容56PASS、模型/框架2348PASS；新增71项纯契约和6项schema门禁，
其余旧项保留。两个新reached/checked组要求七条义务，required schema110→112。
纯模型/框架测试不产生DUT覆盖，未扩大XFAIL、跳过失败或改变原生分母。

[SDK诊断HTML](../results/production-owned-ahead-20261015-v1/diagnostic-coverage-report.html)
明确标为FAILED/NOT publication；1164份功能输入仅合并一次，309组中290组满目标，
新两组的七条义务均完整，旧19个未满实例的精确集合不变。功能组完成、功能点
通过及原生比例不混用。当前SC336/TAGE120、BPU写缓冲120局部矛盾证明均重验；
PHR仍分别是13局部键与1404有自有checkpoint前提的键，不把它们合成无条件证明。

## 2026-10-15：大缺口再归因——PHR余数约束与物理副本（只读）

本轮不是新增全量，也没有新增DUT功能ID。090完整测量的BPU尚缺12910个原生
DA键，其中以下三个区域共11148键，占**86.35%**。不能把每条生成赋值当新功能，
也不能因物理bin低就恢复bank/set笛卡尔遍历。

| 区域 | 缺键 | 具体归因及边界 |
| --- | ---: | --- |
| AheadBtb | 4926 | 923个分配弱正初始化、1000个increment、各1001个decrement选择/非零guard/赋值，全部是1024个物理counter的五类展开；1004个cell仍有缺键。已有语义路径组100%，不代表自主Ahead/Main组合oracle已完整。 |
| BypassShadowBuffer | 2440 | useful分配选择/初始化各480，饱和选择/更新各490，保持500；映射500个物理cell，未映射0。 |
| BypassShadowBuffer_1 | 2365 | useful分配选择/初始化各437，饱和选择/更新/保持各497；映射497个物理cell，未映射0。 |
| Phr | 1417 | 13个无条件局部guard矛盾；1404个仅在复位及同epoch真实检查点约束下不可能的cell/offset余数组合。 |

两块shadow的geometry各512项。上述“物理映射”不等于证明功能正确，更不是从
分母排除；有缺键的cell并非有一个新硬件事件。现有useful行为组44/56、78.57%，
12个未命中为age_nonzero×3、上饱和保持×3、increment×2、decrement×2、下饱和
保持×2的bank投影；每个table的七类操作均已在至少一个bank发生。应继续验证
输入资格、历史/tag归属、版本并发与真实consumer，而不是新增12个同义功能ID。
这也不豁免独立UTAGE的六个普通FAIL，或把实现级cut-point比较冒充完整BPU模型。

### PHR：把局部矛盾与受约束可达性严格分开

逻辑模型的cursor为`-SHIFT*taken_edges mod (2*WIDTH)`，当前SHIFT=2、WIDTH=52。
复位为0，taken减2，not-taken保持，恢复只能取自有checkpoint，因此value恒为偶数；
flag仍可为0/1。改变width或shift可消除这个不变量，不能把当前配置推广到其它配置。

生成RTL对15个taken hash位和13个not-taken恢复位各自展开52个cell。例如
`rtl/bpu/Phr.sv:2056–2057`把`ptr+15`写入cell0：合法偶数ptr加15为奇数，不可能
等于0。`2084`的同类guard行却可能被ELSE producer记为命中，不能把它改成未命中；
其真正的IF赋值2085仍是零。工具核对所有存储指针RHS、四路循环减2、逐位循环
offset，以及每个实际native `l/o/S` producer。不是看到DA为0就称“不可达”。

另外13键不需要输入前提：S2/S3获胜已经蕴含各自valid，S1获胜蕴含valid且taken；
其内部相反ternary arm自相矛盾，九个S1 fold保持arm同理。默认只分类这13键。
复验命令（stdout小摘要，无隐式JSON审计、波形或逐周期轨迹导出）：

```sh
python -m tools.review_history_gaps \
  --baseline results/production-direction-burst-20261015-v1

python -m tools.review_history_gaps \
  --baseline results/production-direction-burst-20261015-v1 \
  --assume-owned-checkpoints
```

前者13局部键、1404未分类；后者仍是13局部键，另列1404个**有输入前提的键**，
PHR剩余未分类0。不得混成“1417个无条件RTL不可达”。任意外部奇数metadata、
无复位、其它epoch或未知物理checkpoint寿命都不由该条件结论保证；工具不设置
ignore/exclude，不改变全项目原生分母，不给功能PASS或整体formal结论。

`BPU-INT-034`原来就要求reset-reachable偶数orbit，035–038覆盖两级taken/not-taken
修复。因此本轮不为同一需求重复加ID。历史raw PHR coverage仍保留全部52个pointer
bin和208项cross，两种cadence仍75%；不删除奇数bin，也不把证明当真实采样填满。
将“合法语义场景”与“输入位宽编码空间”分别展示是后续测量设计，不在本轮偷换。

### 本轮验证和下一步边界

新增39项纯契约分别检查自有history的reset/hold/taken/restore闭包、外来/复制/
旧epoch/已释放checkpoint拒绝、源码winner和cursor几何突变、非零/错误arm/重叠/
缺失native producer、过期epoch、隐式导出及默认不能启用约束。抽象模型闭包测试
不证明任意旧检查点的物理存储寿命，更不是DUT坐标枚举或覆盖贡献。

[完整模型/框架门禁](../results/history-gap-gates-20261015-v1/summary.json)2271PASS、
4进程165.17秒，完整保留2232旧项；[真实DUT兼容](../results/history-gap-compatibility-20261015-v1/summary.json)
16PASS、4进程31.50秒。后者重新运行恢复、S2/S3修复、历史/反馈并发及090两方向，
其本轮原生点再验同样13/1404拆分。两轮epoch为1999文件，证据完整；相比090
只加四个诊断/测试文件，原1995文件零修改，RTL/DUT/SDK和五份正式报告均不变。

**本轮新增原生命中0；功能计划仍335点。** 最新完整数据仍是下节090，不把16项
选测冒充全量、不从旧报告拼分子。仍需关注真正的自主预测器组合/来源关联、合法
FTQ时序、其余区域扣除既有局部证明后尚未归因的键及既有RTL差异；不因大块物理展开已解释就宣称
目标完成。

## 2026-10-15：090并行旧来源学习的完整生产复验（未发布）

[本轮完整运行](../results/production-direction-burst-20261015-v1/exit.json)共17791项，
64进程、pytest439.06秒：**17767PASS、21普通FAIL、3strict XFAIL**，无ERROR/
SKIP/XPASS。FAIL/XFAIL精确集合与前一完整089相同。335功能点全部执行，
318PASS/15FAIL/2XFAIL，PASS/计划94.93%。collection/JUnit/controller、64份
收据、1494个产物hash与终态1995文件epoch均核对；RTL/DUT/SDK未改、未重建，
正式五份根报告不替换。普通RTL差异仍保留，不能宣称全量验收通过。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11676/0/2 | **33631/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另有959项framework PASS。[原生诊断](../results/production-direction-burst-20261015-v1/diagnostic-rtl-line-coverage.json)
包含失败刺激；不是用普通失败后的状态续跑刷分。相对完整089，BPU恰新增8个
WriteBuffer_8键，逐键等于两个最终合格隔离场景的去重增量。十DUT零旧命中丢失，
其余九个命中集合逐键相同，所有分母和构建provenance不变。

这里缺的事件合同不是“再访问几个bank”，而是**多个旧预测在同一逻辑key迁移后
并行学习，当前版本必须逐笔合成并在饱和后保持**。四个不同真实来源都保留原5/
旧way，而当前已为4/新way。四个实际接受相邻、原提案都6，完整SDK提交必须是
新owner的5/6/7/7；三个新消费者还要保留邻居5/useful1和被替换key的miss。每个
提案/提交须与自己的来源因果对齐，第四份原metadata也不可变。四笔来自最短
到界并保持程序，不来自物理深度；case不搓时钟、引脚或并发task。详见
[090语义与资格](semantic-reference-models.md#跨owner旧来源突发090原快照固定当前版本逐笔饱和)。

新键810/1427是跨owner的counter饱和保持赋值，1455/1456、1475/1476、1495/1496
是其它保留rank同输入命中/未写路径的条件及伴随赋值。后六键不是六项额外功能，
也没有为它们增加rank枚举；本轮只增加一个语义功能ID。两个方向各有独立的
reached/checked组，共四组全部闭合，required schema106→110，计划334→335。
隔离每方向1PASS、兼容53PASS、模型/框架2232PASS；纯模型测试不计DUT命中。

[SDK诊断HTML](../results/production-direction-burst-20261015-v1/diagnostic-coverage-report.html)
标明FAILED/NOT publication；1163份本轮功能输入只合并一次，307组中288组满
目标，原19个未满组的精确集合不变。功能组完成、功能点通过与原生覆盖分开报告。

WriteBuffer_8缺314→**306**；原生producer与精确源码guard再次验证120个局部
矛盾，余**186**个未分类。整个BPU仍缺12910键，不能把局部证明扩大到整个模块。
独立SC336/TAGE120个局部矛盾也重验；均不缩分母、不给功能PASS。其它预测器
自主组合、完整FTQ合法性与21个普通RTL差异仍开放。

## 2026-10-15：089旧来源跨owner更新后的完整生产复验（未发布）

[本轮完整运行](../results/production-direction-migration-20261015-v1/exit.json)执行
17717项、64进程、pytest443.72秒：**17693PASS、21普通FAIL、3strict XFAIL**，
无ERROR/SKIP/XPASS。FAIL/XFAIL的精确集合与前一完整086/087相同。334功能点
全部执行，317PASS/15FAIL/2XFAIL，PASS/计划94.91%。64份收据、1476个产物hash、
collection/JUnit/controller身份与终态1988项源码epoch均已核对。RTL/DUT/SDK及
正式五份根报告保持不变；失败全量不作为合格发布。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11614/0/2 | **33623/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另有947项framework PASS。当前[原生诊断](../results/production-direction-migration-20261015-v1/diagnostic-rtl-line-coverage.json)
包含失败刺激。相对前一完整086/087，BPU恰新增**15**个WriteBuffer_8键，十DUT
零旧命中丢失，其余九个命中集合逐键相同，所有分母不变。相对更早正式基线是
另一个比较范围，不把此处“零旧键损失”扩大为与所有历史范围相比均无损失。

缺失前提是**旧输入指定way/counter与当前保留逻辑owner/counter不同**，不是
又一个bank坐标。089以三个真实历史造成正常替换/保护/重分配；保存原5/旧way
来源，当前同key已经4/新way。正确T反馈不重读SRAM，actual proposal仍为旧way/
counter6；SDK真实提交必须是相反owner/counter5。新消费者还要证明邻居5/useful1
不变、被替换blocker仍miss。每个准备输入和所有输出均由自有history/Main/TAGE/
pipeline模型比较，不以实际provider、分配建议或prepared shadow初始化golden。
20步正常学习无需八tag全表准备，更没有bank×depth枚举。

两个方向的[最终隔离](semantic-reference-models.md#跨owner旧来源089原metadata不是当前保留版本)
相对正式基线各8键；相对086/087则为8、7键，互不重叠。全量新增集合与这15个
合格键逐键完全相等，没有其它未归因的新键。它们包含条件头与key/counter伴随
赋值，不是15项功能；真正义务由实际旧输入、跨port提交和三类新消费者关闭。
两个方向分别两组reached/checked，四组均100%，required schema102→106，
计划333→334；只执行一边不能通过合并门禁。

完整[SDK诊断HTML](../results/production-direction-migration-20261015-v1/diagnostic-coverage-report.html)
明确标记FAILED/NOT publication；1161份本轮功能输入只合并一次，303组中284组满
目标，原19个未满组的精确集合不变。088及其更严格checked边界也被本轮重新执行，
不是把历史PASS加进当前功能组。功能组完成率与功能点通过率、原生比例分开报告。

WriteBuffer_8剩余缺行329→**314**；现有只读工具在本轮原生点上重新验证同样
**120**个局部矛盾，剩**194**个未分类，不删分母、不记功能PASS。其它主要缺口
及21个普通RTL差异仍保留；完整FTQ和其它预测器自主组合尚未完成，整体目标开放。

下面保留088的初次分析和更早完整测量，数字按各自冻结源码理解。

## 2026-10-15：088补满容量新key合同，但不是新的原生行增量

087后的329个WriteBuffer_8缺行不能直接解释为329个缺失功能。新增088独立检验
“无背压full miss恰好替换victim、新key用自身counter、其它义务全部保留”合同，
不是再访问一个bank/set。五种真实历史、每种两个owner，五个旧checkpoint相邻反馈；
E到达时实际八个dirty必须都为1，两个front必须仍是A的待写0/7。E自己的旧2/5
应得1/6，不能继承A的counter。五个旧消费者、八次SDK完整survivor提交、五个新
消费者及完整repair都成功才关闭六条checked。详见
[088模型与边界](semantic-reference-models.md#满容量新键088被替换义务与新键初始化的独立合同)。

严格隔离对比最近完整086/087，**新增原生DA键0**；相对早期正式基线的45键
（Tage1、WriteBuffer_8共44）已全部被最近全量覆盖。功能合同已补强，但不会把
“1个新功能点”折算成新增行数，也不会拼接隔离分子冒充当前全量。

最终隔离1PASS、49项兼容PASS、2098项模型/框架/负向门禁PASS，终态epoch和证据
完整性已核对。当前计划333点；required schema102组。共用086/087/088 checker的
“保留/仅替换指定victim”checked已延迟到全部真实提交和新消费者之后；旧消费者
阶段只能50%，不再凭front提前证明尾部版本保留。最近完整仍为下方332点的运行。

### 集成WriteBuffer_8的120个局部矛盾缺行

[只读归因工具](../tools/review_guard_gaps.py)现在支持`--dut bpu`。它首先核对独立
TAGE与集成BPU这两个1739行文件：去注释后的代码仅第46行模块名不同；其余整个
body必须逐行相同。随后复用经过负向测试的独立TAGE局部证明，重新核对每个guard、
body及词法包围关系，并按BPU实际原生点的l/o/S和所有重叠producer再次验证。
不能只换模块名、只看某个DA文本，或借用独立UT命中计数。

例如集成[WriteBuffer_8.sv:546](../rtl/bpu/WriteBuffer_8.sv#L546)定义
`_GEN_58 = hit & ~rowIdx & _GEN_25`，其832外层为真后，833的`hit`必为真，840–841
的内层else赋值不可能执行。804/808/815是对应的port1例子。其它证明还包括优先
分支已经排除同一selected项后再次要求该项的dirty/clean copy。native跨度可能
覆盖else头，因此证明范围及原生producer必须精确匹配，而非盲目扩展相邻行。

对下方最新完整诊断确认：BPU总缺12933键，其中WriteBuffer_8缺329；**120键是
上述有界局部矛盾，WriteBuffer_8剩209键仍未分类**。不是全设计形式证明，不替
任何功能记PASS，不删分母，也不因此推断其余209键可达。可按需复现，默认只输出
计数、不导出审计JSON或逐周期轨迹：

```sh
python -m tools.review_guard_gaps --baseline results/production-direction-capacity-20261015-v1 --dut bpu --native-report results/production-direction-capacity-20261015-v1/diagnostic-rtl-line-coverage.json
```

088时剩余的重要功能前提是输入port与逻辑保留owner不一致的陈旧来源/way迁移，
不是四个slot或bank分别新建功能点。独立TAGE已有对应counter范围和普通失败的
useful归属证据；集成BPU当时仍需从自有history/Main/TAGE程序正常构造迁移，不能把
组件实际provider或旧诊断里prepared实际shadow快照当成新的golden。
这个counter范围现由上面的089正常程序验证，useful陈旧来源范围仍不能据此豁免。
另外，PHR、AheadBtb和两种shadow的大块缺行仍须分别区分合法恢复/回绕事件、
物理副本及局部条件；本节的120键证明不适用于这些其它模块。

## 2026-10-15：086与087后的完整生产复验（未发布）

[最新完整运行](../results/production-direction-capacity-20261015-v1/exit.json)执行
17611项、64进程：**17587PASS、21普通FAIL、3strict XFAIL**，无ERROR/SKIP/XPASS，
pytest442.33秒。普通FAIL及strict XFAIL的精确集合与上一完整085相同，没有扩大
XFAIL或为了覆盖率继续消费已错状态。332个功能点全部执行：315PASS、15FAIL、
2XFAIL；PASS/计划94.88%。64份收据、1484个产物hash、collection/JUnit/controller
逐项身份及最终1974项源码epoch均已核对。正式五份根报告不替换，RTL/DUT/SDK不改。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11535/0/2 | **33608/46541** |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另有920项framework PASS。当前[原生诊断](../results/production-direction-capacity-20261015-v1/diagnostic-rtl-line-coverage.json)
含失败刺激，不是合格发布覆盖率。逐键对比085：BPU新增**50**，其余九DUT集合
完全相同，十DUT没有旧命中丢失、分母均不变。50键全部在WriteBuffer_8，恰等于
086和087最终隔离合格增量的去重并集，不缺键也没有未归因的新键。

086的功能前提是两种历史在持续读优先下各自保留两个owner；087增加的是**每owner
四条保留容量已满时，原逻辑key命中更新仍须保留其它义务**。四种真实历史各有
两个旧2/5 provider，五份A/B/C/D/A来源全部在反馈前采集。实际八个dirty必须在
第五proposal到达时全部占用；四个新旧值消费者、八次SDK完整提交以及四个不同
计数结果消费者共同关闭检查，不以driver已接受或内部满标志单独判PASS。

087相对正式基线87键，其中34键在085仍为零；086有30个这样的键，两者有14键
交集，所以完整净增为50，而非34+30。087相对086独有20键主要是保留记录2/3的
row/tag/counter赋值及伴随条件头；它们不是20项独立功能。仍保留086独有16键和
其两历史合同。满后第五个新key的overwrite是另一个尚未声明闭合的合同，不能
由本项的满容量hit推出。更不能继续枚举所有bank/slot来替代功能归因。

087隔离1PASS、兼容48PASS、完整模型/框架门禁2057PASS，均epoch一致、证据完整。
六条reached/checked完整，两组加入门禁，required schema98→100；
[详细模型、历史别名发现和证据](semantic-reference-models.md#满容量命中087容量边界不能退化为多地址枚举)。
当前[SDK诊断HTML](../results/production-direction-capacity-20261015-v1/diagnostic-coverage-report.html)
明确标记FAILED/NOT publication；1158份本轮功能输入仅合并一次，297个功能组中
278个达到完整目标，19个未满组的精确集合不变。086/087四个reached/checked组均
100%。功能组完成率另报，不等于功能点通过率。
完整FTQ和其它预测器自主组合、既有RTL差异及未满功能组仍未完成；整体目标开放。

下面保留086初始隔离资格和更早完整测量，不作为当前全量分子。

## 2026-10-15：086读优先服务的隔离增量（未重跑全量）

085后的缺行中，`WriteBuffer_8`保留记录1的row/tag/counter与未写回命中分支，
对应尚未区分的功能前提：**同bank持续读取时，不同历史的同way更新是否同时
保留，并在释放后逐一提交**。一条历史只能产生每owner一个pending，重复相同
反馈也不能证明不同历史不会覆盖；不是简单增加bank/set坐标。

新增086以两个真实checkpoint路径A/B在同一PC形成不同历史，均建立两个对立
强provider，捕获A/B/A/B四个不同旧来源。四笔完整路径反馈在连续预测中相邻
接受但不重读SRAM，独立模型保留四份0/7版本；读取期间A/B各一个新consumer仍见
旧2/5，释放后SDK monitor确认每owner两次完整提交，再各自消费新0/7。
六条reached/checked均100%，两组加入门禁，required schema96→98、计划330→331。

最终[隔离资格](../results/direction-service-qualified-20261015-v1/summary.json)1PASS，
[严格差分](../results/direction-service-qualified-20261015-v1/qualified-line-delta.json)
相对正式历史基线83键，其中53键已在下方完整085生产测量命中；新增隔离资格
为**30个WriteBuffer_8键**。条件头/伴随赋值不等于30项功能或30次有效写入。
47项兼容、2012项模型/框架/负向门禁全部PASS，三轮最终epoch一致、证据完整，
没有RTL/DUT/SDK改动、VPI、固定settling等待、bank枚举或逐周期JSON轨迹。

单历史早期对照虽然PASS，但相对085完整基线净增0，不替代双历史资格；更严格
语义检查还纠正了复制mispredict标签的问题：selector跨历史共享，B的弱provider
此时已取得资格，其增强是正确反馈。最终资格已用修正后输入重跑。
实现、输入边界及全部证据见
[086语义与验收](semantic-reference-models.md#读优先服务086接受保留提交和可见性分开验证)。
本轮未重跑全量，仍以下方085作为最近完整生产诊断，不把33558+30登记为当前
完整分子。旧21个普通RTL失败、原生分母及正式根报告都不更改，整体目标仍未完成。

## 2026-10-15：085后的完整生产复验（未发布）

[本轮完整运行](../results/production-direction-forwarding-20261015-v1/exit.json)重新
执行当前全部17498项，64进程、pytest499.61秒：17474PASS、21普通FAIL、3strict
XFAIL，无ERROR/SKIP/XPASS。collection、JUnit与controller逐项一致；64份worker
收据及1477个产物重新验hash，evidence完整、integrity为空，最终源码epoch一致。
21个普通FAIL及3个XFAIL的nodeid集合与下方v2完全相同，没有新增失败或放宽标记。

330个功能点全部执行：313PASS、15FAIL、2XFAIL，PASS/计划94.85%。新增085
通过；不能把131个新增PASS测试算成131个功能点，也不能把FAIL全量发布为合格。
正式根报告继续保持历史完整基线。本轮[原生诊断](../results/production-direction-forwarding-20261015-v1/diagnostic-rtl-line-coverage.json)
包含失败刺激，不是合格发布覆盖率。

SDK原生生成的[诊断HTML](../results/production-direction-forwarding-20261015-v1/diagnostic-coverage-report.html)
标题保留FAIL及NOT publication。当前功能数据合并为293组、274组达到100%，新增
004自主方向学习及085转发的四组均100%；这只是分组统计，不是功能点通过率或
整个BPU功能完整度。19个未满组没有被删除或改小分母。

| 模块 | 测试PASS/FAIL/XFAIL | 本轮诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11434/0/2 | 33558/46541 |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另有908项framework测试PASS。逐键对照上一完整v2：**BPU新增42键，十DUT零旧键
丢失，所有原生分母不变**；其余九DUT命中集合逐键相同。42键均在
`WriteBuffer_8.sv`，恰等于085最终隔离PASS的53键中尚未被v2命中的集合，无额外/
缺失键。相对更早正式基线则累计新增301个BPU键，不将这与本轮42混用；其他
模块相对正式基线的旧范围/早期FAIL损失仍按下面v2归因保留。

### 缺行所对应的功能缺口

085补的是两笔不同checkpoint的旧counter2/5在相邻真实接受周期分别更新两个
对立owner，后续必须读到0/7而非只更新一次的1/6；再以新metadata验证饱和保持。
旧025是新metadata串行闭环，旧026每笔只更新一个不同owner，不覆盖此组合。
这不是增加bank/set或把52个写缓冲条件/赋值键拆成52项功能。两份来源、两个完整
NT前缀/T尾项、实际相邻接受、两个新consumer及全部repair由自主history/Main/TAGE
模型比较，实际metadata不作为golden输入。

六条reached/checked各100%，两组进入发布门禁（required schema94→96）；隔离
1PASS、兼容42PASS、完整模型/框架/负向门禁1946PASS。原始53增量含近期已覆盖的
11键，故本轮完整净增42；其中候选条件头不冒称独立真实写入效果。详见
[语义程序、差分与边界](semantic-reference-models.md#相邻双owner学习085两份旧读必须合成而非丢失一次更新)。
RTL/DUT/SDK均未修改或重建；仍缺完整FTQ epoch及其他预测器组合，整体目标未完成。

以下保留085之前的完整测量与逐模块历史归因，不替代本节当前结果。

## 2026-10-15后续：强化004自主组合，不冒称原生增量

晚于下面完整生产v2的本轮变化：MainBTB/TAGE由自主周期engine和自有历史组合，
不再依赖实际组件provider/base来推导golden。六条学习、raw/qualified选择与实际
consumer义务加入已有004；required schema为94组，功能ID仍329。
最终隔离1PASS、兼容41PASS，严格相对历史完整基线新增原生行键**0**。这是判错
能力与事件覆盖义务的增强，不是行覆盖率提升，也不是重新发布完整生产分子。
实现边界、SDK本地admission支持及证据见
[MainBTB/TAGE自主组合](semantic-reference-models.md#最新004强化mainbtbtage自主组合不以组件输出为oracle)。
RTL/DUT保持不变，已发现的普通RTL失败保留，完整BPU oracle仍未完成。

## 2026-10-15当前语义模型的完整生产测量（未通过发布）

[当前完整运行v2](../results/production-semantic-current-20261015-v2/exit.json)实际执行全部
17367项，64个独立进程、pytest442.86秒：17343PASS、21普通FAIL、3原strict XFAIL，
无ERROR/SKIP/XPASS。64份worker证据完整、integrity为空，JUnit、controller与
collection逐项一致，结束及诊断时源码epoch核验一致。不是把多个选测或历史
集合拼接成的“全量”。由于失败，原发布门禁退出1，正式根报告保持历史版本。

329个功能点均执行：312PASS、15FAIL、2XFAIL，PASS/计划为94.83%。测试XFAIL数
与功能点XFAIL数不是同一量：RAS-008有一个旧strict XFAIL及另一个普通FAIL，
功能点整体仍FAIL。历史7个XFAIL测试中的TAGE026及3个UTAGE旧场景，在更早的
独立模型检查中抛出普通Mismatch，未匹配其原来狭义异常；因此现在是FAIL，不是
删除/放宽XFAIL，也不通过恢复宽泛标记把它们隐藏。

下表原生数来自本次[诊断报告](../results/production-semantic-current-20261015-v2/diagnostic-rtl-line-coverage.json)，
**包含失败刺激、pytest退出1，不是合格发布覆盖率**。测试数包括各模块纯模型、
契约、绑定和真实DUT用例，不能将其全部称为真实DUT场景数。
另有SDK原生生成的[诊断HTML](../results/production-semantic-current-20261015-v2/diagnostic-coverage-report.html)，
标题明确保留FAIL及未发布标记；功能点状态仍以本轮pytest证据为准。

| 模块 | 测试PASS/FAIL/XFAIL | 当前诊断原生DA命中/分母 |
| --- | --- | --- |
| ABTB | 1984/1/0 | 17854/17854 |
| BPU | 11315/0/2 | 33516/46541 |
| ITTAGE | 124/2/0 | 1398/1398 |
| MBTB | 833/3/0 | 1004/1056 |
| RAS | 428/4/1 | 569/585 |
| SC | 130/0/0 | 3145/3481 |
| TAGE | 1091/1/0 | 4467/4587 |
| UBTB | 98/1/0 | 794/794 |
| URAS | 129/3/0 | 91/91 |
| UTAGE | 315/6/0 | 6987/11053 |

另有896项framework测试PASS。21项普通FAIL与各独立模块已记录的RTL
差异一致：ABTB1、ITTAGE2、MBTB3、RAS4、TAGE1、UBTB1、URAS3、UTAGE6。
此前[完整v1](../results/production-semantic-current-20261015-v1/exit.json)还发现BPU的
两个纯Python测试使用旧redirect payload期待，缺少新增的明确`ras_action=0`字段，
故为17341PASS、23FAIL、3XFAIL，pytest484.83秒。随后仅修正这两个严格字典期待，
保留所有其他字段比较，相关70项全PASS；源码epoch差异核对只有两个测试文件，
模型、RTL、DUT和SDK均未变。v2失败集合恰好只删除这两个旧契约失败，没有新增
失败，3个strict XFAIL及所有功能点状态不变；十DUT原生分母与命中集合也逐键
等同v1。v2不是在源码变化后沿用v1计数，而是重新执行全量并重新汇总当前输入。

缺口必须先按来源分开，不能将覆盖数字下降自动解释为新增功能缺失：

- BPU相对历史33257精确新增259个DA键，零旧键丢失；对应此前已验证的独立
  场景集合，两集合逐键相等、无额外或缺失键。仍需用PASS隔离证据判断功能
  资格，不能拿失败全量替代它们。
- MBTB少52键，全部为ReplacerState物理index写入副本，与先前1004/1056模块
  诊断一致。旧单test曾串行访问64indices，当前生产为index0/63的32项独立
  场景；完整物理profile仍1024项、6144-bin分母保留。这不是52个新功能点。
- UTAGE新命中3键，同时旧命中2920键变零，净少2917；丢失位置为lower shadow762、
  upper shadow2158。六个场景因更早的模型失配中止，本次6987/11053与先前同模型
  模块诊断一致；不能继续在已错误状态上运行来恢复数字，也没有证据把全部零键
  宣称不可达。先处理既有功能/RTL差异，物理未访问仍单独保留。
- BPU的AheadBtb剩余4926键均能由源码索引归到1004个物理counter cell的重复
  增减/弱正复位路径，非4926项独立功能。未做等价证明，不删除分母；shadow、
  PHR及其他学习/恢复事件仍需单独建模与验证。

本轮功能覆盖有1154个当前输入文件、289组，其中270组达到100%；功能点通过率
与覆盖组比例不可互换。19个未满组还包含物理副本、已知FAIL的checked义务及
未闭合历史/响应场景。功能JSON合计约1.01GiB（SC four-key角色约646.61MiB、
训练对齐169.26MiB、replacement90.62MiB），这是报告输入而非波形或逐周期轨迹；
重复schema/计数序列化是后续报告性能优化候选，不能靠裁剪分母改善比例。

归因起点是 `production-representative-20261012-v2`。后续完整生产刷新
`production-semantic-partial-wrap-20261013-v2` 已通过门禁并发布：BPU32755/46541，
相对起点新增25个原生键、零回退，其余9 DUT不变；shadow选择cross22/30。
后续 `production-sparse-wrap-20261013-v1` 又通过完整门禁并发布：相对v2
新增192键、十DUT零回退，BPU32947/46541，shadow cross26/30。
此前 `production-utage-split-context-20261013-v1` 又完整发布：297功能点全执行，
14,678 PASS/7 strict XFAIL/0 SKIP，MicroTAGE新增3键至9904/11053，十DUT零回退。
此前 `production-sparse-boundaries-20261013-v1` 已完整发布：298功能点全执行，
14,702 PASS/7 strict XFAIL/0 SKIP，BPU新增10键至32957/46541，shadow cross29/30，
十DUT零回退。
此前 `production-ras-retirement-gap-20261013-v1` 又完整发布：299功能点全执行，
14,810 PASS/7 strict XFAIL/0 SKIP，RAS新增4键至569/585，新故障需求36语义格通过，
十DUT零回退。以下RAS20键分类保留为上一基线的归因过程，其中4键现已动态关闭。
此前 `production-integrated-high-index-useful-20261013-v1` 已完整发布：300功能点
全执行，14,874 PASS/7 strict XFAIL/0 SKIP，BPU新增70键至33027/46541，新增
10语义格通过、十DUT零回退；66键恢复旧范围、4键连旧范围也未命中。
此前 `production-ittage-region-directory-20261013-v1` 已完整发布：301功能点全执行，
14,929 PASS/7 strict XFAIL/0 SKIP，BPU新增46键至33073/46541，RegionWays至162/162，
10语义格通过、十DUT零回退。46键旧全物理范围也未见；另有零置信度跨region重写
普通失败尚未解决，不计覆盖，不伪装成已有七项XFAIL已穷尽全部缺陷。
此前 `production-early-ras-pipeline-20261013-v1` 已完整发布：302功能点全执行，
14,998 PASS/7 strict XFAIL/0 SKIP，BPU新增46键至33119/46541，集成MicroRAS83→87/91，
16语义格通过、十DUT零回退；两种自然流水线意图，不做bank/set遍历。
此前 `production-neutral-ras-correction-20261013-v1` 已完整发布：303功能点全执行，
15,069 PASS/7 strict XFAIL/0 SKIP，BPU新增10键至33129/46541，集成MicroRAS87→89/91，
10语义格通过、十DUT零回退。两条前递行由实际三方流水线重叠关闭，另8键来自
自然哨兵缓存路径，旧全物理范围也均未见。
此前 `production-sc-threshold-bounds-20261013-v1` 已完整发布：304功能点全执行，
15160 PASS/7 strict XFAIL/0 SKIP，BPU新增17键至33146/46541，十DUT零旧键回退。
直接证明的功能增量是SC whole-delta范围拒绝的3键；14个TAGE候选算术键不等于
有效训练写入。旧64格属于阶段/检查清单，当前源码已经改为来源关联的事件
reached/checked，新增合格混合票抵消义务，八场景52/52事件格通过但原生新增0。
事件版已完整发布；不能用分母改变宣称覆盖提升。见
[事件提取、资格和剩余迁移](hardware-event-functional-points-20261013.md)。
后续 `production-sc-threshold-events-20261013-v1` 也已完整发布：15228 PASS、7既有
strict XFAIL、0 SKIP，305功能点298 PASS，52/52阈值reached/checked，十DUT原生
零旧键回退、新增0；BPU仍33146/46541。后续MicroRAS事件版也已完整发布：
`production-micro-ras-events-20261013-v1` 为15252 PASS、7 strict XFAIL、0 SKIP；
年轻RETURN取消补真实上下文，4/4 reached与checked均完整，原生新增0。
新增TAGE selector更新提交与真实预测消费需求072现也完整生产发布：
`production-tage-selector-events-20261014-v2` 为15387 PASS、7 strict XFAIL、0 SKIP，
306功能点299 PASS，精确新增11键、十DUT零回退，BPU33157/46541。
其中8键直接对应selector更新、另3键为伴随候选/预测路径；不将11键冒称11项功能。
最新073 useful老化事件也已完整发布：`production-tage-useful-aging-events-20261014-v1`
15522 PASS、7 strict XFAIL、0 SKIP，307点300 PASS，精确新增92键、十DUT零回退，
BPU33249/46541；两种饱和T3触发及维护/消费者六组reached/checked完整。
88键在旧全物理范围也未命中，4键恢复旧路径；不把组合候选/queue行都称功能关闭。
见 [输入、比较边界与差分](integrated-tage-selector-events-20261014.md)。
072路由补强已通过最终三用例资格及完整生产发布：同一容量准备在每表建立弱/强
两种base置信度，不增加bank遍历或老化case；reached/checked各八个逻辑对象均
完整。`production-tage-selector-routing-20261015-v1` 为15543 PASS、7既有strict
XFAIL、0 SKIP，307点300 PASS，228组216满目标。相对073基线精确新增8键，
集合与资格一致，十DUT零旧键回退，正式BPU33257/46541，集成Tage3011/3021。
八键旧全物理范围也未见；64收据/987功能输入/1780源码及全部发布链接核验一致。
067目录事件版随后完整发布：`production-ittage-directory-events-20261015-v1` 为
15595 PASS、7既有strict XFAIL、0 SKIP，307点300 PASS，231组219满目标。
补未满时已有项优先reuse输入，分配/消费各reached/checked四组完整，旧十标签
不混入新测量；完整目录/端口/所有resident/PHR/最终S3/drain继续保留。
原生新增0、十DUT分母和命中集合逐键相同，不用分母变化冒称上涨。1781源码、
64收据/987功能输入及全部发布链接独立复核，BPU仍33257/46541。见
[目录事件与证据](ittage-region-lifecycle-20261013.md#2026-10-15事件化分配提交和预测消费分别测量)。
原生 SF/DA 分母不变，
以下分类不删除行、不代替功能断言，也不把未执行需求登记为 PASS。

## 先区分三种缺口

| 缺口类别 | 当前例子 | 下一步 |
| --- | --- | --- |
| 缺失有效输入/状态序列 | BPU shadow 的 priority 外旧项回读 | 设计合法反馈、部分回绕、精确关联的新请求，比较完整 payload/state |
| 已知 RTL 缺陷阻塞 | MicroTAGE lower 高地址的 same-PC useful 更新上下文 | 保留原需求和零计数；同时检查不同 index/tag PC 的独立场景，不能把局部阻塞外推全 DUT |
| 局部守卫矛盾 | TAGE/SC WriteBuffer 的部分赋值 | 核对当前源码、条件与缺失键；记录局部证明，不能外推全 RTL 不可达 |

切换生产/物理范围造成的旧命中丢失另行报告，不能都自动归入第三类。
扩大 bank/set 笛卡尔积不能替代上述归因。

## 集成TAGE：路由资格后的剩余事件，不按原生行数定义功能点

073正式基线缺18个Tage原生键。072路由三用例资格及后续完整生产关闭其中8个；
当前正式残差10个。以下仅定位与定义下一步义务，不登记尚未验证的PASS：

| 原生位置 | 硬件语义与缺失前提 | 合格完成证据 |
| --- | --- | --- |
| Tage.sv:619、621 | 预测slot2存在table3 provider及table2 alternate，真实选择次长命中；其中alt最高表分支的局部守卫需与该原生键实际插桩区分 | 同源完整metadata、有效TAGE方向及最终S3 target/taken/position，不能只看Mux算术 |
| Tage.sv:9951、9969 | fastTaken预测slot0/1的table2选择way1方向；是逻辑provider身份/输出路由，不是再扫bank/set | 独立预期provider身份、实际fast valid/bits及同源消费者；也不把两行自动称两种新行为 |
| Tage.sv:6805、6935、7065、7325、7455、7585 | resolved反馈槽1/2/3/5/6/7的providerUseful候选加一；真实资格要求valid conditional、MainBTB owner、provider正确且与alternate/base分歧 | 同源有效T3 writeUsefulEn/完整写payload、提交或有效保持和后续provider consumer，邻项隔离；候选加法命中不是提交 |

反馈槽与预测metadata槽是不同身份：公开metadata必须按MainBTB position匹配，不能
把resolved槽号直接拿来索引TAGE metadata。现有BpuBatchTraining支持None空槽，
但这本身不是任意洞洞反馈都满足完整FTQ合法性的证明。新的多分支场景应保证
较早实际not-taken、末尾实际taken的可达路径及每个owner；不能伪造多条同时taken
或复制相同metadata条目，只为了触发六个候选表达式。

这批缺口能归因到“有效逻辑输入/来源路由”与“合格有用性写入”两族义务，不能说
所有剩余行都无关紧要或都是物理复制。现有073单候选集参考也不能直接当多分支/
alternate完整状态参考。后续需扩展明确的模型边界及故障契约，而非在case里增补等待。

2026-10-15后续独立资格：075以完整TAGE模型和稀疏双conditional真实反馈关闭
6805/7455两个useful候选键；078以同row对立owner方向、弱/强资格及完整S2/S3
纠正序列关闭9951一个fast路由键。均有独立的单场景原生差分，尚未合入新的完整
项目回归；不能改写上方历史正式分子或用选测集合拼接全量。
见[参考模型、事件资格与证据](semantic-reference-models.md#原始方向与合格方向078让两个owner的方向真正有区分性)。

079后续又用T3弱T / T2强NT alternate / taken base的真实层级，独立检查完整S2/T与
S3/NT纠正及增强后provider重新取得资格，最终单场景新增619/621两个原生DA键。
其中619虽包含`_alt_T_21`文本，但不是“T3自己当alternate”的独立语义分支计数；
T2 alternate能到达外层表达式。局部guard矛盾不能直接外推为原生行点不可达，也
不缩减任何分母。见[源码边界、反向检查和资格证据](semantic-reference-models.md#provideralternate层级079局部guard不等于原生行点不可达)。

## 集成MicroBTB：容量语义关闭物理复制路径，不按bank/set扩展

082使用32个逻辑分支达到配置容量、一次真实预测保护原预期victim，再用第33项
的真实反馈验证替换；逐项公开读回新项、victim miss和所有31个幸存者。
自主流水线及独立UBTB模型从reset比较所有阶段、纠正和历史；没有DUT状态种子或
victim线依赖。单case的99个来源是容量边界前提，不是bank/set笛卡尔积。

六条事件义务的reached/checked两组100%，严格单场景差分新增196键：
MicroBtb168、MicroBtbReplacer28。33项兼容及1041项模型/负向/门禁均通过。
见[082输入作用域、相位与证据](semantic-reference-models.md#集成microbtb容量近期访问保护与替换的真实消费者082)。
旧正式全量报告不变；该场景也不替代完整BPU/FTQ组合验证。

历史MicroBtb缺失中仅1486未被082覆盖：这是相邻同key更新转发的confidence
加一，不是再添加另一个地址即可关闭的物理复制项。后续083已用一个弱owner的
两笔真实相邻T反馈完成合成，并要求三次公开hit后才miss；静稳点只读actual计数
与独立模型比较，绝不初始化golden。五条事件义务reached/checked两组100%，
严格单场景只新增1486一个DA键。34项兼容和1602项完整框架/模型/负向门禁通过。
见[083输入、观测边界与资格证据](semantic-reference-models.md#集成microbtb相邻正向学习必须能被后续消费者区分083)。
已有连续NT耗尽复活普通FAIL仍保留，未加入新的XFAIL或缩减原生分母；隔离增量
不作为当前全量覆盖率发布。

## 集成MainBTB：已有覆盖路径仍需要独立oracle与精确请求归属

本轮强化现有`BPU-INT-004`而不新增功能ID。自主周期engine组合独立MicroBTB与
MainBTB模型，每笔查询保留自己的不可变MainBTB快照；训练必须关联到真实S1/S3
来源对应的确切已发布token。相同PC/history数值不能区分学习前后两个不同查询，
不能靠实际metadata填golden，也不能在出现差异时搜索附近同PC重新匹配。

两种取指窗口布局各执行一次冷态学习counter2、NT减弱至1、MainBTB纠正仍taken
的MicroBTB、原owner再恢复至2的完整链。五条事件义务reached/checked均100%，
两组加入发布门禁，required schema86→88，计划数保持328，不做bank/set矩阵。
2项真实DUT、36项兼容、1738项框架/模型/负向门禁全部PASS，同一最终源码epoch。
单布局隔离PASS相对历史完整基线严格新增**0个原生DA键**；因此这次提高的是已有
功能的判定质量与来源合同，不能写成行覆盖率上涨或新的完整BPU模型已验收。
见[独立模型、输入边界和证据](semantic-reference-models.md#集成mainbtb独立查询快照精确反馈归属与方向纠正强化004)。
其他预测器组合、完整FTQ及已知普通RTL FAIL继续保留；正式根覆盖率报告不改，
没有修改RTL、重建DUT或绕过失败门禁。

## 集成TAGE：学习发现历史不同于物理记录顺序

078随后补足旧场景缺少的前提：较晚conditional已进入MainBTB，随后才发现较早
conditional，但TAGE仍先建立较早强NT再建立较晚弱T。MainBTB记录、TAGE provider
way和逻辑branch position不能等同。新的真实程序历史必须检查raw方向在S2的
消费、qualified方向在S3的反向纠正，以及单独增强后的保持和邻分支隔离。
两个严格有先后的实际taken conditional miss建立发现历史，参数标签、重复/未接受
反馈和早于发现的旧source不能获得信用。只增加一种程序历史，不枚举bank/set。

仍强化同一078，计划数328；两种发现历史的四组reached/checked各5/5，新增两组
纳入生产门禁（required schema88→90）。严格单场景新增`Tage.sv:9969`一个DA键，
原顺序的9951增量独立复验保留；两者都由独立TAGE状态及完整consumer资格支持，
不是仅触发了一个Mux表达式。MainBTB/PHR仍是component输入cut point，不声称
自主全BPU模型已完成。见[发现语义、限制及隔离证据](semantic-reference-models.md#078补强较晚分支先被发现方向仍按逻辑分支而非记录顺序归属)。
最终2项真实DUT资格、39项兼容、1767项框架/模型/负向门禁全部PASS，五轮最终
epoch一致、证据完整且integrity为空。新的9969与原9951均经各自单场景严格差分，
不能把两者的隔离并集加到历史33257后宣称全量已更新。
这不是新的完整项目覆盖率；原分母、正式根报告、已知普通RTL FAIL均保留。

## 集成TAGE：valid但未跟踪，不等同于空resolve槽（084）

剩余useful表达式不能通过简单移动两个None空槽就算功能补足。084改为真实8条
conditional全部有效：位置4/6/10/14拥有独立预测状态，0/2/8/12没有MainBTB记录。
完整8条NT反馈里，matched/unmatched按position交错；四个已有provider正确NT且
与T base分歧，均必须counter2→1、useful0→1，保持自己的原owner。后来再正常
引入全部四条原untracked分支，以完整NT前缀/真正T误预测尾项形成新发现，公开
验证没有意外TAGE provider；不能只看四个已跟踪结果未坏便声称过滤正确。

六条实际事件义务reached/checked各6/6，新功能点084使计划328→329，不按物理
slot复制功能点；两组进入发布门禁，required schema90→92。相对同一历史完整
基线严格新增15个DA键：6935/7065/7325/7585四个useful键、10个写缓存伴随键、
以及旧078已有的9951。因此去掉此前16份BPU隔离资格的重复，新增14个不同键；
不是宣称15个新的功能行为。详见[独立模型、延后消费者和差分](semantic-reference-models.md#集成tage有效但未跟踪的分支不能挤占或获得匹配owner的学习084)。
最终1项真实DUT资格、40项兼容及1785+32项模型/负向/门禁全PASS；四轮最终源码
epoch一致、证据完整且integrity为空，未新增SKIP/XFAIL或改RTL/DUT/SDK。
`Tage.sv`历史缺失的10个DA键至此均有同源码隔离合格场景，但没有据此修改正式
完整分子或分母；WriteBuffer其他残差、独立TAGE普通FAIL及完整BPU组合仍未关闭。

## 邻模块的小残差：区分真实维护事件与局部冗余守卫

历史基线中BPU集成`Ittage.sv:696–697`缺的是全局tick饱和后的清零路径。发生资格见
`Ittage.scala:382–400`：有效错误更新且并非“零置信provider已经给出正确目标”，
无可用分配时增加tick、有分配时减少；饱和即清零并通知各表。不是给mispredict=1
再空等255周期。独立ITTAGE满原生覆盖不能豁免集成反馈、真实源和维护资格，
不能因为只差两行就分类为无价值复制。

维护机制也不能照搬073：`IttageTable.scala:185–197`中`needReset`只在无预测req
握手且无普通update时推进，按set游标扫全部bank。持续预测会阻止清理，完成条件
应依赖真实游标/needReset及实际SRAM效果，而非case空等固定NumSets周期；刺激只需
一个有维护前提的生命周期，不为每个bank重做计数累计。

现有`dut/bpu/BpuDut_offset.yaml`已导出memory-direct的`ittage.tickCnt_value`及三表
`needReset/resetSet`，没有观测能力缺失，不需要VPI或重建DUT。另一方面，当时
`suites/frontend/bpu/bpu/bundle/activity.py`的`writes`只包含ITTAGE写buffer在途，没有包含
`needReset`：普通pipeline/buffer空闲不能证明维护完成。这是当时的代码缺口，
不是当前状态；后续074已经把真实维护状态纳入committed契约，并检查read-free
推进、完整写掩码、实际SRAM效果及最终consumer，没有增加case固定等待。

2026-10-15的074单场景已完成：1PASS，真实反馈驱动一次全局维护，1024次硬件自身
扫掠写入；独立语义模型维护历史读取快照，六组reached/checked均100%。严格新增
31个原生键，含上述tick2、三个table cursor各1及维护写缓存26键。这是已有隔离
资格，不是尚待实现的缺口，也不是新全量发布。见
[074周期语义与精确差分](coverage-ittage-semantic-aging-20261015.md)。

相反，`CommonHR.sv:869–871`是可直接定位的当前编译源码局部守卫矛盾：外层
`if (r1_valid)`已处理恢复，内层位于它的else，却再要求`r1_valid`为真。现有真实
恢复走外层有效路径，不能靠更多redirect输入触发这个冗余分支，也不需发明新的
“第二次恢复”功能点。该三键原始零计数和分母继续保留；这是局部两态条件说明，
不是整个CommonHR形式证明或允许排除所有历史覆盖缺口。

## MicroTAGE：从1,152个缺口找到输入层缺失，剩余1,149个物理行键

前一生产结果为 **9,901/11,053**，当时所有 1,152 个缺失键都在 lower
`rtl/utage/BypassShadowBuffer.sv`：384 个高地址 useful 单元，各有三行更新路径。
例如地址128对应 bank0/row32 的4084、4085、4087；地址511对应
bank3/row127 的7916、7917、7919。

输入几何见 [独立地址模型](../utage/model/addressing.py)：

```
lower_index = (pc XOR fold(history, 6, 6)) & 511
lower_index[8:7] = pc[8:7]
```

history 在这个 index 中只能改变低6位；PC 的 bit7/8 又进入完整预测 tag 的
高位，而 history 的 tag 混合只能改变低6位。对 index128..511，至少一个相关
PC 高位必为1，完整预测 tag 不能与当前8位存储 tag 匹配。改变 history 不能
消去这个约束。**这里的前提是 index PC 与 prediction/tag PC 相同**，对应当前
`BPU-UTAGE-021` 的输入上下文，不是所有流水线请求的全局不可达证明。
PC 采用模型里的 halfword 表示，不能直接混用字节地址位号。

源头是 [Helpers.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/Helpers.scala)
的 `computeHashIdx/computeHashTag` 与
[MicroTage.scala](../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/MicroTage.scala)
的实际预测 tag 比较；更完整的原生/源码反例见
[tag-width 影响范围](../results/coverage-utage-useful-address-tag-scope-readonly.json)。

`BPU-UTAGE-021` 已经在两种反馈节奏下执行全地址更新需求并保留768个被阻塞
provider 上下文（384×2）；它仅接受具体 `UtageUsefulProviderBlocked` 异常作为
既有 strict XFAIL。不能伪造 hit/provider metadata 再宣称更新功能通过。
已通过的 `BPU-UTAGE-022` 是另一项部分回绕读回需求，不会消除这个位宽障碍。

### 必须修正的归因边界：index PC 不总是 tag PC

稀疏四节点 DUT 实验证实了真实 BPU 中不同阶段的 PC/PHR 来源：
`Bpu.scala:194` 将 `newStartPc` 连接到 S1 的 next target；MicroTAGE 的 index
仍来自更早的 `startPc/oldFoldedPhr` 请求。先前将384个高地址零计数全归为
tag-width 阻塞的说法过强，必须收回为 **same-PC 上下文受阻**。

最初的纯输入反例为 A/B/C/D=`0x40010006/16/80/1e2`（后三个省略共同高位）。
标量52位 PHR、完整 PHR reference 与 index/tag 阶段联合检查224步：A 的 lower
index来自更早的 D 请求，正负两种分支阶段均为 **462**；tag PC则为 A，完整
lower tag为 **208**，能放入8位存储。纯模型本身不证明 DUT 更新，但已经表明
仅凭 `index[8:7]` 推断 tag 超宽缺少 PC 同一性前提。
契约见 `tests/bpu/scoreboard/integrated/test_sparse_geometry.py`。

后续 `BPU-UTAGE-023` 已完成真实独立 DUT 资格验证：agent 提供独立 index/tag
PC和history，省略参数时保持原行为；index462成为真实 lower provider，并在
串行/相邻反馈下完成 useful 增减、饱和保持、base一致保持与邻居不变。
不同PC的4笔相邻lookup通过同一绑定Scoreboard比较完整输出，不需gather。
20个语义bin通过，原8192格物理cross仅新增8格，不复制到383个剩余地址。
全部19个history字段及provider反馈metadata检查通过后才能训练。

最终隔离资格1 PASS，相关驱动/模型/负向/真实DUT契约254 PASS；精确新增
`BypassShadowBuffer.sv:6796,6797,6799` 三键。最新完整生产回归精确重现这3键，
MicroTAGE至9904/11053，十DUT零旧键丢失；剩余383个高地址的1149键仍未覆盖，
不能再全归位宽阻塞。useful更新物理cross从5120至5128/8192，完整分母保留。
既有strict XFAIL仍检查原same-PC位宽缺陷，断言和分母不变；
新模块接口证据也不冒称完整FTQ生命周期已经验证。
见 [输入分层、检查门禁和精确增量](utage-split-context-useful-20261013.md)。

### 集成层的新功能需求：正确 provider 对抗错误 base

`BPU-INT-066` 将上述 index462/tag208 几何推进到真实集成 BPU：完整公开来源及
独立上游策略检查下，实际触发 allocation、agreement-hold、useful 1→2 与2→1。
为了增长 useful，只增加一个 semantic base-alias 返回节点，保持 ABTB index200，
分离两张 MicroTAGE 的 index，并要求整个 alias 窗口不训练原 key。
它不是从383个缺失物理地址继续枚举出来的场景。

最终隔离资格1 PASS、10/10语义格，精确新增70个 BPU 行键：其中66键恢复旧
物理范围，4键连旧范围也未命中。仅 lower shadow 的6796/6799和6828/6831属于
后者；不能把70键误称70个新 useful 功能点，也不能据此改动独立 UTAGE 分母。
完整资格与边界见 [集成 high-index useful](integrated-high-index-useful-20261013.md)。

## 集成 ITTAGE：目录生命周期关闭46键，但目标重写仍有独立失败

独立ITTAGE的1398/1398不证明集成层RegionWays满表路径。旧INT-062的反馈目标
均在PC region内，集成RegionWays仅116/162；剩余46键连旧全物理遍历也未见。
归因后的INT-067只用一组非别名几何、20个容量/复用/替换context，比较每一步所有
resident及完整目录/公开目标/真实反馈/PHR状态后，独立资格与完整生产精确关闭46键。
16个region是容量前提，不是bank/set笛卡尔积；不继续复制物理地址刷行。

另一个target-feedback需求暴露普通失败：已分配foreign region的反馈没有新table
allocation，provider confidence为0，registered update却带usePcRegion1。
目录7436项与PHR7094项检查正确，下一公开providerTarget仍回到PC region，
altDiffers也失配；正确alternate遮蔽本笔即时预测错误。因果指向
`Ittage.scala:320`的`!updateAlloc.orR`编码与`IttageTable.scala:259`的零置信度
目标更新。RTL未改，不新增XFAIL、不导入失败raw，不用RegionWays满行宣称需求完成。
见 [同一冻结epoch的正向资格、普通失败与发布复核](ittage-region-lifecycle-20261013.md)。

## 集成 MicroRAS：补齐在途操作组合，区分局部集成约束与动态缺口

原嵌套程序主要由S2 MainBTB修正推进，不能替代连续S1 call/return的前递/抵消。
INT-068以3个不同call和3个真实return，直接相邻或隔一条普通跳转，实际形成
S1-pop/S2-push/S3-push及S1-pop/S3-push。全部9寄存器/完整输出由reset-derived
参考比较，完整PHR与公开metadata关联、6笔真实退休及全部提交单元也比较。
16语义格闭合后，完整生产精确重现独立46键并集：MicroRas4、MicroBtb36、其替换器5、
RasStack1，旧全物理范围也均未命中。集成MicroRAS83→87/91，独立DUT91/91不变。

剩余133/134并非应当硬造的测试：BPU的`s3_fire=s3_valid`使`s3_ready=1`，
所以`s2_fire=s2_valid`，而`s2_override`又要求`s2_valid`。当前编译连接下
`s2_override && !s2_fire && call`局部矛盾；裸MicroRAS不受这个集成约束。
源码绑定复核了16种局部赋值和4项变异，不增加PASS或扣减91分母，也非全RTL证明。
180/181现由INT-069动态关闭：UBTB冷/MainBTB热中性跳转在S2修正，与较老call
及真实较年轻wrong-path CALL重叠。检查老返回地址前递、年轻pending冲刷、完整S2
修正/每笔最终S3目标，wrong-path不得进入最终metadata/main RAS；完整参考、六笔
真实退休和排空后10/10语义格闭合，集成MicroRAS至89/91。新原生10键包括该2键和
8个自然哨兵缓存键，不枚举bank。必须让taken/position/attribute产生差异，单纯错
target不会触发当前S2。见 [真实三方重叠与发布](neutral-micro-ras-correction-20261013.md)。
见 [输入及完整发布](early-micro-ras-pipeline-20261013.md) 和
[局部连接/守卫复核](../results/micro-ras-held-correction-local-review-20261013-v1.json)。

## TAGE：历史112个局部矛盾赋值与8个块头的后续复核

生产原生结果 **4,467/4,587**，120 个缺失键均位于 `rtl/tage/WriteBuffer.sv`。
当前缺失键与旧分类逐一相交：counter40、priority48、key-copy24，合计112，
均仍为零计数，没有把已经命中的行算入“不可达”。

本轮按当前源码重新执行现有审计：

```sh
python -m tests.tage.diagnostics.key_copy_audit \
  --report results/semantic-gap-review-20261013-v1/tage-key-copy-revalidated.json
```

结果见 [本次复核](../results/semantic-gap-review-20261013-v1/tage-key-copy-revalidated.json)。
例如 key-copy 路径要求 `!(H && S) && H && S`，或
`!(H && S) && H && !(!W || C || !S)`，枚举局部布尔取值均无解；四种源码
变异（删除优先级、削弱 clean 守卫、错目标行、错输入端口）均被审计拒绝。
这是精确局部两态条件证明，不是整个 WriteBuffer 的形式可达性证明。

另外8个键为871、966、1061、1156、1550、1578、1606、1634的相关 `else begin`
块头。当时审计正式分类的是赋值体，尚未把块头纳入重复可执行的证明输出；
因此仍记录为8个待分类键，不能把112直接说成120，也不减4587的分母。

### 2026-10-15：结合实际native producer/span，补齐八个块头的分类

079证明了“局部条件不成立”不能直接等同于“含该条件文字的DA行点不可能命中”。
因此这次不单纯扩展旧行号区间，而是同时检查三层证据：当前生成源码中的确切
guard与嵌套关系、两态布尔条件无解、每个缺失DA键的**全部**native `l/arm/S`
producer都来自被证明的那条分支。没有找到producer、存在额外/错误producer，
或矛盾分支居然有非零计数，都必须报错，不能把缺失或不一致当零。

[可重复复核入口](../tools/review_guard_gaps.py)已实际检查历史完整原生报告与当前
源码哈希，结果为：SC 336/336、TAGE 120/120个缺失键得到局部分类，无未分类键；
其中TAGE为112个赋值体加8个上述块头。TAGE的64个producer中，一组四个块头
落在clean-copy else的`S`范围，例如`l=849,arm=else,S=871-875`；另一组为
`l=1548,arm=else,S=1550-1553`等。非零的同anchor `if`不能混作这些else的命中。
SC的336个键对应16个producer，例如`l=365,arm=if,S=365-374`与外层hit/
内层not-hit赋值严格对应。

这是当前编译变体的局部条件与原生插桩关联，不是全RTL formal；不说明已经命中的
路径不存在功能缺陷，也不等于排除了更一般的模块功能点缺失。特别是TAGE026的
普通FAIL不会被这项分类豁免。**原生分母、命中数、功能点状态均不因此改变**，
不能通过重新计算“可达分母”宣称SC或TAGE已经100%。这批残差不适合再用bank/
set遍历追数字，应将新增刺激投入真正缺失的语义事件。

工具默认只打印汇总；只有显式`--output`才生成一份小型聚合分类报告，已有文件
一律不覆盖，不生成逐周期审计/trace。审阅坐标已从可删除的历史JSON移到
[固定变体目录](../tage/coverage/guard_catalog.py)，但目录本身不是证明：
每次仍需源码验证和native producer关联。pytest单测使用明确标注的合成native
fixture，不依赖旧结果文件，也不将合成计数当真实验证证据。

```sh
python -m tools.review_guard_gaps \
  --baseline results/production-ittage-directory-events-20261015-v1
```

该命令的真实产物、当前模块复验与负向检查见
[模型验收说明](semantic-reference-models.md#sctage写缓冲残差源码条件与原生覆盖点关联复核)。

### 集成TAGE不能套用独立DUT的上述分类

`production-micro-ras-events-20261013-v1`基线中`Tage.sv`另有71个未命中原生键。逐段核对当前源文件后的
实现位置分类如下；这是原生键归属，不是71个功能需求，也不是动态可达证明。

| 位置族 | 缺失键数 | 需验证的事件语义/归因边界 |
| --- | --- | --- |
| selector训练，3141等及3454–3531 | 39 | 合格conditional/owner、弱provider且与alternate/base分歧时，按实际正确方形成增减票；按selector聚合后T3提交，净零保持、边界饱和、其他selector隔离 |
| provider/alternate预测及metadata组合选择 | 18 | 真正有效预测事件的来源、置信度和selected provider/alternate关联，不能以组合候选被计算代替最终选择 |
| 分配候选优先级，1925–1982 | 5 | 需要分配时先选invalid，再选weak且not-useful，最后not-useful；还需真实选中与写入确认，不能仅从候选mask命中断言分配完成 |
| 分配失败老化，3440/3441/3446 | 3 | T3有效、需分配而不可分配、无reset-in-flight时递增；饱和且有效T3触发useful reset，计数归零并追踪表端完成 |
| provider useful候选算术，6805等 | 6 | 候选+1未命中；本身不证明对应branch valid或实际useful写入需求缺失，须关联真正更新资格 |

selector共8个寄存器，当前至少部分索引已有训练路径命中，不能把39键说成整个
selector算法完全未测；缺少的是特定provider-table/alternate-confidence上下文
及完整集成事件比较证据。它不是bank/set地址矩阵。
`Tage.scala:427–430`限定训练分歧，`:433`的entry有效资格和`:637–659`的按索引
聚合/T3提交共同定义事件；仅反馈送入或candidate改变不能记checked。

老化条件来自`Tage.scala:561,627–635`，属于全局生命周期事件，不是复制行。
正常255次有效失败可能是到达8位饱和状态的必要工作量，但不能换成遍历255个
bank/set，也不能把任意等待255周期视为255次合格失败。

上述基线的`suites/frontend/bpu/bpu`及`tests/bpu`未找到针对TAGE的`useAltOnNa`或
`usefulResetCtr`状态的独立checker/monitor比较；找到的`useful_increase/age`监视
属于MicroTAGE。SC provider准备过程确实使用TAGE并检查真实provider metadata，
但不等于完整selector/老化状态参考。因此上表是下一轮集成事件扩展优先级，
尚未登记PASS或将失败/局部未知项改为XFAIL。

后续072已实现selector独立checker/monitor和真实消费比较，完整生产精确关闭
其中11键，`Tage.sv`剩60键：selector31、预测选择17、分配候选3、失败老化3、
provider useful候选6。这里没有新增完整SRAM/allocator/usefulResetCtr参考。
见 [已发布事件需求和剩余分类](integrated-tage-selector-events-20261014.md)。

073随后进一步补全局失败累计/清零3键及四表清理地址推进48键，完整生产新增92，
集成`Tage.sv`还剩18键：selector0更新7键（3454..3461的实际原生键）、预测/metadata
5键（619,621,9951,9969,9973）、branch-slot useful候选6键（6805,6935,7065,7325,7455,7585）。
已命中的三处分配候选算术有部分来自无allocation需求的无效组合上下文，分配
优先级需求仍未据此关闭。selector0的下一候选前提是弱provider与弱MainBTB base
真实分歧；当前容量准备选择strong base，不需要再复制整套bank或255事件循环。
以上未执行前提不登记PASS；ITTAGE目录事件化及已有普通失败也未被本轮豁免。

## SC 与 RAS

SC **3,145/3,481**：剩余336键与现有局部矛盾赋值分类完全相交，
`WriteBuffer.sv`72、`WriteBuffer_8.sv`264。本轮只读复核了当前源码的
外层 `hit` 与内层 `~hit` 等守卫，没有生成新的功能 PASS，也未删除原生键。
既有证据见 [SC 局部分类](../results/coverage-sc-unreachable.json)。

另须区分集成BPU中的SC顶层缺口：`rtl/bpu/Sc.sv:1491,1531,1571`不是上述
336个WriteBuffer矛盾赋值，而是way1/2/3的`t1_writeThresVec`保留旧阈值分支。
`Sc.scala:506–511`先按同way的增减票得到candidate，再要求其落在640..5040；
越界时**整个更新被拒绝**，不是饱和到边界。普通net-zero、correct-used保持或
单纯增加若干训练拍，都不保证执行这个分支。

独立SC的BPU-SC边界用例已检查单票640/5040、四同way票642减4/5038加4的整体
拒绝及向内恢复，见 [已有独立场景](../sc/case/threshold_scenario.py)。
归因起点时，集成用例虽有完整reset-derived阈值/SC SRAM/PHR参考，但SC-used场景主要
在初值1130附近学习，缺少真实集成反馈下的上下界、拒绝和恢复证据。
way0的原生分支已有计数，也不能据此断言有效反馈下该行为已被验证：组合分支
计数本身不携带训练资格。下一轮应检查完整四阈值向量与非目标保持，明确metadata
来源和FTQ合法性边界，而非把三个复制行直接展开成bank/set遍历。
这些集成范围拒绝现已由070动态关闭；071再补内部/边界合格混合票抵消，事件版
52/52 reached/checked已完整发布。上述三行与独立SC336个矛盾键不混为一谈。

RAS前一基线 **565/585**：当时剩余20键均在 `RasStack.sv`，不能再笼统归到既有
enable-metadata缺陷。当前源码逐项检查给出以下边界：

- 508/512/516/520/524/528/532/536：每个 `else if` 要求 `!S && Pop && Nonzero && S`，
  与前一个同槽选择守卫矛盾；局部两态8种赋值无解。
- 542/546/550/554/558/562/566/570：位于push分支，却又要求pop。
  当前编译顶层 `dut/ras/RasDut.v:508,509` 分别按同一个两位action等于2或1
  产生push/pop，8种valid/action组合无同时成立者。此结论依赖当前顶层译码，
  **不适用于允许自由驱动push/pop的裸RasStack模块**。
- 598/600/601/602：BOS与commit的距离大于2时的回收路径。现由BPU-RAS-016独立
  资格和完整生产精确重现：有意丢失一/两次call退休通知，使用独立预期检查过的
  真实pre-operation metadata提交return/call，比较距离2保持、距离3回收、push优先，
  同代/跨代及后续持续操作。6上下文×6契约全满，870周期的全状态均比较。
  这是公开端口故障注入，不冒称正常FTQ流，也不伪造action0 neutral commit。
  见 [输入作用域和发布证据](ras-retirement-gap-20261013.md)。

只读记录包含源码、编译wrapper及原生报告哈希，见
[RAS逐键源码归因](../results/ras-gap-triage-readonly-20261013-v1.json)。这只是有边界的
源码/译码核对，尚未纳入独立全动态审查；它本身没有新增功能PASS。后续动态
场景独立增加一个PASS需求及4命中，当前569/585，剩余16键，不减少585的分母。
enable-metadata缺陷仍由其原strict XFAIL独立检查，不能拿它解释这些不同路径。

### 集成RAS的缺口与独立RAS不是同一覆盖实例

`BPU-INT-080`补的是集成BPU中“真实重复call检查点恢复+重放+真实return退休”，
不是为独立RAS的16个局部守卫残差枚举更多槽位。复用从reset独立拥有调用帧和
检查点的`RasReference`，连续比较公开投影与全部保留组，并检查每个真实后端
来源及S3返回目标。只用压缩组末项/新组首项两种语义上下文，没有bank/set遍历。

隔离合格场景相对`production-ittage-directory-events-20261015-v1`严格新增：
组末项`RasStack.sv:325,580`；组首项`325,330,580,748`；去重**4个DA键**。
分别对应恢复重复调用、计数清零分组、重复return提交递减及恢复组选择相关
路径；DA键不是功能点或分支数。6/7条实际事件规则各有reached/checked证据，
四组100%，已加入生产发布门禁。覆盖点通过率与原生分母均未裁剪。

两条真实DUT场景、27项兼容与945项模型/负向门禁均通过，同一最终源码epoch。
详见[输入边界、时序合同与严格差分](semantic-reference-models.md#集成ras真实检查点的重复调用恢复重放与返回退休080)。
这不是新的完整BPU覆盖数字，不更新独立RAS的569/585，也不豁免已知普通FAIL。
RTL/DUT/SDK均未修改或重建；完整BPU组合reference与全量验收仍未完成。

081随后补真实return检查点的恢复与重放：同组/跨组pop各配推测/保留前驱寿命，
四种上下文各六条事件义务，八组reached/checked均100%，没有物理槽位遍历。
严格隔离差分分别3/5/5/8，去重8键，其中580已由080覆盖；其余7键为
`RasStack.sv:749,752,755,756,827,831,832`。参考模型同时修复恢复时年轻未退休
owner未清除的问题，以自有逻辑操作前沿取消错误路径，再创建唯一重放owner。
29项兼容、1003项模型/负向门禁全PASS，独立RAS仍是原4普通FAIL/1严格XFAIL，
诊断原生569/585。详见[081语义与隔离证据](semantic-reference-models.md#集成ras恢复真实return先回滚再弹栈081)。
未修改正式全量分子、分母或RTL，完整BPU组合reference与全量验收仍未完成。

## 集成 BPU：优先新增输入语义，而不是物理重复

`BPU-INT-063` 用两个真实程序、实际反馈和模型控制的部分回绕，在完整 replay
与公开请求/响应比较后命中 lower slot4、upper slot7 fallback。独立结果相对
上述生产基线新增15个原生键，其中 shadow 7个是旧物理遍历也未命中的路径，
AheadBTB 8个则是恢复生产范围缺失的真实 counter 路径。
详细资格和精确差分见 [场景设计](shadow-response-gap-design.md)。

另外，行回退门禁暴露了旧 early-source 用例只检查 held-S1、依赖隐式额外接受
顺带命中流水线更新的问题。已有 `BPU-INT-017` 已补充两组相邻 resolve 反馈、
三次公开 MicroBTB target 读回和恢复双源后真正相邻接受的 S1/S3 比较；
恢复全部9个旧键并新增10个 MicroBTB 键。完整v2独立重跑重现上述25行的精确集合，
没有混入旧 raw。这10个新键在旧物理遍历中也全部为零。

下一类候选是稀疏条件分支流：在合法程序环中用无条件跳转分隔 conditional
反馈，使 shadow 写入之间存在可解释的暂停机会。先用纯输入 PHR/metadata
相位模型证明状态可以形成，再用真实 DUT 验证；不能按实际 chosen slot
过滤成功输出，也不能为了每个槽位再乘全部 bank/set。
现已完成 `BPU-INT-064` 的独立资格验证：稀疏 negative upper payload 返回时
选择真实较后 CFI，补 lower1/2/7和upper6共4个 fallback 组合；相对已发布生产
精确新增192行键，其中27个是旧物理遍历也未命中的 lower shadow 路径。
同范围完整生产回归已实际退出0并发布，精确重现独立192键增量、零旧键丢失。
详见
[输入阶段、计数器学习和失败前提修正](shadow-response-gap-design.md)。

后续BPU-INT-065把最高old survivor要求收紧到upper3/4/5。首轮slot4准备失败
说明反复暂停第一笔A会破坏正常阶段上下文；环境现在保持自然流，并将停流后
实际已接受写入的退休计入下一停止边界。3种状态×9项契约全满，精确关联新请求
返回old negative payload并选择较后CFI，完整独立重放后才采样。隔离增量分别
0/10/3键，去重10；最新完整生产精确重现并集，都是恢复旧物理范围路径。
只剩upper1 fallback 的完整 consumer 契约未通过。新冻结诊断已经做到回绕前
停流及排空，形成mask0x01/old hits0x02；真实公开旧payload返回正确，但后续
same-slot训练将新dirty清零，漏掉期望SRAM写回，正常FAIL、不新增XFAIL或覆盖信用。
所以不能再把这格称为“尚未证明读响应可达”，也不能提前结束测试登记PASS。
本笔counter0未改变，证明dirty/写回契约违例，不单独声称已丢失变化后的payload。
见 [slot1真实因果诊断](shadow-slot1-dirty-collision-20261013.md)。
见 [退休感知回绕设计](shadow-wrap-boundary-retirement-20261013.md)。
