# Sbuffer 验证结果与测试用例独立复核

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 审核结论

**暂不通过测试充分性与验证结论的签核。** 已复现检查器漏检，不能用现有 PASS 或功能覆盖率
100% 排除这几类缺陷。**本次没有确认新的 RTL 功能 bug**；以下问题首先属于测试、检查器或
证据链，而不是把审计注入的错误当成 DUT 的真实错误。

先前对 CMO 的结论应缩小为：固定基线确有两个不同层级的空信号；消费方接线及上游提交支持
`flush.empty` 包含 `sqempty` 的设计意图，因此这一个表达式本身不能认定为 bug。
但现有用例不能据此证明 CMO 排空状态机、所有排序或父块集成都正确。

## 审核边界与方法

- RTL 基线：`893e1580b705d81f113c30c7a05734e09a08050e`。
- 不修改原始 RTL、参考模型、正式用例、fixture、构建或既有结果。
- 新增内容仅位于本报告和 `review/independent_20261024/`。
- 复用现有共享库，无重新编译，无 VPI、internal-cfg 或内部信号访问。
- 独立重跑 15 个 SbufferData 用例与 16 个 Sbuffer 用例；审计插件显式请求暂停波形。
  `WaveformPaused()==1` 表示 API 的请求状态，不等于证明没有初始化文件 I/O。
- 用三个边界/期望扰动检验测试区分能力，并用有效字节数据翻转作阳性对照。
  **这些不是 mutant RTL 实验**：分别扰动检查器读到的请求快照、驱动的分类输入、参考期望。
- 用假公开信号构造检查器最小反例，不把它们称为真实 DUT 失败。
- 从原始 coverage.dat/coverage.info 重新统计，核对 manifest 中的文件和二进制哈希，
  不直接信任原 `delivery-audit.json` 的 PASS。

## 1. 已核实的正面证据

| 项目 | 独立核验结果 |
|---|---|
| 当前用例重跑 | **31 PASS**，其中子块 15、顶层 16 |
| 顶层结果产物与 DUT 文件哈希 | manifest 中列出的现存文件全部匹配 |
| 子块历史结果产物与 DUT 文件哈希 | manifest 中列出的现存文件全部匹配 |
| 顶层 DUT LCOV 行 | **12648/13191 = 95.8836%** |
| 顶层原生 line-point | **809/1269 = 63.8%**，不能与 LCOV 行口径互换 |
| 顶层原生 toggle | **70275/85706 = 82.0%** |
| 顶层原生 branch | **2690/2724 = 98.8%** |
| 子块历史 DUT LCOV 行 | **8518/8518** |
| 子块历史 toggle / branch | **70684/70684**；**2115/2116**，后者不是严格 100% |
| 顶层构建 | mem_direct、VPI OFF、trace fst、coverage ON |
| toffee 来源 | 本地分支为 migration/toffee，但 HEAD 与本地 origin/main 均为 `4a09d21a89d2a8367efd56cbd440575edbe646d3`；不能只凭分支名指控未使用 main |

子块覆盖率是历史 `sbuffer-data-initial-04` 的证据；本次 15 PASS 是当前代码的功能重跑，
没有为这次 pytest 重跑生成新的原生覆盖率，二者不混报为同一轮。

## 2. 可复现的检查器/用例问题

### R1 — P1：默认入队会默默放弃未接受的请求，缺少独立进展检查

位置：`sbufferverify/sbuffer/env.py:148-161`；
`tests/sbuffer/test_sbuffer.py:109-126`。

`enqueue()` 以实际 ready 筛选 accepted，这是正常的握手记账；问题在于没有显式
`expect_ready` 时，只对已存在行的 merge 检查 ready。新行 ready=0 不报错、不重试，
一个 edge 后撤销 valid，参考模型也不记录该 store。`_predict_ready()` 存在但未被调用。

最小反例：空模型、两端口 ready=0，提交新行；`enqueue()` 正常返回，模型仍为空。
`test_timeout_writeout_all_lanes` 随后用 `while env.model.lines` 决定是否检查写出，且不核对
接受/完成总数。因此不能保证该用例真的完成了标题承诺的四次 store。

**影响：** 错误拒绝请求或丢失激励可能同时从模型和检查中消失，产生空跑 PASS。
这不是“所有依赖 ready 的参考模型都有耦合问题”，而是缺少独立的握手要求与活性约束。

**修复条件：** 为预期应接受的场景给出合同期望；或保持 valid 到 fire 并设置 watchdog；
分别统计 offered/accepted/completed，结束时核对预期事务数和所有 outstanding。

### R2 — P1：排空循环耗尽预算后正常返回，不等于真正完成

位置：`sbufferverify/sbuffer/env.py:350-367,386-406`；
`tests/sbuffer/test_sbuffer.py:407-411,475-479`。

`drain_requests()` 达到 max_cycles 后直接返回部分结果，没有检查 `model.lines` 是否为空；
`drain_uarch()` 也可在未排空时返回，并把 `model.uarch_drain` 清零。
部分调用方之后仅等待几拍、撤销 flush，没有检查全部行消失或完成计数。

最小反例：模型保留一行，公开 req_valid 永远为 0；max_cycles=4 后函数正常返回，
`drained=[]`，模型仍有一行。

**影响：** 排空卡死或漏发某些行可能没有变成失败。某些调用方的 empty 断言能兜底，
但不能替代所有调用路径的统一完成约束。

**修复条件：** 耗尽预算必须抛错；只有所有应完成事务均确认后才清除软件 drain 状态；
每个用例退出前做一致的 outstanding/空状态检查。

### R3 — P1：请求接受与槽 ID 生命周期检查不完整

位置：`sbufferverify/sbuffer/env.py:223-235,237-272`。

- `wait_req()` 检查一个历史快照后，`accept()` 仅置 ready、等待 edge 并更新模型；
  不重新检查接受 edge 的 valid、payload 是否仍与快照一致。
- 没有逐拍监视 backpressure 期间的 valid/payload 行为，也没有完整的请求 fire 计账。
- ID 仅检查数值范围，未维护 `id -> outstanding transaction` 的绑定/占用表。

最小反例一：req_valid=0，调用 `accept()`，函数仍把模型行标成 inflight。
最小反例二：两个不同物理块先后使用同一个 id=3，第一个仍 outstanding；
`verify_req()` 对第二个请求仍然通过。

**影响：** 请求撤销、快照与实际 fire 不一致、多个 outstanding 重用槽 ID、响应关联错误
缺少必要的独立检查。不能仅靠“按 DUT 给出的 ID 回送 hit”证明关联正确。

**修复条件：** 根据真实接口合同建立被动 fire/响应监视器、ID 绑定及释放规则；
加入多 outstanding、延迟/乱序合法响应及接受前后变化场景。对 valid 是否必须保持的要求
先核对具体接口合同，不能擅自套用其它总线规则。

### R4 — P1：active-over-inflight 覆盖命中，不代表验证了同字节优先级

位置：`tests/sbuffer/test_sbuffer.py:283-309`；
`sbufferverify/sbuffer/env.py:319-339`。

同块串行用例中，旧 inflight 数据写 lane0，新 active 数据写 lane1；转发查询 lane1。
它验证了 active 数据可见、同块暂缓写出，但没有让同一个有效字节同时从两者竞争。
`active_over_inflight` 的采样只看标签下是否同时存在 active/inflight，不要求 mask 重叠。

审计将参考期望的合成优先级反转成 inflight 覆盖 active：**顶层仍 16 PASS**。
共执行 240 次 forward oracle 调用，没有一次 active/inflight 同 lane mask 重叠。
这是期望端敏感性实验，说明已执行的场景不区分两个候选优先级，不是 RTL 被反转。

此外，现有 kill 查询使用虚实标签一致的地址；即使不实现 kill 抑制 mismatch，
该查询本来就应输出 invalid=0，不能证明 kill 功能。

**修复条件：** 同一字节安排不同旧/新数据，检查新值及未覆盖字节回退；
kill 与真实虚实标签不一致交叉；相关 cover bin 在竞争/抑制实际发生并检查成功后采样。

### R5 — P1：CMO 用例验证了空信号，却没有区分 CMO 分类路径

位置：`tests/sbuffer/test_sbuffer.py:191-219`；
`sbufferverify/sbuffer/env.py:369-379`；
`XiangShan/src/main/scala/xiangshan/mem/sbuffer/Sbuffer.scala:539-559,571-574`。

`sbempty` 和 `flush.empty` 的计算本身与 isCmo 无关；isCmo 用于 drain 状态退出条件。
因此只检查两个空信号，不能证明 isCmo 所选择的路径有效。

审计在驱动端把所有 `start_flush(cmo=True)` 改为 cmo=False，
实际扰动两次 CMO 请求：**顶层仍 16 PASS**。
这不否定两个 empty 断言的价值，但证明不能把其 PASS 说成“CMO 状态机已被验证”。

`flush_and_finish()` 还在 sqempty=1 的 CMO 场景直接采样 `cmo_ignores_sq`，且采样早于
后续 empty 断言。这个 bin 的计数不能逐项解释为“不等 SQ”的受检证据。

**修复条件：** 给“空信号关系”和“分类选择的状态退出/后续行为”分别定义功能点；
设计符合父块时序且能区分错误分类的续接事务，或明确把状态机路径列为未验证。
不能为杀死扰动而杜撰“所有条件下禁止提前写出”的非合同断言。

### R6 — P2：写出地址低位被丢弃，完整接口值未检查

位置：`sbufferverify/sbuffer/env.py:201-235`；
`XiangShan/src/main/scala/xiangshan/mem/sbuffer/Sbuffer.scala:703-704`。

请求匹配只比较 `addr >> 6` / `vaddr >> 6`，不检查低六位。
审计给每个被读取的请求快照的两个地址都置 bit0=1，共扰动 97 个快照：
**顶层仍 16 PASS**。

**影响：** 行标签和数据检查仍有效，但不能声称完整写出地址已经验证。
这是接口精度缺口，不直接断言该位必然造成系统数据错误；下游若按行忽略低位，
系统影响还需依据下游合同评估。

**修复条件：** 在明确定义行对齐要求后检查完整地址/对齐；若低位确为 don't-care，
明确记为不检查而非宣称整个 addr 正确。

### R7 — P1：没有残留波形不等于运行时已关闭波形

位置：`conftest.py:32-47,55-56`；`tools/run.py:59-88`；
`dut/sbuffer/SbufferDut_top.sv:1566-1567`。

生成 harness 无条件调用 `$dumpfile`/`$dumpvars`；Picker 的 Verilator 模板设置
`traceEverOn(true)`。正式 fixture 不调用暂停接口，改用临时 cwd 并删除目录。
`trace-policy.json` 由脚本写死部分策略字段，PASS 判据只验证结果目录没有残留文件。
这不足以支持“trace 仅编译、从未启用”的断言。

本次审计回归显式调用 `PauseWaveformDump()`；Picker 提示可能延迟到 dumper 建立后才暂停。
因此本报告不声称连初始化 header 都没有写出，也不以 audit 插件的请求状态代替文件 I/O 证据。
未为了测量而主动恢复波形或做长时间 dump。

**修复条件：** 独立证明实际运行不进行周期 dump；区分编译能力、初始化文件、逐周期写出与
保留策略。不要用删除文件的方法宣称关闭了生成。

## 3. 其它需要修正的证据/范围表述（P2）

1. **`wline` 场景分类仍不完整。** 顶层零 payload 符合数据域，但连续塞入 16 个 wline、
   最后才 flush，不是父块 CBO FSM 每条 `writeZero -> flushSb -> writeback` 的实际时序。
   可作为子接口压力/能力场景，不能不加区分地称作父块可达 CBO 序列。
2. **“一份 DUT / 每层 trace 编译”未完全落地。** 当前仍有 sbuffer 与 sbuffer_data 两个包；
   子块 Makefile 为 TRACE OFF，顶层为 TRACE fst。`verify_delivery.py` 只审计顶层构建，
   子块历史运行豁免 trace 检查。这不影响已核实的功能 PASS，但不能替代用户对交付形态的要求。
3. **审计脚本不是测试充分性的认证。** `verify_delivery.py` 检查用例函数名、字符串和已有
   JSON 状态；不验证反例会失败，也不校验所有 test/model/fixture 的版本与原运行完全一致。
   其 `wline` 检查只是附近几行是否出现 data=0，并非完整数据域或协议审计。
4. **ISA 论证存在过强措辞。** ISA 不定义这些微架构信号；CMO 按 PPO 作为 store 处理，
   不能直接推成“任意地址的所有前后 store 必须全序且都到达某一统一一致性点”。
   固定实现排空整个 SB/MSHR 可以是保守实现。应以架构排序要求、微架构合同与被测行为
   三层分别表述，不用 PR/消费者实现替代全系统独立规范。
5. **剩余缺口不是覆盖闭环已完成的证据。** 顶层仍有 543 个 DUT LCOV 行、34 个分支臂、
   15431 个 toggle 点未覆盖；功能 bin 的 100% 不能证明缺口全是无关紧要的情况枚举。
   对未建立功能点的并发/响应/优先级场景，也应增加功能点而非只写“已有点的情况缺失”。

## 4. CMO 原始疑点的独立裁决

本地固定提交中重新核对了：

- PR #6183 对应提交 `102a72f83aef34ebca2bbaca73ee85dd68384ba4` 的设计说明；
- `Sbuffer.scala:539-559` 的两级空；
- `MemBlock.scala:1175-1186,1222,1239` 的 Fence/Atomics 与 LSQ 接线；
- `NewStoreQueue.scala:967-1003` 的 CBO FSM。

**裁决：原来“CMO 期间 flush.empty 仍受 sqempty 门控，因此是 bug”的指控不成立。**
CMO 消费的是 sbempty，不是 flush.empty。该指控可以撤销，但不应把整个 CMO 功能标成
“无缺陷/充分验证”；R5 的漏检仍然存在。

本轮访问 RISC-V 官方页面及官方仓库原文均超时；因此没有声称重新完成在线规范全文核验。
上述局部裁决有本地固定基线和提交证据，不依赖在线页面可用性；ISA 级全系统排序签核不在
本次可验证范围内。

## 5. 扰动与阳性对照结果

| 实验 | 实际触发量 | 正式顶层用例结果 | 解读 |
|---|---:|---|---|
| 基线 | 子块15 + 顶层16 | **31 PASS** | 复现当前功能回归 |
| 请求快照地址 bit0 置 1 | 97 个请求快照 | **16 PASS** | 未检查地址低位 |
| CMO 分类输入强制普通 flush | 2 次 CMO 请求 | **16 PASS** | 未区分类别退出路径 |
| 期望模型 inflight 覆盖 active | 240 次 forward 查询；0 次有效 mask 竞争 | **16 PASS** | 优先级场景不具区分力 |
| 有效 mask 内的数据 bit 翻转 | 1 次 | **1 FAIL（预期）** | 数据 checker 确有工作；不是插件未执行导致全部假通过 |

最小反例另复现：新行被拒绝但不失败、排空超时但正常返回、不同 outstanding 复用 ID 被接受、
req_valid=0 仍在软件标记接受。反例脚本包含有效数据破坏应被捕获的对照。

## 6. 重新签核的必要条件

1. 修复 R1/R2/R3 的握手、完成、响应关联检查，并让相应最小反例被明确拒绝。
2. 补真正同字节竞争、kill+mismatch 和有区分力的 CMO 后续场景；不能只命中标签 bin。
3. 将功能覆盖采样绑定到已经验证的行为，避免情景名字直接等于完成证据。
4. 明确并落实 runtime trace 策略、合法父块协议域及 DUT 交付范围。
5. 固定 test/model/fixture/工具与 DUT 的版本证据，在同一版本重跑两层回归和原生覆盖率。

在此之前，建议结论写为：**“现有场景下未发现已确认 RTL bug，但测试平台有已复现漏检，
不能据此排除相应缺陷；验证充分性签核未通过。”**

## 7. 证据与复现

审计目录：`review/independent_20261024/`。

- `provenance-coverage.json`：独立哈希核对、逐文件 LCOV、原生 summary、工具/包情况。
- `mutation-regressions.json`：各回归命令、返回码、耗时。
- `baseline.json` / `.log`：31 PASS 的当前重跑。
- `unaligned_request_address.json` / `.log`：地址低位扰动。
- `cmo_classification_stuck_zero.json` / `.log`：分类扰动。
- `forward_priority_reversed_oracle.json` / `.log`：期望优先级扰动。
- `masked_request_data_flip.json` / `.log`：真实运行 checker 阳性对照。
- `checker_probes.py` / `checker-probes.json`：检查器最小反例及对照。

在项目根目录使用已锁定的 Python 运行，选择全新 summary 路径以保留本轮记录：

```sh
PYTHONPATH="$PWD" SBUFFER_AUDIT_MUTATION=cmo_classification_stuck_zero \
  SBUFFER_AUDIT_SUMMARY=/tmp/opencode/sbuffer-review-cmo-repro.json \
  /home/xyl/xreactor/output/toffee-migration/venv/bin/python -m pytest \
  -p review.independent_20261024.fault_injection -p no:cacheprovider -q tests/sbuffer
```

阳性对照模式 `masked_request_data_flip` 的预期退出码是 1，不应把该审计实验失败当成
未扰动 RTL 的原生失败。审计日志只保存测试摘要/失败回溯，没有逐周期信号或事务 dump。
