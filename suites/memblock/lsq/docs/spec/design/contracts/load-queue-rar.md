# LoadQueueRAR：年轻已释放load的保守违例检查与槽位回收

状态：**用例前合同，尚未功能验收。** 目标为开源 `LoadQueueRAR.scala` 的实际生成 `LoadQueueRAR`，保留真实96项FreeList和RAR地址CAM及三个直连辅助模块，六文件闭包。已验收叶子模型只能作为本工程独立参考的语义组件，不能替换父DUT中的硬件。

原样闭包提取/逐文件哈希、Picker原生导出和实例化走钟已通过，构建报告为 `results/builds/20261018T041257034272Z-load_queue_rar/report.json`（相对LSQ根目录）。现已实现独立参考和功能用例；`rar-expanded-01` 为27通过、1失败，本体行覆盖3898/3898，语义50/51。失败是前拍release窗口，不能因行覆盖已满而视作功能通过。

## 1. 业务语义和真实接口

RAR记录“仍有更老load未完成”的已执行load，用来判断一个更老load到来时是否遇到了同地址域、已经被cache release（或按NC处理）的更年轻load，要求保守重执行。它不是普通FIFO，也不是选择最老指令的模块。

- 3路req/ready查询，每路ROB(flag/value/isFormer)、LQ(flag/value)、48位paddr、dataValid、nc，以及各自1拍/2拍revoke；每路输出resp.valid/nuke。
- 真实输入还有redirect、48位cache release和来自VLQ的ldWbPtr；LQ=120、ROB=160的环形域不能当作128/256项。
- 公开输出lqFull和两个6位性能事件。源码`validCount`在当前top中已删除，不能绑定为观察点；只验证实际可见的容量门限/ready和回收行为。
- `lqFull`表示空闲池少于 **6=2×3** 项，提前禁止双半部重放反复唤醒；不是“一个槽也没有”。即使lqFull为真，分配ready仍可能允许使用剩余槽位，不能把二者强行等同。

## 2. 合法域与所有权

查询到来的顺序可不同于ROB/LQ到达顺序，不能用分配先后代替微指令年龄。输入ROB与LQ指针处于相应合法半环窗口；ROB former早于同entry的latter。ldWbPtr只向前推进，测试应包含120项非2幂回绕和ROB160项回绕。

只有 `req.valid && lqIdx在ldWbPtr之后 && !该请求被本拍redirect取消` 才需要新RAR槽位。其他请求不占容量且ready为真。需要分配的lane按其前面**需要分配**的lane数量压紧offset，忽略不需要分配的lane；当前可用前缀决定ready及实际接受数。空间不足时不能确认一个不存在的槽位，但仍有查询结果流水。

- 真实接受槽位由独立FreeList可用ID序列/延迟回收账本推导，不读取DUT内部allocateSlot/headPtr/位图。
- 同一个ROB/LQ load可因非对齐头尾等形成多个记录，不以LQ索引唯一性错误地拒绝合法输入；不同记录有独立RAR槽位生命周期。
- `req.valid`不受`ready`握手门控地进入响应流水：不需要分配、被redirect取消或容量nack的查询，仍在下一观察边沿有resp.valid。分配接受与查询响应是两条不同义务。
- reset期间输入idle，保持至少6拍并暖机，清空旧记录、revoke/release流水和参考义务；不能用reset完成旧回收证明。

## 3. 物理地址比较与release窗口

RAR的16位partial-address/hash是保守编码，不是48位物理地址完整相等。等价的语义计算：

1. 忽略低6位cacheline内offset；高11位编码由48位地址从bit6起每11位一组异或折叠。
2. 低5位编码为地址[10:6]与地址[15:11]反位序后的异或，最后与高11位拼接。

因此，同line不同offset应匹配；不同line也可因hash碰撞参与保守违例。例：同时翻转地址bit17和bit28不改变该hash，必须作为碰撞定向情形，而非断言不同完整地址永不nuke。逐个地址位翻转和跨高位编码仍需检查，不能只用生成器和模型共享一个hash函数就宣称覆盖。

新分配条目的released初值为：`nc || (dataValid && 本拍或前一拍有效release的完整cacheline地址相等)`。这个分配前后拍捕获使用**完整line地址**，不能用hash碰撞冒充full-line命中。dataValid=false不通过该初始化窗口标记released；nc按已released处理，不虚构NC被硬件排除。

已有条目收到release时使用hash CAM：release在N观察边沿登记命中，N+1更新released，此时查询仍采旧released，N+2查询响应才可反映这次标记。旧miss/等待refill的条目也能被后来的release标记，不要求当初dataValid=true。released是粘滞状态，直至条目释放/重用重新初始化。

## 4. 查询、取消与回收的时序

每个查询的nuke来自边沿前的旧条目集合：存在allocated、同hash、ROB slot更年轻且released的条目。相同ROB slot不算更年轻；same-entry former/latter要精确区分。多个匹配只需输出OR，但反例必须包含较老、同slot、未released、不同hash和已回收项。

- resp.valid在输入边沿N后对应本拍req.valid；有效nuke与同一拍请求的地址/年龄对应，不能串lane。无效响应payload是don't-care。
- 本拍新分配的条目不能零延迟参与同拍查询；本拍被ldWbPtr/redirect/revoke释放的旧条目仍可能出现在该拍采样的查询结果。不能把响应改成next-state或补上源码没有的取消过滤。
- 记录的LQ位置不晚于ldWbPtr、或ROB被redirect取消时归还槽位。1拍/2拍revoke只针对同一lane在相应历史拍**确实接受新分配**的记录，不是对任意req.fire或当前新分配条目撤销。
- 多种释放原因命中同一槽位时合并为一次通知；对已经回收的历史revoke不能重复free。FreeList的释放登记/选择/重新可分配具有真实延迟，不能因RAR记录位已清零就立即增加可用容量。
- lqFull按FreeList实际可用容量（含回收在途）计算，不用当前RAR记录个数代替。父块需保留真实FreeList/CAM，检查所有跨块时序。

## 5. 性能事件也属于实际接口

`io_perf_0_value`不是累计数，而是每拍req.fire数量的两级寄存输出，含不需要分配但握手的有效查询；接受新记录数可能不同。`io_perf_1_value`是有效nuke响应数的两级寄存输出。相对于输入采样边沿N，perf0在N+1体现，perf1在N+2体现对应查询的nuke数；高4位应为0。最终以原生实测确认，不忽略这两个实际保留端口。

## 6. 用例前的人类可读功能点

| ID | 行为要求 | 必需情形与检查依据 |
|---|---|---|
| RAR-RESET | 复位终止旧记录、release/revoke和回收流水 | 初始、占用、回收/违规流水中reset；重建记录并实际查询/释放 |
| RAR-ALLOC | 只有存在未完成老load且未取消的查询才占槽 | 三lane、稀疏need、head相同/更早/更晚、redirect阻止分配、空间不足；ready及后续违例/回收证明 |
| RAR-NUKE | 对年轻且已released的同hash记录生成保守nuke | 正例和各过滤反例、多匹配、lane独立、nack仍响应、同拍新/旧状态边界 |
| RAR-HASH | 16位编码符合cacheline/高位折叠和保守碰撞语义 | 同line不同offset、逐位区分、高48位、bit17/28碰撞；真实查询/release结果 |
| RAR-RELEASE | 新/旧条目在正确release窗口建立粘滞状态 | 分配同拍/前拍full-line匹配及碰撞反例；dataValid true/false、NC；已有记录随后release与两拍查询可见性 |
| RAR-AGE | ROB/LQ关系按真实slot/环绕而非数值比较 | former/latter、相同ROB不算年轻、ROB160与LQ120跨界、乱序查询到达 |
| RAR-DRAIN | ldWbPtr和redirect只释放正确的记录集合 | 指针前移、部分/全部取消、旧条目同拍响应、实际容量恢复与重新使用 |
| RAR-REVOKE | 1/2拍撤销与本lane真正接受的新记录关联 | 两个窗口、同时撤销不同记录、无历史分配/已回收无效撤销、与当前分配重叠 |
| RAR-CAPACITY | 提前full门限和最终ready容量表达不同义务 | 空闲6/5项门限、仅余1/2/0项、三lane部分接受、回收流水内不早恢复、反复96项复用 |
| RAR-RACE | 分配、release、回收、redirect、revoke并发不串生命周期 | release与新/旧条目、同条多原因free、查询与释放同拍、回绕重用与旧标记隔离 |
| RAR-IDLE | 无有效输入时条目保持，禁用payload不改变语义 | 空/满/部分池、在途release/回收允许推进、旧released不会无故清除 |
| RAR-PERF | 保留事件输出对应真实fire和有效nuke数量 | 0/1/2/3个查询、fire与分配不同、正反nuke混合、规定两级流水及reset暖机 |

功能覆盖在被动观察路径记录reached，checked要等相关ready/响应/full/事件输出比较及对应生命周期的后续证明；不能以发过req/release/revoke计作完成。内部信号只可辅助定位，不是正确答案。

## 7. 首轮和补例规则

先做空池、最小分配、NC与基本nuke/无匹配响应以及回收，建立公开接口时序实测。保存首轮真实LCOV和语义缺口，再逐行定位到分配写入、hash/release、revoke、回收和统计路径；区分既有功能点缺少情形还是整项功能点未定义，补例并在新目录重跑。不能用父块smoke代替本块UT，也不以本块通过代替LoadQueue真实组合。

## 8. 独立参考的实施边界（待实现，不是通过证据）

建议用语义记录`{uid, RAR槽位, 解环ROB-slot, 解环LQ位置, 原地址/hash, released}`，复用本工程已验收的FreeList可用ID/等待集合参考而不导入其DUT。父DUT仍编译真实全部子块。

每个观察边沿的参考次序应明确：

1. 由真实当前输入解环ldWbPtr、query和redirect；ROB查询本来可以乱序到达，不施加VLQ dispatch的入队顺序约束。LQ记录也不要求唯一索引，允许合法的非对齐多记录。
2. 先比较旧状态下的组合ready/lqFull和寄存响应/事件；仅使用被动采到且已核对的ready决定真实分配fire。
3. 用旧记录计算本拍每lane的match/nuke快照、下一拍release标记、ldWbPtr/redirect/revoke的合并free集合；此时不能把刚分配条目放入同拍nuke。
4. 分配只能消费旧FreeList的有效前缀；将合并free输入送入独立回收账本，不能把清allocated的同拍当作容量已回来。检查参考持有槽位集合与当前RAR记录集合守恒。
5. 插入新记录的released初值由nc/dataValid及当前/上一拍**完整line**决定；随后应用上一拍排队的旧release标记。上一拍release标记和FreeList至少两拍回收的组合不能污染已经换代的新记录，需用定向重用检查。
6. 推进同lane一拍/两拍真正接受索引、release历史、响应有效与性能事件。对无效响应payload不比较，对真实保留的两个perf输出不能忽略。

正例probe可用`query.lqIdx=ldWbPtr`避免额外分配，同时给更老ROB和所需paddr；这仍是有效query/fire，必须有响应并计入perf0，但不占新槽。唯一匹配probe可以为某个具体记录的分配/标记/删除提供公开输出证明；多个同hash匹配只能证明OR，不能据此把所有隐藏槽位逐一标成已检查。

复用VLQ的RobPtr/QueuePtr或解环数学工具仅属于本工程内部语义设施共享；不得导入其他验证工程的领域模型，不得将DUT内部信号作为预测slot或released的答案。既有VLQ逐拍记录4881条的pre/post输入完全一致，确认当前被动采样在driver恢复idle之前发生；RAR仍需在自己的首轮实测检查这一相位，不能靠猜测修补组合ready。

## 9. 首轮缺口和补例门禁

`rar-initial-01` 首轮3/3通过，本体2282/3898=58.54%；只覆盖10/51个可执行语义情形。真实子块FreeList为463/1132、地址CAM为104/290，三份直连辅助块无DA；整个真实闭包的插桩行为2849/5320。子块之前独立通过的覆盖不能替代这里的父块集成覆盖。

本体1616条未覆盖行中，1615条是96个槽位从不同lane保存ROB/LQ身份的条件路径，1条是前拍release地址捕获；归为既有ALLOC/AGE/DRAIN/REVOKE或RELEASE/RACE功能的情形缺失。FreeList的669条和CAM的186条缺口也逐条映射到父块回收/容量/复用和分配/hash/release行为，均不排除。原始needs_review清单保留，人工映射另存新文件。

补例在开发前明确：三个入口各自遍历96项；全池唯一hash正例和释放后负例；由实际返回槽位的独立账本安排同通道积压与各通道长回收并复用；完整line/release的前后拍、hash别名反例与逐个高低地址位；ROB former/latter/环绕及LQ120回绕；1/2拍撤销和无分配历史反例；剩6/5/2/1/0槽、容量nack仍响应、释放到再次ready的真实流水；同槽多原因free、reset和合法并发。

“未分配”情形使用NC输入使错误隐藏分配可观察，并要求**紧接下一边沿**的更老、同key负probe，不能等自动head清理后才记通过。分配需要唯一正probe证明具体UID；删除需要曾经正probe证明存在、再负probe证明消失。初始未released和复用/完整line别名的反例要求先负后正，避免把从未真正建立的记录误当作正确过滤。

## 10. release窗口不一致的补充判别（补例前定义）

原始生成RTL的 `release2Cycle_valid` 经两级寄存，而 `release2Cycle_bits_paddr` 只有一级有效使能。首个孤立release后的下一拍新分配未初始化released，与源码“delay 1 cycle”意图和第3节合同不符。保留严格参考，不调整预期、不修改目标RTL、不使用xfail掩盖失败。

新增判别情形：

- `RAR-RELEASE.previous_isolated`：前一拍为孤立release（更早一拍无release），随后分配 `dataValid=true,nc=false`、同完整line记录，紧接的更老probe必须nuke。
- `RAR-RELEASE.no_expired_window`：release距分配已两拍，前一拍和当拍均无release；新记录不能捕获过期标记，先负probe，再真正late release和正probe证明记录真实存在。
- `RAR-RELEASE.late_hash_alias`：已分配的未released记录，由不同完整line、相同hash的release经既定两拍时序标记；与分配窗口的完整line比较明确区分。
- `RAR-NUKE.old_snapshot_insert`：同拍一个lane分配年轻NC记录、另一lane查询其同key，不得看见新记录；下一拍唯一正probe证明分配真实发生。

补例扫描三个lane、release距离0/1/2/3拍和dataValid真假；实际复现通过Picker+xreactor被动观察的公开引脚记录，未执行另行的直接引脚脚本，不宣称存在独立于该运行路径的第二份动态复现。活动reset的checked收紧为“曾由公开正probe证明的旧记录在reset后负probe消失”且“新记录正probe证明”，不靠reset清空参考义务计通过。
