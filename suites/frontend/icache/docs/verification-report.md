# ICache 功能验证交付报告

目标：对 XiangShan kunminghu-v3（`893e1580b`）的 ICache 及 10 个子模块完成"功能点定义
→ ISA/文档驱动参考模型 → 功能点驱动用例 → `xreactor run` → 行覆盖率缺口倒推补功能点"
的闭环验证。

## 总览

| DUT | 功能点 | 功能点判定 | 覆盖率证据 | 闭环文档 |
|---|---|---|---|---|
| ICacheWayLookup | 16 | 15 PASS + 1 XFAIL | 语句 2756/2756 = **100%** | `docs/waylookup-coverage-closure.md` |
| ICacheReplacer | 7 | 7 PASS | 语句 6201/6201 = **100%** | `docs/replacer-coverage-closure.md` |
| ICacheMshr | 8 | 8 PASS | 语句 29/29 = **100%** | 计划内证据 |
| ICacheMissUnit | 11 | 11 PASS | 语句 487/487 = **100%** | `docs/missunit-coverage-closure.md` |
| ICacheMainPipe | 15 | 15 PASS | 语句 432/432 = **100%** | `docs/mainpipe-prefetchpipe-coverage-closure.md` |
| ICachePrefetchPipe | 14 | 14 PASS | 语句 295/295 = **100%** | 同上 |
| ICacheDataBank | 7 | 7 PASS | 语句 **100%**（含逐 way BIST 访问） | `docs/sram-dut-coverage-limitation.md` |
| ICacheMetaInterleavedBank | 11 | 11 PASS | 可执行语句 **100%**；剩 1 条零宽 `bd_array` 直连 | 同上 |
| ICacheMetaArray | 12 | 12 PASS | 可执行语句 **100%**；剩 1 条零宽 `bd_array` 直连 | 同上 |
| ICacheDataArray | 11 | 11 PASS | 语句 **100%**（8 bank × 4 way BIST 与功能读） | 同上 |
| **ICache（整块）** | **30** | **28 PASS + 2 XFAIL** | 语句 11452/11970 = 95.67%；518 条缺口逐行对账（504/2/1 由字节相同子模块覆盖，8 条预留 MSHR，3 条死代码） | `docs/icache-coverage-closure.md` |

- 功能点总数：**142**；全部有用例判定（无 NOT_RUN）。
- 用例：**290 passed + 3 xfailed**（line/branch/toggle 分析 + 随机战役 + 功能点缺口补全 + 复位/反压/指针边界 + 软预取/FTQ 合并 + 按经验文档逐条复核用例）。
- 三个 XFAIL：两个是整块 ICache 的软预取路径（`prefetch.i` 的 stale `vSetIdx`，ICACHE-012；软预取/未接受 FTQ 请求的合并，ICACHE-030），第三个是 WayLookup 在 flush 同拍取消写时仍锁存异常的模块级潜在缺陷（WAYLOOKUP-020，集成中因预取管道 `s1_flush` 门控而不可达）。

## 给后续 agent 的经验总结

`docs/verification-lessons.md` 是一份**与具体设计解耦**的通用验证方法论长文，约 720 行，
按"命题 → 合法例外 → 组合覆盖 → 模型表达 → 断言可见性 → 握手检查 → 随机到达性 →
计数 → 复盘 → 覆盖率边界 → 流程 → 自查 → 反模式 → 复核流程 → 模型不反推 → 检查器
自身失效 → 术语"展开，可用于任何 DUT 的单元或集成验证。它由本工程的漏检案例提炼而来，但全文不含本工程的信号名、文件路径或
issue 编号。接手新 DUT 前建议通读；本工程的原始案例仍保留在 `docs/error-review.md`
作为出处。

## 工具链与流程

- `picker` memory-direct 构建（`--rw mem_direct -w memory-direct.fst -c`），Verilator 5.052，
  xcomm native ABI 3 / coverage protocol 5，xreactor `dev/coverage-v2`（`2461d0f`）。
- 所有用例只通过 `xreactor run` 启动（串行 `--workers 1`，并行 `--workers 4`），
  未直接调用 pytest。
- 每个 DUT 保持独立的 `icacheverify/<dut>/{agent,bundle,transaction,env,case,model,checker,coverage,driver,monitor}`
  角色目录；`tests/framework/test_repository_layout.py` 的 `IMPLEMENTED` 已如实列出全部 11 个 DUT。
- 参考模型依据 ISA/公开文档/教科书语义（MSHR 纪律、tree-PLRU、循环 FIFO、VIPT 组相联、
  RISC-V Svpbmt/fence.i/WFI 语义），模型注释中给出语义出处；未从 RTL 反推期望值。
- 缺失对端的模块使用事件驱动外置辅助模型（TL 存储对端、TL 寄存器从端、FTQ/IFU/ITLB/PMP
  对端、replacer 对端），辅助模型只使用 DUT 的公开端口。

## 缺口倒推摘要

| DUT | 初版功能点 | 倒推补出的功能点 |
|---|---|---|
| WayLookup | 6 | 007–013（updateStall、miss 更新、槽位、回卷等） |
| Replacer | 6 | 007（全集合/全端口扫描） |
| MissUnit | 10 | 011（14 个 MSHR 槽位逐一 issue/回填） |
| MainPipe | 10 | 011（第二取指跨行/缺失/回填异常）、012（全 bank ECC） |
| PrefetchPipe | 9 | 010（回填更新 stage-1 元数据）、011（miss 反压） |
| MetaArray | 7 | 008（全集合写解码） |
| MetaBank | 6 | 007（全集合写解码） |
| DataArray | 7 | 008（request×bank×way 矩阵） |
| ICache | 14 | 015–018 第一轮；019–028 第二轮（refill 修正/失效队列条目、BIST、环形槽双端口、BPU 尾冲刷、第二半行 way 命中、RVC 拼接、10 个 prefetch MSHR、ITLB 重发、跨行双 fetch MSHR） |

每轮倒推都先重跑，用 `tools/coverage_gaps.py` 取新的缺口，再决定是补功能点还是书面归因；
没有改 RTL、没有剔除分母、没有 skip。

## 参考模型缺陷（模型修正，非 RTL）

- WayLookup：`waySame` 是**等值**比较；`(tag,set)` 参数化重叠。
- Replacer：tree-PLRU 的高编号 way 在 older-bit=1 一侧；victim 端口有锁存副作用；victim
  必须按"触摸前"状态取值。
- MissUnit：`victim.resp.way` 是 2-bit way 索引（`waymask = UIntToOH(way)`）；fence.i/flush
  抑制已发出事务的响应与阵列写；denied 必须伴随 corrupt。
- MainPipe / PrefetchPipe：`PrunedAddr` 端口携带 `address >> 1`；set 索引是 `addr[13:6]`；
  pTag 是 `blkPAddr >> 6`；命中行只读 bankSel 覆盖的 bank，回填行填满整行。
- ICache：`twoPrefetchCase` 必须按 FTQ 规则由两个请求推导（同奇偶组的非跨行对是 Conflict）；
  ITLB 响应是 1 拍流水、PMP 是组合；异常取指后必须重定向释放 waylookup 的异常条目。
- xcomm 电平语义：请求只在一个采样沿有效；同一 `valid` 保持过久会被空闲下来的对端重复接受。

## RTL 缺陷（已登记 XFAIL）

**`prefetch.i` 的组索引取上一拍地址**（`ICacheImp`）：

```verilog
if (_GEN) begin
  softPrefetch_startVAddr_addr <= {pc_addr[48], pc_addr};
  softPrefetch_vSetIdx_0 <= softPrefetch_startVAddr_addr[12:5];   // 旧值
end
```

- 影响：软预取的块地址/页标签正确，但写入的组是**上一次**软预取的组（复位后为组 0）。
  该行永远无法被需求取指命中，等于浪费一个 way。
- 证据：`test_software_prefetch_warms_the_requested_line`（xfail）先验证组 0 的对照组
  （`0x8000`）命中，再断言 `0xB000`（组 0xC0）的软预取应使需求取指命中；后者失败。
- 硬件预取路径不受影响：每个 FTQ issue 的预取管道都用当前地址查元数据
  （`ICACHE-ICACHE-015` PASS）。

**软预取与未接受的 FTQ 预取请求合并**（`ICacheImp`，`ICACHE-030`）：

- 影响：`fromFtq.toPrefetch.ready` 被 `!softPrefetchValid` 拉低，但预取流水仍以
  “软件预取 + FTQ req(1) + FTQ twoPrefetchCase”的合并请求 fire，导致未被接受的
  FTQ 请求的第二块被预取（跨页时用软件预取的页标签），并触发 `ICacheMetaArray`
  的 interleaved-bank 断言条件。
- 证据：`test_pending_soft_prefetch_does_not_process_an_unaccepted_ftq_issue`
  （strict xfail）中 `ready` 连续 24 拍为 0，仍观测到 req1 block `0x100` 的 acquire。
- 上游：issue #6674（open）报告同一断言；PR #6691（open，尚未合并）明确删除这段
  ICache-top 选择逻辑。`origin/kunminghu-v3` 最新 `6705b6368` 未包含修复。

**WayLookup 在 flush 同拍取消写时仍锁存异常**（`ICacheWayLookup`，`WAYLOOKUP-020`，模块级潜在）：

- 现象：`exceptionEntry_valid` 的置位项是 `write_0_fire & |itlbException_value`，没有被
  `io_flush` 门控；同一拍的 flush 却把读写指针清零。于是“被 flush 取消的写”仍把异常
  指针留在旧 `writePtr` 上。
- 影响：flush 后队列为空，但 `write.ready = free & ~exceptionEntry_valid` 恒为 0，
  空队列拒绝所有后续写入，预取管道随之停摆。实测另一次完整 `flush` 可清除该标志、
  写口恢复；stage-3 flush 只有在它算出的被丢弃指针恰好等于旧指针时才清除，空队列时
  不会。旧指针本身不会把异常载荷带到后来的条目上——它命名的槽在被读出之前一定会被
  新写入覆盖——所以可观测的损害是停摆，不是错误异常。strict xfail 用例
  `test_flush_in_the_write_cycle_discards_the_entry_and_its_exception` 在
  `rtl_write_ready() == 0` 处失败。
- 可达性：整块 ICache 中不可达。`ICachePrefetchPipe.io_wayLookupWrite_0_valid_0`
  含 `~s1_flush`，而 `s1_flush = io_flush | ...`，redirect flush 同拍预取管道不会
  给出写有效。这是子模块接口契约层面的潜在缺陷，不影响本 ICache 集成。
- 模型：已按规范修正（被 flush 或 stage-3 drop 取消的写不再锁存异常），RTL 行为由
  strict XFAIL 记录。

## 完成审计

| 检查项 | 证据 |
|---|---|
| 11 个 DUT 全部有功能点/模型/用例 | `verification_plan.json` **142** 个功能点；`results/xreactor-audit-full-4/feature-points.json` 每个功能点都有 tests 列表 |
| 功能点全部有判定 | **139 PASS + 3 XFAIL，0 NOT_RUN**（三个 XFAIL 都是具体 RTL 行为/缺陷） |
| 覆盖率缺口有解释或补全 | 各 DUT 的闭环文档 + `docs/sram-dut-coverage-limitation.md` + `docs/icache-coverage-closure.md`：10 个子模块可执行语句全部 100%（SRAM 四个 DUT 仅 4 条零宽直连），整块 ICache 518 条缺口逐行对账（504/2/1 由字节相同子模块 DUT 覆盖、8 条预留 MSHR、3 条死代码） |
| 串行全量通过 | `results/xreactor-audit-full-3`：**290 passed + 3 xfailed**，`coverage_complete=true` |
| 并行全量通过 | `results/xreactor-audit-full-4`：**290 passed + 3 xfailed**，`coverage_complete=true` |
| 无 RTL 修改 | `git -C XiangShan status --short` 为空，`git diff --stat` 为空，HEAD=`893e1580b` |
| 无分母剔除 | `tools/coverage_gaps.py` 读取全部 57 个 RTL 源的原始 `coverage.dat`，仅排除 picker 包装（全仓库统一口径） |
| 无 skip | 全仓库无 `pytest.mark.skip` / `skipif` / `pytest.skip` |

## 复现

```bash
cd /home/xyl/kmh-v3-test/icache-verify-kunminghu-v3
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 1 --output results/xreactor-full-32 -- tests
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 4 --output results/xreactor-full-33 -- tests
```


## 第三、四次闭环（最终数字）

| 指标 | 本轮之前 | 最终 |
|---|---|---|
| 功能点 | 118 | **125**（+ DATABANK-006 / METABANK-008 / METAARRAY-009 / DATAARRAY-009 / METABANK-009 / METAARRAY-010 / ICACHE-029） |
| 子模块可执行语句 | 99.31%–99.71%（5 个模块有缺口） | **100%**（MissUnit/Mshr/Replacer/WayLookup/MainPipe/PrefetchPipe） |
| SRAM 四个 DUT | 63.74%–96.32% | **6518/6522 = 99.94%**（4 条零宽 array 直连，结构不可达） |
| 整块 ICache | 95.67% | 95.67%（518 条缺口从“待补”变为“逐行对账完成”） |
| 用例 | 172 passed + 1 xfailed | **200 passed + 1 xfailed** |

本轮倒推出的真实缺失情形（不是“行点归因”）：

1. 四个 SRAM DUT 的 MBIST 端口从未驱动 —— 补 BIST 功能点与用例；
2. WayLookup 环尾 slot 31 的 refill 与写同拍更新 —— 补“双写填满、释放 2 槽、单写+refill”
   的精确时序用例；
3. MainPipe 请求 1 的 bank 1/5/6 从未真正置 corrupt —— 补全行逐 bank 奇校验用例；
4. PrefetchPipe 的 meta 校验位恒 0、第二读端口未取到 1 —— 补跨行 metaCodes 用例；
5. PrefetchPipe 的 EnterS2→Idle —— 补“s2 被 miss 反压时第二个请求进入 EnterS2”用例。

随后按 line/branch/toggle 三类原生覆盖点复核（`docs/coverage-line-toggle-branch.md`），
新增 15 类情形与 3 个功能点（全 set×全 way valid、24 种 PLRU touch 顺序、Overlap2/
GPF/AF/后端/PMP、第二行/第二请求 denied/corrupt/RVC shift、异常条目读出、三端口
软预取），整块 branch 缺口归因为 530 条单模块覆盖 + 434 条构造性不可达 + 3 条开放。

错误复核结论见 `docs/error-review.md`。


## line / branch / toggle 三类覆盖（新增）

此前的“语句覆盖”来自 LCOV `DA`，混合了基本块与分支臂，不能表达翻转覆盖。新增的
`docs/coverage-line-toggle-branch.md` 直接读取 Verilator 原生 `coverage.dat` 的
`line` / `branch` / `toggle` 点（不剔除 DUT 源、存储宏或 payload 位），结论：

| DUT | line | branch | toggle |
|---|---|---|---|
| WayLookup | 100% | 83.79%（129 条优先级 mux 死臂） | 33.86%（payload 为主） |
| Replacer | 100% | 93.73%（257 条死臂） | **99.69%** |
| Mshr | 100% | 87.50%（1 条 initial-block） | 18.17%（payload 为主） |
| MissUnit | 100% | 94.63%（16 条 initial-block） | 23.33%（payload 为主） |
| MainPipe | 100% | **99.36%**（余 1 条 initial-block） | 56.12% |
| PrefetchPipe | 100% | **98.59%**（余 1 条 initial-block + 1 条 PMP 开放项） | 30.27% |
| DataBank | 100% | 95.65%（2 条 initial-block） | 63.82% |
| MetaBank | 100% | 97.37% | 84.91% |
| MetaArray | 100% | 98.01% | 79.46% |
| DataArray | 100% | 96.41%（12 条 initial-block） | 53.39% |
| **ICache（整块）** | 788/854 = 92.27% | 5521/6488 = 85.10% | 90845/140398 = 64.71% |

整块 ICache 的 967 条 branch 缺口逐点对账为：**530 条由字节相同的单模块 DUT 覆盖、
434 条构造性不可达、3 条开放**（CtrlUnit 注入 FSM 的保持/背压臂）。toggle 的 49,553
条缺口为 14,136 条单模块覆盖、236 条结构不可达、35,181 条开放；开放项约 99% 是
payload/存储位（payload 31,977、其他 2,745、存储 8），control 位 451 条，已在分析文档中列出下一步清单。

本轮据此新增 15 类情形（MetaBank/MetaArray 全 set×全 way valid 位、Replacer 24 种
touch 顺序、MainPipe 的第二行/第二请求 denied/corrupt/RVC shift、PrefetchPipe 的
Overlap2/GPF/AF/后端/PMP/第二行 refill、WayLookup 异常条目读出、ICache 三端口软预取），
并修正两条参考模型/检查器错误（PMP 属于 s2、corrupt 回填数据为 don't-care）。


## 受约束随机战役（toggle 补强）

在 line/branch/toggle 分析之后，对合法输入空间使用固定种子的受约束随机 + 独立参考模型
（随机数据/地址，不随机期望），子模块 toggle 合计从 **85,135/150,192 = 56.68%** 提升到
**144,111/150,192 = 95.95%**：

| DUT | 随机前 | 随机后 |
|---|---|---|
| WayLookup | 33.9% | 98.7% |
| Mshr | 18.2% | 97.9% |
| MainPipe | 56.1% | 96.6% |
| PrefetchPipe | 30.3% | 95.1% |
| MissUnit | 23.3% | 96.3% |
| DataArray | 53.4% | 95.0% |
| DataBank | 63.8% | 95.6% |
| MetaBank | 84.9% | 95.0% |
| MetaArray | 79.5% | 96.4% |

随机流同时暴露并修正了 4 处模型假设（Svpbmt 编码、48 位物理地址、未读 bank 掩蔽、
PMP 流水级），详见 `docs/coverage-line-toggle-branch.md` §9。剩余未覆盖是 DFT 控制总线、
`initial` 块 reset-else、优先级 mux 死臂、取指 MSHR 2/3 预留容量和父模块独有 mux 输入，
逐条结构性证据见同文档 §9.3。


## 第五次闭环：逐信号复核后的功能点补全

对 line/branch/toggle 的残余控制信号逐条查 RTL/Scala 后，确认其中 **8 类是功能点缺口、
不是结构不可达**，已补：

| 新增/扩充功能点 | 语义 |
|---|---|
| `ICACHE-MAINPIPE-013` | BPU s2/s3 重定向按 FTQ 指针杀掉在/晚于目标的取指（含 flag 回绕扫描） |
| `ICACHE-MAINPIPE-014` | satp 冲刷标签、第二取指 taken、后端异常标志/代码送到 IFU |
| `ICACHE-PREFETCHPIPE-012` | BPU 重定向杀投机预取（s0/s1、ITLB 流水同冲、软件预取豁免） |
| `ICACHE-PREFETCHPIPE-013` | corrupt 回填不算命中、不改 stage-1 元数据；其它行的回填也不改 |
| `ICACHE-PREFETCHPIPE-014` | stage-2 到达的回填直接满足请求，不再发 miss |
| `ICACHE-WAYLOOKUP-014` | corrupt 回填不改写已排队条目 |
| `ICACHE-WAYLOOKUP-015` | 真实双取指一次消费两个队列项，读指针 +2 |
| 扩充 005/006/009/002/003/004/005/009 | stage-3 指针、异常槽位置/第二槽异常码、最大取指 mask、逐槽重复检测、第二请求双行低 bank、fence.i 后复用 |

同时修正了随机生成器"从不产生跨行取指"的缺陷（`start` 只取到 30，而跨行要求
`start & 0x20`），并把非跨行取指的第二行元数据按 don't-care 处理（RTL 会保留上一笔
寄存器内容，主流水不消费）。第五轮结束时子模块 toggle 为
**144,471/150,192 = 96.19%**，control 类未翻转 **125 条**（第六轮进一步把它们降到 61 条，
见下一节）。

第五轮结束时的运行：串行 `results/xreactor-full-24`、并行
`results/xreactor-full-25` 均 **256 passed + 1 xfailed**，132 个功能点
**131 PASS + 1 XFAIL**（第六轮结束时的数字；第七轮见下一节）。


## 第六轮迭代：复位语义、反压与指针边界

继续"缺口 → 功能点 → 语义"的迭代，本轮新增 4 个复位功能点
（`DATABANK-007`/`METABANK-010`/`METAARRAY-011`/`DATAARRAY-010`），并把上一轮
3 个开放项全部闭合：

- WayLookup：写指针回绕后的异常指针 flag（0→1 与 1→0）、stage-3 重定向丢弃异常条目后
  释放写停顿、FTQ 指针 flag；
- PrefetchPipe：单次跨行请求发出两条 miss、stage-2 回填只抑制对应线、端口 1 命中→缺失清零；
- MainPipe：miss 反压在请求出现前拉低（请求被保持）、IFU 反压、ECC 报告单拍清除。

同时修正了 3 处项目验证代码/用例缺陷（2 处 agent 握手与观察逻辑、1 处用例激励生成器；
未修改 xreactor/picker），
详见 `docs/coverage-line-toggle-branch.md` §12。

最终：子模块 toggle **144,604/150,192 = 96.28%**，control 未翻转 61 条（56 条结构不可达、
5 条 liveness 采样开放项）；串行 `results/xreactor-full-28`、并行 `results/xreactor-full-29`
均 **278 passed + 1 xfailed**，136 个功能点 **135 PASS + 1 XFAIL**（第六轮结束时的数字）。


## 第七轮迭代：软预取与未接受 FTQ 请求的合并（新 RTL 缺陷）

按上游 issue 线索复核 `prefetch.i` 路径时，发现第二个真实 RTL 缺陷：`ICacheImp` 用
`!softPrefetchValid` 拉低 `fromFtq.toPrefetch.ready`，但仍把软件预取合并进预取流水，
导致未被接受的 FTQ 请求的第二块被预取（跨页时还使用软件预取的页标签），并触发
`ICacheMetaArray` 的 interleaved-bank 断言条件。

- 复现：`results/xreactor-ic-ic30-2`，`ready` 连续 24 拍为 0，却出现 req1 block 0x100 的 acquire；
- 上游：issue #6674（open）、PR #6691（open，明确“removes the ICache-top softprefetch
  selection”）；`origin/kunminghu-v3` 最新 `6705b6368` 未包含该修复；
- 登记：`ICACHE-ICACHE-030`，strict XFAIL。

最终：串行 `results/xreactor-full-30`、并行 `results/xreactor-full-31` 均
**278 passed + 2 xfailed**，137 个功能点 **135 PASS + 2 XFAIL**。


## 关于"为什么没早点验出来"（验证自身的假阴性复盘）

第二个 RTL 缺陷（ICACHE-030，对应上游 issue #6674）此前漏检有两个原因，均属验证方：

1. **功能点组合缺口**：软预取与 FTQ 预取各自都有用例，但从未在同一拍同时出现。
2. **harness 盲区**：`soft_prefetch()` 为容忍提示自身的那条 acquire 打开了
   `allow_unexpected`，却从不检查窗口内是否只有被提示的块。即使有组合用例，多出来的
   acquire 也会被静默放过。

已修正：`soft_prefetch()` 现在记录并强制"窗口内只能有被提示的块"，新增
`test_soft_prefetch_fetches_only_the_hinted_block`；并新增 `ICACHE-ICACHE-030` 的
strict XFAIL 复现。修完后整块 ICache 用例数为 39（+1），全量 279 passed + 2 xfailed。


## 第八轮迭代：按经验文档逐条复核现有用例

这一轮不是加功能，而是拿 `docs/verification-lessons.md` 的检查项把已有 290 个用例
重新过一遍。凡是“检查被放宽”“组合从未同拍”“模型算出的字段没人比”“随机种子到不了的
取值”，都当作缺陷处理；修完后串行 `results/xreactor-audit-full-3`、并行
`results/xreactor-audit-full-4` 均 **290 passed + 3 xfailed**，142 个功能点
**139 PASS + 3 XFAIL**，`coverage_complete=true`。

### 1. 全局静音：`check=False` 全部收窄为按字段放行

整块 ICache 里原有 6 处 `check=False`：ECC 注入后读污染行、跨行全 miss 的 RVC map
拼接、以及两处 stale-`vSetIdx` 对照。前两类改成 `send(..., undefined=("data",))` /
`undefined=("maybe_rvc_map",)`：只把体系结构上确实未定义的那个字段清零，其余字段
（行数、range、异常、acquire 数量、miss 请求）照常比较；后两处直接恢复完整比较。
现在整块 ICache 没有一处 `check=False`。

PrefetchPipe 里剩下的 5 处 `check=False` 保留，因为它们是“在模型预测窗口之外手工
插入 refill / 反压”的中途序列，模型期望本来就不可套用；每处都显式断言了它要验的
字段（waymask、RVC map、miss 列表），不是整段静音。差别写在这里，避免下次复核时
再把两类混为一谈。

### 2. 组合覆盖：找出六处“从未同拍”，其中一处是真缺陷

- **MetaBank / MetaArray 的 `flushAll` × 写/读**：此前 `flushAll` 永远单独出现。
  新增 `METABANK-011`、`METAARRAY-012`：RTL 中 `flushAll` 优先，同拍写被丢弃；
  读口在 `flushAll` 期间 `ready=0`。第一版“flush 同拍读”用例其实无效——`read()`
  会等 `ready`，等到 flush 撤销后才读，等于什么都没测；改为直接断言 `read_ready()==0`
  后才是真的同拍检查。
- **Replacer 双端口**：replacer 有两条取指口，但所有用例只驱动一条。新增
  `REPLACER-003/004` 三个用例（双口同拍、每口两请求、双口 + victim 同拍），全部通过。
- **Mshr 的 fence.i × completion**：新增 `MSHR-006` 用例，确认完成优先于 flush：
  entry 立即释放而不是 drain；同时验证碰撞后内部 sticky fencei 会被下一次分配清除，
  否则 MSHR 会永久静音。
- **DataBank / DataArray 的“读响应拍写”**：SRAM 宏寄存读地址、下一拍组合输出；
  在响应拍接受写只会改变再下一拍的地址，不会污染已接受的读。两个 DUT 各补一个用例
  （`DATABANK-005`、`DATAARRAY-011`），验证读回的是旧字、写随后生效。
- **MainPipe 的 miss bubble**：`perf.pendingMiss` 在 miss 口被反压的每一拍都必须为高；
  在 `miss_stall_cycles` 分支里逐拍断言，并新增 `MAINPIPE-015` 用例。
- **WayLookup 的 flush × 写**：新增 `WAYLOOKUP-020`，直接发现第 3 个 XFAIL（见上节）。

### 3. 检查器过严：无效 way 的载荷是 don't-care

补 `flushAll` 用例时，MetaBank/MetaArray 的 `check_read` 把无效 way 的 tag 存储也比了。
tag SRAM 和 validArray 是两套存储，flush 只清 valid，旧 tag 自然留在原地；这既不影
响命中（命中要求 valid=1），也不是设计承诺。于是把比较规则改成“valid 永远比，载荷只在
valid=1 时比”，并让 `read()` 的提前退出复用同一规则（否则每次读到无效 way 都要空转
256 拍）。这是“检查器过严”的典型：过严不会放过 bug，但会把真实信号淹没在假告警里。

### 4. 模型死角：没人驱动的参数就是没人验的承诺

`MissUnitModel.complete()` 原来有 `fencei_now` / `flush_now` 两个参数，但
`MissUnitAgent.complete()` 从没把它们驱动到 DUT，所有用例也都没用过。尝试补“响应拍
fence.i 只挡写、不挡响应”的用例时发现：本 harness 的电平要提前一拍提交，而同一电平
又会在该拍置起 MSHR 的寄存 fencei 标志、把响应本身压掉，所以“响应仍发布但写被实时门控”
这一拍在本环境里构造不出来。与其留一个永远为 0 的开关，不如删掉参数并在模型处写清原因；
已登记的“fence.i 先于完成 → 响应抑制且不写阵列”由既有 `MISSUNIT-009` 用例覆盖。

### 5. 随机到达性：固定种子到不了的取值要显式扫

复算生成器分布发现：DataBank 的固定种子只踩到 15 个非空 waymask 中的 13 个，
DataArray 只踩到 14 个。随机数据保留，waymask 改为确定性地遍历 1..15——随机负责
激励多样性，不负责“碰运气覆盖边界”。其余生成器的跨行/非跨行、组索引、页标签高位
都确认可达。

### 6. 按拍计数与握手可见性

逐个核对 agent 里的计数器：refill beat 流每拍推进一拍，而本 DUT 的 D 通道没有
ready（miss unit 每拍消费一个 beat），因此不会丢 beat；`fetch_count`、`edges`、
`waited` 都只用于日志/超时，不参与判定。响应、miss 请求、way 更新都以握手沿为事件，
没有“电平持续几拍就记几次”的计数器。

### 7. 复核后仍然保留的判断

- `perf.hits` 只比较 request 0 的那一位：第二位是推测的下一行原始查找，不与本次取指
  的体系结构结果绑定。
- PrefetchPipe 的 5 处 `check=False` 保留（理由见 §1）。
- `pendingMiss` 不在响应拍比较：它是 s1 级电平（`s1_valid && !s1_fetchFinish`），
  在 miss 等待期间持续为高，响应拍已回 0；只在“miss 口被反压”的无歧义窗口断言。
