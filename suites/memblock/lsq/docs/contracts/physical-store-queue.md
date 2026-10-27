# PhysicalStoreQueue：真实STA/STD、就绪、转发与写出组合

状态：**首轮、逐行缺口补例、完整公开阶段参考及独立UID审计已执行；`psq-expanded-05` 63例45 PASS/18 FAIL、39/45 checked，严格验收受六项失败语义阻止，NOT_PASS**。基线开源893e1580b，原始`PhysicalStoreQueue.sv` SHA `c1ea3980b9d75a42a68a0b31867102a8145ebd4932ebb055cc59be4b37bab166`。本体保留真实ForwardModule、DeqModule、EnterSbufferQueue与UnalignQueue，五文件闭包；Python只代理外部VSQ/ROB、STA/STD、load查询及总线，不替代内部子块。

## 1. 实际端口与生产者合同

- 原SV为119输入（不含clock）、333输出：两路Valid-only STA/STD、与上一拍STA对应的无valid S2属性、两路UQ请求、三路分阶段load转发、VSQ完整指针、Cache/Uncache/Sbuffer/WB、ready指针和64位图、deq/physicalUpper、异常。
- STA/STD的SQ只保留低6位，没有动态完整flags输入；必须由外部发行账本确保位于`[deq, physicalUpper)`当前代，两个同类端口不得同时写同槽。UQ及VSQ、forward保留完整双flag，必须检查四圈身份。
- 普通STA先接收VA/PA/size/unalign，下一拍同lane S2提供nc/mmio/memBackTypeMM/exception及isLastRequest；无valid字段不等于可以随意把旧S2用于新事务。TLB miss不置地址就绪，重试仍属同UID。
- 普通size编码0..4，对应1/2/4/8/16字节。跨16B地址分首/末请求，首请求保存原VA/PA/mask，末请求完成地址就绪；跨页第二PA必须经真实UQ，非跨页不能虚造第二页。
- NC/MMIO/CBO的许可来自真实VSQ preCommit/retired边界，不直接驱动内部committed；普通stream必须由递增的已分配物理区间和ROB许可构造，未分配或取消槽不能接收晚到写入。device NC编码5在源码属性表与1837断言存在张力，普通首轮不假称已证实可达，专项核查后区分接口与producer域。
- `validCnt`为虚拟`physicalQueueEnqPtr-deq`，可到128；仅64项可驻留物理写入。full不是简单物理64项满。WFI安全输出源2035常真且已被优化删除，没有实际WFI输入，不伪造动态控制测试；inactive源1745恒false同样不计动态覆盖。
- Uncache resp保留valid、idResp仅valid/is2lq，删除错误/ID字段不能伪造动态检查。Cache denied/corrupt、WB ready及ROB/VA/isHyper保留，继续严格检查错误保持与实际fire。

## 2. 独立领域与时间

外部账本记录每个UID的虚拟位置、当前物理代、VA/PA/size/原data、STA/S2/STD到达、许可、取消和真实完成。独立字节来源/顺序性质不得读取DUT内部数组。ready指针只越过连续就绪前缀；位图应对应真实输入历史且按原SV公开寄存延迟。commit/preCommit/retired/redirect存在输入寄存，首轮定向先核验相位，再冻结阶段参考，不能用额外随意Step修补。

forward保留原S0年龄→S1 PA/kill与当前bank→S2公开响应的时序合同，父块额外检查真实STA/STD写入、deq前后可见窗口和取消/同槽重用；已知Forward三类失败不是豁免。写出只计真实Sbuffer/WB/NC确认及随后sqDeq反馈，Sbuffer接受不等于PSQ释放。reset前后的控制、无reset流水/数据分开，不将中止算消费；公平排空必须UID守恒。

## 3. 用例前语义功能目录

| ID | 可读微架构行为及必需情形 | 真实检查义务 |
|---|---|---|
| PSQ-RESET | 空/活动/等待请求reset后旧事务无副作用 | 新UID在同槽实际完成，reset单列 |
| PSQ-WRITE | STA先/STD先/同拍、两lane与全部64slot | 原始地址、mask、data经真实forward/写出观察 |
| PSQ-STAGE | S1/S2正常、TLB miss重试、分拆首末请求 | 无早commit/错误memoryType，S2按lane配对 |
| PSQ-READY | 地址/数据独立位图、洞及连续前缀、stride/upper停顿 | 完整SQ ready指针与公开寄存位图 |
| PSQ-PERMIT | preCommit、retired、无许可、异常、阻塞头 | 未许可不写出，许可后按序完成 |
| PSQ-BYTE | 全部size/offset、跨word/line/page | 逐有效PA字节、第二页来自真实UQ |
| PSQ-FORWARD | 原数据、最年轻候选、缺数据/地址、PA/VA别名、精确等待 | 实际三lane响应/重放/依赖身份，不借用叶子通过 |
| PSQ-DEQ | 满内部流水/部分消费、前后deq可见窗口 | 单次释放与sqDeq反馈、无早释放或重复 |
| PSQ-SPECIAL | NC/IO请求保持、方向、Cache CBO四类、WB错误 | req/resp/WB身份与真实完成，保留Deq失败 |
| PSQ-RECOVER | 取消后缀、环绕恢复、S1/S2/STD/UQ同拍恢复 | 幸存不丢/取消不泄漏，晚到写不能污染新代 |
| PSQ-CAPACITY | 物理64/虚拟128、physicalUpper推进、forceWrite | 无越界发行/full空满边界与虚拟计数 |
| PSQ-REUSE | 普通完成及取消后多圈同槽复用 | 新UID新字节、旧异常/属性不得残留 |
| PSQ-CONCURRENT | 合法固定种子STA/STD/forward/写出/恢复并发 | 完整输入历史、所有UID公平排空及守恒 |
| PSQ-CHILD-FAULT | Deq WB错误/split wline、Forward别名/身份/mask | 用真实父级输入最小复现或具体producer不可达证据，不扩大为系统后果 |

## 4. 运行与覆盖闭环

先五文件原样构建、全部端口/编码独立核验，再跑定向真实写入→forward/写出/完成。首轮逐条分类本体和真实下级未覆盖DA：已有功能缺失情形或遗漏完整行为；只由对应实际检查驱动补例重跑。叶子DA/局部fault再现/本体行满都不是PSQ整体验收。后续范围保持StoreQueue→LoadQueue→LsqWrapper，不扩大为整个MemBlock。

## 5. 首轮缺口驱动的补例范围（用例前）

`psq-initial-01`21例16 PASS/5 FAIL，本体3733/5396、闭包4113/5817，首轮42项目录15 checked。独立审计577公开记录、181检查、36个真实forward响应、12个正常store实际完成；3个Cache错误在真实父级WB fire丢失、2个split在真实父级Sbuffer fire带错wline。仅证实PSQ公开输入可达，仍未验证真实VSQ/上游发射约束。

全部1704缺行（本体1663+真实依赖41）逐条保留在`psq-initial-01/line-audit-classified.json`，均为原合同已有功能缺情形，没有行排除：本体高槽STA/S2/STD/CBO保存与双lane、跨first_flag计数、redirect寄存；真实下级NC/IO、奇数尾复用、forward选择中间分组、UQ保存/消费/恢复。

下一补例先覆盖64slot×双lane×四圈普通真实写入→三lane转发→实际Sbuffer消费、128个逐head CBO（各物理槽两lane，四类操作）、NC/IO真实属性和完成；随后继续UQ/redirect/异常/随机及完整父级参考，不能因前两项高覆盖就停止。完整size/offset及新旧UID不共享值，所有已启动业务必须真实排空。

原首轮`PSQ-SPECIAL.wb_error`同时被无等待正常控制样例计checked过宽；新运行单列`wb_response`，严格`wb_error`只由背压保持到fire的用例填充。旧42项目录和快照不改，新目录43项；失败功能不能靠不触发背压的对照冒充通过。

## 6. 第一次补例证据与剩余工作

`psq-expanded-01`23例18 PASS/5 FAIL。本体3733/5396→5387/5396，真实五文件闭包4113/5817→5772/5817；剩45条全部再次分类，没有删分母。普通4圈256 owner及逐head128个CBO全部实际完成，独立审计从原始STA/STD/公开输出重建384分配=384完成、768个新forward响应、288个Sbuffer消费、128次WB及96个Cache请求；两个新长流各覆盖128种slot×lane组合。2947条连续记录、957检查、213份启动文件结束SHA、全部artifact/build哈希通过。见[PSQ阶段报告](../reports/physical-store-queue-20261018.md)。

剩余本体9条redirect输入寄存；依赖分别Deq12条NC/IO、ESB6条奇数尾第二输入、Forward3条低年龄候选中间分组、UQ15条保存/消费/恢复。`line-audit-classified.json`逐项解释为何普通四圈对齐窗口/双入仍未触发这些情形。

本节记录`psq-expanded-01`时的待办：当时仅定向公开probe及两个长流，尚无完整逐拍PSQ阶段参考、恢复/异常/随机和22项未checked功能。后续按第7～9节完成补例与审计；旧轮的范围和分母不追溯改写。

## 7. 第二次缺口补例的用例前检查义务

- NC/IO：两STA/STD入口分别生成memory NC、PBMT IO、device IO，S2属性严格按前拍同lane配对；请求背压、load方向idResp负例、store确认或真正resp/WB，必须由真实PSQ自动生成完成，不由测试伪造内部handleFinish。
- UQ：两个跨页store各经首/末STA及两项真实UQ保存非连续第二PA，等待地址前缀的ready再接受；真实Sbuffer先只消费首段，证明无early credit，然后四段原始字节和两个owner真实完成。
- 恢复：四项先只保留前两项，真实redirect寄存后检查取消槽地址/数据位图及ready指针回退；在途S1/S2/STD与恢复窗口并发单列，幸存先完成，取消槽以新VA/data重新发行并真正消费。旧数据写入无效槽不等于泄漏，必须用新UID公开结果判断。
- 非零head：先实际完成一个普通store使内部尾为奇数，再以物理窗口[1,65)填满64项；load SQ65读取SQ64（slot0）的低年龄域，随后全部原字节按序实际消费/释放。它补原“全部槽但对齐窗口”的遗漏情形，不缩小候选域或把叶子覆盖搬来。

## 8. 完整阶段参考与外部UID代理的用例前合同

参考用公开STA/S2/STD历史构造语义entry，以标量SQ序列描述就绪/许可/读取/完成阶段，组合已有独立Deq/UQ/Forward参考而不替换实际RTL下级。所有实际输入由独立解码器从被动引脚采样还原，逐拍检查公开输出及独立PA字节来源；perf输出无功能义务，不以内部数组作答案。首个空时钟前的无reset credit、以及由它派生的父级RegNext输出有一拍未知启动窗口，不能把随机初值当真实完成；之后包括活动reset的每一拍均继续检查。

外部VSQ/ROB/STA/STD/总线代理与模型账本分开：维护UID、128项虚拟分配与64项物理发行窗口，地址/数据独立乱序到达；按前拍STA构造S2、跨页UQ占有、普通退休与特殊preCommit、真实请求后的唯一响应，最终根据公开Sbuffer/WB/NC确认和SQ释放完成UID。不读取参考内部entry/指针决定刺激或完成。CBO STA/STD仅在其ROB头许可域发行，而不是任意年轻CBO投机执行；该限制不规避已保留的普通split旁zero严格反例。

固定种子混合流量保留CBO四类、NC/IO、cross-word/page和普通size、独立ready/response等待；随机结束必须公平排空。已有Forward/Deq错误遇到即普通FAIL，不读问题表，不改变安全预期；另有必要条件对照时单列范围。活动reset中止单列并要求同槽新UID实际完成。行满后仍必须完成剩余语义，不以模型校准的4例替代完整父级检查。

`psq-model-expanded-01`随机UID134在原生PSQ实际WB/出队后没有自己的零写，独立actor完成守恒失败；首版Deq参考的writeZero阶段过宽地把任何旧Sbuffer消费当zero完成。新增第44项`PSQ-SPECIAL.zero_owner`，严格要求消费的片段属于当前zero完整SQ身份且wline为真；收紧已有参考，不修改RTL，不把这个新所有权功能遗漏当DA缺口。最小父级补例将保留旧普通项在真实子队列、按ROB先退休普通项后给zero许可，检查zero真实WB之前必须已有自己的Sbuffer零写。

首版完整参考还有两个启动/reset校准错误：无reset child credit的OLD未知传播到父级RegNext一拍、活动reset的retired/preCommit/redirect异步清零。均已按原SV限定未知窗口/修正异步投影，旧4个setup ERROR和reset假失败快照不重写。另两个随机失败分别复现wline污染和Forward完整SQ依赖身份错误，继续保留严格失败。

补真实STA/STD驱动的三lane跨word VA别名、两段16B查询的PA写范围安全检查，未定义字节不能因为VA参考也同意就判正确；三个完整域随机种子仍保留。第45项`PSQ-CONCURRENT.controlled`单列不含zero、最多48活动owner（load落在当前物理窗口）的必要条件对照，仍含NC/IO/其他CBO、跨word/page、重试、独立写入和背压；它不能填补完整域`seeded`或任何错误功能。

剩Forward三条选择分组需要低年龄**物理slot48..63**的候选：生成代码先反转位序，故head1时仅slot0低域还不足。补head60/upper124、SQ123在slot59的真实三lane原字节查询和完整排空；这仍是已有功能的缺失情形，不以覆盖工具异常排除该行。

第二个必要条件随机对照在`psq-expanded-04`暴露actor的过强时限：NC在tick70确认时前面还有两个普通store同拍消费，普通项到tick72释放，NC进入deq头窗口后于tick74释放；这是合法的延迟，不是NC错误。特殊owner应检查真实完成后不早释放并公平排空，不能强制“确认下一拍必释放”；普通Sbuffer寄存credit的规定延迟仍保持严格。修正actor并保留旧失败/源码快照，不调整DUT或掩掉真实事务丢失。

## 9. 完整冻结轮及未验收语义

`psq-expanded-05`为63例45 PASS/18 FAIL，45/45 reached、39 checked；本体5396/5396、五文件闭包5817/5817 DA，原45条缺口全闭合，无行排除。独立`lifecycle-audit.json`核验7424条连续公开记录、1254个probe显式比较、3870条完整参考记录（3858条完整检查，12条真实失败停点）、226份启动源码结束SHA及全部artifact/build哈希。

独立actor重放1429个UID=1097完成+1取消+3 reset中止+328失败保留；3条reset与1条取消的同槽新UID完成见证。另两个全槽长流合计384个owner全部完成，不与actor分配重复；未把所有定向probe声明为完整UID重放。两个必要条件随机种子各300 UID公平排空通过，三个完整域种子仍普通FAIL。

| 未checked语义 | 失败证据 | 限制 |
|---|---|---|
| PSQ-FORWARD.alias | 3个真实父级lane返回老PA字节，无重放 | 未连接真实LoadUnit |
| PSQ-FORWARD.range | 两段×3lane标记没有store来源的字节 | 连续真实size mask，不是任意孔洞压力 |
| PSQ-SPECIAL.wb_error | 3个实际WB fire丢错误7/19 | 真实VSQ/Backend背压组合仍待上级 |
| PSQ-SPECIAL.split_wline | 2个实际尾段fire及1个随机valid污染 | 普通split旁zero；上级CBO发射约束待证 |
| PSQ-SPECIAL.zero_owner | 最小例实际WB/SQ释放而零写0次；随机flush提前 | 新DEQ-ZERO-001，原子块参考也已收紧 |
| PSQ-CONCURRENT.seeded | zero所有权、wline、SQ身份各1种子 | 未完成UID保留，不能以对照代替排空 |

后续真实StoreQueue必须继续检查VSQ→PSQ许可/恢复和PSQ→VSQ释放反馈；不是把这些未验收语义标为完成。原始RTL/Chisel未改，问题表不参与参考或跳过。

## 10. 真实StoreQueue反向驱动的合同补全

真实`sq-expanded-03`已复现Forward三类、WB、split wline、zero owner；不是外部VSQ代理独有。另发现`DEQ-FINISH-ORDER-001`：旧普通项仍在Sbuffer背压时，年轻NC确认或IO实际WB后，第二head的handleFinish被无身份PopCount加入释放计数，使旧SQ0未消费就释放。补第46项`PSQ-DEQ.special_order`及3个PSQ probe；首批`special-order-hierarchy-01`3例均真实失败。旧45-bin/63例证据不改写；收紧共享Deq参考为完成身份的连续年龄前缀后，须新增完整回归检查，不因已有5817/5817 DA豁免此遗漏功能。
