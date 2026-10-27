# ICache 验证中的错误复核

> 可复用的避坑清单见 `docs/verification-lessons.md`（根据本文件的漏检案例整理）。

本文件复核验证过程中出现的全部失败、XFAIL 与“看似缺陷”的观察，逐条判定为：

- **真实 RTL 缺陷**：与 ISA/公开设计文档语义不符，或与上游同一提交的意图不符；
- **外部约束 / 结构不可达**：在合法输入或本配置下该情形不会发生；
- **验证环境 / 参考模型错误**：测试台或模型对协议理解有误，已修正。

## 1. `prefetch.i` 软预取使用上一拍的组索引 —— 真实 RTL 缺陷（XFAIL，ICACHE-012）

**现象**：软件预取 `prefetch.i` 之后，需求取指仍然缺失；预取的行被写进一个无法命中的组。

**证据链**：

1. 生成 RTL（`dut/icache/ICacheDut.v`）：

   ```verilog
   if (_GEN) begin
     softPrefetch_startVAddr_addr <= {pc_addr[48], pc_addr};
     softPrefetch_vSetIdx_0 <= softPrefetch_startVAddr_addr[12:5];  // 旧值
   end
   ```

2. 上游 Scala（`XiangShan` `kunminghu-v3` 分支，`Bundles.scala`）仍是同一写法：

   ```scala
   def fromSoftPrefetch(req: SoftIfetchPrefetchBundle): PrefetchReqBundle = {
     startVAddr    := PcInit(req.vaddr).signGuard
     nextLineVAddr := DontCare
     vSetIdx       := VecInit(get_idx(startVAddr), 0.U(idxBits.W))  // 读的是寄存器旧值
     ...
   ```

   `vSetIdx` 在 `startVAddr` 被赋值的同一拍读取寄存器输出，因此取的是**上一次软预取**的地址
   （复位后为 0）。这不是本工程的输入理解问题：`SoftIfetchPrefetchBundle.vaddr` 是 50 位
   完整虚拟地址，测试驱动的是合法值。

3. 设计文档（XiangShan ICache Design Document, V3）规定：软件预取“follows almost the same
   flow” as hardware prefetch——按请求地址查询 MetaArray 与 ITLB，再决定是否发出 miss。
   因此组索引必须来自本次请求的地址；使用旧地址写入的行永远无法被需求取指命中。

**影响**：缺失请求的块地址/页标签正确，但装置写入错误的组；该行占用一个 way 却不可命中。
硬件预取路径不受影响（每个 FTQ issue 都用当前地址查元数据），已由 `ICACHE-ICACHE-015` 验证。

**判定**：真实 RTL 缺陷，登记 `ICACHE-ICACHE-012` 为 XFAIL（strict），对照组（组 0）正常。


## 1.2 软预取与未接受的 FTQ 预取请求合并 —— 真实 RTL 缺陷（XFAIL，ICACHE-030）

**现象**：当软件预取正在等待、同时 FTQ 送来一个尚未被接受的取指 issue 时，该 issue 的
第二个 block 仍然被预取（跨页时还用软件预取的页标签翻译），而 `fromFtq.toPrefetch.ready`
一直是 0。上游以 issue #6674 报告了同一段逻辑的另一种症状：`prefetch.i` 程序触发
`ICacheMetaArray` 的断言“2 read setIdx must be in the different interleaved bank!”。

**根因**（`ICacheImp.scala`，当前 HEAD `893e1580b`）：

```scala
prefetcher.io.fromFtq.valid       := softPrefetchValid || io.fromFtq.toPrefetch.valid
prefetcher.io.fromFtq.bits        := io.fromFtq.toPrefetch.bits          // 含 req(1) 与 twoPrefetchCase
prefetcher.io.fromFtq.bits.req(0) := Mux(softPrefetchValid, softPrefetch,
                                         io.fromFtq.toPrefetch.bits.req(0))
io.fromFtq.toPrefetch.ready       := prefetcher.io.fromFtq.ready && !softPrefetchValid
```

`ready` 被 `!softPrefetchValid` 拉低，但预取流水仍然拿着“软件预取 + FTQ 的 req(1) +
FTQ 的 `twoPrefetchCase`”这个合并请求去 fire。只要 `softPrefetchValid` 有效，FTQ 请求就
永远等不到 ready，但它的第二块已经在内部被处理：

- **握手违约**：未被接受的请求产生了 acquire（我们实测到 FTQ req1 的 block 0x100）。
- **页标签错误**：合并请求只对软件预取做 ITLB 翻译，第二块用软件预取的页标签组块地址；
  两块跨页时会预取错误的物理行。
- **非法元数据读**：软件预取的 stale `vSetIdx`（复位后为 0，偶）与 FTQ req1 的偶数组
  索引落在同一个 interleaved bank，违反 `ICacheMetaArray` 的断言条件——这正是 #6674。

**复现（`results/xreactor-ic-ic30-2`）**：

- 软件预取 `0x4080`（block 0x102，stale set 0）、FTQ Interleave issue（req0 `0x4040`
  → block 0x101、req1 `0x4000` → block 0x100）；
- `fromFtq.toPrefetch.ready` 连续 24 拍为 0；
- 观测到 block **0x100** 的 TileLink acquire（source 6）——即未接受的 req1 被预取。
- 该用例以 strict XFAIL 登记（`ICACHE-ICACHE-030`）。

**与上游 issue 的对应关系**：

| 我们的功能点 | 上游 | 关系 |
|---|---|---|
| `ICACHE-ICACHE-030`（本缺陷） | **issue #6674**（open）→ **PR #6691**（open） | **同一根因**。上游看到的症状是 `ICacheMetaArray` 断言“2 read setIdx must be in the different interleaved bank!”；本工程生成的 DUT 已裁掉断言（`grep -c assert ICacheMetaArray.sv` = 0），所以我们观测到的是握手违约 + 未接受的 req1 产生 acquire |
| `ICACHE-ICACHE-012`（stale `vSetIdx`） | **没有独立 issue** | 属于同一段被 PR #6691 整体删除的代码。PR 删除 `PrefetchReqBundle.fromSoftPrefetch`，改由 FTQ 的 `PrefetchQueue` 构造：`fromPrefetchQueueEntry` 里 `startVAddr` 是 wire（非寄存器），`get_idx(startVAddr)` 取到的是队列项的真实地址 |

PR #6691 的关键 diff（`ICacheImp.scala`）：

```diff
-  prefetcher.io.fromFtq.valid       := softPrefetchValid || io.fromFtq.toPrefetch.valid
-  prefetcher.io.fromFtq.bits        := io.fromFtq.toPrefetch.bits
-  prefetcher.io.fromFtq.bits.req(0) := Mux(softPrefetchValid, softPrefetch, io.fromFtq.toPrefetch.bits.req(0))
-  io.fromFtq.toPrefetch.ready       := prefetcher.io.fromFtq.ready && !softPrefetchValid
+  prefetcher.io.fromFtq <> io.fromFtq.toPrefetch
```

**为什么我们的用例此前没报出来**（重要，属于验证自身的假阴性）：

1. **功能点覆盖缺口**：`ICACHE-012`/`029` 只测“软预取单独存在”，`ICACHE-015` 只测“FTQ
   预取单独存在”，从未构造“软预取 pending + 同一拍 FTQ 双预取 issue”这个组合。
2. **harness 盲区（假阴性）**：`soft_prefetch()` 和 `prefetch_only()` 为了容忍自身那条
   **合法** acquire，把 `allow_unexpected = True` 打开；但实现成**窗口级全局静音**——
   `_sample_acquire` 对窗口内任何未被预测的块都跳过断言，从未检查“窗口里是否只有被
   提示的块”。合法的那条放行了，非法的那些也一起放行了。探针阶段正是这样“通过”的。
3. **断言被裁掉**：生成 DUT 不含 `ICacheMetaArray` 的 interleaved-bank 断言，所以上游
   的 abort 症状在本工程不可见，必须用可观测的 acquire 才能判定。

**关于“是不是为了让测试能跑下去而放弃检测”**——要分两层看：

| 问题 | 回答 |
|---|---|
| 放行开关是为了让测试能跑吗？ | **是，但动机合理**。参考模型 `expect()` 是需求取指驱动的，软预取/纯预取没有对应取指请求，模型无法预测那条 acquire；不放行会把合法行为判成错误。`reset()` 同样需要它（寄存器随机化 + 阵列清扫期间的垃圾 acquire）。 |
| 它是否等于“关掉了检测”？ | **是，而且关得过宽**。这是假阴性漏洞，不是“已知失败被容忍”——当时并没有已知失败，只是把整个窗口的检测一起关掉了。 |
| 它是漏检主因吗？ | **不是**。主因是缺少“软预取 pending + 同拍 FTQ 双预取”的组合功能点；两条路径各自都有用例、覆盖率也各自是满的。行/分支/翻转覆盖发现不了**跨路径交互**缺陷。 |

**已修正**：

- `soft_prefetch()` 与 `prefetch_only()` 的放行窗口改为**有界放行**：记录窗口内所有未被
  需求模型预测的 acquire，并要求它们**只能是被提示 / 被命名的那几个块**；出现其它块立即
  报错（`icacheverify/icache/agent/main.py`）；
- 新增用例 `test_soft_prefetch_fetches_only_the_hinted_block`（`ICACHE-029`）把这一契约
  固定下来；
- 新增 `ICACHE-ICACHE-030` 的 strict XFAIL 用例，直接复现“`ready=0` 却出现 req1 acquire”。

**上游状态（2026-10-20 核查）**：

| 项 | 状态 |
|---|---|
| Issue #6674（2026-10-05，open） | 报告 `prefetch.i` 触发同一断言，分支 `kunminghu-v3` |
| PR #6691（2026-10-09，open） | “Fixes #6674, the related ICache-top softprefetch selection is removed.” 用 `FtqPrefetchQueue` 统一调度软件/硬件预取 |
| `origin/kunminghu-v3` 最新 | `6705b6368`（2026-10-19，仅 XSCache 子模块 bump）；ICache 源码无变化 |
| 修复是否已进入本工程 HEAD | **否**。HEAD `893e1580b` 与 `origin/kunminghu-v3` 在 ICache 源码上无差异 |

**判定**：真实 RTL 缺陷，等上游 #6691 合并后可转为 PASS（strict XFAIL 会以 XPASS 提醒
我们复查）。

## 1.3 WayLookup 在 flush 同拍取消写时仍锁存异常 —— 模块级潜在缺陷（XFAIL，WAYLOOKUP-020）

**现象**：`flush` 与带 ITLB 异常的写在同一拍出现时，写被丢弃（读写指针归零），但
`exceptionEntry_valid` 仍被置 1，`exceptionPtr` 指向旧的 `writePtr`。

**证据链**：

1. 生成 RTL（`dut/waylookup/ICacheWayLookup.sv`）：

   ```verilog
   exceptionEntry_valid <=
     _GEN_83                                    // = write_0_fire & |itlbException
     | ~(io_flush | bpuS3FlushValid & (...))
       & exceptionEntry_valid;
   ```

   `write_0_fire`（`_GEN_17`）没有与 `io_flush` 相与；同一拍的 flush 分支只清
   `readPtr/writePtr/tailFtqIdx`。

2. 用例
   `test_flush_in_the_write_cycle_discards_the_entry_and_its_exception`
   在 flush 后断言 `rtl_write_ready() == 1`；实测为 0。原因：
   `write_0_ready = (|free) & ~exceptionEntry_valid`，异常标志把空队列的写口压住。
   实测再发一次完整 `flush` 后写口恢复；stage-3 flush 只在它算出的被丢弃指针等于旧
   指针时才清除，空队列时不匹配。旧指针不会污染后续条目（其命名的槽在可读之前必被
   新写入覆盖），因此可观测后果是写口停摆，而非错误异常载荷。

3. 可达性：整块 ICache 中不可达。`ICachePrefetchPipe.io_wayLookupWrite_0_valid_0`
   含 `~s1_flush`，而 `s1_flush = io_flush | <stage-3 条件>`；redirect flush 的同拍
   预取管道不会给出写有效。因此这是子模块接口契约层面的潜在缺陷，不影响本 ICache
   集成，但也不应被“集成里不会发生”掩盖。

**判定**：模块级潜在 RTL 缺陷，strict XFAIL。参考模型已按规范修正（被 flush / stage-3
drop 取消的写不得锁存异常），而不是照抄 RTL 行为。

## 1.4 本节小结：模型不能从 RTL 反推

`WAYLOOKUP-020` 的模型在复核前**也**把“flush 同拍的写仍锁存异常”写了进去——因为写
模型时读了 RTL 的 `_GEN_83`。这正好违反了“参考模型依据 ISA/公开文档语义”的规则：
从 RTL 反推期望，会把 RTL 的 bug 一起固化进模型，两边一致，测试全绿，缺陷隐形。
修正后的模型按“flush 清空一切状态、被取消的写不产生任何副作用”重写，RTL 才作为
XFAIL 暴露出来。

## 2. 参考模型 / 测试环境错误（已修正，非 RTL 缺陷）

### 2.1 line/toggle/branch 分析中新增的两条模型修正

| 现象 | 根因 | 分类 | 修正 |
|---|---|---|---|
| PrefetchPipe 的 PMP 用例期望 waylookup 条目带 AF，RTL 条目例外为 0 | RTL 在 s1 写条目时只携带 `s1_itlbException_value`（ITLB/后端）；`pmp_resp_instr` 是 s2 的 miss 请求检查，不进入投机条目 | 参考模型错误（对流水级理解错误） | 模型拆分 `write_exception`（s1）与 `s2_exception`（PMP）；PMP 只抑制 miss，条目例外保持 0 |
| corrupt 回填用例的 `info.data` 与模型不符 | corrupt 回填不会安装，`mshrValid` 为 0，数据来自阵列残留；异常（HWE/AF）才是可消费结果 | 检查器错误（把 don't-care 数据当断言） | 期望异常为 HWE/AF 时跳过 `info.data` 比较，位置/异常/范围仍逐项比较 |



| 现象 | 根因 | 分类 | 修正 |
|---|---|---|---|
| 双取指时 MetaArray port 1 读到错误 bank | 测试固定 `twoPrefetchCase=8`，但 FTQ 规则下两个同奇偶组非跨行请求是 **Conflict**；`ICacheMetaArray` 断言要求双行读落在不同 interleaved bank | 输入标准理解错误 | `prefetch_case()` 按 FTQ 规则（sameLine/overlap1/overlap2/interleave）推导 |
| 第二个取指的 paddr 差 0x40 | 参考模型把 `vSetIdx(1)` 当成“跨行时的第二行”，实际 FTQ 恒为 `get_idx(startVAddr)+1` | 模型错误 | 统一 `vset=(get_idx(vaddr), get_idx(vaddr)+1)` |
| RVC 映射整体偏移 | 模型把 `shiftNum` 的坐标（`startVAddr[5:1]`）与 `takenCfiOffset` 的坐标（`startVAddr[4:1]`）混用 | 模型错误 | 两者分别建模 |
| FTQ 请求只被接受一次却多出一条 waylookup 条目 | xcomm 电平驱动下，观察到 ready 后继续多打一拍，空闲下来的 prefetch pipe 重复接受同一请求 | 测试环境错误 | 观察到 ready 的同一拍撤销 valid |
| `toIfu.corrupt` 偶发读不到 | 该信号是 s2 阶段、`io.error` 再晚一级寄存器 | 测试环境错误 | 响应后连续多拍采样 |
| 软预取 refill 后功能读仍为 0 | BIST/软预取写入发生在 SRAM 复位清扫期间 | 测试环境错误 | 等 `write_ready`/`read_ready` 后驱动 |
| MetaBank/MetaArray 的 validArray 位几乎不翻转 | 旧用例每个 set 只写 way 0，且只 flush 4 个 set | 功能点/用例缺口（已补） | 全 set × 全 way 写入 + `flushAll` 逐位清零 |

### 2.2 按经验文档复核用例时暴露的验证侧缺陷

第八轮复核（见 `docs/verification-report.md`）又找出四类“验证代码/用例自己的问题”，
都不是 RTL 缺陷：

- **检查器过严**：MetaBank / MetaArray 的 `check_read` 把无效 way 的 tag 存储也逐字段
  比较。tag SRAM 与 validArray 是两套存储，flush 只清 valid，旧 tag 留在原地是正常
  实现；把它当断言会在新增的 flush 用例里报假失败。修正为“valid 永远比，entry 只在
  valid=1 时比”，`read()` 的提前退出也复用同一规则。
- **用例没有测它声称的东西**：第一版“flush 同拍读”用 `read()` 驱动，而 `read()` 会等
  `read_ready`，`flushAll` 期间 ready=0，于是它等到 flush 撤销后才真正读，断言的是
  flush 之后的状态。改为直接检查 `read_ready()==0` 才是同拍语义。
- **对寄存器门控的时机理解错**：Mshr 的 `info.valid` 由寄存的 `flush`/`fencei` 标志
  门控，完成拍本身仍为 1；释放只能通过撤销 `fencei` 后 `req.ready` 回升来观察。
  第一版断言“同拍必须为 0”失败，属于测试对时序的误解，不是 RTL 缺陷。
- **未驱动的模型开关**：`MissUnitModel.complete(fencei_now=, flush_now=)` 从未被
  `MissUnitAgent` 驱动到 DUT，也没有任何用例使用。按本 harness 的电平提交时序，
  “响应发布但实时写门控生效”这一拍不可构造（同一电平也会置起寄存标志、压掉响应）；
  因此删除这两个参数，并在模型处记录原因，避免它们伪装成已覆盖的组合。

另外，随机生成器的固定种子无法保证踩全 waymask：DataBank 32 次采样只覆盖 13/15，
DataArray 48 次只覆盖 14/15。已把 waymask 改为确定性遍历、数据仍随机——随机负责
激励多样性，边界取值必须显式可达。

## 3. 外部约束 / 结构不可达（不是 RTL 缺陷）

| 观察 | 结构性证据 |
|---|---|
| `ICacheMshr_2/3` 的分配行未覆盖 | 设计文档规定一个取指请求最多引用 **两条 cacheline**；main pipe 的 s1 单条目在 miss 完成前阻塞，故取指 MSHR 同时最多占用 0/1。实测 fetch acquire source 恒为 {0,1}，prefetch 为 {4..13}。2/3 是预留容量 |
| MetaBank / MetaArray bank0 的 `bd_array`/`mbistBd_array` 直连行未覆盖 | 该 bank 只有 **一个** SRAM 宏，`array` 端口宽度为 0（`signals.json`: High=-1），零宽信号不存在 0→1 变化 |
| `ICacheCtrlUnit` 159/160/164 未覆盖 | 159/160 位于写分支内但条件含 `deq_bits_read`，与写分支的 `~read` 矛盾；164 需要 `iState==ReadMetaResp` 且 `iStatus==Idle`，而 ReadMetaResp 只在 Working 期间到达、NotFound 时 `iState` 同步归零。均为 firtool 共享子表达式产生的死代码 |
| `ICacheReplacer` 626 行未覆盖 | 多行 `wire ... =` 声明首行；同文件其余 6200 条语句与字节相同子模块 DUT 全量覆盖 |
| 整块 ICache 中 WayLookup 504 / PrefetchPipe 2 / Replacer 1 行未覆盖 | 三个文件与子模块 DUT **字节相同**（sha256 校验），子模块运行逐行覆盖这些行 |

## 4. 整块 ICache 中“两行全缺失的跨行取指 RVC 映射”

主 pipe 的 RVC 拼接在“两条线都在本轮 refill、且分两拍返回”时，取决于两拍响应的先后顺序：
每个拍只携带一条线的原始 map，并只按当前拍命中的端口做对齐。参考模型采用静态合并，在这种
时序下不能从微架构语义唯一确定期望值；因此整块集成用例 `ICACHE-ICACHE-028` 只断言**数据**
与 refill 归属，跨行 RVC 映射由“第一行命中 + 第二行 refill”的 `ICACHE-ICACHE-003` 断言。
这不是 RTL 缺陷结论，也不放宽任何已定义功能点的断言：单行、命中+refill、第二取指跨行
（`ICACHE-ICACHE-018`）的映射均有判定。
