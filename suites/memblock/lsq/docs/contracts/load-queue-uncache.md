# LoadQueueUncache：排序分配、总线路由与LDU回放数据的真实组合

状态：**已完成首轮、缺口补例与真实父块逐拍迭代，但NOT_PASS、尚未验收。** `load-uncache-expanded-03` 64 PASS/8 FAIL，42 reached/40 checked；LQU-SID-001的7个合法重用反例失败，另1个LQU-MMIO-IF-001仅为UNIT-INTERFACE边界（不声称合法ROB流量可达）。详见 `docs/reports/load-queue-uncache-20261018.md`。全部16个UncacheEntry与FreeList_3已独立验收；本DUT保留真实16个entry、预分配FreeList、两级NC仲裁及两个FastArbiter、总线弹性寄存器和两个wakeup优先仲裁器。闭包按文件去重22份，不以子块通过替代真实组合检查。

## 1. 实际接口和主要义务

三路输入load先按ROB slot年龄排序，再经一级保存，在下一边沿过滤/分配。16个entry将MMIO/NC请求发给外部Uncache代理，经mid回执绑定sid，response按sid找到一个或多个等待entry；返回后先唤醒LDU，再由三路bypass按LQ及replay类型取走地址和数据。容量不足的load不静默丢失，应请求前端rollback。

- 三路req.valid及保留元信息：ROB160/former-latter、FTQ flag/6位value/5位offset、RVC、64位checkpoint、LQ120指针、50位vaddr、64位fullva/gpaddr、48位paddr、16位mask、NC/MMIO/内存属性、10个异常位、need_rep和C_UNCACHE cause。**ready已常量化删除**，不绑定也不声称测了输入背压。
- 总线req为ready/valid，含ROB、cmd、addr/vaddr、8位mask、**7位mid=id**、nc和属性。当前cmd固定M_XRD=0，data端口由原始生成件接0但源语义为读请求don't-care，不将其当作有效store数据。
- idResp含mid7/sid4；response含sid4、data64、error/nderr，response.ready已删除。两个wakeup是Valid-only，无外部ready。
- 三路bypass s0输入LQ及isNCReplay/isMMIOReplay；s1输出valid+paddr48，s2输出valid+data128+nderr/derr，没有ready。输出data是64位响应复制两份，不做按地址移位/符号扩展。
- rollback保留ROB、FTQ、RVC、level和checkpoint；exceptionInfo保留ROB、10个异常位、vaddr64、**gpaddr仅50位**、Hyper/PTE。gpaddr按当前配置截断，vaddr来自fullva而不是50位请求vaddr。top没有full/validCount或perf输出，不虚构观察点。

## 2. 排序、过滤、容量和rollback

有效load排在无效lane之前并按真实ROB slot由老到年轻排序，不按输入lane或value数值；同entry former在latter前，跨160项回绕合法。当前3路排序对于年龄相同项按较小输入lane优先，单列重复年龄/不同LQ情形，不把通用函数注释中的不稳定顺序当作任意可选答案。

分配阶段排除当前或上一拍redirect取消、任何保留异常位非零、need_rep且非C_UNCACHE原因、以及既非NC也非MMIO的load。其余按过滤后的需要分配数压紧FreeList offset，使用真实预分配有效前缀；不能因排序排名存在空洞就浪费槽位。NC/MMIO在普通事务中择一，两者同置的接口行为另作边界，不用它替代真实两种类型。

当前top输入ready不反馈容量，超出16项的合格load必须走rollback：选择拒绝项中最老者，保留原恢复身份，按当前/前两拍redirect过滤后寄存输出。拒绝不能建立隐藏entry，也不能把被其他原因过滤的load误当容量nack。回收来自数据消费或entry.flush，多种原因合并一次，经过真实FreeList延迟和预分配等待才能重新使用。

## 3. MMIO优先、NC仲裁和总线寄存器

MMIO必须遵循真实ROB pending许可，代理不能凭空将pending跨过尚未完成的MMIO来制造不可能的多个架构提交；但接口上多个MMIO selector的实际选择优先级也需单列检查，不因较难就忽略。存在任何活动mmioSelect时，总线内部路径选择MMIO，即使当前没有MMIO req.valid也会阻止新NC进入；正常推进的活性以外部最终响应和LDU最终消费为公平性前提。

NC由两组各8项的仲裁器选择。各组保存上次握手仍等待的成员及上次位置，优先考虑其后方的第一个旧等待者；若该候选已撤回则回退当前最低有效索引，而不是偷偷跳到任意其他旧等待者。组间初始偏好高组，两组并存后在实际内部接受时偏向另一个有请求组。需要有真实低/高组、候选消失、连续和背压检查；不以普通全局轮转假设替代这个实际合同。

entry到总线之间有一个弹性寄存器：空或外部ready时可装入新请求，满且外部阻塞时保持原payload。同拍消费旧请求可以接入新请求。**内部接受entry请求和外部bus handshake不是同一事件**：entry已进入等待response而总线寄存器可能仍阻塞；该寄存器flush接常量false。此后redirect不能擅自删除已捕获请求，必须最终让外部接收、回包并按entry取消语义释放。MMIO优先变化也不能改写已缓冲的NC请求。

## 4. mid/sid、合并与SID重用的边界

mid回执只送对应entry，完整7位范围必须区分。response按slaveId.valid及sid匹配路由，允许外部NC合并：多个mid可绑定同一个sid，一次response同时完成这些尚在等待回包的load，之后分别唤醒/消费。不能人为要求mid→sid映射单射来规避合并。

**SID在外部response完成后可以重用，不能强行延长到LDU消费后。** 合法依据为开源 `cache/dcache/Uncache.scala:493-499` 的resp.fire→updateReturn，以及 `UncacheEntryState.updateReturn:166-171` 立即清除外部entry valid；其后可重新分配同一个sid。旧LQ entry若仍保持已返回数据，新sid同号事务的后续response不得覆盖旧data/error或制造旧异常。这是必须实测的组合风险；仅检查独立entry中“输入response已经被正确路由”的合同不能证明它正确。

总线代理记录每次外部接受的mid/原load和对应sid义务，允许合并与返回后重用；不能用DUT内部slaveId寄存器作为路由正确答案，也不能用限制SID分配来隐藏风险。未匹配sid的外部response、已取消但尚待回包的映射、乱序返回和ID重用都需检查。重复/无对应事务的response另外说明协议域，不与合法重用混淆。

## 5. wakeup、bypass、消费与异常

NC/MMIO各自的wakeup仲裁按entry低索引优先，一拍各最多一个；被更低索引占用的entry必须保持wakeup，不提前提供Out。ID0的ready删除是这个真实优先连接的常量化结果。

bypass仅匹配实际Out有效的entry、相同LQ(flag/value)以及正确replay类型。s0命中在边沿N接受，N后s1.valid/paddr有效；N+1后s2.valid/128位复制数据和错误有效。无匹配时两个valid按规定流水为假，不比较无效payload。等待wakeup、错误类型/flag/value、已消费/取消的entry不能误命中；同一entry被多个bypass lane命中应只消费/释放一次，但各lane都有自己的响应。

entry数据被bypass消费的同一边沿后产生其异常信息，父块同拍多entry报告以低entry索引优先选择一个，不能声称一个输出通道并行报告了全部事件；需检查优先选择和未获选信息的系统边界，而不是将它们虚构为已上报。父块异常不是相邻ExceptionInfoGen的选择验收。

## 6. 用例前可读功能点

| ID | 微架构行为 | 必需情形与公开证明 |
|---|---|---|
| LQU-RESET | 清空保存、entry和总线/bypass/rollback在途义务 | 初始、保存中、缓冲总线、等待响应/消费；重建并完整消费 |
| LQU-SORT | 输入按有效性和真实ROB slot排序 | 三lane六排列、稀疏、same-entry former/latter、相同年龄、ROB回绕；真实mid/恢复身份 |
| LQU-FILTER | 非本类、已有异常、其他replay或已取消load不占entry | 全10异常位、need_rep/cause区别、两拍redirect窗口；无隐藏总线/wakeup并验证容量 |
| LQU-ALLOC | 合格请求压紧分配真实entry ID | 三lane、稀疏need、全部16 ID、连续和回收重用；实际bus id/身份 |
| LQU-CAPACITY | 预分配不足时拒绝并正确恢复 | 余0/1/2、16项、回收等待、并发allocate/free、多轮池；rollback和后续容量证明 |
| LQU-ROLLBACK | 只恢复最老被容量拒绝的load | 部分/全部拒绝、FTQ/RVC/checkpoint、当前/历史redirect过滤和复用 |
| LQU-ARB | MMIO优先及两级NC公平选择不串数据 | 高低组、候选消失、背压、MMIO等待/发起/消费和NC并存 |
| LQU-PIPE | 弹性总线级区分内部接受与外部握手 | 空/满保持、同拍换入换出、重定向不丢已捕获项、属性及id不串 |
| LQU-ID | mid回执正确绑定，sid路由和合法合并/重用不污染身份 | 全MID/SID、未匹配sid、多个mid合并、response后sid重用而旧数据未消费 |
| LQU-WAKE | 正确类型和LQ按真实优先级唤醒 | 同类型/跨类型、多个entry、阻塞保持、取消同拍可见性 |
| LQU-BYPASS | LQ和类型匹配后返回规定s1/s2地址数据 | 三lane、NC/MMIO、正反匹配、重复lane消费同entry、128位复制和错误 |
| LQU-EXCEPTION | 消费后汇聚原元信息及错误，正确截断GPA | 无错也有效、错误组合、VA来源、50位GPA、高低ID和多消费优先 |
| LQU-FLUSH | 共享redirect按各entry阶段释放或延迟到回包 | 保存、未发、缓冲已接受、在途、唤醒/数据、连续取消及跨环 |
| LQU-REUSE | 真实回收后新代不继承旧ID/数据/异常 | 正常/取消、类型交替、旧bypass和延迟总线响应、完整池复用 |
| LQU-IDLE | 禁用输入和非匹配bypass不制造事务 | 空/占用/满池，pipeline合法推进，无有效payload比较 |

## 7. 独立参考与首轮实施顺序

完整参考将用独立请求UID/年龄和FreeList账本、16个已验收entry语义组件、仲裁等待者序列、弹性总线事务以及按到期边沿排队的bypass/rollback报告；父DUT始终保留真实下级RTL。父级response义务按尚未完成的总线事务路由，**已回包但未消费的旧entry不能因sid相等就再次接收新数据**，不能照抄硬件可能存在的错误路由作正确答案。

首轮先用端到端公开引脚事务检查：空闲、NC/MMIO正常总线→ID→回包→wakeup→bypass→异常；另用同SID合并正例和response后重用SID的旧data保持反例，检验第4节风险。该首轮probe/事务账单不冒充完整一般参考或覆盖闭环；随后补齐全部功能点、按首轮真实未覆盖行逐项分类并迭代。首轮失败保留为普通失败，不修改原始RTL、缩小合法SID域或xfail。

当前RAR-REL-001仍开放，不因本块独立进展将RAR、LoadQueue或LSQ整体标为通过。

## 8. 首轮实际结果与补例前分类

`load-uncache-initial-02` 为4 PASS/1 FAIL：正常NC/MMIO端到端和两个mid共用sid合并正例通过，合法SID返回后重用的旧data保持反例失败，记录为开放问题LQU-SID-001。完整原生构建为 `results/builds/20261018T054848945017Z-load_queue_uncache/`，真实22文件闭包。首轮probe不是完整通用参考，父块未验收。

本体364/1126=32.33%，真实闭包1421/3175，语义14/38 checked。本体762条缺口逐条映射：128条排序后第1/2项元信息、372条bypass各入口/entry的选择、24条redirect历史/rollback、238条较高entry异常汇聚；真实FreeList缺112条，16个entry共缺880条。所有缺口归类为既有功能点缺少情况，均不排除。两级仲裁/总线寄存器/wakeup仲裁的原生DA已经全命中，但高组公平、保持/替换等语义仍未检查，不能因此计通过。

下一补例先区分SID问题的必要条件：sid0/3/15、data与error分别保持；旧数据已消费才重用SID应正常；旧数据未消费但新用不同SID也应正常。不能通过禁止“返回后、消费前重用SID”来使测试变绿。此后仍需完整一般参考、排序/过滤/容量/仲裁/取消等所有缺口的补例迭代。

`load-uncache-initial-01` 另有空闲用例将端口s1Resp误写为1Resp的KeyError，已修正并在initial-02通过，历史保留；它与SID真实数据失败分开统计。

第二轮缺口已驱动真实父块的逐拍参考与全池补例：`load-uncache-full-directed-01` 28 PASS/1 FAIL，失败是测试将复用FIFO的槽号数值顺序误当分配顺序；逐拍参考并未失败。修正为按已记录的分配事件顺序验证，保留旧运行。该轮本体1120/1126，闭包3078/3175；剩余子块缺口为15个高ID entry各6条阶段取消、FreeList尾位置15由bank0写回1条，均为既有功能缺情形。补例逐ID等待/请求取消、16条合法同SID合并后的wakeup取消，以及先返回15项再返回bank0并完整复用，不引用叶子覆盖。

`load-uncache-expanded-01` 44 PASS/8 FAIL，7个SID真实失败不变；另一人工仲裁断言忘记最早低组独占时会保存下一次低组偏好，改为先低组1再高组8后，`load-uncache-boundary-directed-02` 2/2 PASS，未改模型或RTL。全部真实子块插桩行已命中；本体剩余6行(2816/3012/3088/3284/3360/3556)不是可达情形：写使能为相同NC/MMIO匹配向量并集OR，选择default需要二者都为0，条件矛盾。`tools/audit_lqu_static.py` 对固定哈希原RTL核对向量成员、使能和三目结构，枚举4行真值表证明，仅豁明这6个guarded defaults，仍保留1126和3175原始分母，不修改RTL/LCOV，不将其扩大为全DUT形式化证明。

最终边界补例前再明确：分别在保存、等待许可、请求、总线缓冲、等待响应、wakeup和数据阶段reset；rollback当前/前1/前2拍取消及过期反例；共享redirect下ROB former/latter及159→160回绕；三路bypass消费与redirect同拍。多个MMIO selector用一个单独**UNIT-INTERFACE边界用例**验证真实高ID优先，该用例pending跨过两个未完成MMIO不冒充合法ROB架构流量；常规MMIO优先用例仍按许可逐一推进。

`load-uncache-expanded-02` 64 PASS/8 FAIL，新增1项仅UNIT-INTERFACE边界：两个MMIO selector共用ready，低ID未上总线却进入response，随后不再发出自身请求；记为LQU-MMIO-IF-001，不宣称合法ROB架构流量可达。其余7项仍为合法SID重用的数据/异常问题。该运行期间调整了coverage完成证明（从消费后延至实际s2比较后），未将其快照作为最终源码冻结验收；另开全新运行，运行期间不再修改测试/参考实现。所有旧产物保留。
