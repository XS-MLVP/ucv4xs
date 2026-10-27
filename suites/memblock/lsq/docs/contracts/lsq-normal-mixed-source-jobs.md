# 完整八类型混合：普通生产者字段、外部依赖与精确恢复（实现前）

继承整体82项合同和精确S4/保留外部NC合同。仅开源893e1580b与固定53文件真实
LsqWrapper，原8种子0x7100..0x7107、八类型与权重(30,12,3,2,36,6,4,7)、600随机
步、后续公平排空及取消槽同物理槽新UID完成保持。旧回归12的1982/221和旧S4混合
2/6不追溯修改；首失败前缀不是完整随机成功。新增驱动仍是普通全输出fixture。

## 新发现缺口：不是再拼几个信号组合

- `MixedOwners.make`把普通Load/Store的hyper按UID翻转；TLB.scala553与
  NewStoreUnit217/334、NewLoadUnit普通issue合同要求它来自HLV/HSV指令。普通LD/
  Store/CBO不是这些指令，本profile固定hyper0/nonleaf0；不靠native LSQ接受任意
  元信息就宣称正常producer。
- 旧流只对最终Replay cause=C_DM的owner发refill，遗漏“真实Cache miss被MA/FF等
  更高原因遮住，或者fullForward/取消使本地Load不再等它，但外部job仍须还”的
  **整个外部所有权关系**。UID%16也不是不同在途Cache行可以共享的MSHR所有权证明。
- S4的head原因优先与head miss/MSHR选择是不同关系：NewLoadUnit1560-1569用完整
  head cause向量的C_DM位选MSHR，不是只看PriorityEncoder后的最小cause是否为6。
  要保留完整源cause向量，再分别检查one-hot投影、head优先和字段来源。

## NMIX-INSTR：保留完整随机意图，而非重新抽一个好测的类型

原8种子、八权重、别名/跨16B split/不同size/StoreSet依赖/背压/分支redirect保持。
CBO意图继续sticky，空ROB才能独立分配，BlockBack直到退休或取消；老Store已退休
但Sbuffer未消费仍合法。不增加read==head、物理SQ必须空等限制。物理窗口64与虚拟
128、LQ120、ROB活动半环<320继续按真实公开历史检查，不blanket放宽128年龄。

普通scalar/vector原操作类型保留；新profile只修确实不相符的hyper/nonleaf，不将
alias/split/NC/MMIO/CBO/错误流改成对齐cached hit。C_WF配置恒false的既有采样意图
仍记账、不重抽，但不伪造cause7正常输出。

**额外准入待核项（首跑前明确，不拿保留字段当当前producer证明）**：旧size4令
`isvec=1/vecWen=1`，而NewLoadUnit180-211的首次issue固定scalar且DontCareVectorFields，
MemBlock958又仅连接这三个NewLoadUnit。不能只因Opcode.scala452有内部lq就把这条
vector首次路径当成已证实；也不能删掉size4或改成8B来让种子更容易通过。本轮仍
完整运行这些原16B输入并逐条做LSQ接口/源事件投影检查，但把该首次vector-route
计为**当前正常上游准入未证明**，报告单列。后续须真实路由/decoder/config源码
闭环或具体配置不支持证明；即使种子全PASS，也不能因此叫全部正常producer已验收。

还须稳定TLB属性一致：旧make把PBMT-NC、PBMT-IO和普通cached放在同一VA页，却没有
SFENCE/权限变化历史。新普通PMA/cached保留原VA/PA及cached/store的8块别名关系；
NC、内存型IO的VA分别放入独立稳定PBMT页，**保留原PA**，所以与较老Store的真实
物理别名/字节冲突不会被映射修正过滤。非内存型io_load另用独立PMA设备PA区域，
它原来按UID唯一、并不与cached的8个PA块重叠。所有原size、word offset和跨16B
split保持；此为来源一致性修正，不是按已知失败选择PA，也不是源TLB已做native UT。

## NMIX-EXT：真实选定源事件的独立所有权

TLB和DCache在本DUT外；外部模型的miss/ready/refill/hint选择是明确边界假设，不是
native上游UT。为正常化来源，建立独立于SID总线的TLB/Cache在途job：

1. 外部翻译按实际S0的VPN登记，合并同VPN；16个公开hint标签不复用到仍在途的异页。
   实际hint还原job，之后retry才能以已知翻译hit；无槽时报告tlb_full而不是丢弃意图。
2. Cache按实际未kill的源访问、PA cache-line登记；同line可以合并MSHR，异line不能
   仅凭UID低位共享。满16时的实际nack是外部资源背压，不重抽指令类型或跳过访问。
3. Cache miss即使被更高Replay原因遮住、fullForward或redirect取消，也保留外部job；
   refills必须每笔真实偿还，不能重复无owner脉冲。未返回的同line重试仍miss/合并，
   不能仅因原Load.initial已置位就无依据变成hit。S4同line head/tail遵守这一关系。
4. S3反馈的MSHR/handled与TLB标签来源独立于最终选中cause；S4完整head cause向量
   优先，head C_DM为真才选head MSHR。实际grant和原slot反馈单列，不当本地结构释放。
5. SID总线仍按resp后即可复用，不等旧bypass；原owner的真实返回、错误和数据消费
   分开，NC Store ack本地完成也不免除后续外部响应。新Cache/TLB模型不改变SID寿命。

### 首次执行后补核：TLB标签不是S0锁死的单一容量状态

source-01实际8FAIL，source-02纠正检查器恢复/重复ROB代际后为1PASS/7FAIL。后者
四个5000公平拍超时都停在C_TM，所声明的真实hint早已归还。NewLoadUnit1170-1171
明确在**S2**采样hint.id/full；Repeater290-291的full是
`!canenq || ptwResp_ReqMatchVec`，不只是容量满。LQR916-925据full/同拍hint/跨段
前拍hint决定阻塞；不能在S0记录过miss后，哪怕job已回包仍一律带full=0。

后续不推迟hint来人为绕开这个窗口，而是在实际S2重建过滤器语义：若原job已真实
返回，或本拍返回与原key/job相符，该仍携miss的管线包为full=1并允许重试；尚在途
仍full=0、同VPN合并，仍不得把异job旧标签复用当原hint。独立checker从其公开返回
历史另行重建，不读取控制器full/cause作为答案。Cache满池nack的冷line也必须保留
外部miss意图直到有槽接受和实际refill，不能因首轮拒绝便在retry无依据变hit。

source-02另外三个FAIL是CBO corrupt到真实WB异常位的全输出失配，源修复不能屏蔽。
初轮检查器错误及四个源代理超时保留为各自原件，不当成已确证RTL活性缺陷。

### 原UID终态复核：不能借异常释放当正常复用

source-03实际2PASS/6FAIL/541源一致，23个S2 TLB早返回窗口已真实投影，四个代理
超时消失；五个CBO错误WB和一个老Sbuffer污染zero的严格FAIL保持。独立UID-v2
进一步拒绝两个绿色种子：28929的4个、28933的3个取消槽只找到新UID异常WB/释放，
没有正常完成见证。后续保留其2/6原结果与拒绝证据，仅扩展原600随机/公平之后的
独立清理段，补同物理槽的**非fault新UID实际完成**。原随机流与六个FAIL前缀不得
改变；故障WB/head-trap、正常本地完成、之后ROB取消和结构取消必须分别统计。

04实际2PASS/6FAIL/542源一致，UID-v2已核验两个通过种子的441UID互斥分账及95个
非fault同槽新UID完成；原六FAIL完整流SHA与03相等。自身DA36925→39695/59602，
新增2770/丢失0，19907剩行逐原source/line分类。此为声明的LSQ接口/外部源profile
进展，不将55个首次vector包的未证明上游路由升级为正常准入，也不关闭整体目标。

## NMIX-PIPE/ROB/RECOVER：原身份和精确时序

S0→S1→S2→同lane S3，split有真实同lane head/tail/S4和正确last/older revoke。
RAR nuke为原Load flushAfter，不是C_NK；STA nuke来自真实较老Store地址/mask。
S3 alignedType=size、lastBeat=最终PA bit6；WB/异常、Replay和VLQ credit分别记账。
S4异常向量/fullva/gpaddr选择head异常则head，否则tail，不OR两个异常或恒取head。

ROB只越过已实际执行的正常前缀；异常需原WB且实际ROB头才flushSelf，不因为LQ已
释放或年轻bypass错误就立即trap。fault-WB/head-trap、结构释放、结构取消、普通
成功是不同终态；每个真正取消的LQ/SQ物理槽均需新UID实际完成。不取消已发生的
Store外部副作用，所有被取消读的已发外部请求仍实际回包并丢弃。

## NMIX-ERROR与配置边界

Uncache.scala99-105把TL denied与corrupt投影为nderr=denied、error=corrupt&&!denied；
保留原两个随机错误意图和随机调用，只按真实生产者规则投影，不制造普通响应两位
同时为真。CBO Cache接口的denied/corrupt压力保持，WB故障不吞掉。

固定生成的StoreQueue.sv394-396/PhysicalStoreQueue.sv324-326对Uncache只保留方向ack
与resp.valid，没有保留该方向的denied/corrupt载荷输入。故不能把给共享Load错误
pin的Store响应说成Store错误传播已经验证；本批界定保留接口，CBO真实错误pin则
继续完整检查。EnableAccurateLoadError=false，不伪造准确S3 DCache错误或无job毒包。

## 检查、运行与证据

先实现独立源/公开历史checker：不读DUT内部或参考寄存器，不导入控制器cause/WB
答案；只接事先声明的指令/外部事件事实和实际输入输出，检查字段投影、连续阶段、
NoSpec/BlockBack、ROB头与真实UID/外部job终态。运行时全输出参考不减，默认0逐拍
JSON/0wave，每case只保留小摘要、失败边沿/原UID终态与必要有界事件。不能宣称未
保存新raw可离线逐拍重放。

首批实际运行原8完整种子，不设置seed过滤/xfail/skip，不追加更窄的替代种子。
失败保留首签名和未完UID，明确源准入已查/未查边界。之后按本目录自身原DA逐行
区分已有功能缺情形与新发现整关系，补例重跑；不借旧59595或叶子分子，也不以少数
种子成功验收整个目标。其他128/旧代、late旧ack/serial reset、后续统一回归与最终
完整请求审计不缩减。
