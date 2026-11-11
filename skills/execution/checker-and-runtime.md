# 如何实现 checker、并发采样和完成性检查

## 何时使用、准备什么

开发环境、修改比较器或复核假通过时使用。输入是有效条件/时间保证明确的合同、独立 oracle、实际生成产物和测试选择清单。

## 怎么做

1. 建立“需求 → 驱动字段 → 观测字段 → 比较器 → nodeid”表。缺字段立即报错；未比较项注明合同原因，不能靠默认 0 掩盖缺接线。
2. 对每字段按 valid/mask/选择条件比较，合法额外事务用绑定地址、类型、UID 和时窗的允许集合处理；不能因模型不支持就开整段 `allow_unexpected`。
3. 在约定采样沿取得全部通道快照，再统一更新状态/账本。等待某通道仍须服务其他通道，不能由 if/continue 串行分支漏掉已经 fire 的事件。
4. 用不可变 UID 分开记录 offered、pending/retry、accepted、completed、合法取消和 outstanding；保持多拍不重复计数，按源分别对账。账本等式依具体协议定义，不机械套用总数守恒。
5. 对要求最终接受/完成的测试设目标和 watchdog；收尾预算耗尽要失败。允许拒绝、取消或无活性保证的情形按合同处理，不能任意加“所有请求最终完成”的假保证。
6. 对 kill/flush/redirect/reset 列必须、禁止及允许延后的全部副作用；当拍检查后再发送新身份事务，验证无旧异常/数据/目的地残留。
7. 对账定义、重复/失活测试、真实 collection 和实际选入结果；核实所依赖断言存在于生成产物并启用。`sample()` 仅计 reached；checked 必须指向实际执行的区分性断言。
8. 做受控自检：错键、缺受检字段、翻转 expected/observation、未授权事务、零接受、接受后不完成、背压重复计数。合同要求的异常必须失败，合法例外仍应通过。标明注入层，避免把 checker 自测计为真实 RTL 功能证据。

## 产出

字段/比较器对账、同拍事件对照、逐 UID/源账本、收尾条件、默认 collection 与额外探针清单、checker 自检结果、实际断言/公开观察位置及剩余盲点。

## 如何验收

正常场景通过；一个代表性错误变体在预期检查点失败，而不是被 setup error 偶然挡住。同拍多通道不丢事件，保持多拍不重复计数；取消不留非法副作用，未偿还义务不能正常退出。

案例：[十二类踩坑 P02/P03/P06–P10](../../docs/lessons/rtl-verification-soundness-20261026.md)。失败归因见 [triage](../review/triage-and-evidence.md)。
另见 [Sbuffer 的整用例反例与修复](../../docs/lessons/transaction-boundary-repair-20261101.md)：
正常对照与零接受、隐藏写出、错分类、反转 oracle 使用同一用例，必须在承诺的检查点
被区分；Decoupled 不自动要求 Irrevocable，快照义务与 DUT 的保持合同分开。
异步pytest fixture未必在yield处收到正文异常；已报告FAIL不应被正常finish重复变成假ERROR。
桥接时必须保留独立清理错误，且正文PASS/缺报告仍严格收尾，吞掉比较/取消错误不能成功；
见[IFU运行边界及控制](../../suites/frontend/ifu/docs/spec/verification/transaction-adapters.md#pytest正文与收尾)。
另见[Uncache逐UID账本](../../suites/frontend/ifu/docs/spec/verification/transaction-adapters.md#ifuuncacheunit-请求回复完成合同)：
flush未必门控ready，物理fire与生效义务必须分开；finish不能自动flush/reset/补响应清债。
无tag的线路不能凭数据反推身份，合法取消后迟到与新WaitResp中的歧义回复应按peer历史
分别处理，不把环境UID说成硬件标签，也不把所有非当前响应一概放行或判错。
运行收据中的seed必须核对实际native构造参数：模块导入时固定默认值、只读取工程旧
环境变量或完全不传argv，都会让CLI多seed成为假证据。保留默认/override/非法值和
构造间变化的正反对照，并以修后真实原生回归补证；旧功能判定不改写为已复现的新seed。
见[seed合同](../../docs/local-configuration.md#回归seed与原生初始化)。
多义务通道还须分别审计接收、仲裁和子事务转发：redirect仲裁被取消，不一定取消已注册
resolve；同一预测回卷重发可有新的attempt而保留输入allocation祖先。无响应的本地handoff
完成不能冒充下游响应/全机退休；无ready许可的未接受offer与已接受待完成义务须在收据
中区分，见[FTQ组合收尾](../../suites/frontend/ftq/docs/spec/verification/transaction-adaptation.md#收尾信用限于真实协议)。
固定延迟SDK关联和自定义expected都不能证明驱动前意图确实到达输入。另核对输入UID、
实际发射/接受沿及阶段来源；相同payload不合并身份，响应只能在合同采样点取得，不能
按“何时等于expected”挑一个后来的样本。metadata深拷贝须保留来源声明，修改诊断副本
不能冒充原lookup；显式端口重放与生产祖先信用分开，见
[MainBTB输入/来源合同](../../suites/frontend/bpu/docs/spec/verification/contracts/mbtb-transaction-contract.md)和
[DataBank首响应反证](../../suites/frontend/icache/docs/spec/verification/transactions/databank-transaction-adaptation.md#首响应检查点)。
对已接受工作发生reset/过滤时，协议终态交付也可能使SDK句柄COMPLETED；须另记有效硬件
响应、终态原因及真正比较过的交付，不能只数completed。长等待应在真实检查失败时立即
唤醒，不能继续跑到monitor溢出。每沿只索引当前义务，不扫描累计已完成历史或删除历史
换速度；最终finish仍逐项核对，见
[MainBTB终态与索引证据](../../docs/history/transaction-goal-mbtb-disposition-index-20261102.json)。
复核不能只比较FAIL数：原语义错误使后续账本停止更新时，SDK比较入口须先传播原错误，
不能拿次生缺sample/交付错误覆盖它。沿前输入getter还可能是排队意图，不等于前一拍
硬件消费；readiness、真实发射和消费必须按原生相位分别绑定，见
[DataBank持续frame与来源](../../suites/frontend/icache/docs/spec/verification/transactions/databank-transaction-adaptation.md#持续事务存储来源与真实阶段)。
finish最终报错也不代表没有清债动作：还要断言它在取消的输入/控制计划未发射时不推进
任何时钟。先核对未发射计划/日程和已观察offer，再等待纯自主尾部，不只检查wire队列。
