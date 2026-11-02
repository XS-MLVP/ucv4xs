# 事务边界与已登记漏检修复（2026-11-01）

## 本轮范围与计划

本轮接续用户“请你修复”，保留所有此前未提交工作，不重新提交/推送 0017350，也不
重跑已经完成的 DCache/MMU 全量作为新证据。旧目标的 complete 不是全部语义正确的依据。
先读正式 skill、工程合同和历史审计，再修改已核实的 bench 问题；不能改名或扩大 XFAIL
来取得通过。

1. 冻结 Sbuffer 原 31 项基线，修复默认零接受与排空预算耗尽的假成功路径。
2. 两个 DUT 接入 Toffee 单周期 Driver、lossless SamplingMonitor 和单一生命周期；
   顶层用不可变写回事务、accepted-edge 快照和 model-owned UID 管理响应/重试。
3. 补合法控制与错误控制：同字节优先级、kill+mismatch、CMO 生产者续接、多 outstanding、
   重复/旧响应、零接受和未完成退出。自检不算正常 DUT 的功能 credit。
4. 去除 LSQ 按测试文件路径切换参考模型的 fixture 分派，显式选择不同合同；冻结 nodeid
   和判定后再比较，不修改参考模型或原有失败。
5. 定向回归、根测试和静态/资产/skill 审计，记录本轮可证明的边界及全仓剩余范围。

## Sbuffer 原因与实现

原基线 `results/ucv-sbuffer-transaction-before-20261101` 为 31 PASS，但历史独立审计的
R1/R2/R3/R4/R5/R6 在当前代码仍有相应缺口。这不意味着 DUT 已发生这些错误。
本轮不改 RTL、设计基线或原生工具/库。

- 顶层 `sbuffer/ports.py` 绑定真实端口并在驱动前完整校验；`driver.py` 复用
  SyncSingleCycleDriver；所有动态输入由该 Driver 所有，配置保留、脉冲及 payload 归零。
- lossless SamplingMonitor 在 DriveStable 捕获所有通道的不可变值，用相邻 RisingEdge
  的真实框架 tick 确认，统一记账，不能由响应分支漏掉同拍入队或新写出。
- Enq 默认承诺本拍接受；显式 expect_ready=[0] 的合法反压控制仍保留。新增独立接受数
  检查，超时用例必须实际接受并完成四行，不能只对 model.lines 循环。
- `checker.py` 的 UID 来自已接受输入建立的模型行，不由 DUT 槽号反推。ID 只能在独立
  地址/mask/有效字节内容匹配后绑定；接受、hit、replay、retry、reset 逐尝试记账，
  旧尝试、未接受响应、尚未完成的槽复用、变槽 retry 均拒绝。
- offered 与 accepted 不混用：固定实现会在输出流水选择时先将行移出 active merge 集合，
  即使 DCache.ready=0。被动观察保留这种 offered 行与年轻输入的边界，但它不能授权响应。
  两次 store 的地址/mask/data 完全相同时，旧 replay 仍按已绑定的输入 UID 检查，不再
  用数据相同来错误地认作“两个模型候选、无法区分”；无效 mask 外字节规范化为 don't-care。
- 地址按合同检查完整行基址，不只比较 tag；invalid mask 字节不作过严比较。排空超时
  抛错，不清软件 drain 状态；正常 Execution 退出不允许 accepted/retry 义务残留。
- SbufferData 复用同一框架能力，在 RisingEdge 取得整阵列不可变快照，保留独立字节模型、
  捕获沿不提前可见/下一沿提交检查。反序/重复端口和位宽溢出在驱动前失败。

## CMO 对照中的错误假设与修正

第一次新控制运行 `results/ucv-sbuffer-transaction-controls-20261101` 为 50 PASS / 1 FAIL。
失败来自新增 CMO 续接用例在看到空后任意再保持 level flush 四拍，又在任意相位同时
撤掉 isCmo：DUT 在 idle 时可以因仍有效的 flush 重入 drain_all，此时撤掉类型会使它等待
all_empty。这不是对实际 producer 合同的有效模拟，不能直接记作 RTL bug。

修正依据为固定源码的 NewStoreQueue.scala:980–1003 与 MemBlock.scala:1175–1185：
CBO FSM 观察注册 sbempty 后离开 flushSb，MemBlock 再寄存 flush/type。新用例在第一次
sbempty 后按该两级回程撤销源；sqempty 仍低、新 store 低占用且高 timeout 时不残留
普通 flush 的 drain_all。合法控制通过；仅将 cmo 类型强制改成 fence 的 bench 变体
必须在后续写出检查失败。该检查是固定微架构路径，不是 ISA 禁止提前写出的普遍规则。

## 已验证与待填证据

- 原 31 项在框架迁入后保持 PASS，Sbuffer/SbufferData 两个 DUT 均已运行。
- 新的同字节竞争逐字面值检查 `(0x22,0x22,0x11,0x11)`；kill 必须真的抑制标签不一致；反序完成
  不得按发出顺序错配；reset/重试后的旧句柄均拒绝。
- 完整原 timeout/merge 用例在 bench 的零接受/隐藏写出控制下必须失败；CMO 错分类和
  反转优先级 oracle 亦应失败；正常父块输入和同配置 DUT 对照通过。这些是 observation /
  encoding / expected 注入，不是 RTL mutation，也不是新 RTL 缺陷。

Sbuffer 最终 `results/ucv-sbuffer-boundary-closed-20261101`（seed=1）及
`results/ucv-sbuffer-boundary-closed-seed2-20261101`（seed=2）均为 **66 PASS**，
各 workers=2、无显式选择。原 31 项 nodeid 和判定不变；新增为 7 个正常原生功能用例与
28 个 bench/框架自检（其中部分使用真实原生 DUT），不能相加称为 66 个正常硬件功能点。
两次最终源码哈希稳定，build 收据未变，产物 committed/coverage_complete=true，gaps=[]。
该完整性只证明产物收集，不等于功能/RTL 覆盖闭环。

**后续seed复核更正（2026-11-01）**：上两份收据中的seed是CLI登记值。随后构造器负控制
证实旧Sbuffer加载器默认只在导入时读取`SBUFFER_VERILATOR_SEED`，没有转发`UCV_SEED`；
因此不能继续用它们证明两种真实native初始化。功能66/66和原nodeid判定不改写。新入口
逐次解析CLI seed并保留显式override；修后完整
`results/ucv-goal-sbuffer-native-seed2-verified-20261101`为真实seed2的66 PASS。当前合同见
[本地配置的seed规则](../local-configuration.md#回归seed与原生初始化)，全仓目标仍未结束。

Sbuffer/LSQ 阶段根测试 **107 PASS**。当时十工程合计 **45869** 个有序 nodeid；Sbuffer
新增 35 项，其余九工程 collection hash 与上轮一致。Sbuffer 的 pin_fields / signal_operations 均为 0，
结构与严格事务边界门禁通过；全仓事务边界仍对六个工程报告失败，未降低门槛。

LSQ 定向基线选择 local_reset、sq_endpoint、RAW/replay 及主模型的使用目录，共
**324 PASS / 16 FAIL**，源码运行中未变化。root 的主 RAW/replay fixture 直接注册，
wrapper fixture 直接以 lsq 名注册；retained/exclusive 模型由 local_reset_lsq、sq_raw、
sq_replay、sq_lsq 显式参数选择，不再读取 request.node.path。局部变量别名只复用原
用例正文，不选择或改写参考模型。这是 fixture 合同修复，不计为 LSQ 事务语义迁移完成。

LSQ 复跑 `results/ucv-lsq-fixture-explicit-20261101` 为 **324 PASS / 16 FAIL**，340 项
逐条判定完全不变。16 个真实 FAIL 保留：sq_endpoint 的 6 个 bypass 数据差异、主 replay
的 4 个严格依赖/反馈差异、normal_mixed 的 6 个异常/flush 差异；这里不重新断言根因均为
RTL，后续仍按合同独立归因。7 个用例文件在显式 fixture 名归一后 AST 正文未变，8 个
参考模型/所有者 fixture 源文件哈希与检查点完全相同。完整 2575 个有序 nodeid 未变。
build 收据未变，源码稳定，产物 committed/coverage_complete=true、gaps=[]；FAIL 不改绿。
此前中间运行仍归各自源码哈希，不改写历史。

## LSU StoreDelay：封闭字段、统一时序与尾拍检查

在恢复中断进度后继续核验 StoreDelay 合同；修复前选择为 14 PASS。发现原差分用例
直接调用 env.drive/dut.Step 并读原生字段，绕过独立逐拍检查；drive 用 dict.get(name,0)
静默补齐缺字段，未知 key 也会被忽略；最后一个输入后的输出不保证曾被检查。

本轮将 StoreDelay 的 fixture 收到工程 pytest 根，环境复用 SyncSingleCycleDriver 和
DriveStable lossless SamplingMonitor，同一记录在相邻接受沿确认。输入必须精确包含
19 个载荷字段及 redirect 字段，未知/缺失/溢出在任何引脚写入前失败；有效 ROB 值限制
在 160 项实际配置中，随机 helper 也不再随机生成 [160,256) 的越域值。不可变 command
隔离调用者后续字典修改。原 RobPtr 关系 oracle 保留，不从 DUT 输出反推。

差分双方现在也逐拍执行独立检查，只比较 valid 及有效 payload；invalid payload 不作为
功能答案。正常上下文退出时再检查最终注册 beat 与下一拍的无重复控制，不能因测试
函数没有再调用 cycle 而漏掉最后一笔。14 个新增自检涵盖错键/缺字段、编码与 ROB 域、
缺端口、不可变性，以及真实 DUT 的最后一个输出在 observation 层被丢弃、改数据或重放；
它们必须在 finish pending beat / finish no duplicate 处失败，不计成 RTL mutation。

定向原 14 项判定不变，连同新增 14 个控制为 **28 PASS**。完整集成回归
`results/ucv-lsu-delay-integrated-20261101` 为 **536 PASS / 7 FAIL**；原 529 项与
`results/20261027T071656Z-f6516a8c` 的 LSU 判定逐条一致，新增 14 项全 PASS。该对比
只是跨日期 nodeid/判定对账，不认证旧验证源码等于当前源码；当前构建收据与本轮修改前
一致、源码哈希稳定、manifest committed、coverage_complete=true、gaps=[]。

7 个失败仍是 HWPF miss、store fault tval、CBO+NC、S3 kill 副作用、matchInvalid cause、
prefetch.w 写意图和 StdExe 性能计数器的反例；没有改预期、删除或新增宽泛豁免。
最新根测试 **108 PASS**，十工程合计 **45883** 项；LSU 增加 14 个控制，其余 nodeid
不变。结构/skill/资产、pip check、diff check 通过，六工程的事务审计继续非零。

逐运行哈希、差分、冻结错误函数控制和范围限制见
[机器可读证据](../history/transaction-boundary-repair-20261101.json)。

对检查点 0017350 的原 enqueue / drain_requests / drain_uarch 函数做同一组合成输入和
观察控制：旧函数在零接受或仍有 1 行未完成时返回成功，且会错误清除 uarch_drain；新
函数分别抛 AssertionError / TimeoutError，并保留真实未完成状态。冻结文件哈希和结果
保存在 `results/ucv-sbuffer-frozen-controls-20261101/summary.json`，是 bench 自检证据。

## 尚未证明

静态无引脚泄漏不是全语义签核。Sbuffer 的高槽同块组合、顶层 toggle/分支剩余、运行时
波形初始化 I/O、父块/SoC 排序等历史限制仍在；本轮不把它们改成通过。允许转发/容量
用例在结束时保留 resident 行，不等于所有 enqueue 必须在无合同保证时最终写出；显式
drain 必须排空，已接受 DCache writeback/retry 则必须完成或由 reset 合法取消。

IFU、DCache、LSQ、LSU、MMU、VAGQ 的其余事务边界和既有硬件失败仍需继续处理；BPU
完整生产原生、VAGQ 穷举及全仓覆盖闭环不在本轮已证明范围。所有后续修复仍未提交/推送。
