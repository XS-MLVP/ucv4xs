# UnalignQueue：跨页store第二物理页地址的保序暂存与恢复

状态：**功能点在用例前定义，当前41/41 PASS、40/40 checked、44/44 DA，固定配置独立UT已验收。** 真实目标是开源 `NewStoreQueue.scala:1430-1515` 的2项UnalignQueue，原始SV `soc-split/rtl/UnalignQueue.sv` 单文件259行。其下无其他业务模块；父级PhysicalStoreQueue必须保留真实本块。实施历史见下文，最终证据见[报告](../reports/unalign-queue-20261018.md)。

## 1. 实际端口和身份

- 两路STA请求，分别带valid/ready、48位paddr和完整SQ指针（first_flag、second_flag、value6）。仅存跨页store第二物理页地址，不是普通store数据队列。
- `fromSQ.addrReadyPtr` 是完整SQ指针，只有与该路请求SQ身份完全相等且队列未满、无redirect时才ready；并非“只要比请求大即可”。
- 向DeqModule输出一个Decoupled的页地址与完整SQ指针；两个物理slot分别输出forwardEntries及forwardValid。只能在对应forwardValid为真时比较entry内容，未分配/已取消payload不定义。
- 仅保存paddr[47:12]，所有有效head/forward地址的低12位必须为0；输入低12位不是另一个字段，不能以原始低12位输出作为预期。
- redirect输入是**SQ恢复指针**，不是ROB redirect。`SqPtr.needFlush`（源码34～58）使用isNotBefore：等于cutoff也取消；按SQ64×2、两个flag构成的四圈身份和环形年龄处理，不按value单独比较。
- 当前top删除调试ROB身份等字段，无full/empty端口，不虚构动态检查；公开head valid、输入ready和forwardValid用于证明占用与排空。

## 2. 合法生产者/消费者协议

1. accepted输入必须one-hot：两路可同时valid但SQ不同，只有addrReadyPtr相等的一路fire；不得同拍使两路都匹配并fire。Mux1H不是多请求仲裁，不能把两个同时有效的相同SQ请求作为普通随机。
2. 新请求严格按完整SQ程序顺序推进，不对同一个仍活跃SQ重复分配；跨页store之间允许存在普通store间隙。活跃/redirect年龄域不得跨半圈128的歧义边界。
3. 满时即使同拍head消费也不接受新请求：本块是`!full`门控，没有EnterSbufferQueue的同拍满池复用。空队列也无组合直通。
4. redirect时两路输入ready全部为0，即使有请求匹配addrReadyPtr也不能接受。被取消条目是按SQ顺序排列的后缀，tail回退取消数量；幸存前缀顺序不变。
5. 当前生成top的head valid不被当拍redirect组合抑制，forwardValid也在边沿后清除；不能错误要求其当拍归零。真实DeqModule只消费已提交store的第二地址，已提交head不能同时被SQ恢复取消。因此普通合法组合允许“消费幸存head并取消年轻suffix”，不允许“消费同拍被取消head”。依据DeqModule的committed前缀（1233～1283）与`fromUnalignQueue.ready`（1294）；后者需真实writeSbufferWire.head.fire及SQ匹配。
6. 被背压时已接受head应稳定；禁用输入payload任意变化不得影响旧entry或forwardValid。reset是中止全部旧UID的事件，不当作Deq消费；未接受的attempt不算所有者。

上述one-hot、完整SQ宽度和同拍取消/消费域在适配/参考入口拒绝；拒绝只算静态domain检查，不声称DUT动态检测了非法输入。不得通过收窄合法hint/redirect情形迎合RTL。

## 3. 时序与独立参考

DriveStable采样旧状态：输入ready来自旧占用、当前完整SQ比较和redirect；head valid/packet来自旧最老请求；forwardValid及有效payload为旧各slot。RisingEdge记录实际head fire，按合法恢复取消后缀，再将实际accepted唯一请求追加；reset则清除全部。

参考是UID顺序列表、SQ环形身份、页号及独立的接受/消费/恢复账本。为验证公开forward槽位归属，可由接受序号mod2和取消导致的tail回退计算槽位，不能读取DUT指针/allocated作为oracle。每个实际输出字段与原请求身份比较，取消checked等待后续新UID在复用位置真实输出并消费；普通checked等待真实head fire。

## 4. 用例前可读功能点

| 功能组 | 微架构语义与必补情形 | checked观察依据 |
|---|---|---|
| UQ-RESET | 初始、单/双在途及回绕reset清除旧地址和转发可见性 | 新UID真实head消费，旧reset中止独立计数 |
| UQ-ADMIT | 只有匹配完整addrReadyPtr的STA跨页第二请求被接收 | 两入口、value/first/second负例、双valid不同SQ仅一接受；之后实际消费 |
| UQ-CAPACITY | 两项容量、满池阻塞、满池同拍消费不偷接、空池无直通 | 实际ready/valid和所有权守恒，下一拍恢复接受并完成 |
| UQ-ORDER | SQ程序顺序保持、稀疏SQ间隙和物理双槽多轮回绕 | 每个UID从真实最老head消费一次 |
| UQ-PAGE | 第二物理页高36位完整保存，输入offset不泄漏 | 两slot/lane、36位walking one/zero、不同低12位的有效head/forward比较 |
| UQ-FORWARD | 未到Deq消费的活跃第二页地址向ForwardModule可见 | 两个slot分别valid及payload，消费/取消/复用后不再公开旧身份 |
| UQ-HOLD | Deq背压保存head及forward内容，不提前释放 | 背压稳定比较与随后实际消费 |
| UQ-REDIRECT | 等cutoff/更年轻后缀取消，较老前缀幸存 | 取消0/1/2项、输入阻断、完整flags/跨圈、连续恢复、幸存head消费与年轻取消同拍 |
| UQ-REUSE | 被消费/取消slot可保存新SQ和新页，不串旧身份 | 相同/不同页、tail回退、取消后新UID完整消费 |
| UQ-IDLE | 禁用输入payload、空闲ready和未分配entry不制造义务 | 公开valid/ready精确检查，未知无效payload屏蔽 |
| UQ-CONCURRENT | 合法单hot流量与背压、恢复组合在公平消费下排空 | 固定随机种子、完整输入/输出逐拍守恒 |

初轮先空闲、lane0单项页保存/背压/消费和lane1匹配门控；分析真实未覆盖原始RTL行，再把缺口逐条分类为既有功能缺少情形或遗漏整体功能，补例到双slot/满池/恢复/回绕/随机。即便DA首轮已满也不跳过剩余语义。

## 5. 工具、记录和验收

使用原样Picker导出及本工程xreactor managed runner，实际绑定19个输入（不含clock），公开被动监视器逐拍消费全部DriveStable/RisingEdge。每次新结果目录，固定工具/RTL/包哈希和验证源快照、记录种子/波形/全检查与reached/checked；成功例最终排空，取消及reset分开记账。

首轮、未覆盖行映射、补例与最终回归、独立公开输入历史审计都完成后才可验收本模块。高覆盖不等于任意参数或父块正确；当前仍未实现原生功能UT，不以合同或build/smoke计通过。

## 6. 原生导出历史节点（仅此节点非功能验收）

真实原样导出及原生实例化走钟已PASS，`results/builds/20261018T075508771717Z-unalign_queue/report.json`：单文件SHA `a19982ca4a2f60abf3428d60e6a30d3658304b8001c868b5fbd91b5e0d90b63b`，导出包及signals已记录哈希。当时独立参考、逐拍fixture和原生功能用例仍待实现，不能将该构建节点追溯计作功能通过。

## 7. 首轮原生功能与逐行补例前审查

已实现以UID/页号/SQ顺序为核心的独立参考、19个真实输入绑定、公开前后边沿被动监视及逐拍检查。`unalign-initial-01` **3 PASS**：空闲ready、入口0单项页保存/背压/消费与offset清零、入口1错误addrReady值拒绝/正确身份接收。普通checked等真实head消费，取消checked等相同物理槽的新UID真实消费。

首轮本体 **37/44=84.09%**，语义 **11/40 checked**。7条原始DA缺口逐项定位：156～159为第二物理槽保存页号及完整SQ，共4条；182～184为redirect尾部回退，共3条。全部属于已有UQ-CAPACITY/ORDER/PAGE/FORWARD及UQ-REDIRECT/REUSE缺少情况，未遗漏新的整体功能；保留原始分母和原needs_review清单，另存映射。先补双槽、满池/不支持同拍满池接收、取消0/1/2项及同槽新UID完成，再补双flag边界、页号位/offset、活动reset、禁用payload和合法随机，不能只让7条行命中就验收。

## 8. 补例后验收

`unalign-expanded-01` 41 PASS、44/44本体DA、40/40 checked；原生/功能覆盖/146份源码哈希门禁通过，5947条公开历史独立审计：1967分配=1726消费+237取消+4 reset中止；取消全部有同物理槽新UID消费见证，成功例全排空。256种SQ编码和36位页号walking one/zero由真实完成证明，原始RTL未改。此结论不扩展到ForwardModule或真实父块。
