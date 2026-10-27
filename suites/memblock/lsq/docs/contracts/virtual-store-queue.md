# VirtualStoreQueue：store区间快照、预提交、退休与恢复

状态：**功能点先于用例定义；完整42例40 PASS/2接口FAIL、3125/3125 DA、54/55 checked，公开历史已审计，严格验收仍NOT_PASS。** 目标为开源893e1580b的原样`VirtualStoreQueue.sv`，真实父实例见`NewStoreQueue.scala:2137`；源码`VirtualStoreQueue.scala`，不使用带SnapshotInterval=4且不满足当前require的独立Main配置。

## 1. 当前配置与公开接口

- 物理SQ为64项，虚拟队列128个store uop，每uop保存`numLsElem`与exclusive物理`reqEndPtr`快照；SnapshotInterval=1。虚拟128项容量和物理flow容量不是同一计数。
- 8个Valid-only dispatch入口，各有valid、needAlloc、ROB(flag/value/isFormer)、numLsElem5和完整SQ双flag/endPtr；原SV没有reqStartPtr、uopIdx、isVec或分配响应输出。
- ROB输入只有head指针，没有commit向量。PSQ反馈是完整deqPtr和deqCount.valid，**没有deqCount.bits端口**；不能虚构反馈数量字段或用内部寄存器作参考。
- 输出redirectPtr(valid+完整SQ)、preCommitPtr(valid+完整SQ)、retiredPtr、physicalQueueEnqPtr、headRobIdx、empty和sqRecoverStall。`enq.canAccept`虽在Chisel定义、内部allowEnqueue仍影响接受，但未保留为公开端口；不能伪造ready或覆盖删除接口。

## 2. 合法事务和时序约束

1. dispatch按lane顺序压紧`valid && needAlloc`的store uop，每项numLsElem为0～16，物理end是此前物理tail加flow数；0流项仍是一个真实虚拟uop，end保持。稀疏lane、非store needAlloc=false、valid=false的旧payload须分别检查。
2. 外部producer负责容量与恢复阻塞，不向满的128项VSQ或已观测恢复stall时发送新dispatch。物理SQ允许先预留虚拟区间而超出当前64项物理窗口，但距离不超过虚拟容量128且完整SQ比较不出现半圈歧义。满池边界不利用未公开canAccept来构造普通随机接受假设。
3. ROB按程序顺序，160 entries、双slot former/latter；相等ROB entry不等于相同slot，退休比较和preCommit匹配保留isFormer语义。dispatch的end快照来自合法分配，不任意填位拼接。
4. ROB head前移到store之后才表示已退休；store**恰处ROB head**仅可preCommit，不能冒充已退休。preCommit允许真实PSQ提前写Sbuffer并回馈deq.valid；该反馈必须对应已被许可、实际消费的完整物理前缀，不能在尚未许可时虚构出队。
5. `fromPhysicalQueue.deqPtr`表示已消费的exclusive物理位置；deqCount.valid为消费脉冲，不以任意deqPtr的静态值替代消费事件。合法普通反馈每拍至多消费2个physical flow；多flow uop需整个end被越过才释放其VSQ记录。
6. redirect按完整ROB/flushSelf取消年轻后缀。若旧ROB head之前仍有应退休uop，先release这些已退休项，锁存redirect前head，再walk恢复；不能用取消覆盖尚未完成的退休记账。redirect同拍dispatch仅为UNIT-INTERFACE恢复碰撞边界：实际LsqEnqCtrl把`valid && !redirect`寄存一拍，而MemBlock的redirect也延迟一拍，正常生产者不产生该同拍组合（LSQWrapper.scala:499-502、CtrlBlock.scala:818/830/867、Backend.scala:235/578、XSCore.scala:150/210、MemBlock.scala:494/1055/1058）。合法对照应将dispatch放在redirect前一拍；两者都保留，不能只用可通过分区替换原边界压力。
7. 普通生命周期等待实际preCommit/retired/redirect输出和最终empty；取消后用新UID占用被取消虚拟/物理区间，并等待实际许可/退休，不能写入即记checked。reset中止单列，不当普通完成。

## 3. 分阶段公开时间合同

- ROB head在idle每拍捕获；release/walk期间保持redirect前head，避免后续ROB输入改变已退休范围。
- 接受dispatch的边沿保存ROB、flow数与exclusive end；physicalQueueEnqPtr取当拍最后一个被接受lane的end。needAlloc=false/valid=false不影响压紧、快照或tail。
- 按已捕获ROB head或PSQ消费形成最多8项的连续虚拟退休前缀；记录先释放，随后虚拟head推进，再按前缀flow总数推进公开retiredPtr。参考以延迟事件队列记账，不把virtual uop数当physical flow数。
- preCommit逐uop遍历恰在ROB head的记录；其有效payload为该uop的end快照，headRobIdx是对应ROB身份。preCommit持续valid时可能保持最后一个被许可end，不将重复观察误记为新事务。
- redirect生成取消集合后，下一拍统计并回退虚拟tail，再下一拍选幸存最后一项的end；全取消/已空时使用已退休物理位置；再输出redirectPtr.valid。若先release则整体延后。physicalQueueEnqPtr在真实redirect输出被采纳的下一边沿恢复，不能提前更新或读内部恢复寄存器作答案。
- sqRecoverStall覆盖release/walk和实际恢复流水；恢复valid payload、空队列、preCommit禁用窗口按实际相位比较；连续redirect单列检查，不假设第一条自动完成。
- 原SV有`always @(posedge clock or posedge reset)`，reset断言在DriveStable之前已清空队列控制与tail；pre-edge必须检查已异步清空的empty/stall/redirectValid/physicalEnqPtr，不能仍期待旧活动队列。另一个`always @(posedge clock)`保存未reset的ROB/payload/部分退休流水，需要空闲reset时钟边沿收敛；保持3拍后恢复所有已定义输出检查。无valid的preCommit/redirect payload、尚未获许可时的headRobIdx为don't-care；不比较不初始化数据，不计作功能通过。

## 4. 用例前可读微架构功能点

| 功能组 | 必需行为/情形 | 实际检查义务 |
|---|---|---|
| VSQ-RESET | 启动、活动中、恢复中reset中止 | 实际输出回零/empty/stall收敛，新UID完整生命周期 |
| VSQ-ADMIT | 8lane、稀疏/密集、needAlloc/valid门控 | 真实最后接受end及后续preCommit/退休身份 |
| VSQ-INTERVAL | 0/1/2/多flow和16上限，不同uop共享ROB | 快照end和retiredPtr按flow总和，不按uop计 |
| VSQ-SNAPSHOT | 全128虚拟槽、完整双flag跨64/128/256边界 | 后续许可/恢复/退休重建真实分配end |
| VSQ-ORDER | 只有连续程序前缀退休，不越过未退休head | 头阻塞、8项批次、尾短批次、完整ROB身份 |
| VSQ-PRECOMMIT | ROB head同slot逐uop预许可，former/latter不同 | valid/end/headRobIdx精确相位，非head不得早许可 |
| VSQ-RETIRE | ROB head越过记录才退休，最多8uop/拍 | 独立flow账本、输出延迟、无重复/丢失 |
| VSQ-RELEASE | 已预提交PSQ实际消费释放，脉冲门控 | 部分多flow不释放、跨越end才释放、最多两项反馈 |
| VSQ-REDIRECT | flushSelf/flushAfter、零/部分/全取消 | 真实取消后缀、幸存end和有效redirectPtr |
| VSQ-WALK | idle直接恢复与先release再walk | 锁存ROB头、stall完整窗口、已退休流不被取消 |
| VSQ-RECOVER | 空恢复、幸存快照、连续恢复 | 输出次数/有效相位、真实exclusive物理尾 |
| VSQ-RACE | redirect/dispatch、退休/消费/恢复碰撞 | 无重复退休、不遗留幽灵分配、优先级明确 |
| VSQ-REUSE | 虚拟槽/物理区间回绕与取消后复用 | 新UID后续实际许可和退休，旧快照不污染 |
| VSQ-CAPACITY | 虚拟128uop边界与物理flow边界区别 | 容量producer约束，接近边界时不冒用删除ready |
| VSQ-IDLE | 无效payload、空闲保持 | empty及无伪redirect，后继新事务正确 |
| VSQ-CONCURRENT | 固定种子合法dispatch/ROB/PSQ代理 | UID守恒、取消/退休分列、公平排空 |

## 5. 运行与覆盖闭环

先核对原SV全部真实引脚与53文件基线，原样Picker构建并实例化走钟；首轮建立reset、基本分配/preCommit/退休与恢复相位的逐拍原生证据，再分析本体DA逐条缺口。对可达缺口分清既有功能缺失情形与整个功能遗漏，补例后用新目录重跑。即使本体DA满，也须完成上表语义、生命周期和公开历史审计；父StoreQueue/PSQ的真实连接另做组合验证，不以本合同或build smoke替代。

## 6. 首轮运行后的逐项缺口分类与补例前计划

原样build/实例化走钟已PASS：`results/builds/20261018T091203225287Z-virtual_store_queue/report.json`，SV SHA为`61685efc3ab12cba8d0695f23d033929b8ead3a30688d71dd51ecf2644bda822`。静态公开端口核对85输入/19输出、256样本/4非法拒绝（不是功能通过）。`vsq-initial-01`原生13/13 PASS，本体1438/3125 DA（46.02%）、32/55 checked，174份启动文件结束SHA一致，仍不是完整验收。

首轮1687条未覆盖DA全部逐行保留，分类为**已有功能的缺失情形**，未发现必须另增整个功能组：

- 6477～14274的1680条为slot8～127保存ROB/numLsElem/物理end快照（每slot14条）。对应既有VSQ-ADMIT/INTERVAL/SNAPSHOT/REUSE。补8入口各自遍历全部128虚拟槽，按0/1flow令物理在途区间不超过64；每块实际退休后合法PSQ消费释放物理前缀，再进下一块，覆盖虚拟与SQ双flag回绕。成功证明必须由退休/恢复结果而非写行命中提供。
- 15848～15857的7条为release/walk状态路径。对应既有VSQ-WALK/RETIRE/REDIRECT/RECOVER。补redirect前已有ROB退休前缀、release期间改变外部ROB head但锁存范围保持、之后只取消年轻后缀；检查真实物理retired与redirect输出及新UID复用。

原始`line-audit.json`的needs_review不改写，另存`line-audit-classified.json`覆盖全部1687行的语义归类。其余未checked功能按第4节继续补同ROB多uop、former/latter、PSQ preCommit消费/partial/valid门控、空/全/零取消、相邻恢复、活动/恢复reset、合法随机及最终排空；不能只补两片RTL行就验收。

`vsq-expanded-01`完整34例30 PASS/4 FAIL、本体3125/3125 DA、52/55 checked。其中2例活动/恢复reset为检查器未处理异步断言相位，按原SV改正pre-edge合同，不是RTL缺陷；旧证据与176份结束源码SHA保留。另2例同拍dispatch+redirect实际返回恢复end2而非幸存end1；已通过完整真实上游路径核对限定为UNIT-INTERFACE边界，继续保留普通失败并补3lane合法前一拍对照，不混称生产者合法缺陷。

`vsq-expanded-02`完整37例35 PASS/2接口FAIL、3125/3125 DA、54/55 checked；修正后的活动/恢复reset和3个合法相邻拍对照均通过。3228条公开历史独立审计，1573分配=1541退休+28取消+2reset中止+2失败保留，1024个入口×虚拟slot成功见证；176份启动文件结束SHA一致。还需强化恢复快照和取消后同槽复用的跨圈交叉：计划将物理位置合法推进到0/63/127/191/255，虚拟head推进到124附近，分配跨128边界8项，保留3项/取消5项，再用5个新UID逐槽覆盖原取消区间并实际退休；检查完整SQ恢复指针，不能仅凭前一轮55个粗语义bin代替这些边界。

`vsq-expanded-03`已完成上述5个跨圈补例，完整42例40 PASS/2接口FAIL；3125/3125 DA、55/55 reached/54 checked。4531条连续公开历史审计，2258分配=2201实际退休+53取消+2reset中止+2失败保留；1024个lane×slot成功见证、36条同槽新UID退休见证（跨圈专项25/25）与178份启动文件结束SHA核验通过。完整结论和域边界见[VSQ报告](../reports/virtual-store-queue-20261018.md)。普通生产者分区未发现失败，仍保留VSQ-RACE.dispatch_redirect边界未通过，不宣称整个接口通过。
