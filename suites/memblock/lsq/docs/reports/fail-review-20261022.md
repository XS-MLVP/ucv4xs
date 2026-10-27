# LSQ FAIL复核：首批根因、接口边界与验证侧错误

## 结论

本轮已经实际复核，不是只提出计划。四组问题在**不调用旧领域参考模型**的新
Picker/X Reactor公开端口探针中复现，并有必要条件对照；确认的是固定RTL的
模块接口违约，不是四个已经证明ISA后果的整核bug。另三条当前FAIL属于明确
producer域边界；历史reset误报、此次新探针端口错误和审计工具错误分别保留。
**未将其余FAIL默认认定为RTL问题或误报，未修改旧参考/测试/RTL。**

复核前语义合同：`docs/contracts/fail-review-v1.md`。
机器入口：`python3 -B tools/audit_fail_review_v1.py`（只读DUT原件，不启动仿真）。

## 1. 真实库存与去重

| 原运行 | 节点 | PASS | FAIL |
|---|---:|---:|---:|
| `lsq-progress-regression-15` | 2330 | 2103 | 227 |
| `replay-cause-lifetimes-contributor-regression-03` | 1765 | 1569 | 196 |

两者有195条共同失败，失败节点并集为228；最新独有1条是head预许可后自取消
的容量复用用例。**不把227和196相减作为修复量，不把228当作独立bug数。**

`results/fail-review-baseline-01/failure-inventory-v1.json`逐节点保留运行、第一失败、
完整失败详情SHA、候选根因和实例审定状态。165条可以按已有问题记录/明确用例
名称提名到13族，63条尚未提名；其中73条关联本轮四个已复核根因。
名称/同指纹映射只是检索，不证明原输入历史相同，因此没有把73条实例一键改成
“全部确认”。随机在第一错误停止后，公平排空和其它未执行阶段也不计新bug。

## 2. 四组独立实际复核

| 根因 | 有效探针/对照 | 判定 |
|---|---:|---|
| LQU-SID-001 | 4 PASS / 2 FAIL | 已确认模块接口响应身份违约 |
| DEQ-WB-001 | 3 PASS / 3 FAIL | 已确认模块接口写回错误保持违约 |
| LRQ-STRICT-001 | 9 PASS / 3 FAIL | 已确认无效输入对活动strict owner产生副作用 |
| RAR-REL-001 | 6 PASS / 2 FAIL | 已确认声明的release关联窗口错拍；过期额外重放不单独证明ISA错误 |

32条有效独立探针合计22PASS/10FAIL，分别取自fresh01的WB/RAR、fresh02的strict、
fresh03的SID。**这是32条不同探针的证据选择，不是一轮新的统一回归，更不是
跨dat OR覆盖。** 已完成组不重复执行来掩盖失败。

### 2.1 SID合法归还后重用：不是don't-care误报

新LQU投影只使用两个8B对齐NC Load，fullVA=VA、连续mask=0xff、FTQ结束半字1/3，
不借此前PA[6]错误helper提供上游合法性。实际req.valid/ready握手取得公开mid，
绑定外部SID3；A响应后SID归还、A数据未消费，B才重用SID3。每次当前SID都在独立
外部台账中真实活跃，原LQ的wakeup和s1/s2 valid逐项核验。

- A原响应为`0x0123456789abcdef`；B为`0xfedcba9876543210`。
- 随后消费A，实际s2是B数据（复制成128bit），不是A数据；B有error时A错误也变1。
- B使用SID4，或A先消费再让B使用SID3，共4对照都保留各自原数据/错误并完成。

固定`Uncache.scala:166..171,493..499`响应fire即归还外部entry；没有等LDU消费的
接口。`LoadQueueUncache.scala:94..110,190..197,438..439`则显示旧slaveAccept可
驻留到消费，SID匹配的新响应再次写旧uncacheData/错误；原生成件保留此机制。
这是有效输出中原事务的数据，不能作为无效载荷放行。

边界：公开LQU响应ready端口已被裁掉，不能伪造其动态读数；本轮观察真实response
valid及后续原LQ wakeup/有效结果，结合固定匹配SID和entry always-ready源关系。
原生Uncache分配器联合仿真、完整LoadUnit/Backend及ISA后果仍未由本探针证明。
这里的规范化NC投影也不等于已联合证明PMA/PBMT、翻译或Cache的实际生成历史。

### 2.2 WB背压：错误在实际消费时已经丢失

原head保持committed、addr/data有效及同一CBO请求，Cache req/resp各实际握手一次；
WB ready从响应前就置0，不在看到valid后才抢着拉低ready。响应刚返回时错误正确。
denied、corrupt、二者同时存在三种情况，经三拍背压后，WB.valid仍为1但错误都
清0，最终ready=1的实际fire也消费0。三个立即fire对照都保留原错误。

`NewStoreQueue.scala:1082..1117`在writeback状态无条件清错误而不等fire；原
`DeqModule.sv:395..415`同样清除。检查的是有效WB及消费边沿，不是valid=0数据，
也不只是检查背压期间的瞬态。这一接口违约已排除“旧模型比较太严”的解释。
完整Backend里该错误/仲裁/背压组合是否可达仍单列，不扩大为整核已确认异常丢失。

### 2.3 strict：输入valid=0并不意味着可以修改活动状态

原LD的ROB10/LQ20/SQ8保持，等待SQ7。没有地址wakeup，连续ready指针仍0。
ready位7单独为1时，三个入口各自的valid=0 feedback若schedIndex=0，都会让
原owner在合法解除前提前valid；输出原uop的strict仍1。

指向别slot、ready位未置位的9个对照均不提前。随后真正把连续ready指针推进到8，
每例均实际grant、使用公开slot成功反馈，最后观察Replay owner释放。
提前valid窗口内ready一直0，**不声称观察了错误Replay握手或ISA副作用**。

`LoadQueueReplay.scala:825..865`的otherwise会清strict，索引却来自无效输入字段；
`393..395`随后允许位图解除非strict阻塞。原SV同样使用未被valid保护的enqIndex
生成strict保留掩码。这里观察的是受污染后的**有效输出**，不是对无效输入payload
内容作不合理比较，因而不能简单归为“invalid数据don't-care”的误报。

### 2.4 RAR：前拍漏报与过期额外重放必须分开理解

以同一PA构造年轻Load ROB2/LQ2和老Load ROB1，LQ头0不越过未完成项，无revoke。
距离0/1/2/3与dataValid真假组成8例。dataValid为真时实际窗口为0/2，而声明窗口
为0/1：前拍release漏报，两拍前release却额外nuke；dataValid为假四例及其它
时间对照均符合检查。

原SV的release2Cycle.valid经过两个寄存器，而地址在原release有效时保存；固定
Scala的注释和关联表达式也明确指向需要捕获当前/前拍窗口。此错拍不依赖旧RAR
模型预测。**前拍漏报是需要处理的正确性问题；过期额外nuke可能只是保守重放，
不能把这一半单独夸大成ISA错误或第二个独立bug。**

## 3. 哪些是接口边界，哪些是验证侧错误

### 当前三个边界FAIL：不是已确认的正常整机bug，也不是删掉的“误报”

新`fail-review-domain-controls-01`实际6PASS/3FAIL：

- VSQ同拍dispatch+redirect两个入口仍FAIL；合法提前一拍dispatch的3个对照PASS。
  固定LsqEnqCtrl先`!redirect`门控再寄存dispatch，MemBlock对同源redirect也寄存
  一拍，完整连线到VSQ没有额外延迟。已核对utility gitlink中实际寄存语义，
  32组布尔门控组合都排除此正常路径的同拍重叠。
- 多MMIO selector例把pending直接越过两个未完成MMIO，仍FAIL；正常许可/优先
  对照PASS。固定pending来自ROB deq头，不能把该人工许可历史叫正常提交历史。

三个新FAIL的实际断言、tick和结果与旧统一回归相同；完整错误文本的栈行号不同，
因此**没有伪报失败全文SHA相等**。原件不动，台账同时保存两份详情SHA。

### 已确认的验证侧问题，不能冒充当前227个FAIL的修复量

1. **历史VSQ异步reset误报（2例）**：旧`vsq-expanded-01`在reset已异步清空指针
   后，仍在before相位期望io_empty=0，实际为1。固定SV明确posedge reset清指针；
   正确相位的当前两例重新执行均PASS。它们不属于当前227个失败。
2. **本轮新探针访问不存在的ready端口**：01有18次KeyError，修正后02的SID仍有
   6次另一ready端口KeyError；总24次失败执行、18个不同新节点。均属新测试接口
   假设错误，不是RTL问题，也不扣减旧FAIL。两次纠正都重建旧测试字节/整个测试
   聚合并保存sole diff；只补跑未完成组，未改旧参考或吞掉失败。
3. **旧PA[6]推导**：固定256bit总线对应32B refill，应为PA[5]；64B是Cache块宽。
   这是真实验证侧来源错误，削弱旧PASS的合法源声明，并不使SID/WB等其它FAIL
   自动变成误报。当前新探针不复用那些错误helper。
4. **首次本轮审计工具错误**：source_summary只统计docs/contracts，第一版guard
   却扫描全部docs，造成假“源码改变”告警；已纠正比较范围并只续审，无DUT重跑。
   原失败日志/receipt保持。后续审计通过，不回写原失败。

## 4. 额外检查：head许可后自取消还不能裁定

最新独有的必需FAIL首先报的是`RuntimeError: coroutine raised StopIteration`，
触发点为`StoreActor.step`在live owner中查找Sbuffer字节身份，不是RTL断言。
独立读取现存compact witness仍确认tick932输出属于被取消的旧UID315/SQ254，
而不属于64个replacement owner；实际PA/mask/字节也对应旧owner。

actor.cancel已从live表删除该旧owner，随后身份查询失败。原EnterSbufferQueue
没有redirect端口，已接受请求可能持有到之后消费。但是现存compact证据不重建
早先FIFO接受时刻，也未证明头precommit后的flushSelf可由完整合法上游产生。
因此**不能因异常来自Python就将它关闭为误报，也不能仅因看见旧字节就确认
正常整核bug**。必须继续审许可后取消的合法性及不可撤回副作用的账本规则。
原required/FAIL保留，未把旧字节错归给replacement，不放宽参考。

## 5. 证据、保持与下一批

- `results/fail-review-baseline-01/first-batch-review-v1.json`：四根因逐例见证、源链、
  域分类、历史误报、端口纠正、head待定项及真实审计失败。
- `results/fail-review-baseline-01/failure-inventory-v1.json`：228个去重失败节点，
  各自原始范围/详情指纹/候选族/未审定状态。
- `results/fail-review-baseline-01/next-review-queue-v1.json`：下一批52个FWD候选、
  33个Deq所有权候选、4个共享总线候选及63个未提名混合/head节点的具体义务。
- 新测试：`tests/fail_review/{conftest.py,test_public_contracts.py}`。公开端口直接
  驱动/采样，纯类型/编码只负责接线，没有读私有寄存器或调用旧模型算预期。

前后核验旧验证源码聚合和141个原产物SHA全部保持，四旧索引未改；原227/196份
FAIL及覆盖分母不变。所查原生成件的相关assert/fatal计数为0，不能以“没有断言
触发”证明合法性。默认仍无逐拍JSON、波形或完整新源码副本。

下一步优先用独立PA字节来源/SQ完整代号复核Forward三族，再查split/zero/特殊
完成的原owner与连续退休前缀。混合种子必须按第一违约最小化，不能只凭引脚名
相同就关闭为已知问题。首批四根因确认不代表228个实例全部审定或LSQ整体验收。

最终重审已实际exit0（`first-batch-final-audit-receipt-v1.json`，5.254937秒）：
连续两次重算新证据，四个guard/台账/报告文件SHA幂等，无重复归档；旧141原件
及源码聚合仍保持。该重审没有再运行DUT，首次审计失败日志仍在。
