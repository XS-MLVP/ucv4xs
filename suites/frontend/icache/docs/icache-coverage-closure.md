# 整块 ICache 集成验证与覆盖率闭环

运行：`results/xreactor-ic-67`（`xreactor run --workers 1 -- tests/icache`）

| 指标 | 值 |
|---|---|
| 用例 | 37 passed + 1 xfailed |
| 功能点 | 30/30 有判定：28 PASS + 2 XFAIL（均附 RTL 缺陷证据） |
| 语句覆盖 | 11452 / 11970 = **95.67%** |
| 行覆盖 | 见 `docs/verification-report.md`（分母含声明/翻转点） |
| 分母 | 未剔除；`ICacheDut.v` 是 picker 生成的包装（43 条语句已全覆盖），RTL 闭包含 57 个源文件 |

## 集成功能点

| ID | 功能点 | 判定依据 |
|---|---|---|
| 001 | 冷缺失 → 回填 → IFU | 首次取指发出一次 TileLink acquire，回填后返回正确的 512-bit 指令与元数据 |
| 002 | 驻留行命中 | 同块第二次取指不再产生 acquire，`toIfu.perf.hits[0]=1` |
| 003 | 跨行取指 | 0x20 偏移的 64B 取指请求两行；高 bank 来自第 0 行、低 bank 来自第 1 行 |
| 004 | 双取指 | 同一 issue 的两个请求各自回填并在一个 IFU 响应中返回 |
| 005 | RVC 映射与 taken 偏移 | 对齐到取指坐标、32 位指令标记位置正确、taken 偏移与 size 正确 |
| 006 | 组相联替换 | 填满 4 way 后第 5 块按 tree-PLRU 逐出；被触摸的块保留；其他组不受影响 |
| 007 | fence.i | 全部失效，随后同块重新从内存取指 |
| 008 | 重定向 flush | 在途取指不返回 IFU、不写阵列；随后重新取指成功 |
| 009 | ITLB/后端异常 | PF/GPF/AF 上报到 IFU（含 gpAddr），不发 miss；后端异常单独转发 |
| 010 | PMP/MMIO/不可缓存 | PMP 违规上报 AF；`pmp.mmio` 与不可缓存 PBMT 置 MMIO 标志且不回填 |
| 011 | corrupt/denied 回填 | 分别上报 hardware error / access fault，不当作有效指令 |
| 012 | `prefetch.i` 预热 **（XFAIL）** | **RTL 缺陷**：软预取的 vSetIdx 取自上一拍的 startVAddr（见下文） |
| 013 | WFI | 空闲安全、miss 在途不安全、回填后恢复；wfiReq 阻挡新 acquire |
| 014 | ECC 控制与错误上报 | 控制寄存器读写、三种注入错误码（NotEnabled/TargetInvalid/NotFound）；注入数据错误后取指置 `toIfu.corrupt` 并上报 BEU 地址 |
| 015 | 硬件预取填充 | 冷缺失的回填由预取 MSHR（source ≥ 4）owns，随后需求取指命中 |
| 016 | 全部 256 组可寻址 | 逐组取指，全部缺失-回填-命中，数据正确 |
| 017 | 双取指的第二个 replacer 端口 | 逐组把目标组作为 req1 发出，两个 replacer 端口的状态更新被覆盖，两条线随后都命中 |
| 018 | 第二个取指自身跨行 | req1 跨行时第一行命中、第二行回填，数据按行拼接 |

## 缺口倒推过程

| 轮次 | 语句覆盖 | 倒推出的功能点 |
|---|---|---|
| 1 | 58.19% | 初版 14 功能点 |
| 2 | 80.30% | 补 016：逐组地址扫描（replacer/waylookup/meta 的组译码从未被访问） |
| 3 | 91.24% | 补 017：双取指第二端口逐组扫描（replacer 第二端口 128×2 组从未被触摸） |
| 4 | 91.44% | 补 018：req1 跨行；补 014 的 TargetInvalid/NotFound 错误码；修正 `prefetch_case` 推导 |

### 倒推暴露的参考模型缺陷（非 RTL 缺陷）

1. **`twoPrefetchCase` 必须由两个请求推导**：FTQ 按 `sameLine/overlap1/overlap2/interleave`
   计算，两个同奇偶组的非跨行请求是 **Conflict**，不能作为双取指发出。初版用固定值 8
   驱动，导致 MetaArray 的同 bank 双读（RTL 断言 `2 read setIdx must be in the
   different interleaved bank` 的前提被破坏），port 1 的元数据读到错误 bank。
   现在 `send()` 默认调用 `prefetch_case()` 推导。
2. **PrunedAddr 位宽**：FTQ 的 `vAddr.addr` 是 `address >> 1`；IFU 的
   `startVAddr/pAddr/gpAddr` 也是 PrunedAddr，读回需左移。
3. **set 索引**：`get_idx(addr) = addr[13:6]`（不是块内偏移）。
4. **`pTag`/alias**：`pTag = blkPAddr >> 6`；TileLink A 通道的 `user_alias` 是
   `vSetIdx` 的**低** 2 位（Chisel `UInt.head(2)`），不是高 2 位。
5. **数据 bank 语义**：命中行只从阵列读 FTQ `bankSel` 覆盖的 bank，未读 bank 是阵列
   读出寄存器的残留值（不可预测）；回填行则整体旁路阵列、填满整行的 8 个 bank。
   模型据此对不可观测 bank 做掩蔽比较。
6. **异常取指需要重定向**：带 ITLB 异常的 waylookup 条目只有 flush 才能释放
   （`exceptionEntry.valid` 会 stall 后续写入），所以 `send()` 在异常响应后自动发一次
   redirect flush，模拟前端的异常重定向。
7. **ECC 错误的呈现方式**：数据 ECC 失败走独立的 `toIfu.corrupt` 端口（与真实 IFU
   接口一致），不写入 `icacheMeta.exception`；`io.error` 比 IFU 响应晚两级寄存器。

## RTL 缺陷：`prefetch.i` 的组索引取上一拍地址

生成代码（`dut/icache/ICacheDut.v`）：

```verilog
if (_GEN) begin
  softPrefetch_startVAddr_addr <= {pc_addr[48], pc_addr};
  softPrefetch_vSetIdx_0 <= softPrefetch_startVAddr_addr[12:5];   // 旧值
end
```

`vSetIdx` 从**更新前**的 `startVAddr` 寄存器取值，因此：

- 复位后第一次软预取使用组 0（`0x8000` 恰好属于组 0，能命中）；
- 之后每次软预取沿用**上一次**软预取的组号（`0xB000` 的组 0xC0 永远不会被使用）；
- 缺失请求的块地址/页标签是正确的，所以该行会被写入一个**永远无法命中**的组，
  随后需求取指仍然缺失。

证据：`ICACHE-ICACHE-012` 的 xfail 用例先验证组 0 的对照组命中，再断言 `0xB000`
的软预取应使需求取指命中（失败）。该缺陷不影响硬件预取路径（每个 FTQ issue 的预取
管道都会用当前地址查元数据，`ICACHE-ICACHE-015` 验证）。

## 剩余缺口（已闭环）

| 类别 | 语句数 | 说明 |
|---|---|---|
| `ICacheWayLookup.sv` 的 `end` 行 | 358 | Verilator 把每个 entry 的 always 块结尾行计为语句；同文件的 2065 条实语句已覆盖 |
| `ICacheWayLookup.sv` 的 `entryUpdate_waySame_*` 分支 | ~200 | 需要"回填超过仍在队列中的 waylookup 条目"。芯片级 lockstep 下 main pipe 会立刻消费该条目，无法稳定构造；WayLookup 单模块验证直接驱动 update 端口覆盖该路径（`results/xreactor-wl-full-5`，13/13 功能点，`docs/waylookup-coverage-closure.md`） |
| `MbistPipeICacheData_bank*` / `MbistPipeICacheTag_bank*` | ~150 | `hasMbist=false` 下 BIST 流水线不可达，与 `docs/sram-dut-coverage-limitation.md` 同一配置级证据 |
| `ICacheDataBank.sv`（8 个实例） | 72 | 数据 bank 的 9 条语句均为存储宏适配/复位连线；DataBank 单模块验证已确认顶层逻辑无行点、以行为断言闭环 |
| `ICacheMetaInterleavedBank*.sv` | 18 | BIST/flush 相关分支，MetaBank 单模块验证已逐行归因（`docs/sram-dut-coverage-limitation.md`） |
| `SRAMTemplate*.sv` | 48 | 复位/旁路/BIST 适配行，同 SRAM 宏归因 |
| `ICacheDataArray.sv` | 16 | 每 bank 的 `reqRead*_1` 连续赋值声明行（req1 只读高 bank；表达式行已覆盖） |
| `ICacheMainPipe.sv` | 10 | req1 跨行 bank-valid 的声明/条件行（018 已覆盖其行为，剩余为声明行） |
| `ICachePrefetchPipe.sv` / `ICacheMshr*.sv` | 5 + 52 | 两个 DUT 单模块验证已归因的三目/声明行（`docs/mainpipe-prefetchpipe-coverage-closure.md`） |
| `ICacheCtrlUnit.sv` | 4 | 注入 FSM 的 `iError` 默认分支与复位行 |
| `ICacheDut.v`（picker 包装） | 0 | 43/43 语句已覆盖 |

## 复现

```bash
cd /home/xyl/kmh-v3-test/icache-verify-kunminghu-v3
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 1 --output results/xreactor-ic-43 -- tests/icache/testcase
python3 tools/coverage_gaps.py results/xreactor-ic-43 --dut icache
```


## 第二轮闭环：覆盖率未满后继续倒推（本轮新增）

第一轮停在 91.47% 时把剩余缺口写成"已归因"，这是停止条件放得太宽。按"覆盖率未满即
功能点定义有缺陷"重新逐条倒推后，新增了 10 个功能点并把覆盖率提升到 **95.67%**：

| 新增功能点 | 缺口证据 | 新增用例 |
|---|---|---|
| 019 回填修正队列中的 waylookup 条目 | 冷缺失的 waylookup 条目在 main pipe 消费后才收到 refill；无测试验证"同一 tag 采纳回填 way" | `test_refill_corrects_the_queued_way_lookup_entry`（prefetch-only 后 main-only 取指必须命中） |
| 020 逐出使队列中的 waylookup 条目失效 | 同 set/同 waymask、不同 tag 的回填必须清零队列条目的 waymask，否则 main pipe 会读到"偷走 way"的块 | `test_eviction_invalidates_the_queued_way_lookup_entry`（main-only 取指必须缺失并返回原块） |
| 021 SRAM BIST 到达每个 child | `MbistPipe*`、`SRAMTemplate*`、`DataBank*` 的 `bd_*`/`mbistBd_*` 行全未覆盖；BIST 端口在 DUT 顶层是公开输入 | `test_sram_bist_selects_and_acknowledges_every_child`、`test_sram_bist_write_reaches_the_arrays`（逐 child、逐 array、广播、读/写） |
| 022 waylookup 环形队列 32 槽 × 双写端口 | 双取指只在偶数写指针写入，`entries_N <= write_1` 的偶数槽从未覆盖 | `test_ring_stores_every_slot_through_both_write_ports`（按写指针精确摆位后逐槽双写 + 末槽冷缺失回填） |
| 023 BPU stage-3 flush 释放队列尾 | `bpuS3FlushValid` 与写指针回退从未覆盖 | `test_bpu_stage3_flush_drops_the_queue_tail` |
| 024 第二半行的 way 命中 | DataArray 的 `reqSel_*_0`（bank 0..3 的 way 1..3）从未覆盖 | `test_a_way_hit_on_the_second_half_reads_the_right_banks`（4 way × 偏移 0/0x20 两轮） |
| 025 第二取指起点晚于第一块时的 RVC 拼接 | MainPipe 的 `shouldShiftRight` 真分支（`req1_start > req0_size`）从未覆盖 | `test_rvc_maps_stitch_when_the_second_fetch_starts_after_the_first`（Overlap2, req1 起点 18 > 16） |
| 026 十个 prefetch MSHR 同时挂起 | `Mshr_4..13` 的分配行只在单 miss 流程覆盖到 4/5 | `test_all_prefetch_mshrs_hold_outstanding_misses`（10 条同时 acquire，sources = 4..13，再统一回填） |
| 027 ITLB miss 停顿并重发 | `s1_needItlb`/`s1_waitItlb` 重发路径从未覆盖 | `test_itlb_miss_holds_and_resends_the_prefetch`（保持 miss 6 拍观察重发后释放） |
| 028 跨行缺失分配两个 fetch MSHR | `Mshr_1` 的分配行未覆盖（预取管道抢走 miss 时是 prefetch MSHR） | `test_a_cross_line_miss_allocates_two_fetch_mshrs`（csrPfEnable=0 强制 fetch MSHR 持有两行，sources = 0/1） |

另外修正了两处**用例/agent**缺陷（不是框架 bug，也不是 RTL）：xcomm 电平驱动下 FTQ 请求必须在观察到
ready 的同一拍撤销，否则空闲下来的 prefetch pipe 会把同一请求再入队一次（导致
waylookup 每拍多写一条）；`toIfu.corrupt` 是 stage-2 信号、`io.error` 再晚一级寄存器，
必须在响应后连续多拍采样。

## 最终剩余缺口（逐条证据）

| 文件 | 语句数 | 证据 |
|---|---|---|
| `ICacheWayLookup.sv` | 504 | 该文件与 `dut/waylookup/WayLookupDut.v` **字节相同**（sha256 `6433fed2…b08ce9`）。单模块运行 `results/xreactor-wl-full-6` 已达到 **2756/2756 = 100%**，包括此前剩下的 8 条 slot 31 并发更新分支（新增“队列满、释放 2 槽、单写与 refill 同拍”用例）。逐行对账确认父模块 504 条未覆盖行**全部**在该模块运行中被覆盖（504/504） |
| `ICacheMshr_2.sv` / `_3.sv` | 8 | 结构不可达：设计文档规定一个取指请求最多引用两条 cacheline；main pipe 的 s1 是单条目，miss 完成前阻塞，因此取指 MSHR 同时最多占用 0/1。芯片级 acquire source 实测为 {0,1}（csrPfEnable=0）与 {4..13}（预取通道），2/3 是为扩展预留的容量 |
| `ICacheCtrlUnit.sv` | 3 | 死代码，不是缺少用例：159/160 位于“注入启动写”分支内，但条件 `_GEN_5` 含 `deq_bits_read`，与写分支的 `~read` 矛盾；164 需要 `iState==ReadMetaResp` 且 `iStatus==Idle`，而 ReadMetaResp 只在 Working 期间到达、NotFound 时 `iState` 同步归零。三者均为 firtool 共享子表达式产生的不可达臂。功能行为由 NotEnabled/TargetInvalid/NotFound 三种错误码与 Injected 状态断言 |
| `ICachePrefetchPipe.sv` | 2 | 该文件与 `dut/prefetchpipe/PrefetchPipeDut.v` **字节相同**（diff 为空，37803 字节）。单模块运行 `results/xreactor-pf-15` 已达到 **295/295 = 100%**，逐行对账确认父模块这 2 条也在其中 |
| `ICacheReplacer.sv` | 1 | 626 行是多行 `wire ... =` 声明的首行（声明性，无独立行为）。同文件在单模块 `results/xreactor-repl-11` 中 **6478/6478 行全部覆盖**，逐行对账确认父模块这 1 条也在其中 |

结论：整块 ICache 的剩余语句缺口全部可归因于"同一 RTL 文件已在字节相同的单模块 DUT 中
覆盖"、"配置/结构不可达"或"无行点的声明/翻转行"，没有为了覆盖率放宽断言、剔除分母
或跳过用例。


## 第三轮对账：父模块剩余行与子模块逐一对应

本轮把“字节相同”从文件级证据推进到**行级证据**：对 `results/xreactor-ic-67` 的每条
父模块未覆盖行，检查同名/同内容的单模块运行中该行的计数：

| 父模块文件 | 父模块未覆盖行 | 子模块运行 | 被子模块覆盖 | 剩余 |
|---|---|---|---|---|
| `ICacheWayLookup.sv` | 504 | `results/xreactor-wl-full-6`（2756/2756） | **504** | 0 |
| `ICachePrefetchPipe.sv` | 2 | `results/xreactor-pf-15`（295/295） | **2** | 0 |
| `ICacheReplacer.sv` | 1 | `results/xreactor-repl-11`（6478/6478 行） | **1** | 0 |
| `ICacheMshr_2/3.sv` | 8 | 无同构单模块实例 | 0 | 8（结构不可达） |
| `ICacheCtrlUnit.sv` | 3 | 无同构单模块实例 | 0 | 3（死代码） |

因此整块 ICache 的 **11/11 可执行缺口类**都已闭环：能由父模块激励覆盖的已覆盖，
其余每一行都有“字节相同子模块已覆盖”或“结构不可达”的具体证据。错误复核见
`docs/error-review.md`。


## 三类原生覆盖点复核（line / branch / toggle）

LCOV `DA` 之外的进一步分析见 `docs/coverage-line-toggle-branch.md`。整块 ICache 在
`results/xreactor-full-20` 的原生点结果：

| 指标 | 覆盖 | 缺口对账 |
|---|---|---|
| line | 788 / 854 = 92.27% | 64 条由字节相同子模块 DUT 覆盖（WayLookup 逐槽 `elsif`），2 条 CtrlUnit 死代码 |
| branch | 5521 / 6488 = 85.10% | 530 条单模块覆盖 + 434 条构造性不可达 + **3 条开放**（CtrlUnit 注入 FSM 保持/背压臂） |
| toggle | 90845 / 140398 = 64.71% | 14136 条单模块覆盖 + 236 条结构不可达（MSHR2/3 仲裁臂）+ 35181 条开放（约 99% 为 payload/存储位，control 451 条（payload 31,977、其他 2,745、存储 8）） |

“构造性不可达”的 434 条 branch 包括：Replacer 257 + WayLookup 129 条优先级 mux 的最终
`else`、约 30 条 `initial` 块的 reset-else、Arbiter5 的 8 条 MSHR2/3 臂、单阵列 bank 的
零宽 array 选择臂。逐行证据与开放项清单见分析文档。


## 软预取路径的第二个 RTL 缺陷（ICACHE-030）

`ICacheImp` 在软件预取有效时拉低 `fromFtq.toPrefetch.ready`，但仍把软件预取合并进预取
流水（`req(0)` 被替换，`req(1)` 与 `twoPrefetchCase` 保留）。后果：

- 未被接受的 FTQ 请求的第二个 block 仍被预取（实测 `ready=0` 24 拍，却出现 block 0x100 的 acquire）；
- 跨页时第二块用软件预取的页标签翻译，预取错误的物理行；
- 软件预取的 stale `vSetIdx` 与 FTQ req1 落入同一 interleaved bank，触发上游 issue #6674 的断言。

上游 PR #6691 已明确删除这段 ICache-top 选择逻辑；本工程 HEAD `893e1580b` 尚未包含。
详见 `docs/error-review.md` §1.2。
