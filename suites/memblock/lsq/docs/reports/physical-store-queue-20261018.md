# PhysicalStoreQueue阶段报告：真实写入、转发与子块错误的父级复现

## 结论与范围

**完整覆盖迭代、公开阶段参考和独立历史审计已执行，但六项语义仍严格失败，NOT_PASS。** Picker构建真实五文件闭包并完成原生实例化/走钟：`results/builds/20261018T104340012291Z-physical_store_queue/report.json`。本体SHA `c1ea3980b9d75a42a68a0b31867102a8145ebd4932ebb055cc59be4b37bab166`，119实际输入/333输出，不使用Python子块替换真实ForwardModule、DeqModule、EnterSbufferQueue或UnalignQueue。

| 运行 | 结果 | 本体DA | 真实闭包DA | 语义checked |
|---|---:|---:|---:|---:|
| `psq-initial-01` | 16 PASS/5 FAIL | 3733/5396 | 4113/5817 | 15/42（含下述一项过宽口径） |
| `psq-expanded-01` | **18 PASS/5 FAIL** | **5387/5396** | **5772/5817** | **21/43** |
| `psq-expanded-02` | 29 PASS/5 FAIL | 5396/5396 | 5814/5817 | 30/43 |
| `psq-expanded-03` | 43 PASS/9 FAIL | 5396/5396 | 5817/5817 | 38/44 |
| `psq-expanded-04` | 44 PASS/19 FAIL（含actor过强NC时限1例） | 5396/5396 | 5817/5817 | 39/45 |
| `psq-expanded-05` | **45 PASS/18真实FAIL** | **5396/5396** | **5817/5817** | **39/45** |

最新轮同时保留定向probe、全槽长流、完整公开PSQ逐拍阶段参考与外部UID代理；独立审计按各自实际范围分列，不冒充每个probe都具有UID账本。不是StoreQueue/LsqWrapper验收。实际VSQ、Backend和更高层约束仍需真实层次验证。

## 用例前语义与首轮检查

[合同](../contracts/physical-store-queue.md)先定义STA/STD先后、S1/S2属性、连续就绪前缀、preCommit/retired许可、原始字节、真实forward/写出、恢复/重用、容量和公平排空等14组可读功能。真实无valid S2按前拍同lane STA配对；STA/STD被优化为低6位SQ输入，合法域必须由外部发行账本约束，而非伪造完整flags引脚。WFI常真及inactive恒false已优化删除，不记动态覆盖。

首轮21例包含：空reset；两lane×STA先/STD先/同拍×preCommit/retired的12个完整写入→真实三lane转发→Sbuffer背压→实际消费→SQ释放；三个无等待错误CBO正常控制；三个背压后实际WB错误失败；两个真实split尾段消费失败。

独立`audit_psq_initial.py`核对577条连续记录、181个显式检查、36个真实forward响应、12个正常store实际完成与信用；210份启动文件结束SHA及全部artifact/build哈希一致。原始证据见`psq-initial-01/initial-audit.json`。

## 子块故障经真实PSQ公开输入复现

- **DEQ-WB-001**：通过真实STA/STD写入CBO，经S2及真实preCommit许可，Cache req/resp实际握手；3个有错误响应在WB等待后，真实父级`writeBack.valid && ready`消费异常7/19为0。无等待三个错误组合均实际完成一次SQ释放。公开高位VA、isHyper和ROB flag/former身份仍正确。
- **DEQ-SPLIT-WLINE-001**：真实两段STA保存普通8B头store，旁边真实STA/STD写入未获head许可的CBO.zero；VSQ代理enq=2而preCommit=1，仅许可普通头。无等待和3拍背压两例在实际Sbuffer fire上尾段地址/mask/data正确，wline却为1而非0。

这证明**PSQ的公开输入可以到达两类叶子故障**，不再仅为直接驱动Deq原始rdata的反例。但真实VSQ/StoreQueue/Backend是否允许相应发射/许可/背压组合仍未运行证明，不能据此直接宣称架构错误或整line破坏。五个普通失败没有xfail/skip、问题表豁免或RTL改动。

首轮`wb_error`同时由无等待控制填checked过宽：第二轮单列`wb_response`，严格背压`wb_error`保持未checked；旧42目录和产物不改，新目录43项不能直接把分母差当覆盖退步或改写历史。

## 逐行分类与第一次补例

首轮1704条缺口（本体1663+依赖41）全部保留原source/line，另存`line-audit-classified.json`：

1. 高物理槽的STA/S2/STD/CBO数据/控制、两输入lane保存路径：原合同已有功能缺少槽位/入口/复用情形。
2. 距离跨first_flag与redirect输入寄存：已有容量/四圈/恢复情形尚未执行。
3. 下级NC/IO、ESB奇数尾、Forward低域选择、UQ第二页/消费/恢复：父级合同已经定义但没有实际用例，不能借叶子行满替代。

新增两个真实长流，不只扫入队行：

- **256个普通owner**：64slot×4代、两输入lane交替映射，1/2/4/8/16B含连续vector chunk；每个slot在每代均由三个真实load入口读回原数据，再按程序顺序实际写入Sbuffer并完成64个SQ credit，才允许下代复用。
- **128个CBO owner**：64slot×两输入lane，逐head发射四类操作；96次Cache req/resp→WB和32次真实zero Sbuffer写出→flush→WB。每个owner实际释放一次，不将zero的早期写入当SQ完成。

`audit_psq_storage.py`只读原始公开引脚，从STA/STD重建原始地址/size/data与zero强制数据、从实际Sbuffer/WB和sqDeqPtr重建所有者。两个长流384分配=384完成，768个forward响应、288次Sbuffer消费（1838有效字节）、128次WB、96次Cache请求。每条长流各覆盖128种地址slot×lane及数据slot×lane；汇总256是两个独立长流之和，不声称硬件有256个输入组合。

全轮2947条连续记录、957个显式检查及213份启动源码结束SHA核验；`psq-expanded-01/storage-audit.json`保留全部5个失败的实际fire tick/源SHA。剩45条再逐项分类，分母5817不变：

| 来源 | 未命中 | 具体语义缺口 |
|---|---:|---|
| PhysicalStoreQueue | 9 | redirect输入完整身份寄存尚未运行 |
| DeqModule | 12 | NC/IO真实属性→请求→确认/响应→完成 |
| EnterSbufferQueue | 6 | 需要奇数尾时第二输入写slot0，普通双入始终偶数尾 |
| ForwardModule | 3 | 物理窗口需非零head跨low/high边界，普通四圈对齐窗口未触发低域分组 |
| UnalignQueue | 15 | 真实第二页保存、消费和取消/恢复 |

## 第二轮逐行补例与完整语义

45条缺口均经真实父级情形闭合：两lane memory NC/PBMT IO/device IO，真实请求保持及load方向确认负例；两项UQ非连续第二PA的四段实际写出、部分消费不早credit；在途S1/S2/STD恢复及取消后同槽新数据完成；head1奇数尾和head60/upper124的低年龄slot59在三lane查询后全部消费。无新增排除、闭包分母5817不变。head1仅低域slot0还不足触发反转位序后的中间选择分组，head60补齐最后3行。

完整参考用公开STA/S2/STD历史及标量SQ序列组合已有语义子参考，逐拍检查公开ready/许可/写出/异常/forward及PA字节安全；外部actor不读取模型内部状态，独立生成虚拟128/物理64窗口、乱序地址/数据、TLB重试、UQ、ROB许可和总线回应。测试覆盖异常阻头/取消复用、容量128、三类活动reset同槽新UID完成、forward缺数据与最年轻字节、deq边缘可见窗口等。

两个必要条件随机对照（不含zero、load在物理窗口内）各300 UID公平排空，含其他CBO、NC/IO、跨word/page、重试和独立背压；它们只填单列`controlled`，不能填完整域`seeded`。三个完整域种子分别遇到zero所有权、split wline及FWD-SQID-001，保留失败停点和328个未完成UID。

## 新发现：CBO.zero错误借用旧store完成

`DEQ-ZERO-001`：源码`NewStoreQueue.scala:975-978`以公开Sbuffer head任意fire退出writeZero，而该请求可以是EnterSbufferQueue中的旧普通store，不一定属于当前zero。最小真实PSQ例先退休普通SQ0并保留其请求，之后真实STA/STD发射ROB头CBO.zero SQ1。tick46只消费普通VA0x10000/PA0xabc000、wline0；tick50实际zero WB，tick56已释放至SQ2；**自己的VA0x20000/PA0xdef000零写从未发生**。无旧普通项的必要条件对照有一次正确零写并完成。

最初由独立UID账本发现，首版Deq参考也误用了任意消费条件；现已收紧为当前zero完整SQ身份且wline为真，旧模型/失败快照保留。严格随机在tick808更早捕获非法flush，最小probe则继续到实际WB及SQ释放；不以模型和RTL同错宣称通过。尚未运行真实VSQ/StoreQueue/Backend的相应序列，不提前声明架构后果。

## 独立审计与当前剩余验收项

`results/psq-expanded-05/lifecycle-audit.json`、冻结审计器及原生manifest核验：

- 7424条连续被动公开输入/输出记录，1254个probe比较；完整参考3870条记录中3858条完成检查，12条为严格失败停点。
- actor独立重放**1429分配=1097完成+1取消+3 reset中止+328失败保留**；1064次实际Sbuffer fire、186次WB、75次Cache请求、153次Uncache请求、52次NC确认、21次UQ接受。
- 3条活动reset、1条异常取消均有**同物理槽新UID实际完成**，不能用空reset或任意新事务替代。
- 另两个长流合计384分配=384实际完成；与actor范围分列，不重复计数。
- 226份启动源码与结束SHA一致，全部artifact/build哈希核验；本体5396/5396、闭包5817/5817 DA不代表分支/表达式/任意配置穷尽。

18个真实普通FAIL分为：ALIAS3、RANGE6、SQID1、WB3、split wline3、zero owner2。六项未checked为`PSQ-FORWARD.alias/range`、`PSQ-SPECIAL.wb_error/split_wline/zero_owner`及完整域`PSQ-CONCURRENT.seeded`，全部已reached并有实际失败证据，没有未运行点被算通过。`audit_psq_codec.py`另静态核验256组119输入/333输出映射与9个非法宽度拒绝，不算原生功能UT。

首版完整参考启动未知传播/活动reset异步投影、actor的NC固定时限误差分别保留在旧校准及expanded-04目录，新轮仅修正检查器合同，不改目标RTL、不放宽实际错误/控制所有权。

## 必需后续

StoreQueue必须保留真实VSQ/PSQ，再推进LoadQueue和LsqWrapper完整组合；此前1075例回归04不含Deq/PSQ，本轮独立结果不追溯混入旧门禁，未commit/push。
# 新增：66例真实PSQ回归与完成顺序独立审计

回归06为**45 PASS/21 FAIL、46 reached/39 checked、闭包5817/5817**。新版
`psq-lifecycle-audit-v2.json`核验7489记录，原63例全部原始输入、pre/post输出
和tick逐bit匹配已独立审计的旧冻结轮；新增3例单独重建NC/IO完成与Sbuffer
消费0次后head0→1的证据。旧63例及其1429 UID计数不改写，也不以新签名门禁
冒充新生命周期审计。新增special_order仍FAIL，详见
[回归06](lsq-progress-regression-06-20261018.md)，本模块保持未验收。
