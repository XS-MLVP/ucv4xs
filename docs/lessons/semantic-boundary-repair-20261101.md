# 提交后语义修复（2026-11-01）

## 检查点与本轮计划

先按用户要求提交并推送检查点 `001735033979f52712808b25280efc262a48654f`，
远端 origin/main 已核对。该检查点包含 Toffee 2.1 升级、FTQ/IFU 接入、十工程根
命名空间、布局和证据；它不是全部事务语义或硬件验收完成。

本轮遵循现有 package-layout、legal-stimulus、independent-oracle 和
checker-and-runtime 方法，不自动安装或提升 pending skill。

1. 冻结 DCache/MMU 当前源码，以正式入口取得逐用例基线。
2. 修复核实的握手、接受/完成身份和检查器漏检；每个修复保留合法与错误对照。
3. 加强静态门禁，揭露 raw_dut、引脚集合和 .Set 盲区，不将新发现隐藏为通过。
4. 重跑受影响工程，比较原 nodeid 判定；新增自检与原生语义用例分开说明。
5. 更新本轮证据、当前状态及工程合同；未完成的全工程事务迁移继续列为未证明。

## 初始发现与核验

- 旧布局审计仅看 .dut/.pins/io_* 与 P 字段，漏掉 DCache wrapper 的 raw_dut、
  通道字典及 .Set；“2 个引脚字段”不是该工程仅有两处原生耦合。
- DCache shared service_miss 在推进时钟后才读 D.ready；这不是接受沿的 fire，
  且默认多个 A.ready 一起拉高，却只记录首个请求。
- Wrapper eviction 用例对 C 多拍事务按头字段去重，无法证明第二个数据 beat 正确；
  固定保持 D.valid 三拍也没有按实际握手决定 beat 边界。
- MMU PTW 的完成判断依赖累积 llptw_requests；须核对是否可能把历史 handoff
  当成新请求的完成，不能仅因 408 PASS 认为账本无误。

在冻结基线结束前未改工程源码。以下结论以实际回归、注入层和合同依据为准。

## 已修复的问题

### 默认多 worker 收集不能依赖 scratch cwd

第一次正式基线 `results/ucv-semantic-before-20261101` 选择 DCache/MMU、总 workers=4、
seed=1。MMU 408 PASS，但 DCache exit=5、collected=[]；总报告保留 INCOMPLETE/产物缺口，
不是又一次 DCache PASS。原因是 DCache pytest_configure 在 worker 启动前改了控制进程
cwd，worker 从 scratch 启动，默认发现没有使用工程 testpaths。

改为执行期的 autouse session fixture；控制进程不切 cwd，执行 worker 在收集后才隔离
原生副作用。`tests/test_dcache_collection.py` 用真实 conftest，在无显式选择的 1/2 worker
下同时验证正常结束和故意用例失败，均检查收集、退出码、cwd 恢复和无源码 dumpfile。
新基线 `results/ucv-dcache-collection-fixed-20261101` 全量为 210 PASS / 3 XFAIL。

### DCache：接受沿、完整数据和独立 L2 数据源

`dcache/tilelink.py` 修复既有同步适配器，不宣称完成框架架构迁移：

- A 只打开选中通道，其他 pending 请求不被无记录消费。
- D 沿前 valid&&ready 才计接受，背压保持同一个 beat；finally 恢复输入，超时失败。
- C 记录完整消息和双 beat，允许相同数据、拒绝半包/头变化；dirty eviction 比较全部
  64B。原有两个 dirty 用例与 clean 用例仍在，没有删除或改成宽泛 XFAIL。
- GrantData.denied 同时设置 corrupt，依据当前 rocket-chip Monitor.scala 的合法性检查。
  另外查证 AcquirePerm 允许 Grant[Data]：没有把旧 GrantData 路径误报成协议违规，新增
  full-line store + 单拍无数据 Grant 的合法控制，并读回两个半行。

第一次全量协议修复暴露随机流 helper 的两项真实 bench 错误，旧结果
`results/ucv-dcache-semantic-final-20261101` 的 224 PASS / 2 FAIL / 3 XFAIL 原样保留：

1. 它永久发送 source=0 的 ReleaseAck，没有对应 C 完成。新 guard 正确拒绝。没有
   放松 guard，而是将 helper 移到实现侧 dcache/traffic.py：只在完整 C 接受之后按
   原 source/size 发一次 Ack，同拍捕获 C 与 D，未完成义务超时失败；观察窗外反压 C。
2. 它先调用 expected_line（已叠加待写 store 字节），再清 pending，导致实际给 DUT 的
   L2 refill 已含 golden store 字节；DUT 漏写也可能恰巧得到正确读回。现在 refill 仅用
   未修改 L2 内容，pending store 只用于独立答案，不再泄漏到被测输入。

`tests/checkers/test_l2_responder.py` 保留原错误的区分性控制，包括 ready 沿后变化、
零接受/超时、两个同时 pending 的通道、错第二 beat、相同数据的两个合法 C beat、
完整 C 后的正确 Ack 与未完成 Ack、禁止 golden 字节进入 refill。真实 DCache/wrapper
的新协议用例另列，不能把这些 bench 注入自检计作 RTL mutation 或硬件功能 credit。
详细字段/时序与限制见
[DCache 传输合同](../../suites/memblock/dcache/docs/l2-transport-contract.md)。

### MMU PTW：不能由历史日志证明新请求完成

冻结 WalkRequest 的调用者身份，只在沿前真实 fire 后标记 accepted；response 核对
source/stage，LLPTW 只消费该次接受后的记录并核对 VPN/source/stage。没有接受、旧
handoff、重复完成、错误身份、等待中取消都不能返回成功。正常 field 范围在驱动前校验，
请求接受后撤销 payload。详细依据与限制见
[PTW 完成合同](../../suites/memblock/mmu/docs/ptw-completion-contract.md)。

早期探测保留 30 PASS / 5 FAIL：是新增校验把 xcomm mWidth=0 误作零位的 bench 错误；
查 xcomm 文档后按 scalar logic 的 1 位二态请求域处理，并新增拒绝 2/3（Z/X）控制。
之后一次全量为 415 PASS / 1 FAIL，唯一失败是新增错 source 自检的 fake 响应缺 pteidx；
补齐 fake 字段而非弱化生产检查。最终
`results/ucv-mmu-semantic-final-20261101` **417 PASS**，原 408 项逐条判定不变，
新增 8 个 checker 自检和 1 个原生身份用例通过，build 收据与旧运行完全一致。

## 冻结错误实现的正反对照

直接从检查点 0017350 提取旧函数，采用同一组 transport/观察层替身，不改 DUT 或原
源码。`results/ucv-semantic-controls-20261101` 的两个 summary 记录原文件哈希及结果：

| 控制 | 旧函数实际表现 | 修复后的表现 |
|---|---|---|
| D.ready 接受沿后下降 | 错误拒绝已接受 beat | 两 beat 均按真实 fire 完成 |
| D.ready 接受沿后上升 | 首 beat 没接受却前进，实际只收到第二 beat | 保持首 beat 直到真正接受 |
| 双 A pending | 同沿消费两条，只记录/响应一条 | 另一条保持反压，随后可独立服务 |
| denied GrantData | denied=1/corrupt=0 | 两 beat 都为 1/1 |
| 旧 handoff/零接受 | 返回 None，假成功 | TimeoutError / RuntimeError |
| 空闲 ReleaseAck | 无 C 仍 D.valid=1/source=0 | 空闲 D.valid=0 |
| L2=0，pending byte4=AA | refill 带入 AA<<32 | refill=[0,0]，golden pending 保留 |

这些证明 bench 修复具有区分力，不证明 ISA golden 独立性的所有方面，也不等于 RTL
故障注入覆盖率。

## 门禁与剩余范围

最终 DCache 使用 `results/ucv-dcache-semantic-verified-20261101`：**229 PASS / 3 XFAIL**。
原 213 项 nodeid 的判定逐条不变；新增 15 个 bench checker 控制和 4 个真实
DCache/wrapper 协议用例全 PASS。MMU 原 408 项亦逐条不变；新 9 项分别为 8 个自检和
1 个真实 PTW 身份用例。两工程最终均 seed=1、workers=2、无显式测试选择，验证默认
工程发现；源码前后哈希一致，manifest.state=committed、coverage_complete=true、
report.gaps=[]，build/RTL/native 收据与各自基线完全相同。

3 个 XFAIL 仍是已知硬件缺陷，不计为 PASS；完整产物不等于覆盖闭环。所有早期 FAIL /
INCOMPLETE 均保留在原目录，不能因最终通过就改写为已通过的历史运行。逐运行哈希、
前后 nodeid/判定差分、注入控制与限制见
[本轮机器可读证据](../history/semantic-repair-20261101.json)。

根回归为 **102 PASS**；十工程均可收集，共 **45834** 项，仅 DCache 增加 19 项、
MMU 增加 9 项，其余八工程的收集哈希与检查点之前的记录一致。结构、skill 和资产
审计通过；事务门禁仍按真实缺口非零。

signal_operations 与旧 pin expressions 分开计数，避免改写旧历史口径。扩展审计揭露
DCache/MMU 大量显式信号操作，也揭露 Sbuffer 的 27 处访问；不能再因它旧 pin 数为 0
就称事务迁移完成。检查仍是语法扫描，不是完整数据流或语义认证。

本轮未修改 RTL/设计基线、没有重建原生库，不将既有 FAIL/XFAIL/UNCERTAIN 改绿。
IFU、LSQ、LSU、VAGQ、Sbuffer 等仍有事务适配技术债，DCache/MMU 本轮也不是完整
Toffee Driver/Monitor/Agent 迁移；BPU 全生产原生和 VAGQ 穷举验证仍未认证。
本轮后续修复保留在工作树，未包含在已推送的 0017350 检查点中。
