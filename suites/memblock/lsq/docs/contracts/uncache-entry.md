# UncacheEntry：不可缓存load的发起、ID绑定、唤醒与消费

状态：**全部16个实际ID已完成当前接口配置独立UT与覆盖迭代。** `entry-expanded-01` 384/384 PASS，各top106/106行，ID0语义75/75、ID1～15各77/77；另有86129条公开引脚记录的独立事件历史审计，见 `docs/reports/uncache-entry-20261018.md`。同一个语义参考覆盖16个真实特化top：`UncacheEntry`为ID0，`UncacheEntry_1`～`UncacheEntry_15`为ID1～15，各自独立原生DUT和覆盖结果。未以ID0推断其他ID，也不以独立entry通过替代LoadQueueUncache父块。

## 1. 职责和实际接口差异

每个entry保存一条MMIO或NC load。MMIO要等到ROB允许的提交前位置，NC可以先发；总线接受请求后，即使被redirect取消也必须等回包再安全释放。正常回包先向LDU发wakeup，再保持数据直至LDU replay/bypass消费；消费同时释放entry，并在后一拍报告异常元信息（包括无错误的完成）。

- req是**Valid-only，无ready**；一次只能保存一个所有者。上层FreeList负责合法分配，单测不得随意覆盖活动entry。
- ROB pendingPtr需要经过一级寄存后参与MMIO发起，按ROB160项/former-latter关系判断不晚于pendingPtr，而非仅value相等。NC不受该等待条件限制。
- uncache.req有valid/ready，输出ROB、48位paddr、50位vaddr、8位mask、nc、memBackTypeMM；mask选paddr bit3对应16位输入mask的低/高8位。
- idResp是Valid-only，mid宽7、sid宽4。只有mid等于该entry ID且当前有所有者才绑定sid并拉高slaveId.valid；其他entry的广播回执不能污染当前路由。
- **uncache请求ID输出在各实际top中已删除**，只通过mid接受/拒绝和slaveId输出检验特化ID；不能伪造req.id端口。data response已由父级按sid路由到本entry，本top没有response ID输入或response ready输出；它们的路由验证属于LoadQueueUncache。
- ID0的mmioWakeup.ready、ncWakeup.ready常量化为true并删除；ID1～15保留二者，可真实背压。全部变体仍有mmioOut.ready和ncOut.ready。
- mmioSelect表示保存的MMIO处于非空闲事务阶段，不等于uncache.req.valid或总线请求已经握手。slaveId.valid则可从绑定保持至释放。
- data输出分别为mmioRawData.lqData、ncOut.data，64位；附带LQ120指针、paddr和两个响应错误位。exception输出有延迟valid、原ROB/fullva/gpaddr/虚拟化字段及8个保留输入异常位、两个响应错误位。

## 2. 合法事务和边界

普通合法请求为mmio与nc二者择一；req仅在entry无所有者时到来，且父级已阻止被当前redirect取消的输入。`flush`优先于req写入，本拍flush时送新req会被丢弃，不当作可用的零气泡分配协议。

response仅在真实uncache.req握手后、当前等待回包时到达，最多一次。正确mid的idResp在握手后/同拍绑定、response之前；不测试父级不可能路由的“无sid却收到data”来声称支持该协议。其他mid可在任意阶段广播；mid的高3位也要检查，不能只比较低4位。sid完整遍历0～15并检查保持。响应错误00/01/10/11都有效。

ROB和pendingPtr处于合法半环窗口，含former/latter和159→160回绕。LQ指针保持合法value0～119并含flag；地址与完整异常元信息只在有效输出阶段比较。输入保留异常位的透传可作为entry接口级元信息检查，但父级普通分配会过滤已有异常，不能据此宣称父级异常入队合法。

## 3. 生命周期和相位

参考用“保存请求/等待ROB、等待总线接受、等待回包、等待wakeup接受、等待LDU消费”的事务阶段，不复制RTL编码、不读取内部状态。

1. 边沿N保存新req，不把同拍输入直接当成已发总线请求；下一边沿用旧保存项、旧寄存pendingPtr决定是否进入发起阶段。
2. 未握手的uncache.req保持valid和全部payload；redirect命中时当拍抑制请求并flush，不造成副作用。
3. 总线接受后等待response；期间redirect只记录待取消，不立即释放。后续redirect撤回也不能遗忘取消。真正回包同拍产生flush，条目不向LDU报告数据。
4. 正常response保存64位data、nderr、error，并进入wakeup阶段；wakeup携带原LQ身份。ID1～15被ready阻塞时valid/payload保持，不能提前出现Out有效。
5. wakeup被接受后Out有效，保持到对应NC/MMIO消费者ready。消费输入在边沿N接受时产生flush/释放；N之后的寄存输出exception.valid即对应该次消费（一级寄存），N+1无新消费时撤回，不再额外等待一个idle边沿。内容为原load完整异常元信息和响应错误；没有错误也有exception.valid，不按error门控。
6. 每次重用重新初始化错误和sid有效，旧data/异常/取消状态不得泄漏；reset取消旧义务而不算正常消费或回包。

上述相位先用最小原生用例确认，不靠散落Step(n)修补checker。对actual output的无效payload不比较；mmioRawData在mmioOut.valid时才有数据意义，slaveId.bits仅valid时比较。

## 4. redirect与可见性的细节

- 等待ROB或总线未握手时可立即flush；等待回包时必须延迟到response，以避免过早重用并误收旧数据。
- wakeup阶段同时出现当前redirect时，源码只用**上一拍保存的取消位**屏蔽wakeup.valid，当前拍可能仍有wakeup握手；同时flush终止后续数据，不能擅加当前redirect门控来修改接口合同。
- Out等待消费阶段不以当前redirect直接屏蔽Out.valid；redirect命中与ready同拍时仍可能发生消费和后一拍exception报告。这是实际保留接口的行为，不能声称所有被取消的数据都没有任何公开输出。
- flushAfter/flushSelf、same-entry former/latter、较老请求幸存及ROB跨环都需检查；较老/无效redirect不能取消当前所有者。

## 5. 用例前语义功能点

| ID | 人类可读行为 | 必需检查 |
|---|---|---|
| UE-RESET | 初始和活动/在途复位终止旧事务且可重用 | 保存、等总线、等回包、wakeup、消费阶段；reset后无旧完成并重新实际完成 |
| UE-ALLOC | 一个所有者保存完整请求，旧记录不被禁用payload覆盖 | MMIO/NC、LQ flag/value、地址/属性/元信息透传；无req.ready的边界 |
| UE-ISSUE | MMIO等待寄存的ROB许可，NC不等待 | pending较老/相同/更晚，former/latter、跨环，pending改变的一级相位 |
| UE-REQ | 总线请求在背压下保持并且只握手一次 | 0/短/长背压、原ROB/地址/vaddr/属性、握手前redirect |
| UE-MASK | 选择正确8字节half和保留请求字节范围 | paddr bit3真假、16位mask的单bit/多bit/互补值 |
| UE-ID | 只有本entry完整mid能绑定sid且不串生命周期 | 全16个实际ID、所有其他mid及高位别名反例、sid0～15、回执保持/释放/重用 |
| UE-RESP | 响应数据和两个错误位正确保存至消费 | 00/01/10/11、数据高低位、延迟响应、NC/MMIO输出路由 |
| UE-WAKE | 先唤醒正确LQ，再开放数据给LDU | 两类型、ID0实际常量ready边界、ID1～15独立背压、非选择ready不影响 |
| UE-OUT | 数据和身份在消费者背压下保持，消费后释放一次 | 两类型、短/长背压、错误/数据保持、消费与flush、连续重用 |
| UE-EXCEPTION | 每次实际消费在正确后一拍报告原元信息和响应错误 | 无错误也报告、两个响应错误及8输入异常位、fullva/gpaddr/Hyper/PTE、单周期valid |
| UE-FLUSH | 不同事务阶段按正确时机取消，已发请求要等回包 | 等ROB、等总线、等待回包的粘滞取消、wakeup/Out、当前/历史redirect与同拍消费 |
| UE-AGE | 取消/发起按真实ROB slot而非value比较 | ROB160非2幂跨环、former/latter、flushSelf/After、老请求幸存 |
| UE-REUSE | 正常完成或取消后的新事务不继承旧sid/error/data | 同/异类型、各slot元信息、重复多轮，实际新请求/响应/消费证明 |
| UE-IDLE | 无效输入和非选择通道ready不产生额外事务 | req/idResp/resp/redirect禁用payload，空闲稳定和各保持阶段 |

功能覆盖分别记录reached/checked。发过req不等于完成：发起、ID绑定、wakeup、数据与异常的checked均需实际对应公开valid/handshake及payload比较；删除/取消需观察flush、无错误旧完成，并证明后续可重用。所有reset打断的旧证明单列取消，不冒充通过。

## 6. 首轮与补例计划

先对16个实际ID各执行空闲、最小NC、最小MMIO三类用例，实测保存→发起→总线→idResp→response→wakeup→Out→exception相位；每ID独立保存行/语义缺口。对未覆盖行逐项映射至等待、背压、匹配ID、取消、保存元信息和异常路径，明确缺少情形还是遗漏功能；补前后拍/并发/错误/全部路由/取消及合法随机后重跑。只完成导出或ID0不能验收家族；更不能替代LoadQueueUncache真实父块排序、容量、仲裁、sid路由与bypass组合。

## 7. 首轮实测和补例前缺口分类

16个原生构建均已导出/实例化走钟通过，报告为 `results/builds/20261018T051833889230Z-uncache_entry_0/` 至 `20261018T052247749623Z-uncache_entry_15/`。首轮 `entry-initial-01` 为 **48/48 PASS**（每ID三例），各top本体100/106=94.34%；ID0语义17/75，其他ID各17/77。两点分母差别仅是ID0没有实际wakeup ready，未虚构其背压已测。

首轮同时实测确认exception一级寄存的pre/post相位：消费边沿后即为该次报告，无新消费的下一边沿撤回；用上文明确边沿定义消除“后一拍”文字的歧义，不改变模型或测试预期。

每份top的6条缺口逐条定位：等待ROB阶段取消的判断/赋值各1条、总线未接受阶段取消各1条、wakeup阶段取消各1条；ID0为252/253、263/264、273/274，其他ID整体偏移2行。16份共96条，均为已有UE-FLUSH/AGE/REQ/WAKE/REUSE缺少阶段情形，不排除可达行。原始needs_review清单与人工映射分开保存。

补例在开发前明确：三个背压位置、全部7位mid正反路由和16种sid、请求mask两半及逐字节、64位data逐位、四种响应错误和8个保留源异常位、pending寄存相位/ROB年龄、五个阶段分别redirect和reset、已发请求粘滞取消到回包、当前wakeup/消费与取消同拍、类型交替重用与sid/error清除、禁用payload和两个种子的合法事务随机。即使6条行缺口已由少量取消用例命中，也必须继续补齐以上语义，不以行覆盖替代功能。

保留 `entry-directed-01` 的38通过/4失败：失败发生在用例外层人工断言，逐拍严格参考与DUT并无不一致。原因是本工程共享 `RobPtr.encode` 默认 `former=True`，两组测试误把省略该参数当作latter。现将former/latter显式写出；不改模型年龄语义或目标RTL。该失败属于刺激/断言标签错误，不作为硬件缺陷。
