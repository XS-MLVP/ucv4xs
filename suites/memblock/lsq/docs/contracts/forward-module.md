# ForwardModule：较老store字节转发、安全重放与虚实地址一致性

状态：**完整冻结回归184例165 PASS/19 FAIL、64/64 reached与61/64 checked，本体253/253 DA；公开历史与live边界审计完成，3项严格语义因真实失败未验收。** 固定开源基线893e1580b；真实top `ForwardModule`，单文件原始RTL11476行，64个物理SQ槽、3个独立load查询、2个UnalignQueue页输入。父级PSQ仍使用真实本模块，不以Python转发器代替硬件。

## 1. 实际接口和配置边界

原SV头逐项静态核对为除clock外**695输入、129输出**。每个查询lane有s0Valid、vaddr50、完整SQ64×2双flag、size3、loadWaitBit/Strict、waitSqIdx，下一阶段s1Req.paddr48与s1Kill；输出仅s2Resp valid、16个字节data、16位mask、forwardInvalid/matchInvalid和addrInvalid/dataInvalid及各自完整SQ身份。

每个store槽保留size3、vaddr50、paddrHigh36、byteMask16、data128、cboType2以及dataValid/addrValid/cross16Byte/isCbo。物理地址低12位与vaddr相同，参考不能另造不存在的低位输入。两个UQ项保留paddr48、完整SQ、valid；deqPtr和physicalQueueUpper是完整SQ指针。

**当前top没有reset、没有ready、没有s1Resp、没有perf输出、没有allocated/committed/ROB字段。** 初始化只能用已知公开bank和连续无效s0输入排空两级valid；无效响应payload/未初始化保持寄存器不比较，不声称reset或上述已删除功能通过。

## 2. 合法微架构输入

- load SQ身份表示其之前的store前缀；按完整环形指针确定较老store域，物理候选限制到公开physicalQueueUpper。不按slot值排序，不让已出队、年轻、域外槽或未有效地址参与转发/CAM判断。
- 普通查询使用deqPtr锚定的独占边界0..128，含超出64项物理窗口的load和恰好128个老Store后的满池端点；不得把任意两个相距半环的指针比较当合法顺序。早期不足128合同漏掉真实Dispatch可达的full端点，见[端点纠正合同](lsq-sq-endpoint.md)。waitSqIdx另覆盖已退休、物理窗口内和窗口外的预测目标；通用after半环拒绝保持。
- 当前真实PSQ通常给deqPtr+64的physicalQueueUpper，出队反馈有寄存滞后；参考使用公开边界而非私自重算。年龄、当前地址ready和后续上界变化必须按各阶段相位检查。
- MemorySize 0/1/2/3分别1/2/4/8字节，**4～7均按Q的16字节语义**（`MemCommon.scala:146-178`），不能把5～7当非法编码跳过。
- store size定义连续范围，byteMask保存有效数据字节（相对store数据起点）；cross16Byte表示真实范围跨16B。请求可以未对齐，跨16B或跨页由真实store/UnalignQueue输入表达。不得仅用byteMask与load位图相交替代地址范围比较。
- 已进一步核对当前PSQ生产者1931～1949：活跃byteMask由size生成连续低位mask。任意mask孔洞仅作为UNIT-INTERFACE边界保留，不混称普通PSQ合法流量；生产者合法随机另外使用完整size mask，原孔洞压力不删除或跳过。
- S1未被kill的正常load PA与其VA页内offset一致；S1 paddr属于前一拍同lane s0请求，不能把当前s0的PA错接到旧请求。不同lane允许完全不同流量及连续有效请求。
- store输入可按PSQ协议逐拍更新；S1选择时的地址/数据状态和S2实时物理CAM/精确MDP状态不能混为同一快照。真实父级的取消/slot复用/retire域后续仍须组合审查，不凭叶子测试虚构原子银行快照保证。
- UQ有效页来自真实跨页第二页地址（低12位0），完整SQ必须在load之前；valid=false时任意旧页/flag不能影响重放。CBO.zero可提供有效零数据，其他CBO子类型必须要求重放而非伪造正常数据。

## 3. 参考语义、选择与响应

参考使用按SQ年龄排列的store记录、VA/PA字节范围、原始data/mask和明确到达拍的查询UID，不读DUT内部选择one-hot、年龄mask或pipeline寄存器作oracle。

1. 在load之前、未退休且处于物理窗口的store构成合法候选域。S1按store VA与load当前16B段/同页下一个16B段，以及CBO同cacheline规则判断虚拟候选；比较真实字节范围是否重叠。
2. 有多个虚拟候选时只选**最年轻的较老store**，不能因为该store数据未就绪就回退到更老store的旧值。缺数据返回该store完整SQ的dataInvalid；没有候选不能捏造dataInvalid有效。
3. 单候选或所选候选满足本实现完整覆盖规则时可提供转发；多候选但所选store未覆盖load完整范围时forwardInvalid要求重放，不拼接多个store补成虚假的完整值。
4. 按load字节起点与所选store起点的差值旋转16字节数据与mask，截取load长度，再放到load的16B偏移；比较实际有效mask及有效字节数据，不读取未选中/无效字节作正确答案。
5. 与原候选年龄/有效/重叠域一致的PA命中集合必须和VA候选集合一致，否则matchInvalid要求重放。不能只核对被VA选中的那个store的PA，更年轻的物理别名store同样不能被漏掉。
6. **安全性独立检查**：若物理别名中有更年轻但仍早于load、有效且字节重叠的store，旧VA匹配store的数据不能当作安全完成；必须有相应matchInvalid/forwardInvalid/依赖等待证明。此性质按完整PA字节范围推导，不能用RTL生成的虚拟重叠mask作oracle掩盖跨16B别名缺陷。
7. strict等待所有较老地址未知store，load超出物理范围也不能过早解除，addrInvalid指向loadSq-1；非strict仅在loadWaitBit时等待预测目标，已退休目标不阻塞，窗口内目标读取当前addrValid，窗口外目标等待。
8. UQ命中较老cross-page第二页要求forwardInvalid，不声称本配置支持跨页转发；wrong SQ、年轻、无效UQ页的负对照分别检查。

## 4. 逐阶段时间合同

- S0接受valid-only查询，捕获load范围、SQ年龄域与原边界；无ready，不重复发送同一查询UID补等候。
- 下一拍S1使用同lane的s1PA、s1Kill及**当前store/UQ输入**完成虚拟匹配、最年轻选择和数据/原因快照。kill使该UID没有S2有效响应，不允许它污染后继新UID。
- 再下一边沿后S2有效响应（需首轮实测准确相位）：被选中的data/mask/控制与原VA候选域来自S1快照；**物理CAM及非strict精确MDP使用S2当前bank/指针/addrValid**。S2保持有效的周期内这些组合输入变化仍可改变原因，不能把整个响应错误冻结成原子快照。
- 对所有DriveStable/RisingEdge均比较，含fixture排空/切换空拍；无效s2Resp不比较payload。no-reset启动通过2级valid排空确认，不把初值0当规格。

## 5. 用例前可读功能点

| 功能组 | 行为和必需情形 | 实际检查 |
|---|---|---|
| FWD-PIPE | 3路独立查询、连续吞吐、空洞与S1 kill | UID在规定S2边沿出现一次，kill旧UID后新UID完成 |
| FWD-AGE | 较老/年轻、deq与upper、四圈flag及64槽回绕 | 以SQ顺序选择而非槽号/PA命中数量 |
| FWD-SELECT | 单/多候选中的最年轻store及未就绪不回退 | 完整dataInvalid SQ、实际字节和mask |
| FWD-BYTE | 1/2/4/8/16B、全部16偏移、byteMask/partial/no overlap | 有效数据逐字节比较，不凭行命中 |
| FWD-CROSS | 同页跨16B、第二段、VA页边界不错误长进位 | 真实范围/旋转、UQ跨页重放与负例 |
| FWD-VA-PA | 同VA异PA、VA别名同PA、匹配集合一致性 | matchInvalid及安全完成禁止旧值性质 |
| FWD-REG-6693 | 历史88fb444c5：VA1旧store、VA2年轻store、load VA1同PA | 更年轻物理别名必须使旧数据不被安全接受 |
| FWD-REG-NEG | 年轻/无效/无字节重叠物理命中不误参与 | 无假matchInvalid；旧有效数据仍正确 |
| FWD-WAIT | 地址未知/数据未知、strict与精确MDP | 原因有效与完整SQ身份，目标退休/窗口变化 |
| FWD-CBO | CBO.zero与其他子操作，同cacheline范围 | 允许零数据与拒绝非zero CBO分别检查 |
| FWD-UQ | 两个真实跨页页输入与完整SQ年龄/valid | 较老页要求重放，其余不污染 |
| FWD-LIVE | S1快照与S2 live PA/MDP更新边界 | 不误将当前bank当原数据快照，精确相位检查 |
| FWD-REUSE | kill/退役/slot复用后新UID和新数据 | 旧查询无泄漏、后继实际结果正确 |
| FWD-IDLE | 无效查询/未选entry/禁用UQ payload不产生义务 | valid/原因门控及新查询完成 |
| FWD-CONCURRENT | 合法随机字节/顺序/双flag/背靠背 | 固定种子、可审计来源和最终管线排空 |

## 6. 既有历史回归证据与运行顺序

已只读核对开源commit **88fb444c574a52c1e33f682f5ab6770204cb923f**（2026-10-13，fix(StoreQueue): fix forward older store data #6693）。提交说明明确VA1/VA2同PA导致旧值，diff将原单选PA核对改为同候选域PA/VA集合XOR；这只是用例来源，不是本UT已运行或现成SV已正确的证明。

先原样导出与695实际输入静态适配；首轮空闲、单store正确字节转发、未就绪与历史别名回归，实测S0/S1/S2相位。然后逐条分类原始未覆盖行并补64槽×3lane、优先年龄、字节/跨段、kill、MDP/CBO/UQ、live更新和合法随机；记录功能检查、种子、行分母、缺口分类及提升，不以smoke/历史提交/高覆盖替代验收。每次运行新目录和源码快照，保留普通失败，不修改目标RTL迎合参考。

## 7. 当前原生实施证据与逐行补例

原样导出及实例化走钟PASS：`results/builds/20261018T081233332925Z-forward_module/report.json`，原SV SHA `2427f03c60c6fea0b69be1315aa5aedbc4554025a349870388a7c3d775ac35e1`。`forward-codec-static-01`核对695输入/129输出、25个有效样本和8个非法拒绝；静态编码不作功能通过。当前无reset，fixture通过3拍无效查询排空；逐拍参考区分S0年龄/S1数据选择/S2实时PA与MDP，独立PA字节安全检查不使用VA重叠mask作oracle。

`forward-initial-01` **10 PASS/3 FAIL**，250/253 DA、13/62 checked：普通转发/数据未就绪与88fb444c5同word别名回归通过；跨word别名三个lane均不安全返回旧值，开放FWD-ALIAS-001。公开字节重建审计见`initial-audit.json`，不是完整模块验收。

首轮缺3条原始DA：4675/6736/8797为三个lane的回绕低年龄段优先树分支，逐项映射到既有FWD-AGE.wrap/all_slots和FWD-SELECT.youngest缺少情形；不排除行。映射冻结在首轮`initial-audit.json`，补deq60、SQ112(slot48)、load114和全部64slot×3lane的真实字节结果。

`forward-expanded-01` **31 PASS/3 FAIL**，253/253 DA、24/62 checked。15个必要条件对照（年轻/地址无效/无范围重叠/同VA/其他PA页）全部通过，原3个跨word别名失败仍存在；161份启动文件在结束时SHA全部一致。剩余字节/长度/kill/MDP/CBO/UQ/live边界与合法随机仍必须完成；不能以行覆盖满缩小到目前34例或声称模块已验收。

## 8. 剩余语义定向补例与新身份边界

`forward-semantic-directed-01`为120例114 PASS/6 FAIL（5个长度/随机用例另行运行）；partial/next16B、最年轻不回退、strict/精确MDP、CBO、UQ、S1 kill/连续查询和S2 live边界的定向检查已执行。新增FWD-SQID-001：deq60、upper124、真实slot48即SQ112缺数据，load SQ128/129却返回SQ176，3lane共6个普通失败；SQ124/127的6个对照通过。source550～554低年龄段借用load的operation_flag，但年龄域被upper裁剪后所选store已经不属于load的generation。

按该真实失败在既有FWD-WAIT.identity中补充`FWD-WAIT.clipped_identity`情形（分母62→63，旧快照不改写）。load与deq距离68/69小于128，属于虚拟SQ内而物理窗口外的合法查询；不得收窄到物理窗口内或使用错误flags作为预期。跨代identity失败继续保留，未声明真实父级的架构后果已验证。

`forward-bytes-random-01` 的3个全尺寸/偏移/mask扫描通过，两个原始随机失败于“被标有效字节没有物理producer”；其孔洞mask现明确为接口边界。继续用真实连续size mask和同一RNG序列、以及单个合法8B跨16B store与word对齐16B load的最小定向确认，不能直接把接口随机失败当架构缺陷，也不删除这些压力。已补既有字节范围功能情形`FWD-BYTE.range_mask`，分母63→64；随机checked收紧为整段流量完成、两级管线实际排空后才采样，不能因部分早期query通过便宣称随机结束通过。

`forward-range-mask-01`确认FWD-RANGE-001：两个真实连续PSQ size mask随机失败；6个3lane×两段最小定向也失败，store从PA0xabc00c写8B，word对齐16B load两段均得到mask0xf00f且无原因标志，正确当前字节范围分别仅0xf000/0x000f。另两个对齐store随机种子完整排空通过（是额外分区，不替代失败的未对齐和接口随机）。新增15个必要条件对照，分别缩短store使其不跨段、使store结尾恰好对齐、缩短load只读实际首/次段、完全不重叠；对照不把失败的range_mask功能点记为checked。新情形来源于独立安全性质，不是新RTL未覆盖行；行满后的功能缺口仍需要如实记录。

## 9. 本轮完整证据与未验收项

`forward-expanded-02`已实际完整运行184例165 PASS/19 FAIL，253/253 DA、64/64 reached与61/64 checked；15个新增range必要条件对照通过。缺口恰为ALIAS跨word、裁剪后SQ身份、range mask三项，17个生产者域和2个仅接口mask失败分列。163份启动文件结束SHA一致，5599条公开历史及全部artifact/build哈希审计通过，3196接受=278kill+2906有效响应+12失败保留在途；有效响应不等于成功，2881个处于完全检查通过边沿，25个处于失败边沿不计成功。192个lane×slot成功见证、每个checked语义UID/provenance及6个pre-edge live更新均有独立审计。见[报告](../reports/forward-module-20261018.md)和`results/forward-expanded-02/{trace-audit,live-audit,end-source-check}.json`。仍NOT_PASS，局部缺陷不阻止独立VSQ实施。
