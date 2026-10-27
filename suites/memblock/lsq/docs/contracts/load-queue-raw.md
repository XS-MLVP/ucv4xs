# LoadQueueRAW：地址迟到的老store对年轻load的最老违例恢复

状态：**按本合同完成当前配置独立UT和覆盖迭代。** `raw-expanded-01` 32/32 PASS、本体4005/4005行、真实闭包5139/5139行、60/60语义checked；另有独立公开输入历史审计，详见 `docs/reports/raw-20261018.md`。固定开源基线中的 `LoadQueueRAW`，56项，3路load查询、2路store地址输入；父DUT保留真实FreeList_1、LqPAddrModule_1、LqMaskModule及流水辅助块，未用已验收叶子模型代替硬件。此结论不替代LoadQueue/LSQ组合验收，也不消除RAR缺陷。

## 1. 微架构职责与实际端口

已执行load仍可能早于一个尚无地址的老store读到旧数据。RAW记录这些load；store地址到来时用地址和字节mask找出更年轻且已有数据的冲突load，每个store端口输出其最老违规load的rollback，另外选两个rollback中最老者训练MDP。

- load输入：valid/ready、ROB(flag/value/isFormer)、SQ(first_flag/second_flag/value)、48位paddr、16位mask、dataValid、isRVC、FTQ(flag/6位value/5位offset)、64位checkpoint_id；每lane有1/2拍revoke。**没有load查询resp端口**。
- store输入：两个Valid-only流，含ROB、FTQ flag/value/offset、isRVC、paddr/mask、wlineflag、tlbMiss；不捏造ready或握手背压。
- 控制：redirect与stAddrReadySqPtr；输出lqFull、两个rollback、实际保留字段的mdpTrain及两个6位事件值。
- rollback的load ROB/FTQ flag/value/offset、isRVC、checkpoint及store FTQ flag/value/offset、isRVC要逐字段比较；store的FTQ flag由真实 `DelayNWithValid_160` 子实例直接驱动top输出，不能因top无assign误判为未驱动。load pc/target、rollback level等已优化删除，不虚构绑定。mdpTrain只保留双方FTQ value/offset、isRVC及valid，无ROB或FTQ flag输出。

## 2. 合法年龄与分配所有权

SQ实际为64物理项×2=128逻辑项，另有first_flag区分128项的环；second_flag是逻辑位置的第6位，不是普通单flag64项队列。参考以绝对SQ序号解环到256范围，合法活动窗口小于128；stAddrReadySqPtr只向前推进，需测试63→64、127→128和多圈。ROB仍是160项、每项former/latter两个slot；所有相关年龄在合法半环窗口内，查询到达可乱序。

只有valid、SQ位置在地址就绪指针之后、且未被当前redirect取消的load才需要新槽。三个lane的offset按前方**需要分配**的lane数压紧。FreeList启用预分配：ready依赖已预告容量，不能简单用当拍空闲数替代，返回新槽后可能还有额外预取等待；lqFull对应实际空闲池为零，不是RAR的6槽预留门限，也不必与所有ready同拍相等。

参考使用独立可用ID/回收账本，分配只消耗边沿前可用前缀，不读取DUT内部索引、位图、矩阵或选择寄存器。记录包含UID、原始元信息、解环ROB/SQ年龄及字节/地址语义。

## 3. 冲突语义和最老选择

store触发时在旧记录快照中筛选：已分配、load ROB slot比store更年轻、load dataValid、当前redirect不取消该load、当前revoke不撤销该条；然后检查partial地址相等及16位mask相交。

- partial地址是paddr[27:4]，低4位由16字节mask表达，高于bit27的地址被丢弃，可有保守alias，不能断言不同48位地址永不冲突。
- wlineflag=false要求相同16字节word；true忽略partial地址低2位，即同64字节line，并**仍要求mask相交**。翻转word/line内外边界、高位alias与每个mask bit需有正反例。
- dataValid=false、同ROB slot或较老load、无mask重叠、不匹配地址及无效store都不能产生有效rollback。
- 每个store端口选最老ROB slot，不按分配先后或物理槽号；same-entry former早于latter。相同slot的合法重复记录应有一致的恢复身份，不以任意不同元信息的歧义输入作为普通合法随机。
- 两个store端口彼此独立，允许同拍不同违规load；mdpTrain在有效rollback中选最老，年龄相同时端口0优先。

## 4. 写入、选择与取消时序

地址/mask写入有真实2级写流水；store的地址/mask先寄存，与旧allocated/datavalid/年龄/revoke检查对齐，再经过8项分组的两级最老选择。当前56项配置为 `ceil(ceil(log2(56))/log2(8))+1 = 3` 级寄存：输入在边沿N接受，预期在N+2后产生rollback（包括N共三个边沿），先用最小原生用例实测确认。

- 同拍新分配不参与当前store的旧状态检查；前一拍分配在需要的CAM比较时刻应已可见，不能任意插入空拍来掩盖写对齐问题。
- store采样同拍的revoke显式排除候选；更晚revoke不等于源码没有的选择流水取消，需按实际旧快照检查。
- redirect在候选采样、组选择及最终输出的窗口都过滤应取消的load；不能只在store输入边沿过滤。保留老项、flushAfter/flushSelf、former/latter和连续redirect需检查。
- stAddrReadySqPtr越过、redirect或revoke使记录失效，合并单次free；同拍地址指针回收不在entryNeedCheck条件内，不擅加过滤。记录被清除不等于FreeList容量立即返回。
- 返回流水保证槽复用不能污染在途选择；需要实际复用、旧写/旧store响应与新记录身份隔离，而不只看line写过。

## 5. 性能、复位和don't-care

perf0为req.fire数的两级寄存事件（0～3，含不分配的fire），perf1为“任意rollback有效”的两级寄存事件（0/1，不是两个rollback数的和），都不是累计值；需从公开历史核验实际相位和高位零。无效rollback/train的payload不比较；未初始化CAM内容不单独作为正确答案。

reset期间所有valid/revoke关闭，至少保持6拍并暖机，取消旧义务；只有reset后旧条目负probe和新条目实际rollback证明才能计活动reset通过。禁止靠reset消除未完成回收或在途响应而当作完成。

## 6. 用例前功能点

| ID | 人类可读行为 | 必需情形和真实检查 |
|---|---|---|
| RAW-RESET | 初始及活动/在途复位不泄漏旧条目和恢复 | 空闲、占用、store选择途中reset；新条目实际rollback |
| RAW-ALLOC | 只在存在未就绪老store时记录load | 三lane、稀疏need、SQ指针等于/早于/晚于、当前redirect取消；后续唯一store证明记录存在或不存在 |
| RAW-CAPACITY | 预分配ready与真实full正确表达容量和返回时机 | 56项、余1/2/0项、预取等待、回收再分配、多轮复用 |
| RAW-ADDRESS | 16字节word/64字节line及截断alias比较正确 | wline开关、逐位地址、不同offset、高位保守alias |
| RAW-MASK | 只有交叠字节才违规 | 16个单bit、零mask、多bit、部分交叠、wline仍需mask |
| RAW-ORDER | 冲突只针对更年轻load，并选最老违规项 | 老/同/年轻、former/latter、ROB160跨界、乱序到达、组内/跨组最老 |
| RAW-DATA | 没有有效数据的load不能引起恢复 | dataValid真/假、过滤后选次老有效项、复用重新初始化 |
| RAW-PIPELINE | CAM写、store采样、最老选择和元信息对齐 | 紧邻写读、同拍新分配不可见、连续store、双store、精确N+2响应 |
| RAW-REDIRECT | 选择不同阶段都排除被取消的load并保留幸存项 | flushSelf/After、各阶段、连续redirect、相同ROB边界、释放后的负probe |
| RAW-REVOKE | 本lane的1/2拍撤销只关联真正分配并正确过滤当前store | 两窗口/同时窗口、无历史、nack历史、同拍新分配和查询、晚撤销的旧快照边界 |
| RAW-DRAIN | 地址就绪指针/取消后的槽位最终恰好回收 | 部分/全部、SQ多flag回绕、多原因合并、回收流水、全池复用 |
| RAW-ROLLBACK | 每个store的最老load恢复身份不串端口或流水 | ROB/FTQ/RVC/checkpoint和store元信息逐字段比较，连续/双端口与空响应 |
| RAW-TRAIN | MDP选择两个rollback中最老者且同龄端口0优先 | 两端口正反组合、不同年龄、同一load、全部无效；比较实际保留字段 |
| RAW-PERF | 事件区分fire/分配及rollback OR/数量 | 0～3fire，0/1/2个rollback，两级事件延迟，reset暖机 |
| RAW-IDLE | 空闲和禁用payload不产生分配或恢复 | 空/占用/满池、payload毒化、合法流水推进不误判 |

功能覆盖分reached/checked。分配、回收、过滤、复用都要等待有效公开rollback或明确负probe/真实容量证明，不能仅看参考对象变化。多个候选仅证明最老一个，不能把所有隐藏记录标成已检查。

## 7. 首轮与覆盖闭环

先实现空池、最小分配、单store违例/无冲突、真实字段和N+2相位；保留首轮原生行与语义缺口。逐行定位分配字段、分组选择、真实CAM/FreeList/辅助流水，分类为已有功能点缺少情形或整项功能缺失，补用例再跑新目录；最终保持所有失败和未通过边界，不用smoke或叶子结果替代父块验证。

RAR的开放问题RAR-REL-001不在本DUT中，不能靠RAW通过把RAR或LoadQueue标成通过；后续真实父块仍需保留该问题。

## 8. 首轮实测及补例前缺口分类

原生构建/实例化走钟：`results/builds/20261018T045549413157Z-load_queue_raw/`，12份原样RTL。`raw-initial-01` 为3/3 PASS，实测确认输入边沿N→N+2 rollback及逐字段元信息；本体1298/4005=32.41%，语义13/59，真实闭包1963/5139行。

本体2707条缺口逐项归类：277条为各槽dataValid的不同load入口路径；113条为store入口1的候选快照；2103条为槽位ROB/SQ/FTQ/RVC/checkpoint身份写入；2条为load lane2的revoke索引历史；212条为最老分组/第二store通道元信息。另真实FreeList缺397条、地址CAM缺40条、mask CAM缺32条；八份实际流水辅助模块的77条插桩行首轮已覆盖。以上都属于既有功能点的情形缺失，不排除可达行，另存人工语义映射。

补例先明确：所有三个load入口各覆盖完整56项并分别用两个store入口唯一探测；各回收通道长积压和多轮56项复用；打乱分配顺序后的组内/跨组最老选择；16个单字节及零/不交叠mask；地址bit4～27区分、bit28～47保守alias、word/line和offset；三个选择阶段的redirect、1/2拍revoke及晚revoke旧快照；SQ两种flag和ROB160回绕；完整容量及预分配额外等待、真实回收和复用；两个store连续/并发、TLB miss、训练同龄端口0优先、事件OR而非计数；活动和在途reset、禁用payload与合法并发随机。

正向覆盖只在对应job真的产生有效公开rollback后checked；被redirect或tlbMiss抑制的job不能完成“地址命中/相交/相邻写读”等正向证明。负probe须有有效store且无TLB miss/在途redirect干扰；回收需旧记录正probe后再负probe，非分配需紧接下拍store采样，不能等自动回收再声称没分配。

可观察性特例：RAW没有load响应，rollback又要三级寄存，**一拍revoke之前不可能先得到该条目的正rollback**。其删除不能伪造正probe，改用真实满56项时的精确容量证明：最后一次接受后full、revoke后不提前ready、只归还指定数量、返回同槽的全新记录实际正rollback，并对旧地址做负probe、其他记录做幸存检查。仅在旧池真实full且替代生命周期已经公开证明时，允许该容量证明完成一拍revoke删除；普通回收仍用先正后负。测试和报告必须明确这种证据边界。
