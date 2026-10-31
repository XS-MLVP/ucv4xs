# KMH-v3 验证假阴性跨模块总结

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


> 历史快照：以下“当前”、计数、代码位置及改进计划均保留 2026-10-26 原文含义，不代表 ucv4xs 重建后的验证结论或已实施项。正文旧路径用于识别原证据；[经验索引](README.md) 提供当前工程入口与旧路径对照，[迁移记录](../history/experience-import.json) 保存原文件哈希。

> 当前操作方法按 [`skills/<阶段>/<问题>.md`](../../skills/README.md) 读取；十二类具体踩坑见 [历史案例](rtl-verification-soundness-20261026.md)。本文保留原案例矩阵、状态快照、诊断树、检查表和改进计划；后几项也是历史原文，不代表本次已实施或另建一套现行流程。


**日期：2026-10-26**
**范围：LSU 失败复核 + 工作区内 LSQ、Sbuffer、DCache、ICache、MMU、VAGQ 已有验证复盘。**

---

## 0. 一页结论

### 0.1 直接结论

- LSU 当前确认 **7 个独立 RTL Bug**，当前回归 `memblock-hash/lsu/results/upstream-review-regression-02` 为 **582 PASS / 7 FAIL / 589 项**，19 个原生 DUT。
- 另有 **11 项验证/报告问题**：9 项已完成修正，2 项仍未闭环（历史日志无法恢复、逐 bin 独立 reached/checked 未完成）。
- 7 个 RTL Bug 中，**没有一个是靠“再跑更多随机测试”就能可靠发现的**。主要漏检来自：同源参考模型、检查点选错、组合空间缺失、覆盖 bin 只记录“到达”、架构语义没有独立 oracle。
- 其他模块的经验与 LSU 高度同构：LSQ 的 `#6634`、`#6229/#6312` 是参考模型与 RTL 同错；Sbuffer 的 R1/R2 是空跑和排空超时仍 PASS；MMU 有 8 条旧归因被撤回；VAGQ 有 6 个 XFAIL 取消遮罩后全部真实 FAIL；ICache 已把三类漏检写成系统方法。

### 0.2 六条最值得记住的判断

1. **覆盖率证明“执行过”，不证明“检查过”，更不证明“期望正确”。**
2. **参考模型和 RTL 同时错时，相等比较一定通过。** “不读 DUT 内部信号”不等于“参考独立”。
3. **功能点没写出的组合，不会被任何用例承诺覆盖。** 单路径各自 PASS 推不出同拍组合 PASS。
4. **检查器只看主输出，会漏掉“主握手正常、副作用错误”的缺陷。** kill/redirect/flush 尤其要查全部副作用。
5. **空跑、排空超时、被拒绝请求、宽泛 XFAIL 都会把失败变成绿色。** 必须核对 offered/accepted/completed/outstanding。
6. **发现漏检后只补一条用例，通常只修了激励缺口；必须同时回答功能点、检查器、激励三问。**

---

## 1. 证据来源与口径

本文是**跨模块经验总结**，不是把其他模块的结果当成本工程的验证证据。

| 来源 | 关键文档 | 本文使用方式 |
|---|---|---|
| LSU 本轮复核 | `memblock-hash/lsu/docs/bug-reports-20261026/01`–`06`、`review/upstream_check_20261026_01/audit.json` | 7 个 RTL Bug、11 项验证问题、当前回归状态 |
| LSQ | `memblock-hash/lsq/docs/reports/same-source-audit-20261022.md`、`docs/bug-reports-20261022/12`、`13`、`14` | 同源模型、槽序 vs 年龄、半完成窗口、参数边界、XFAIL/归因 |
| Sbuffer | `memblock-hash/sbuffer/docs/reports/independent-audit-20261024.md`、`bug-recheck-20261024.md` | 空跑、排空超时、ID 生命周期、同字节竞争、检查器扰动 |
| DCache | `memblock-hash/dcache/docs/reports/functional-point-audit-20261025.md`、`coverage-20261025.md` | 功能点与 RTL/测试不一致、只查握手、known-issue XFAIL、覆盖口径 |
| ICache | `icache-verify-kunminghu-v3/docs/verification-lessons.md` | 三类漏检、组合维度、参考模型不能从 RTL 反推、检查器三种失效 |
| MMU | `memblock-hash/mmu/docs/reports/verification-soundness-20261025.md` | 全 case 审计、重复/失活用例、宽泛 XFAIL、缺省端口、事件采样 |
| VAGQ | `vqgq-d4566d5-20261016/results/vagq-xfail-contract-review-20261018-v1/README.md`、`vagq-exhaustive-review-20261020-v1/README.md`、`vagq-reference-repair-rtl-rereview-20261020-v2/README.md` | XFAIL 逐条解遮罩、架构 vs 协议层级、参考模型先修再复核 |

**边界：**

- 其他模块可能使用不同基线、配置、外部代理和统计口径；其数字只在原报告范围内有效，**不跨模块相加**。
- 本文引用其他模块的“确认 Bug”或“误报”是为了提炼方法，不等于 LSU 已复现相同问题。
- 本文不修改任何 RTL、旧测试、旧参考或历史 JUnit。

---

## 2. LSU 7 个已确认 Bug 的漏检画像

| Bug | 旧测试到达了什么 | 旧检查器是否检查出错量 | 旧期望来源 | 主要漏检类型 |
|---|---|---|---|---|
| `LSU-HWPF-MISS-001` 硬件预取 miss 事件恒 0 | 性能测试驱动了预取 miss | 检查 perf3，但期望 0 | 直接复制 RTL 互斥条件 | 同源预期 + 把“实现上不可能”误当成“规范应为 0” |
| `LSU-STORE-TVAL-001` Store 故障 tval 未用掩码地址 | 写回测试同时给了输入 VA 与 TLB fullva | 检查 tval，但期望输入 VA | S1 模型从输入转抄 fullva | 同源预期 + 测试注释把 RTL 行为写成合同 |
| `LSU-CBO-NC-AF-001` PBMT=NC 的 CBO 误报 AF | CBO 与 NC 分别到达 | CBO 测试不看异常；MMIO 测试只看写回 | 模型把 `CBO && uncache` 统一判 AF | 组合缺失 + 用 IO 样本代表整个 uncache 等价类 |
| `LSU-S3-KILL-WB-001` redirect kill 后仍写回 | kill 拍确实到达 | 只看 `pipeOut`，没看 `ldout/intRF/lqWrite` | 模型写回未加 kill 门控 | 断言范围不足 + 同源预期 |
| `LSU-MATCHINV-CAUSE-001` matchInvalid 仍带 replay cause | matchInvalid 拍确实到达 | 只看 rollback/pipeOut，没看 LQ cause | 模型未让 matchInvalid 清零 | 断言范围不足 + 同源预期 |
| `LSU-PREFETCH-W-INTENT-001` prefetch.w 丢失写意图 | 只测了 prefetch.i/r | 未检查 dcache cmd | 模型固定产生 `M_PFR` | 激励缺失 + 同源预期 + 无 pftCoh 观察点 |
| `LSU-STD-PERF-001` StdExe 越界发射计数器取反 | 没有可观测端口 | 无模型、无测试、无 bin | 无 | 可观测性/范围缺口 |

**关键判断：**

- 前 6 个里，4 个的相关组合已经执行过（HWPF、Store tval、S3 kill、matchInvalid），甚至“代码覆盖”很高；失败在**期望值或检查点**，不在“没跑到”。CBO 是 CBO 与 NC 两条边分别到达但组合未到达；prefetch.w 的写变体未枚举。
- 即使把断言数量加倍，只要仍以旧模型为 oracle，这 6 个中的多数仍会通过。
- StdExe 是唯一“根本没有观察点”的例子：功能接口不导出该 perf 计数器。

### 2.1 一个具体的同源闭环

固定常量 `VADDR=0x1000`、`FULLVA=0x4000`，TLB 默认返回 `fullva=0x4000`，测试却断言：

```python
# exceptionInfo.vaddr is the store's own full virtual address (src+imm),
# not the TLB response's fullva (that one only feeds the unaligned tail).
assert int(nsu.exc["vaddr"].value) == VADDR
```

模型 `memblock-hash/lsu/lsuverify/store_s1/env.py:281` 也写 `"fullva": pipe_in["fullva"]`；RTL `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala:473-474` 只回写 `paddr/gpaddr`，`NewStoreUnit.scala:823` 再用 `sxData.fullva`。**测试、模型、RTL 三方同错。** 这不是缺一个随机种子，而是预期来源错了。

### 2.2 一个具体的组合缺失

模型 `memblock-hash/lsu/lsuverify/store_s2/env.py:115-120` 把 `is_cbo && is_uncache` 统一判 AF；测试只驱动 CBO+IO：

```python
got = run(s2, 1, beat(instr_type=1, is_cbo=1, pbmt=PBMT_IO), "cbo io")
assert got["out_bits"]["uop_exceptionVec_7"] == 1
s2.coverage.sample_case("exc.cbo_uncache_faults")
```

bin 名覆盖“CBO uncache”，实际只采样 IO。CBO+NC 从未同拍，于是“IO 应报 AF”被错误推广到 NC。

### 2.3 其他模块各自最硬的教训

| 模块 | 最硬的教训 | 对 LSU 的直接启示 |
|---|---|---|
| LSQ | 参考不读 RTL 寄存器，也可能复制 RTL 的“候选条件/仲裁顺序”；范围覆盖不等于逐字节覆盖；槽号顺序不等于程序年龄 | 不要用“模型没读内部信号”证明独立；tval、CBO、prefetch 的 expected 必须来自规范 |
| Sbuffer | 正式用例可以在 offered=4/accepted=0、drain 超时仍有 8 行时 PASS；扰动检查器才能证明盲区 | LSU 的 driver 必须记账 accepted/completed/outstanding，drain 超时必须失败 |
| DCache | 功能点文档本身可能写错，用例可能只查握手；known-issue 可以严格 xfail，但不能把 xfail 当通过 | 先审计合同和断言质量，再谈覆盖率；性能/状态字段不能因“非主通路”排除 |
| ICache | 漏检分三类：功能点缺口、检查器缺口、激励缺口；参考模型不能从 RTL 反推；检查器有过严、死字段、死开关三种失效 | 用三问复盘每个漏检；建立字段×比较器对账和组合矩阵 |
| MMU | 旧归因可以成批撤回；重名/注释中的 def 会让用例从未收集；宽泛 XFAIL、缺省端口补 0、空闲周期采样都会制造假通过 | 对全量测试做 AST 和 collection 审计；缺省字段 fail-closed；事件按握手沿计数 |
| VAGQ | 6 个 XFAIL 取消遮罩后是 6 个真实 FAIL、4 类不同原因，不是 6 个 Bug；架构元素数不等于协议槽数；forced-port 不等于生产入口 | XFAIL 必须精确到 nodeid+原因；架构 oracle 与协议 oracle 分离；越域刺激单独标注 |

**共同点：** 这些模块最终都不是靠“再多跑一些随机”解决问题，而是靠**独立性质、逐项解遮罩、检查器扰动、完成性记账、功能点/组合矩阵审计**发现问题。

---

## 3. 跨模块假阴性分类

以下 10 类按“最容易伪装成绿色”的顺序排列。每类给出跨模块实例和检测方法。

### 3.1 功能点缺口：需求语义没有进入功能点或组合矩阵

**表现：**

- 单路径各自 PASS，但没有“同拍组合”用例。
- 功能点写成“A 发生时产生 B”，隐含 A 独占；没有写“A 与 C 同时发生时”。
- 用例清单按信号/端口组织，而不是按微架构语义组织。

**跨模块实例：**

- **LSU**：CBO×PBMT=NC、kill×写回副作用、matchInvalid×replay cause、prefetch 类×DCache cmd 都没有组合 bin。
- **LSQ**：`#6704` 的“Store 首请求之后、尾请求之前”半完成窗口没有作为独立功能点；对首尾连续发完的定向驱动掩盖了中间窗口。
- **ICache**：`verification-lessons.md` 第三部分明确指出，多个请求源同拍、请求与响应同拍、数据与控制同拍、控制事件与正常事务同拍是通用组合维度；单路径正确推不出组合正确。
- **MMU**：多个“成功”用例只查 `valid/PPN`，不查 `af`；同拍 enqueue/dequeue 原来只是顺序操作，没有真正同拍 fire。

**检测：**

- 把功能点列表当组合矩阵的行；对每个模块强制列出：多请求源、请求×响应、数据×控制、控制事件（flush/redirect/reset/fence）×正常事务、指针/容量边界×并发。
- 对每个空格写“不需要验证的原因”，否则就是空白，不是“已覆盖”。

### 3.2 检查器缺口：只看主输出、死字段、整段静音

**表现：**

- 只检查 `valid/ready` 或最终数据，不检查过程副作用。
- 模型算了一个字段、观测也接了，但比较器没有比较它（dead field）。
- 为了容忍合法例外，把整段检查关掉，而不是只放宽某个字段。
- 检查器按电平持续采样，而不是按握手沿计数。

**跨模块实例：**

- **LSU**：S3 kill 测试只断言 `pipeOut_valid==0`；matchInvalid 只断言 rollback/level/pipeOut，没有检查 `lqWrite` 的 13 个 cause。
- **Sbuffer**：R1 的 `enqueue()` 以实际 ready 过滤 accepted，未接受的新行不报错也不重试，模型仍为空，正式用例 PASS；R2 的 `drain_requests()` 预算耗尽后正常返回，模型仍有 8 行，用例仍 PASS。
- **DCache**：`functional-point-audit-20261025.md` 发现 `test_all_sixteen_entries_occupied` 原来只检查 `req_ready`，已补每个 entry 的 address 与 opcode。
- **MMU**：多个“成功”用例只查 `v/PPN`，不查 `af`；`DTLB opt()` 对缺失输出静默补 0。
- **ICache**：检查器自身有三种失效：过严、死字段、死开关；三者都让结论比实际更强。

**检测：**

- 对每个 DUT 建“输出字段 × 比较器”对账表；每个字段要么被比较，要么被删除，要么标注不可观测及原因。
- 对每个“放行”写清放行范围：字段、事件集合还是整段结果；整段放行必须有合同依据。
- 用 readback fault / expected mutation 做检查器灵敏度实验：故意改错一个观测或期望，确认测试会 FAIL；这只是检查器自检，不是 RTL mutant。

### 3.3 同源参考模型：模型复述 RTL，而不是复述规范

**表现：**

- 模型作者打开 RTL，把表达式抄成 Python；RTL 错，模型同错。
- 模型复制了 RTL 的“候选产生条件”“仲裁顺序”“覆盖判断”，即使不读内部寄存器，也不是独立 oracle。
- 测试注释把观察到的 RTL 行为写成“合同”。

**跨模块实例：**

- **LSU**：Store tval、CBO NC、S3 kill、matchInvalid、HWPF、prefetch.w 的模型都与 RTL 同形。
- **LSQ**：`#6634` 的 RTL 对任何 writeback 都产生异常候选，并按物理 entry 顺序选第一个；参考模型 `uncache_entry/model.py:96-100` 和 `load_uncache/model.py:165` 也这样做。独立双 lane 探针才证明同拍“正常完成 + 真实错误”会丢掉真实错误。`#6229/#6312` 的 `s2FullOverlap` 和 `forward/model.py:100-104` 都按“起止范围=完整覆盖”判断。
- **VAGQ**：`maskgen/reference.py` 的 `mergeWriteMask` 把 field-major 的 `destLsrcOffset` 当成 `destination_window`；13536 个 uop 全输出资格失败，修正字段含义后才一致。另一个案例把“架构元素数”直接当“协议槽窗口”，导致 fractional LMUL 的 XFAIL。
- **MMU**：PMP reset 把 live DUT 的 PMA 初值当期望，无法抓初值错误；后来改为固定配置表及 SHA。

**检测：**

- **先写契约，再看 RTL。** 在打开 RTL 前，用自然语言写出可观察后果；RTL 只用于确认接口名和时序，不定义“应该是什么”。
- 每个 expected 标注来源：ISA/特权规范、上游修复说明、独立性质、还是“实现观察”。最后一类不能单独作为通过依据。
- 对“取消/丢弃/冲刷”类语义，显式列出需要清除的状态清单，而不是只清指针。
- 参考模型分两层：架构 oracle（规范期望）与协议 oracle（内部时序/接口契约）；两者的结论不能互相替代。

### 3.4 抽象层级/表示错误：架构语义 vs 协议实现

**表现：**

- 把“物理槽号小”当成“程序年龄老”。
- 把“地址跨度”当成“每个字节都被覆盖”。
- 把“架构有效元素数”当成“内部预留槽数”。
- 把“输入地址”当成“TLB 掩码后的异常地址”。
- 把“读预取”当成“写预取”。

**跨模块实例：**

- **LSQ**：`#6634` 用物理 entry 顺序代替 `robIdx/uopIdx` 程序顺序；`#6229` 用起止范围代替逐字节 mask；`#6688/#6697` 只在默认阈值 12 下测试，没有参数 0 边界。
- **VAGQ**：fractional LMUL 的架构有效元素是 2/4/8，但 Rename/LQ 实际预留 16 个槽，非 active 槽走 `lsqEmptyReq` 清理；把两者混为一谈会误报“越界读”。ordered store 的 ISA 要求是最终内存效果按元素顺序，不是“每周期只能发一个地址请求”。
- **LSU**：Store tval 应使用 TLB 返回的 masked fullva，而不是输入 tagged VA；prefetch.w 应带写意图，不是统一 `M_PFR`。
- **MMU**：sfence 的 rs1/rs2 是寄存器编号是否为 x0，不是地址值；原 0/0 + addr=0 的契约错误造成误报。

**检测：**

- 对每个检查点问：这是架构可见语义，还是微架构实现选择？两者分别用不同 oracle。
- 对“范围/掩码/年龄/槽号/地址”这类容易换表示的字段，写出明确的代数定义和边界。
- 参数、配置、编码变体单独建域；默认配置全绿不能证明其它配置合法。

### 3.5 激励缺口与生产者合法性：该到的没到，或不该到的到了

**表现：**

- 变体没枚举：只测了 prefetch.i/r，没测 prefetch.w；只测了默认阈值。
- 时序窗口没构造：跨 16B Store 的首尾之间、请求与响应同拍、flush 与正常事务同拍。
- 直接给子模块施加真实上游不会同时出现的信号，制造“越域压力”，却当成正常路径 bug。
- 非法输入导致未定义行为，失败是噪声，反而掩盖真正问题。

**跨模块实例：**

- **LSU**：prefetch.w 从未使用；旧测试还构造过 `entrance=0x20` 的“硬件预取 replay”，但该接口没有 `pftType`，且 0x20 是 vectorIssue 码，属于无效刺激。
- **LSQ**：`#6704` 没有构造首尾半完成窗口；`#6714` 只用普通 retired 对照，没有“已退休目标 + 跨 flag 回绕”组合。
- **LSQ 误报**：VSQ 同拍 dispatch+redirect、ROB pending 越过未完成 MMIO、把 RAR 回滚接成 C_NK、8B 包当整行 CBO.zero、对已不可撤回的 Store 发 `flushSelf`。这些是越过真实 producer 约束的刺激。
- **MMU**：LLPTW/Bitmap responder 串行服务漏掉同拍多个 ready 的请求；修复为每沿并行捕获所有 fire 后，原“RTL 调度 bug”被撤回。
- **VAGQ**：`nf>0` 的 forced-port 输入不经过当前 Decode 的 `useVAGQ` 正常入口；2278 个失败不能直接算成生产路径 RTL bug。

**检测：**

- 建“生产者准入条件”：互斥、延迟、ROB 头、许可、不可撤回点、配置使能。压力测试可以保留，但必须标注越域，不能与正常路径缺陷混计。
- 用独立生成器枚举合法域；每个随机维度给出边界到达证据（跨/不跨、满/空、最高/最低优先级都出现过）。
- 对每个新用例问：真实上游能否在这个时刻发出这组输入？如果不能，结论只能是接口压力，不是架构 bug。

### 3.6 完成性/活性/记账缺口：空跑和超时都可能是假通过

**表现：**

- offered 了 N 笔，accepted 0 笔，测试仍 PASS。
- drain/while 循环达到预算后返回部分结果，没有断言 outstanding=0。
- 只检查最终输出，不检查“请求被拒绝后是否留下痕迹”。
- 监视器按电平计数，把一拍事务算成多拍。

**跨模块实例：**

- **Sbuffer**：R1 空模型、两端口 ready=0，提交新行，`enqueue()` 正常返回；R2 预算耗尽后模型仍有 8 行，用例 PASS。二次复核确认这是**测试空跑/完成性缺陷**，不是已确认 RTL bug。
- **MMU**：多个 issue 的 ready while 没有超时，等待时还不服务其它端口；后来加有界超时和全通道采样。
- **LSU**：父块 `prime()` 使用 `compare=False`，初始化窗口不比较；虽补了首条 Load 无 prime 对照，但完整初始化状态仍未证明。
- **VAGQ**：零 mask 导致 ACK 无法完成，原始运行 73–89 cycle，延长到 296–416 cycle 仍停滞；这说明“等得不够久”不是根因，但也说明必须把超时作为失败而不是正常返回。

**检测：**

- 每个用例维护 offered/accepted/completed/outstanding 计数；退出前断言 `outstanding==0` 或明确允许的残留。
- 所有 drain/wait 循环：预算耗尽必须抛错；不能静默返回部分结果。
- 对握手类缺陷检查“未授权副作用”：未被接受的请求不得发下游事务、不得推进状态、不得增加计数器；被撤销的请求不得在若干拍后“复活”。

### 3.7 XFAIL/waiver 遮蔽：宽泛标记会吞掉不同根因

**表现：**

- 整个测试函数打 XFAIL，任何 assertion、timeout、setup 异常都被吞掉。
- strict 只防 XPASS，不限制失败原因。
- 多个不同根因共用一个 marker，计数被误读成“一个已知问题”。

**跨模块实例：**

- **VAGQ**：6 个 XFAIL 取消遮罩后全部真实 FAIL，但对应 4 类不同原因：fractional 架构窗口 vs 协议槽、ordered store 断言过强、wide segment 非生产入口。不能解释成 6 个已确认 RTL/ISA 缺陷。第一个 fractional XFAIL 甚至更早被 checker mismatch 截住，没有执行到最后的 ISA 断言。
- **MMU**：5 个 strict XFAIL 被逐项证伪后移除；宽泛 XFAIL 可能吞掉任意 setup 异常。
- **DCache**：3 个 xfail 是同一个已确认 RTL 缺陷在三个层次的严格复现，不计入通过数；这是正确用法。
- **LSQ**：旧 FAIL 通过调整模型/相位消除，缺少逐节点日志，无法逐项判断；这是“事实上的 waiver”，比显式 XFAIL 更隐蔽。

**检测：**

- XFAIL 只允许“精确 nodeid + 精确失败原因 + 指向已确认缺陷/未支持配置”；任何其它失败必须暴露。
- 定期 `--runxfail` 全量解遮罩，逐条核对实际失败位置。
- 不用“失败数量符合预期”替代通过；不把多个根因合并成一个 marker。

### 3.8 可观测性/断言缺口：检查点根本不存在

**表现：**

- 源码断言被综合/裁剪流程移除，仿真里从未存在。
- 计数器/状态没有导出到 DUT 端口，测试无法观察。
- 模型有字段但观测缺失；或观测有字段但比较器缺失。
- 缺省端口被静默补 0，缺失输出不报错。

**跨模块实例：**

- **LSU**：StdExeUnit 的 `STD_out_of_range_issue` 没有导出端口，旧 env 只收集 `in/out/toRob/atomicData/sqData/feedBack`；功能覆盖里也没有该计数器。
- **ICache**：`verification-lessons.md` 第五部分专门讲“断言可能根本不在被测对象里”；要清点、确认存活、转换为端口可观察检查、记录。
- **MMU**：`DTLB opt()` 对任何缺失输出静默补 0；后来只允许明确列出的端口裁剪，缺失立即失败。
- **DCache**：perf 计数器高位、宽总线在 toggle 上天然低；不能把“位没翻转”当成“功能没验证”，反之也不能把“功能覆盖 100%”当成“所有输出都检查了”。

**检测：**

- 建“断言清单”和“可观测输出清单”：每条断言在生成 RTL 中是否存活？每条语义是否有端口可观察？没有的写替代检查。
- 对 perf/status 这类非主数据通路，明确纳入功能合同或源码契约检查，不能因为“不影响功能”就排除。
- 缺省端口/缺省字段必须 fail-closed，不能静默补 0。

### 3.9 环境/测试基础设施缺口：绿色可能来自收集失败或重复定义

**表现：**

- 测试函数重名，后定义覆盖前定义，实际 collection 少跑。
- 测试被错误注释/字符串化，从未被收集。
- 恒真断言、`if False`、`or True`。
- 采样在时钟沿前/后不一致，或按电平重复计数。
- 运行器只保留 PASS 计数，不保留逐节点日志和源码版本。

**跨模块实例：**

- **LSU**：复核前发现 3 处恒真断言；历史 17 次 FAIL 没有逐节点 traceback；factory 创建的 DUT 未被覆盖采集登记，导致 `native_inputs=0`。
- **MMU**：L2TLB 19 组完全相同的重名定义、HPTW 1 组不同重名定义；两个 PORT-02 函数被字面量 `\n` 写成单行注释，从未收集；PtwCache 两处 `else True`/`if False`。
- **Sbuffer**：`accept()` 在 `req_valid=0` 时仍可标记模型接受；ID 只检查范围，不维护 outstanding 绑定。
- **DCache**：功能点文档与 RTL/测试不一致（bank 地址位、AMO miss 响应、release opcode、CBO opcode 等 7 项）。

**检测：**

- 对全部 `test_*.py` 做 AST 扫描：恒真断言、重复函数名、注释中的 def、`if False`、`or True`、`pytest.skip/xfail`。
- 比较“Python 定义数”和“实际 pytest collection 数”；任何差异都要解释。
- 运行器保留 console、JUnit、provenance、源码哈希、种子和退出码；失败运行不能只留计数。
- 对 helper/checker 做最小反例自检：非法调用应当被拒绝，而不是静默接受。

### 3.10 证据/归因缺口：把“未确认”写成“已排除”，或把“多个失败”写成“多个 Bug”

**表现：**

- 旧失败缺少逐节点日志和当时源码版本，却给出确定性根因。
- 把“源码看起来有问题”直接算成已确认 Bug。
- 把同一根因在多个种子/层次/节点的失败重复计数。
- 把“未复现”写成“不存在”。
- 把旧的误报结论直接沿用，不重新审计。

**跨模块实例：**

- **LSU**：历史 5 个 run 共 17 次 FAIL 无逐节点证据，当前报告只能判“证据不足，不计为确认 Bug”，不能判“已排除 RTL Bug”。
- **LSQ**：全量裁定把 228 个失败节点分为 221 个 RTL 问题 / 7 个非 RTL 节点，归并为 11 个根因；`#6634` 等上游线索后来新增，但计数严格区分“本地复现/仅源码确认/未复现”。
- **MMU**：8 条旧缺陷/限制归因被撤回；旧报告中的“逐项分类”不等于“不可达已证明”。
- **Sbuffer**：首轮独立审计把若干覆盖不足与检查器缺口列成 P1，二次复核降级为“测试假通过/接口缺口”，没有确认 RTL bug。
- **VAGQ**：2278 个失败 shape 逐项重放，确认的是失败分类与根因证据，不是 2278 个 RTL Bug；原始 6074 PASS / 2278 FAIL 保留。

**检测：**

- 统一证据等级：`confirmed RTL bug` / `confirmed checker or test bug` / `unconfirmed source risk` / `out-of-domain or unsupported` / `ruled out`。
- 每个确认 Bug 必须有：合法激励、公开可观察输出、独立期望、可复现命令、源码/RTL 证据、影响边界。
- 同一根因只计一次；不同根因不能因为出现在同一测试里就合并。
- 不追溯改写历史 JUnit；旧失败保留，新增复核单独记录。

---

## 4. 跨模块案例矩阵

| 模块 | 文档中的案例 | 假阴性机制 | 结果/教训 |
|---|---|---|---|
| LSU | Store 故障 tval | 同源模型 + 测试注释把 RTL 行为写成合同 | 输入 VA 与 TLB fullva 不同，测试却断言输入 VA |
| LSU | CBO + PBMT=NC | 组合缺失 + IO 样本代表整个 uncache | bin 名覆盖，实际只采样 IO |
| LSU | S3 redirect kill | 只查主输出 + 模型无 kill 门控 | `ldout/intRF/lqWrite` 实际全 1 |
| LSU | matchInvalid | 只查 rollback + 模型无清零 | LQ 仍带 cause_4 |
| LSU | prefetch.w | 变体未枚举 + 模型固定 M_PFR + 无 pftCoh 观察点 | DCache cmd=2，预期 3 |
| LSU | HWPF perf3 | 同源预期 + 错误归类为结构死逻辑 | 已知互斥却断言 0 |
| LSQ | `#6634` 同拍异常 | 模型复制候选条件和物理槽序 | 双 lane 探针证明真实错误可被正常完成抢占 |
| LSQ | `#6229/#6312` 前递覆盖 | 模型与 RTL 同用“范围=完整覆盖” | 单向字节检查不够，要查“应前递却未前递” |
| LSQ | `#6704` 首尾窗口 | 半完成窗口未成为功能点 | 连续发完首尾掩盖中间态 |
| LSQ | `#6688/#6697` 参数边界 | 默认阈值 12，未测 0 | 默认配置全绿不能证明参数合法 |
| LSQ | `#6714` 退休目标 | 普通 retired 对照不覆盖跨代回绕 | 边界组合缺失 |
| LSQ | 7 个误报节点 | 越过真实 producer 约束 | VSQ 同拍 dispatch+redirect、ROB pending、RAR 当 C_NK、8B CBO、不可撤回 Store 自取消 |
| Sbuffer | R1 空跑 | 未接受的新行不报错，模型为空 | 正式用例 PASS；offered=4, accepted=0 |
| Sbuffer | R2 排空超时 | 预算耗尽正常返回 | 模型仍有 8 行仍 PASS |
| Sbuffer | R3 ID 生命周期 | 只查范围，不维护 outstanding | 非法 accept/ID 复用未被拒绝 |
| Sbuffer | R4 同字节优先级 | bin 命中但无同字节竞争 | 反转期望 240 次调用仍 16 PASS |
| Sbuffer | R5 CMO 分类 | 只查空信号，不查分类退出 | 强制普通 flush 仍 16 PASS |
| Sbuffer | R6 地址低位 | 只比较 `addr>>6` | bit0 扰动 97 次仍 16 PASS |
| DCache | 功能点审计 | 文档与 RTL/测试不一致 | 7 项修正；只查握手、AMO miss 响应、release opcode、CBO opcode 等 |
| DCache | MissQueue store-merge | 已知 RTL 缺陷用 3 个严格 xfail | 正确用法：同一根因跨 3 层，不计入通过 |
| ICache | 三类漏检 | 功能点缺口/检查器缺口/激励缺口 | 只补用例通常只修第三类 |
| ICache | 参考模型从 RTL 反推 | 取消/清理类语义被一起固化 | 先写契约，再看 RTL |
| ICache | 检查器三种失效 | 过严、死字段、死开关 | 都让结论比实际更强 |
| MMU | 8 条归因撤回 | 环境误报/错误契约/观测不完整 | 全 case 审计 + 最小对照，不沿用旧强结论 |
| MMU | 重复/失活用例 | 重名覆盖、注释中的 def | 实际 collection 必须核对 |
| MMU | 宽泛 XFAIL | 任意 assertion/timeout/setup 异常 | strict 不限制失败原因 |
| MMU | 缺省端口补 0 | 缺失输出静默通过 | 改为 fail-closed |
| MMU | 事件采样 | 空闲/默认 stage 被计入 consume | 功能覆盖只代表已定义 sampled marginals |
| VAGQ | 6 个 XFAIL | 架构 vs 协议层级混淆、断言过强、非生产入口 | 解遮罩后 6 FAIL，但不是 6 个 Bug |
| VAGQ | 参考模型 mergeWriteMask | 字段含义错误 | 先修参考，再独立复核 RTL |
| VAGQ | 2278 个失败 shape | 多个主分类重叠 | 逐项重放，不把失败数当 Bug 数 |

---

## 5. 统一诊断树：一个失败/一个漏检到底属于哪类

按顺序问，每问都要给出具体代码位置或证据：

```text
1. 激励是否合法且真的到达？
   否 -> 激励缺口 / 生产者准入错误（可能是越域假失败）
   是 -> 2

2. 出错的可观察输出是否被采集？
   否 -> 可观测性缺口（端口/断言/字段）
   是 -> 3

3. 该输出是否被比较？
   否 -> 检查器缺口（死字段/只看主输出）
   是 -> 4

4. 期望是否独立、层级是否正确？
   否 -> 同源预期 / 抽象层级错误
   是 -> 5

5. 该组合是否被功能点承诺？
   否 -> 功能点/组合矩阵缺口
   是 -> 6

6. 完成性/活性/记账是否检查？
   否 -> 空跑/超时/outstanding 缺口
   是 -> 7

7. 失败是否被 XFAIL/waiver/triage 抑制？
   是 -> 证据/流程缺口
   否 -> 8

8. 收集/定义/环境是否一致？
   否 -> 测试基础设施缺口
   是 -> 需要新的独立 oracle 或架构 golden，不能只加随机
```

**注意：** 一个漏检往往同时命中多类。LSU 的 prefetch.w 就同时是“激励缺口 + 同源预期 + 可观测性缺口”。复盘必须分别回答，不能只写“补一条用例”。

---

## 6. 复核一套“全绿”用例集的 18 个问题

### 6.1 收集与定义

1. Python 定义的测试数 = 实际 pytest collection 数？差异在哪里？
2. 有没有重名函数、被注释掉的 `def`、字符串化的测试、条件导入？
3. 有没有 `if False`、`or True`、恒真断言、`except: pass`、无断言的 `test_*`？

### 6.2 激励

4. 每个随机维度是否有确定性的边界到达证据（两种极性都出现）？
5. 随机输入是否都在合法域？有没有用非法输入制造“越域失败”？
6. 多请求源/请求×响应/数据×控制/控制事件×正常事务，是否都有同拍用例？
7. 半完成窗口、首尾之间、参数 0/最大值、编码变体是否被显式覆盖？
8. 真实 producer 能否在该时刻发出这组输入？越域压力是否被标注？

### 6.3 检查器

9. 每个输出字段是否都有比较器？模型算了但没人比较的字段有多少？
10. 每个“放行”是字段级、事件级还是整段？整段放行是否有合同依据？
11. 主握手正常但副作用错误（kill/redirect/flush/异常）是否检查？
12. 检查器能否被 readback fault / expected mutation 触发失败？阳性对照是否通过？
13. 有没有按电平重复计数，而不是按握手沿计数？

### 6.4 参考模型

14. 每个 expected 的来源是什么？规范、上游、独立性质，还是 RTL 观察？
15. 模型是否复制了 RTL 的仲裁顺序、覆盖判断、候选产生条件？
16. 架构 oracle 与协议 oracle 是否分离？有没有用协议槽数替代架构元素数？
17. 模型是否“支持但从未驱动”的开关/参数？死开关是否存在？

### 6.5 完成性与证据

18. offered/accepted/completed/outstanding 是否记账？drain 超时是否失败？XFAIL 是否只针对精确原因？失败运行是否保留逐节点日志、种子、源码/RTL 哈希？

---

## 7. 对 KMH-v3 / LSU 的具体改进计划

### P0：先堵住会直接让真实 Bug 通过的路径

1. **契约优先的 expected 表**
   - 每个 DUT 的每个架构字段，先在 `memblock-hash/lsu/docs/contracts/` 写可观察后果，再写模型。
   - expected 标注来源：ISA/特权规范、上游修复说明、独立性质、实现观察。
   - “实现观察”类 expected 不得单独作为通过依据。

2. **全副作用检查清单**
   - kill/redirect/flush/exception 拍：检查 `ldout/toRob/toIntRf/toFpRf/lqWrite/rollback/fastReplay/exceptionInfo` 全部有效位与关键 payload。
   - Store 异常：检查 tval 是 masked fullva；CBO 检查分类与异常；kill 后检查 SQ/LQ/RF 不推进。
   - 不能只检查 `pipeOut` 或主握手。

3. **LSU 组合矩阵**
   - CBO × PBMT（PMA/NC/IO）× align × pmp；
   - redirect kill × 全部写回/队列副作用；
   - matchInvalid × 每个 replay cause；
   - prefetch.i/r/w × DCache cmd / TLB / PMP；
   - 指针掩码 × Store/CBO tval；
   - 性能事件 × 功能事件（HWPF miss、STD 越界计数）。

4. **上游回归语料**
   - 把 #6742、#6060、#6154、#5810、#6158、#6653 作为普通 FAIL 回归；修复后自动转 PASS，不靠人工删 marker。
   - 当前已加入 `memblock-hash/lsu/tests/upstream_spec/`，但仍需把“Issue/PR → 本地最小复现 → 失败证据”做成固定流程。

5. **禁止用改模型消除失败**
   - 失败先分级：RTL / 检查器 / 激励 / 环境 / 未确认。
   - 任何模型改动必须附独立依据；不能用“模型对齐 RTL”作为修复。
   - 历史失败保留原 JUnit/计数，不追溯改写。

### P1：让“全绿”变得有区分力

6. **检查器自检**
   - 每个 DUT 至少一组 readback fault / expected mutation，确认检查器会失败。
   - 对恒定通过路径做“删除断言后仍然 PASS”的反向审计，找出无效检查。
   - 对 helper 做非法调用最小反例（如 Sbuffer 的 `accept()`、LSU 的错误键）。

7. **完成性记账**
   - 所有 driver 维护 offered/accepted/completed/outstanding。
   - 所有 drain/wait 超时必须抛错；退出前检查 outstanding=0。
   - 对“被拒绝但留下痕迹”的请求做延迟观察。

8. **逐 bin reached/checked**
   - 功能 bin 的 `sample_case()` 只算 reached；每个 bin 必须绑定至少一个区分性断言才算 checked。
   - 对没有区分性断言的 bin，要么补断言，要么降级为“仅到达”，不能计入 100% checked。

9. **性能/状态计数器**
   - 能导出端口的，纳入功能检查；不能导出的，做固定源码契约检查并记录边界。
   - StdExe 的 `STD_out_of_range_issue` 是已确认例子；其它 DUT 的 perf 计数器也应清点。

10. **架构 golden / difftest**
    - 对 tval、异常优先级、CBO、prefetch 意图、kill 副作用这类架构语义，模块内模型不足以证明。
    - 在范围内引入独立 ISA/特权检查，或明确标注“仅模块接口验证，不声称架构正确”。

### P2：流程和证据

11. **XFAIL/waiver 政策**
    - 只允许精确 nodeid + 精确失败原因 + 已确认缺陷/未支持配置。
    - 定期全量 `--runxfail` 复核；禁止整函数宽泛 marker。
12. **证据等级和计数规则**
    - 统一 `confirmed RTL` / `confirmed checker` / `unconfirmed` / `out-of-domain` / `ruled out`。
    - 同一根因只计一次；失败节点数不是 Bug 数。
13. **随机合法性**
    - 约束随机而不是任意位模式；每个维度有边界到达证据；非法输入单独标注。
14. **文档回填**
    - 每次漏检复盘必须回填功能点、组合矩阵、检查器清单；只在聊天里总结等于没发生。

---

## 8. 报告与计数规则（避免再次出现“悬而未决”）

### 8.1 确认 RTL Bug 的最低证据

同时满足：

1. 合法激励，且真实 producer 能发出；
2. 公开可观察输出；
3. 独立期望（规范/上游/性质，不是 RTL 观察）；
4. 可复现命令、种子、DUT/RTL/源码哈希；
5. 影响边界明确；
6. 同一根因只计一次。

### 8.2 确认检查器/测试 Bug 的最低证据

1. 用例承诺的事务没有完成，但用例仍 PASS；或
2. 注入一个应被检查器拒绝的故障，检查器没有拒绝；或
3. 检查器在合法激励下产生假失败，且能定位到过严字段/整段静音。

这类问题可以明确写“确认是验证 Bug”，但不能写成“确认 RTL Bug”。

### 8.3 未确认项怎么写

- 写“未确认，原因是缺少 X”，不要写“不是 Bug”。
- 写“不在当前 DUT 范围”，不要写“已排除”。
- 写“证据不足，不计入确认数”，不要写“悬而未决的 Bug”。
- 历史失败没有逐节点证据时，明确说“无法还原当时根因”，不要补造。

---

## 9. 当前 LSU 状态与本总结的关系

- 当前回归：`memblock-hash/lsu/results/upstream-review-regression-02`，**582 PASS / 7 FAIL / 589 项**，19 个原生 DUT。
- 7 个确认 RTL Bug：`LSU-HWPF-MISS-001`、`LSU-STORE-TVAL-001`、`LSU-CBO-NC-AF-001`、`LSU-S3-KILL-WB-001`、`LSU-MATCHINV-CAUSE-001`、`LSU-PREFETCH-W-INTENT-001`、`LSU-STD-PERF-001`。
- 11 项验证/报告问题：9 项已修正，2 项未闭环（历史日志不可恢复、逐 bin 独立 reached/checked 未完成）。
- 当前交付门禁：`memblock-hash/lsu/results/upstream-review-regression-02/delivery-recheck-audit.json` 为 **FAIL**，明确列出未修复 RTL 缺陷、历史证据不足和独立 reached/checked 未闭环。
- 覆盖分母仍逐 DUT 保留；父块 `NewLoadUnit` toggle 为 **39686/40024**，旧 22 点“不可达”已撤回。
- 功能覆盖 100% 只表示声明 bin 采样达标，不表示逐 bin 独立 semantic check 完成。

---

## 10. 已知限制

1. 本文是经验总结，不是“所有可能假阴性已消除”的证明。
2. 其他模块的案例只作为方法证据；不同基线、配置、代理和统计口径不能混算。
3. LSU 仍未完成全量组合矩阵、逐 bin 独立检查、全核 ISA golden；这些是后续工作，不是已完成项。
4. #6678、#6267 等上游线索仍未本地复现，不能计为已确认 Bug，也不能称为已排除。
5. 历史 17 次 FAIL 缺少逐节点日志，无法完整复盘当时 triage；本总结不补造结论。
6. 本文没有修改 RTL、旧测试、旧参考或历史 JUnit；当前回归的 7 个 FAIL 是保留证据，不是待删除的噪声。

---

## 11. 一页检查表（可直接贴到每个 DUT 的报告首页）

```text
[ ] 功能点是否写成“当 A 与 C 同时发生时，结果必须同时满足 B 与 D”？
[ ] 每个功能点是否有 reached 证据 + checked 证据？checked 是否绑定区分性断言？
[ ] 是否列出了本 DUT 的全部输出字段，并逐个说明“比较/删除/不可观测”？
[ ] kill/redirect/flush/exception 拍是否检查了全部副作用，而不只是主 valid？
[ ] 参考模型的每个 expected 是否标注来源？是否从 RTL 反推？
[ ] 是否检查了“应发生却没有发生”，而不只是“已发生的来源正确”？
[ ] 是否构造了半完成窗口、首尾之间、参数边界、编码变体？
[ ] 是否让两个源/请求与响应/数据与控制在同一拍竞争同一状态？
[ ] 随机输入是否合法？每个维度是否有边界到达证据？
[ ] 是否维护 offered/accepted/completed/outstanding？
[ ] 所有 drain/wait 超时是否失败？退出前是否检查 outstanding=0？
[ ] 检查器是否通过 readback fault / expected mutation 自检？
[ ] 是否有恒真断言、重名测试、注释中的 def、未收集测试？
[ ] XFAIL 是否只针对精确 nodeid + 精确原因？是否定期解遮罩复核？
[ ] 断言在生成 RTL 中是否存活？缺失的输出是否 fail-closed？
[ ] 失败运行是否保留 console/JUnit/种子/源码/RTL 哈希/逐节点日志？
[ ] Bug 计数是否按根因去重？是否区分 confirmed / unconfirmed / out-of-domain？
[ ] 是否把“未确认”误写成“已排除”？
```

---

## 12. 证据索引

### LSU

- `memblock-hash/lsu/docs/bug-reports-20261026/README.md`
- `memblock-hash/lsu/docs/bug-reports-20261026/01-LSU-HWPF-MISS-001.md`
- `memblock-hash/lsu/docs/bug-reports-20261026/02-false-positive-review.md`
- `memblock-hash/lsu/docs/bug-reports-20261026/03-false-negative-review.md`
- `memblock-hash/lsu/docs/bug-reports-20261026/04-coverage-and-evidence-review.md`
- `memblock-hash/lsu/docs/bug-reports-20261026/05-upstream-review-20261026.md`
- `memblock-hash/lsu/docs/bug-reports-20261026/06-why-missed.md`
- `memblock-hash/lsu/review/upstream_check_20261026_01/audit.json`
- `memblock-hash/lsu/results/upstream-review-regression-02/`

### LSQ

- `memblock-hash/lsq/docs/reports/same-source-audit-20261022.md`
- `memblock-hash/lsq/docs/bug-reports-20261022/12-false-positive-review.md`
- `memblock-hash/lsq/docs/bug-reports-20261022/13-github-missed-bugs.md`
- `memblock-hash/lsq/docs/bug-reports-20261022/14-relationship-11-vs-5.md`

### Sbuffer

- `memblock-hash/sbuffer/docs/reports/independent-audit-20261024.md`
- `memblock-hash/sbuffer/docs/reports/bug-recheck-20261024.md`

### DCache

- `memblock-hash/dcache/docs/reports/functional-point-audit-20261025.md`
- `memblock-hash/dcache/docs/reports/coverage-20261025.md`

### ICache

- `icache-verify-kunminghu-v3/docs/verification-lessons.md`
- `icache-verify-kunminghu-v3/docs/error-review.md`

### MMU

- `memblock-hash/mmu/docs/reports/verification-soundness-20261025.md`

### VAGQ

- `vqgq-d4566d5-20261016/results/vagq-xfail-contract-review-20261018-v1/README.md`
- `vqgq-d4566d5-20261016/results/vagq-exhaustive-review-20261020-v1/README.md`
- `vqgq-d4566d5-20261016/results/vagq-reference-repair-rtl-rereview-20261020-v2/README.md`
