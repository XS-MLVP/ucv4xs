# S4异常不是head/tail的按位合并（独立补例前合同）

固定开源893e1580b、原53文件LsqWrapper、严格458输出Picker+xreactor；不扩为native
LoadUnit/DCache/Backend UT。回归11的480启动文件冻结，本轮只新增独立文件。原8类型/
种子、全部SID/CBO/Forward/RAR/Replay失败不改，本补例不代替完整随机或STRESS。

## 1. 本次补齐的可读功能

| ID | 人可读关系与实际义务 |
|---|---|
| S4E-IDENTITY | 一个原8B scalar跨16B，head/tail同lane连续S0，分别S1 PA/S2查询，head S3保存、下一拍tail S3与S4合并；原ROB/LQ/SQ身份不能换 |
| S4E-EXCEPTION | head有异常时最终异常向量、fullva/gpaddr/nonleaf取head，否则取tail；不能把两段异常OR。vaddr/PA/mask一直取head，isHyper按最终tail源，不混同 |
| S4E-WB | head异常/mismatch可独立写回，tail Replay不压掉它；clean head才依赖tail写回；head本身Replay时，tail有异常也不自动构成最终WB |
| S4E-REPLAY | head Replay原因优先于tail，而非两段全局最小；needReplay与WB独立。MSHR/handled选择另看head是否cache miss，不能简单跟随所选原因 |
| S4E-REVOKE | head S3先撤销自身Replay/异常查询；最终last=tailRevoke或headRevoke，older=非headRevoke且tailRevoke。不能只看合并后的needReplay |
| S4E-RETRY-FAULT | head Replay、tail异常但无WB时不得假造Backend trap；先真实grant/原slot反馈重试，head正常后才允许异常WB并精确取消 |
| S4E-TRAP-REUSE | 有真实源WB异常才flushSelf原ROB；幸存老Store/Load继续，取消原LQ槽以新UID正常完成；不是把trap或返还信用记完成 |

## 2. 固定配置与外部刺激边界

`Parameters.scala:195`的`EnableAccurateLoadError=false`，开源src无覆盖设置；
`NewLoadUnit.scala:1428`据此关闭S3准确DCache错误。**不生成该分支的正常例**，不把
通用源码有此分支等同于当前配置可达。此项是上游生产者配置依据，不是LSQ DA排除。

实际使用S2 `dcacheResp.tag_error`产生loadAccessFault(5)，以及有效TileLink-D forward
的corrupt且非denied产生hardwareError(19)，CSR cache_error_enable明确为1。前者
仍为cache命中，后者全量外部forward；两者均在S2成为exception并压制该段普通Replay。
mshrNack/cacheMiss仅作用于未异常、未forward的段。不借接口任意设置cause/异常作源证明。

上述DCache/TileLink输入并非本DUT端口，因此在**首次S0前**将选择好的外部刺激写入
独立事件记录。它是测试输入假设，不能冒称native DCache/LDU握手；审计只从这些
预先冻结的输入、真实Forward/RAR/RAW反馈及源规则独立推导最终S3字段，再核对实际
pins、Replay grant/反馈、恢复与原UID完成，不能把actor计算的答案当oracle。

## 3. 首轮情况与完整结束条件

head/tail：hit/hit；单侧AF、单侧HWE；head AF/tail HWE及反向优先；head异常/tail
nack；head nack/tail异常；head nack/tail miss与head miss/tail nack。各三lane，
word跨界与page跨界（tail非连续物理页）分别检查。MSHR head=3、tail=9，wrong-tail
refill不能解除选中head miss，必须真实正确refill后才grant。普通replay重试去除
一次性nack/miss，持续的tag/poison异常保持，不能为了结束变成干净完成。

程序用真实老Store与最老未执行Load保留RAW/RAR头；target的S4有两个真实查询。
异常WB后精确取消target，新UID同LQ槽正常执行，老Store必须原字节Sbuffer消费和SQ
释放、老Load真实S3/VLQ完成。非异常replay则必须原UID grant/反馈后真正完成。最终
每个原UID在完成或取消中守恒，所有取消同槽新UID完成，无遗留Replay/队列义务。

首次结果后分析本目录原DA的每条缺口，区分既有情况遗漏与整个源关系遗漏，补例
重跑并报告真实新增/旧命中丢失，不能借旧53079或59595分子。不修改共享参考/目标RTL。

依据：NewLoadUnit654-667、939-951、993-1006、1059-1097、1111-1146、1395-1457、
1483-1488、1560-1619、1711-1717；Replay对异常位的输出清零须按实际grant核对，不能
把源异常旧值强求在Replay输出继续保留。
