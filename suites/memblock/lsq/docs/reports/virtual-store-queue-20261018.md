# VirtualStoreQueue：快照、预提交、退休与恢复UT

## 结论

**本轮分层UT及覆盖迭代已执行，整体严格验收仍NOT_PASS。** `vsq-expanded-03`完整42例为40 PASS/2 FAIL，55/55 reached、54/55 checked，本体3125/3125 DA。剩余2个普通失败属于同拍dispatch+redirect的**UNIT-INTERFACE边界**，经真实上游路径核对不由正常producer产生；不能混称已证实架构缺陷，也不将失败改成skip/xfail或用行满宣称通过。继续独立DeqModule。

## DUT与独立参考

- 固定开源893e1580b，`VirtualStoreQueue`原始单文件，SHA `61685efc3ab12cba8d0695f23d033929b8ead3a30688d71dd51ecf2644bda822`；真实父实例是64物理项×Multiple2、SnapshotInterval1，不使用源码独立Main中的不适用配置。
- 原样Picker构建及原生实例化走钟PASS：`results/builds/20261018T091203225287Z-virtual_store_queue/report.json`。真实85输入/19输出；enq.canAccept/resp、reqStartPtr、uopIdx、isVec、deqCount.bits均不在公开top，未伪造动态覆盖。
- 静态端口/codec检查256样本与4个非法拒绝，见`results/vsq-codec-static-01/report.json`；静态检查不作功能验收。
- [用例前合同](../contracts/virtual-store-queue.md)先定义16类微架构行为，当前55个可读情形。参考以有序uop、flow区间end快照、ROB身份、UID与延迟事件账本为基础，不读DUT内部存储、mask或指针作答案。rdata输入不涉及本块，不混用Forward领域模型。
- 每个普通UID等到实际retiredPtr/empty和规定的preCommit/redirect输出检查后才可checked；reset中止与取消单列，逐拍消费fixture切换空拍。

## 覆盖闭环与真实运行

| 运行 | 实际结果 | 本体原生DA | 语义checked |
|---|---:|---:|---:|
| `vsq-initial-01` | 13 PASS | 1438/3125，46.02% | 32/55 |
| `vsq-expanded-01` | 30 PASS/4 FAIL | 3125/3125 | 52/55 |
| `vsq-expanded-02` | 35 PASS/2 FAIL | 3125/3125 | 54/55 |
| `vsq-expanded-03` | 40 PASS/2 FAIL | 3125/3125 | 54/55 |

首轮1687条未覆盖DA逐行归类，原始needs_review文件不覆盖，分类另存`vsq-initial-01/line-audit-classified.json`：

1. 1680条位于6477～14274，slot8～127的ROB/flow/end快照保存路径；属于既有ADMIT/INTERVAL/SNAPSHOT/REUSE缺少高槽及入口情形。补8个入口各自遍历128个虚拟槽，128uop只预留64flow；每块真实退休并由公平PSQ代理每拍至多2flow消费，再进下一块。全1024个lane×slot均有后续实际退休见证，非写行即成功。
2. 7条位于15848～15857，为已退休head需先release再walk的恢复路径；属于既有WALK/RETIRE/REDIRECT/RECOVER缺少情形。补已退休前缀、锁存ROB head、年轻取消后缀和后续新UID退休，全部命中，无行排除。

行满后仍补全同ROB多uop逐个preCommit、former/latter、0/1/多flow/16上限、预提交PSQ消费、部分区间不得提前释放、valid脉冲门控、双项释放、退休与消费重叠、空/零/部分/全取消、相邻redirect、ROB160回绕、活动/恢复reset及两个固定种子并发排空。

额外5个跨圈用例把物理位置合法推进到0/63/127/191/255，虚拟head推进到124，再分配跨128边界8项、取消后5项，并逐槽由5个新UID覆盖原取消区间、等待实际退休。完整SQ恢复指针与每个新end均检查；25条该专项同槽新UID完成见证全部成立，不能只用55个粗语义bin替代这类边界。

## 失败分类及检查器修正

`vsq-expanded-01`的两个reset失败源于检查器仍用旧活动状态比较DriveStable，而SV的reset在posedge reset已异步清空队列控制。依据原SV14413～16058修正pre-edge合同：立即检查已定义的empty/stall/redirectValid/physicalEnqPtr，未reset的ROB/payload/退休流水保持3个空闲时钟收敛，再恢复完整输出检查。不是修改RTL或用放宽预期掩盖功能失败；后两轮活动/恢复reset全部通过，旧失败与源码快照保留。

`VSQ-REDIR-IF-001`两例：已有ROB10/11的end为1/2，ROB12与redirect(ROB10,flushAfter)同拍输入；entry写入被禁止，但虚拟tail仍计入请求，公开有效redirect返回end2，严格接口期望仅幸存ROB10的end1。

**域限制来自完整真实路径，而非为通过添加限制：** `LSQWrapper.scala:499-502`对`!redirect`门控后寄存dispatch；CtrlBlock818/830/867、Backend235/578、XSCore150/210直通同源redirect与enq；`MemBlock.scala:494/1055/1058`仅给redirect加一拍，恰与dispatch寄存对齐。正常LSQ侧同拍互斥。新增lane0/3/7的合法dispatch前一拍对照全部通过；两个边界普通FAIL仍保留，未豁免。

## 公开历史与证据完整性

`tools/audit_vsq_trace.py`不导入参考模型或内部oracle，核验全部实际公开输入/输出、flow区间、ROB许可、退休事件、恢复end和UID守恒，并交叉检查详细引脚比较及每个checked语义proof的UID/provenance。

- `vsq-expanded-03/trace-audit.json`：4531条连续记录、4441条checked边沿、18个成功恢复响应。
- 2258次分配 = **2201实际退休 + 53取消 + 2 reset中止 + 2接口失败保留owner**。所有PASS用例实际排空；取消、reset和失败保留不当普通完成。
- 1024个入口×虚拟slot成功见证；36条取消后同虚拟槽新UID实际退休见证，其中跨圈专项25条全部对应5个被取消槽。
- 178份启动文件结束SHA与冻结副本一致，全部artifact/native build哈希核验通过。旧13/34/37例证据及审计器不改写。

本结果只覆盖此固定独立VSQ，未验收真实PSQ/StoreQueue或LsqWrapper。统一回归须增加新版本门禁，不能追溯更改849例/31DUT回归03。
