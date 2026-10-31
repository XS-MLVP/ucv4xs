# ICache 的 line / branch / toggle 覆盖率分析

此前的报告只看了 **LCOV `DA` 行覆盖**。这个数字并不等于 Verilator 的三种原生覆盖点：
`verilator_coverage --write-info` 只输出 `DA`，而 `DA` 同时混合了基本块点和分支臂点，
既无法表达翻转覆盖，也会把“某条分支臂没走”误当成“某一行没执行”。本文件改用
`coverage.dat` 的原生点重新统计：

| 指标 | Verilator 点类型 | 含义 |
|---|---|---|
| **line** | `t=line` | 一个可执行基本块是否执行过 |
| **branch** | `t=branch` | 每个 `cond_then` / `cond_else` / `case` 臂是否被选中 |
| **toggle** | `t=toggle` | 每个信号**每一位、每个方向**（0→1、1→0）是否发生过 |

口径：

- 数据来自 `results/xreactor-full-20`（串行全量，200 passed + 1 xfailed）的 11 个原生
  `coverage.dat`；同一源位置在多个层次实例中只要有一个命中即记为覆盖。
- 只排除 picker 生成的 `*_top` 测试台封装（与 `tools/coverage_gaps.py` 完全同一口径）。
  **没有剔除任何 DUT 源、存储宏或 payload 位**；不可达项单独列出而不是从分母拿掉。
- 分析工具：`tools/coverage_breakdown.py`（三类点）、`tools/coverage_ledger.py`
  （整块 ICache 缺口与字节相同子模块 DUT 的逐点对账）。

## 1. 总表

| DUT | line | branch | toggle | 未覆盖 toggle 中 control 位（扣除模块覆盖前） |
|---|---|---|---|---|
| ICacheWayLookup | 227/227 = 100% | 667/796 = 83.79% | 3515/10382 = 33.86% | 8 |
| ICacheReplacer | 515/515 = 100% | 3845/4102 = 93.73% | 3238/3248 = **99.69%** | **0** |
| ICacheMshr | 2/2 = 100% | 7/8 = 87.50% | 121/666 = 18.17% | 3 |
| ICacheMissUnit | 33/33 = 100% | 282/298 = 94.63% | 3912/16770 = 23.33% | 69 |
| ICacheMainPipe | 5/5 = 100% | 155/156 = **99.36%** | 7992/14240 = 56.12% | 103 |
| ICachePrefetchPipe | 3/3 = 100% | 140/142 = **98.59%** | 1742/5754 = 30.27% | 134 |
| ICacheDataBank | 7/7 = 100% | 44/46 = 95.65% | 4354/6822 = 63.82% | 3 |
| ICacheMetaBank | 10/10 = 100% | 296/304 = 97.37% | 10760/12672 = 84.91% | 8 |
| ICacheMetaArray | 19/19 = 100% | 590/602 = 98.01% | 21283/26786 = 79.46% | 16 |
| ICacheDataArray | 32/32 = 100% | 322/334 = 96.41% | 28218/52852 = 53.39% | 45 |
| **ICache（整块）** | 788/854 = 92.27% | 5521/6488 = 85.10% | 90845/140398 = 64.71% | 3301 |

读法要点：

- **line 几乎已满。** 10 个子模块原生 line 点全部 100%；整块的 66 条缺口里 64 条是
  WayLookup 的逐槽 `elsif` 行点，已被 sha256 字节相同的单模块 DUT 覆盖，剩余 2 条是
  CtrlUnit 的死臂（见 §3）。
- **branch 的缺口绝大多数是“不可达臂”，不是漏测。** 整块 967 条未覆盖中 530 条由
  单模块 DUT 覆盖，434 条是构造性不可达，只有 **3 条** 仍是开放项。
- **toggle 低是正常的，但必须分类看。** 49,553 条整块未覆盖中 14,136 条由单模块覆盖、
  236 条是结构不可达，剩余 35,181 条中约 **34,800 条是 payload/存储位**，control 位
  control 位为 451 条。也就是说，toggle 的缺口几乎全部是“某个地址/数据位没有翻转过”，
  不是控制语义没有验证。

## 2. line：为什么和之前的 95.67% 不一样

之前报告的“语句覆盖 11452/11970 = 95.67%”来自 LCOV `DA`，它由 `verilator_coverage
--write-info` 生成；该工具会把基本块点**和分支臂点**都折算成 `DA`，还会把跨行的
`wire ... =` 声明第一行计入。它是可用的保守指标，但不是 Verilator 原生的 line 覆盖率。

原生 line 点只有 854 个（整块）。其中 788 个执行过；未执行的 66 个是：

| 来源 | 条数 | 归因 |
|---|---|---|
| `ICacheWayLookup.sv` 逐槽 `elsif` 行点 | 64 | 与 `dut/waylookup/WayLookupDut.v` 字节相同；单模块运行 2756/2756 语句覆盖，逐行对账 64/64 命中 |
| `ICacheCtrlUnit.sv` 159 / 161 | 2 | 注入写分支中条件含 `deq_bits_read` 与写互斥，以及 `iState==ReadMetaResp` 与 `iStatus==Idle` 互斥，均为死代码 |

所以“可执行 line 点”在本配置下是 **100%**；那 95.67% 与 92.27% 的差别只是统计口径，
不是新增的行为缺口。

## 3. branch：967 条缺口的逐类证据

整块 ICache 的 967 条未覆盖 branch 点：

| 分类 | 条数 | 证据 |
|---|---|---|
| 由字节相同的单模块 DUT 覆盖 | 530 | WayLookup 254（逐槽 adopt/clear 的 port 副本）、Replacer 256（第二 touch 端口的 way[1] 臂）、MainPipe 6、PrefetchPipe 10、Mshr_2/3 各 2、MetaBank/MetaArray/Mbist 的 BIST 臂等 |
| 构造性不可达 | 434 | 见下表 |
| **开放项** | **3** | `ICacheCtrlUnit.sv` 184/204/209 |

### 3.1 构造性不可达的 434 条

| 类别 | 条数 | 结构性理由 |
|---|---|---|
| 优先级 mux 的最终 `else` | 257（Replacer）+ 129（WayLookup） | 外层 OR 已经保证至少一个 `valid` 为真；firtool 生成的最后一个 `else` 永远不可能被选中。WayLookup 的 128 条还受 `updated = pTagSame \| waySame` 约束，最终 `else` 与 `updated` 同时为真矛盾 |
| `initial` 块里的 `if (reset)` 的 `else` | 40 条（14 个 Mshr、FIFOReg、MissUnit、MetaBank×2、MainPipe、PrefetchPipe、DUT 包装、6 个 SRAMTemplate、10 个 MbistPipe、Queue1、array 模型等） | `initial` 在时刻 0 只执行一次，此时 reset 恒为 1；`else` 臂不可达 |
| 取指 MSHR 2/3 的仲裁臂 | 8（Arbiter5） | 一个取指 issue 最多引用两条 cacheline；main pipe 的 s1 在 miss 完成前阻塞，因此取指 MSHR 只会占用 0/1。`in_2`/`in_3` 的地址、vSetIdx 臂不可达。实测 fetch acquire source 恒为 {0,1}，prefetch 为 {4..13} |
| 单阵列 bank 的 array 选择 | 若干（MetaBank/MetaArray bank0） | `boreChildrenBd_bore.array` 宽度为 0（`signals.json` High=-1），`arrayReg` 恒 0，`arrayReg ? ...` 的 true 臂不可达 |

### 3.2 开放的 3 条

`ICacheCtrlUnit.sv` 的 184、204、209 是 ECC 注入 FSM 的保持/背压臂：

- 184 / 209：注入过程中“本拍没有 meta/data 写完成”的保持臂；
- 204：`io_metaRead_req_ready=0` 时的等待臂。

它们不是不可达，但当前 ICache 用例都在 SRAM 复位清扫完成后注入，且注入地址/waymask
都能在下一拍完成写，因此没有构造出“注入期间 meta ready 为低”的时序。它们被保留为
**开放项**，没有从分母剔除、也没有用“不可达”去解释。整块的 2 条 line 开放项
（159/161）与这 3 条同属该 FSM 的死代码/保持臂。

## 4. toggle：为什么只有 64.71%，哪些才是真缺口

toggle 是逐位、逐方向的。它低有三个完全不同的原因：

### 4.1 payload/存储位（约 34,800 条，占 open 的 99%）

- **宽数据/地址总线**：WayLookup 的 50 位 `gpAddr`、32 位 RVC map；MainPipe 的 512 位
  指令与 miss 数据；MissUnit 的 42 位块地址；DataArray 的 8×66 位 bank 数据。
  测试使用结构化地址（0x1xxx、0x8xxx）和固定数据模式，高位/中间位不会翻转。
- **每个实例一份副本**：MissUnit 的 14 个 MSHR 各自有一份 `io_req_bits_blkPAddr`；
  每个实例只看到自己的地址，要让每一位在每个实例上都翻转，需要给每个 MSHR 喂互补地址。
  这是 Verilator 层次化 toggle 的统计特性，不是 14 份不同的逻辑。
- **存储宏**：`array_*.sv` / `sram_array_*.sv` 的存储单元只有写入对应值才翻转；行为
  模型的上电随机值还会让某些位永远不变。它们已在表中单列（DataArray 124 位、
  MetaBank 40 位等），没有从分母拿掉。

### 4.2 control 位（451 条开放）

这是值得继续做的部分。按文件聚合：

| 文件 | control 未翻转 | 主要信号/原因 |
|---|---|---|
| `ICacheDut.v` | 160 | FTQ 属性（`hasSatpFlush`、`req_1_taken`、`bankSel_1[4:7]`）、BPU flush s2/s3、`itlb_req.fullva` 高位 |
| `ICachePrefetchPipe.sv` | 106 | `s2_mshrHits_valid`、BPU flush、`itlb_req.fullva` 高位 |
| `ICacheMainPipe.sv` | 62 | 同上的 FTQ 属性/BPU flush 副本 |
| `ICacheDataArray.sv` | 25 | 第二读槽 `lineSelOH[1]`、`bankSel_1[4:7]` |
| 14 个 `ICacheMshr*.sv` | 约 5×14 | `lookUps_1_resp_hit`（只用了 lookup 端口 0）、`flush`/`fencei`/`issue`/`acquire_ready` 的实例级翻转 |
| 其余 | 约 30 | SRAMTemplate 的 `io_w_req_ready` 1→0、BIST `selectedOH`/`doSpread` 的 1→0、MetaBank/MetaArray 的 validArray 残留位 |

这些是真实的“某类输入没有驱动过”，但大多不影响已有功能点的判定：例如 `req_1_taken`
只影响对齐计算中已经由 `ICACHE-MAINPIPE-009` 覆盖的 taken 偏移；`bankSel_1` 高位对应
跨行第二半行的 bank 掩蔽，主 pipe 侧已由 `ICACHE-DATAARRAY-008` 的
bank 矩阵覆盖。若要继续把 toggle 推到接近 100%，下一步应补：

1. FTQ 属性扫描（`hasSatpFlush`、`taken`、`bankSel_1` 全 8 位、`ftqIdx` 回卷）；
2. BPU s2/s3 flush 的四种 `(valid, flag)` 组合；
3. Mshr 的 lookup 端口 1 命中 + 每实例 `flush`/`fencei`；
4. DataArray 的双读槽/第二 half 的 `bankSel_1` 全位；
5. ITLB `fullva` 的高位地址（覆盖 50 位地址空间的高段）。

这些是下一步的明确工作项，不是本次“line 覆盖率闭环”的阻塞项。

### 4.3 结构不可达的 toggle（236 条）

全部是 `Arbiter5_MshrAcquireBundle.sv` 的 `in_2`/`in_3` 地址与 vSetIdx 位：取指 MSHR
2/3 在本配置下永不 valid，`in_2/in_3` 的 payload 永远为 0，不会翻转。

## 5. 本轮根据分析补的用例与效果

分析不是只出报表：下面这些是“toggle/branch 缺口 → 功能点/用例”的实际闭环。

| 新增用例 | 补的语义 | 效果 |
|---|---|---|
| `test_every_way_of_every_set_is_set_and_cleared`（MetaBank） | 128 set × 4 way 的 valid 位逐位置位，`flushAll` 逐位清零 | MetaBank toggle 9935→10760/12672，control 1230→8 |
| `test_every_way_of_every_set_is_set_and_cleared`（MetaArray） | 256 set × 4 way，两个 interleaved bank | MetaArray toggle 19444→21283/26786，control 1722→16 |
| `test_every_touch_order_drives_the_policy_state`（Replacer） | 4 way 的全部 24 种 touch 顺序，每步检查 victim | Replacer toggle 2918→3238/3248，control 330→0 |
| `test_denied_second_line_refill...`（MainPipe） | 请求 0 第二行的 denied 回填 | 覆盖 `s1_tlException_reg_1` 的 denied 臂 |
| `test_both_fetches_report_corruption`（MainPipe） | 两个取指都回填 corrupt | 覆盖两路 corrupt 聚合 |
| `test_corrupt_second_line_of_the_first_fetch...`（MainPipe） | 第一路第二行 ECC corrupt、第一行干净 | 覆盖 `firstCorruptPortInfo` 的“第二行”臂 |
| `test_denied_refill_of_the_second_fetch...`（MainPipe） | 请求 1 的 denied 回填 | 覆盖 `s1_tlException_reg_1` 的第二请求臂 |
| `test_second_fetch_refill_map_is_shifted...`（MainPipe） | 请求 1 起点晚于请求 0 的 block | 覆盖 `shouldShiftRight` 的真臂（1037） |
| `test_itlb_gpf_af...` / `test_backend_exception...` / `test_pmp...`（PrefetchPipe） | GPF/AF/后端异常/PMP | PrefetchPipe branch 126→140/142 |
| `test_overlap2_reads_the_two_lines...`（PrefetchPipe） | Overlap2 的两个 meta 读端口 | 覆盖 case[2] 的地址/waymask/metaCodes 臂 |
| `test_refill_updates_the_second_line_metadata...`（PrefetchPipe） | 跨行请求的第二行 refill | 覆盖 stage-1 第二 meta 槽的 refill 臂 |
| `test_exception_entry_is_read_out_with_its_payload`（WayLookup） | 异常条目作为下一槽被读出 | 覆盖 `toMainPipe_1` 的异常字段三目 |
| `test_soft_prefetch_is_accepted_from_each_ldu_port`（ICache） | 3 个 LDU 端口的 prefetch.i 优先级 mux | 覆盖 `pc_addr` 的 port1/port2 臂 |

汇总：

| 指标 | 分析前 | 分析后 |
|---|---|---|
| 功能点 | 122 | **125**（+METABANK-009、METAARRAY-010、ICACHE-029） |
| 用例 | 185 passed + 1 xfailed | **200 passed + 1 xfailed** |
| MainPipe branch | 152/156 | **155/156**（余 1 条 initial-block） |
| PrefetchPipe branch | 126/142 | **140/142**（余 1 条 initial-block + 1 条 PMP 开放项） |
| WayLookup branch | 665/796 | **667/796**（余 129 条优先级 mux 死臂） |
| Replacer toggle | 2918/3248 | **3238/3248**（余 10 条输入位结构不变量） |
| MetaBank control toggle | 1230 | **8** |
| MetaArray control toggle | 1722 | **16** |
| 整块 ICache branch | 5519/6488 | **5521/6488**（530 子模块 + 434 不可达 + 3 开放） |

## 6. 本轮修正的参考模型/检查器

两类，均不是 RTL 缺陷：

1. **PrefetchPipe 的 PMP 异常不进入 waylookup 条目。** RTL 在 s1 写条目时只携带
   `s1_itlbException_value`（ITLB/后端异常）；`pmp_resp_instr` 是 s2 的 miss 请求检查。
   原模型把 PMP 也写进条目，导致 PMP 用例期望值错误。模型已拆成
   `write_exception`（s1）与 `s2_exception`（PMP），PMP 仅抑制 miss。
2. **corrupt/denied 回填的数据是 don't-care。** corrupt 回填不会安装，main pipe 的
   `mshrValid` 为 0，返回的是阵列残留数据；异常才是结果。检查器现在在期望异常为
   HWE/AF 时跳过 `info.data` 比较（位置/异常/范围仍然比较）。

完整错误复核见 `docs/error-review.md`。

## 7. 结论

- **line**：所有子模块 100%；整块 66 条缺口 = 64 条字节相同子模块覆盖 + 2 条死代码。
- **branch**：整块 967 条 = 530 条模块覆盖 + 434 条构造性不可达 + **3 条开放**
  （CtrlUnit 注入 FSM 的保持/背压臂）。
- **toggle**：整块 49,553 条 = 14,136 模块覆盖 + 236 条结构不可达 + 35,181 条开放；
  开放项为 control 451 条、payload 31,977 条、其他 2,745 条、存储 8 条；约 99% 是 payload/存储位。
- 没有修改 RTL，没有剔除 DUT 源/存储宏/toggle 位，没有跳过用例；串行
  `results/xreactor-full-20` 与并行 `results/xreactor-full-21` 均为
  **200 passed + 1 xfailed**，125 个功能点 **124 PASS + 1 XFAIL**。


## 9. 受约束随机 + 参考模型：实测收益

§4.2 的 control/payload 缺口里，绝大多数是“合法输入空间太大，固定用例只走了一小片”。
对这些维度，**受约束随机（constrained-random）+ 独立参考模型**是最合适的补充：随机的是
输入数据/地址，不是期望值；每个响应仍由模型逐字段判定。全部随机用例使用固定种子
（可复现），随机源只使用 DUT 的公开端口，未读取内部信号。

### 9.1 做了什么

| DUT | 随机化对象 | 参考模型判定 |
|---|---|---|
| DataBank | 32 个随机 set/waymask + 64 位数据 + ECC 位 | 每 way 回读等于模型 |
| MetaBank | 128 个 set × 随机 waymask/36 位 tag/32 位 RVC/ECC | 每 set 四 way 等于模型 |
| MetaArray | 256 个 set × 随机 waymask/tag/RVC/ECC | 每 set 四 way 等于模型 |
| DataArray | 48 组随机 8×66 位 bank 数据 + 随机 waymask，逐 bank/way 读回；随机 BIST 写读；双请求随机槽 | 每 bank/way 等于模型 |
| WayLookup | 随机 32 槽完整填充（8 轮）、双写端口、随机 tag/RVC/parity/MMIO/PBMT、随机 refill map、随机异常 gpAddr | FIFO 顺序与每字段等于模型 |
| MainPipe | 随机合法 FTQ block（起始 2 字节对齐、结束偏移合法）、随机 512 位 bank 数据/RVC map、随机 refill 数据、随机 pTag/gpAddr、随机双取指对 | 对齐 map、范围、数据、taken、异常、touch 全部按模型 |
| PrefetchPipe | 随机合法 block、随机 paddr/gpAddr/PBMT/PF/GPF/AF、随机 meta 命中 way/RVC/parity、随机 SameLine/Overlap2/Interleave 双预取 | meta 读地址、写条目、miss 列表按模型 |
| MissUnit | 每轮填满 4 fetch + 10 prefetch MSHR 的随机 42 位块/8 位 set、随机 victim way、随机 256 位 refill 数据 | 分配顺序、acquire source/地址、victim set、响应字段按模型 |
| Mshr | 32 轮随机 block/set/way + 双 lookup 端口命中/不命中 | 分配、issue、lookup、释放按模型 |

对随机数据“只写不读”的边界也做了说明：MissUnit 的 D-channel data 只写入阵列，该单元
观测不到回读；随机数据在那里只作为激励，可观测的控制响应仍逐项比对；数据落盘正确性由
DataBank/DataArray 的读回用例和整块 ICache 的回填用例判定。

### 9.2 实测 toggle（子模块，合计）

| | 随机战役前 | 随机战役后 |
|---|---|---|
| 合计 | 85135/150192 = 56.68% | **144111/150192 = 95.95%** |

逐 DUT：

| DUT | 前 | 后 |
|---|---|---|
| WayLookup | 33.9% | **98.7%** |
| Mshr | 18.2% | **97.9%** |
| MainPipe | 56.1% | **96.6%** |
| PrefetchPipe | 30.3% | **95.1%** |
| MissUnit | 23.3% | **96.3%** |
| DataArray | 53.4% | **95.0%** |
| DataBank | 63.8% | **95.6%** |
| MetaBank | 84.9% | **95.0%** |
| MetaArray | 79.5% | **96.4%** |
| Replacer | 99.7% | 99.7% |

分支/行覆盖没有回退：子模块 line 仍全部 100%，branch 只增不减；整块 ICache 的
`module-covered` toggle 从 14,136 升到 **35,442**（父模块 49,553 条缺口中的 71% 现在
能直接指向字节相同子模块 DUT 的命中点）。

### 9.3 随机也到不了的地方（结构性残留）

| 残留 | 条数（子模块） | 原因 |
|---|---|---|
| `io_broadcast_ram_ctl` | 约 1,800 | DFT/测试控制总线；功能模式恒 0，随机驱动它属于测试模式而非功能激励 |
| `initial` 块的 reset-`else` | 40 branch | 时刻 0 reset 恒 1，不可达 |
| 优先级 mux 最终 `else` | 257+129 branch | 外层 OR 已保证选中，死代码 |
| 取指 MSHR 2/3 仲裁臂 | 8 branch + 236 toggle | 单次取指最多两条线、s1 单条目阻塞，2/3 永不 valid |
| 零宽 array / `gpAddr[0]` / 对齐地址低位 | 若干 | 端口宽度为 0、PrunedAddr 不携带 bit0、block 地址低 6 位恒 0 |
| 未在单元边界暴露的父模块 mux 输入 | 约 13,875 toggle | 需在整块 ICache 层用随机激励；这些信号在子模块 DUT 中不存在，随机子模块无法覆盖 |

### 9.4 随机暴露并修正的模型问题

随机流把模型里“固定用例没碰到的假设”暴露出来，共修正 4 处（都不是 RTL 缺陷）：

1. **Svpbmt 编码**：XiangShan `Pbmt` 是 00=PMA / 01=NC / 10=IO / 11=reserved；
   原模型用 `pbmt & 2` 判 uncached，把 reserved 当 IO 且漏了 NC。改为 `pbmt in (1,2)`。
2. **物理地址宽度**：`info.pAddr` 是 47 位 PrunedAddr（address[47:1]），agent 读回左移
   一位；模型原先再掩到 47 位，随机 pTag 置高 bit 后两边差 2^47。改为按 48 位物理地址。
3. **未读 bank 的 don't-care**：unit DUT 的阵列响应寄存器对未选 bank 保留旧值，模型给 0；
   随机 block 起始 bank 非 0 时暴露。`send(mask_unread_banks=True)` 现在对**两侧**做
   bankSel 掩蔽（不比较未取指的 bank），与整块 ICache 的 `data_masks` 口径一致。
4. **PMP 属于 s2、corrupt 回填数据 don't-care**：见 `docs/error-review.md` §2.1。

### 9.5 结论

能，但要满足三个条件才不是“刷覆盖率”：

1. **激励合法**：随机的是 ISA/FTQ/TileLink 允许的字段（对齐、块结束偏移、one-hot way、
   Svpbmt 编码、同页双取指），不是任意位模式；
2. **期望独立**：每个随机响应都由参考模型判定，模型来自 ISA/文档，而不是从 RTL 抄；
3. **残余分类**：随机覆盖不到的必须是结构/DFT/死代码，逐条给出证据，而不是把分母拿掉。

在这三条下，本轮把子模块 toggle 从 **56.68% 推到 95.95%**，同时全量 224 条用例
全部通过（`results/xreactor-full-22` 串行、`full-23` 并行，各 224 passed + 1 xfailed）。


## 10. 逐信号复核：哪些"随机也到不了"其实是功能点缺口

§9.3 把残余缺口归成"结构/DFT/父模块独有输入"过于笼统。逐条查 RTL/Scala 后，确实有
**8 类不是不可达，而是功能点没定义**；另有若干是随机用例自身的生成器缺陷。本轮已全部
补成功能点/用例：

| 原"残余" | 实际性质 | 处理 |
|---|---|---|
| `flushFromBpu.s2/s3` 在 MainPipe 从未驱动 | **缺失功能点**：BPU 重定向按 FTQ 指针杀掉在/晚于目标的取指（s0 用 s2/s3，s1 用 s3） | 新增 `ICACHE-MAINPIPE-013`，含 `!isAfter` 与 flag 回绕的指针扫描 |
| `flushFromBpu` 在 PrefetchPipe 从未驱动 | **缺失功能点**：s2 杀 s0、s3 杀 s1（并冲刷 ITLB 流水）；软件预取豁免 | 新增 `ICACHE-PREFETCHPIPE-012`，含 s1 等待 ITLB 时被 s3 冲刷 |
| `hasSatpFlush` / `req_1_taken` 恒 0 | **缺失功能点**：FTQ 的 satp 冲刷标签与第二取指的 taken 标志必须原样送到 IFU | 新增 `ICACHE-MAINPIPE-014`（另含后端异常标志/代码） |
| `io_update_bits_corrupt` 恒 0 | **缺失功能点**：corrupt 回填不是一次安装，不得改写已排队条目 | 新增 `ICACHE-WAYLOOKUP-014` |
| `io_missResp_bits_corrupt` 恒 0 | **缺失功能点**：corrupt 回填不算命中、不得更新 stage-1 元数据 | 新增 `ICACHE-PREFETCHPIPE-013`（另含"其它行的回填"） |
| `fromMainPipe_realTwoFetchValid` 恒 0 | **缺失功能点**：真实双取指一次消费队列两项，读指针 +2 | 新增 `ICACHE-WAYLOOKUP-015`（双槽读出 + 连读两对） |
| `s2_mshrHits` / `s2_miss_1` 未翻转 | **缺失功能点**：回填在 stage 2 到达时直接满足请求，不再发 miss | 新增 `ICACHE-PREFETCHPIPE-014` |
| `lookUps_0/1_resp_hit` 只覆盖一个槽 | **缺失情形**：重复检测的 14 个 MSHR × 两条请求流 | 扩 `ICACHE-MISSUNIT-002`（逐槽、fetch/prefetch 两流） |
| `exceptionPtr_value` / `flushFromBpu_s3_bits_value` / 异常槽 | **缺失情形**：异常锁存位置、stage-3 指针比较、第二个输出槽的异常码 | 扩 `ICACHE-WAYLOOKUP-005/006` |
| `bankSel_1` 在 DataArray 只用高 bank | **缺失情形**：第二个请求的第二行可用低 bank | 扩 `ICACHE-DATAARRAY-003/004`（第二请求双行、低 bank） |
| 最大尺寸取指的 range/mask 位 | **缺失情形**：32 指令取指后紧跟小取指，mask 需回落 | 扩 `ICACHE-MAINPIPE-009` |
| `fence.i` 后 MSHR 复用 | **缺失情形**：drain 完成后下一笔 miss 必须被接受 | 扩 `ICACHE-MSHR-005` / `ICACHE-MISSUNIT-009` |

另外修正了随机生成器的两个真实缺陷：

1. **跨行随机从未发生**：`mainpipe`/`prefetch` 的 `random_block` 取 `start ∈ {0,2,…,30}`，
   而跨行要求 `start & 0x20`，所以 `0x20..0x3E` 永远不会被取到。改为 `range(0,64,2)` 后，
   `bankSel_1`、跨行 RVC 掩码等"残余"立刻被覆盖。
2. **第二行元数据是 don't-care**：非跨行取指的第二行不被读取，RTL 会保留上一笔的
   寄存器内容；模型原先假设为 0。现在按"只有跨行才比较第二行"处理（`line1_valid`），
   这不是放宽断言，而是把第二行从"未定义输入"里排除。

## 11. 仍然真正不可达/未闭合的项

| 信号/点 | 条数 | 证据 |
|---|---|---|
| `bankSel_1[4:7]`（MainPipe/DataArray） | 16+8 | 跨行要求 `start≥0x20`，第二行最多 32 字节 → 只覆盖 bank 0..3；高 4 位恒 0 |
| `fullva[0]`、`fullva[50:63]` | 30 | `fullva = {{13{addr[49]}}, addr, 1'b0}`：位 0 是块对齐零，50..63 是 bit49 的符号扩展副本；有效地址位 1..49 已全部翻转 |
| DFT/测试总线（`ram_ctl`、`ram_hold`、`cgen`、`ram_bypass`、`mbist_*`、`sigFromSrams_*`） | ~1,800 | 功能模式恒定；BIST 功能路径本身已由 BIST 用例覆盖 |
| `initial` 块 reset-`else`、优先级 mux 最终 `else` | 40 + 386 | 不可达死代码 |
| 取指 MSHR 2/3 的仲裁臂 | 8 branch + 236 toggle | 单次取指最多两行、s1 单条目阻塞 |
| `exceptionPtr_flag` | 1 | 已加"回绕后锁存异常"用例，但该标志仍未翻转；**保留为开放项**，不声称已覆盖 |
| `s2_mshrHits_1`/第二请求流的部分位 | 约 6 | 已加单行 stage-2 回填；双行 stage-2 回填尚未构造，**保留为开放项** |
| `firstRange/totalRange` 个别方向、ready 类 1→0 | 约 8 | 用例收尾时寄存器保持高电平，属收尾/收敛，不是语义缺口 |

结论：上一轮把 8 类功能点缺口误归为"结构不可达"，这是分类错误；本轮已补齐并新增
7 个功能点、扩充 6 类情形。剩余项里只有 `exceptionPtr_flag` 与双行 stage-2 回填是
真正的开放项，其余有逐条结构性证据，仍计入分母。


## 12. 第六轮迭代：继续找 bug（结果）

本轮继续按"覆盖率缺口 → 功能点 → 语义 bug"的方式迭代，重点是把上一轮 3 个开放项
闭合，并逐条验证"结构不可达"的结论。

### 12.1 新闭合的语义与新增功能点

| 功能点 | 语义 | 验证方式 |
|---|---|---|
| `ICACHE-MAINPIPE-013` | BPU s2/s3 重定向按 FTQ 指针（含 flag 回绕）杀掉在/晚于目标的取指 | 指针全值扫描 + `!isAfter` 预期；含 s0/s1 两级 |
| `ICACHE-MAINPIPE-014` | satp 冲刷标签、第二取指 taken、后端异常标志/代码原样到 IFU | 置位/清零/第二取指 |
| `ICACHE-PREFETCHPIPE-012` | 重定向杀投机预取（s0/s1、ITLB 流水同冲、软件预取豁免） | s2/s3 指针扫描 + s1 等待 ITLB 时被 s3 冲刷 |
| `ICACHE-PREFETCHPIPE-013` | corrupt 回填不算命中、不改 stage-1 元数据；其它行的回填也不改 | 单行 corrupt + 异页回填 |
| `ICACHE-PREFETCHPIPE-014` | stage-2 到达的回填直接满足请求；跨行时只补该行 miss | 单行 + 跨行第二行回填 |
| `ICACHE-WAYLOOKUP-014` | corrupt 回填不改写已排队条目 | 匹配块 corrupt 回填后读回旧值 |
| `ICACHE-WAYLOOKUP-015` | 真实双取指一次消费两个队列项（读指针 +2） | 双槽读出 + 连读两对 |
| `ICACHE-DATABANK-007` / `METABANK-010` / `METAARRAY-011` / `DATAARRAY-010` | 复位清零：各 SRAM 宏的上电清扫覆盖全部 set/way | 写图案 → 复位 → 等清扫 → 全量读回零/无效 |

新增/加强的边界情形：

- WayLookup：异常锁存发生在写指针**回绕后**（`exceptionPtr_flag` 0→1 与 1→0 双向）、
  stage-3 重定向丢掉异常条目后释放写停顿、FTQ 指针 flag 的双向存储；
- MainPipe：miss 反压在**请求出现前**拉低（验证请求被保持而非丢弃）、IFU 反压保持响应、
  ECC 报告单拍清除、`vs_non_leaf` 跟随、指令范围 2→1 收缩；
- PrefetchPipe：单次跨行请求发出**两条** miss（第二个仲裁口/`s2_hasSend_1`）、端口 1
  命中→缺失清除 stage-2 命中寄存器、双请求 miss 去重（防止仲裁器重复呈现同一请求被当成两次）；
- 四个 SRAM DUT：BIST 广播后切回单阵列（`doSpread`/`selectedOH` 回落）、写口 pending 时
  ready 的行为。

### 12.2 验证代码 / 用例缺陷修正（不是框架 bug，也不是 RTL）

这里要区分三个层面，避免混为一谈：

* **xreactor / picker 框架**：未修改（xreactor `2461d0f`，`git status` 为空）；
* **项目验证代码**：`suites/frontend/icache/` 下的 agent / monitor / model；
* **用例激励**：`tests/` 下的测试数据生成器。

本轮三处缺陷的归属如下：

| # | 缺陷 | 归属 | 位置 | 危害 |
|---|---|---|---|---|
| 1 | miss 反压竞态：看到 `missReq.valid` 后才拉低 `ready`，与接受沿竞争 | 项目验证代码（agent 握手时序） | `suites/frontend/icache/mainpipe/agent/main.py` | **假失败**（DUT 正确、测试报错） |
| 2 | 重复 miss 采样：持续 2 拍的同一请求被记成 2 条 miss | 项目验证代码（agent 观察逻辑） | `suites/frontend/icache/prefetchpipe/agent/main.py::wait_result` | **假通过**：双 miss 用例是绿的，但端口 1 从未发出 |
| 3 | 随机跨行生成器：`start` 只取 `0..30`，跨行区间 `0x20..0x3E` 永不出现 | 用例激励数据 | `tests/*/test_random*.py::random_block` | 覆盖率假象 |

修正方式：

1. 反压必须在请求出现**前**建立：进入 `send()` 时就拉低 `missReq.ready`，并在等待期间
   断言 `valid` 与载荷保持不变，恢复 ready 后才允许接受；
2. `wait_result` 新增 `distinct_misses`：只有**载荷不同**的请求才计为新 miss，并要求两条
   miss 的 `(blkPAddr, vSetIdx)` 不同。修正后端口 1 的 `s2_hasSend_1` 才开始翻转——
   说明此前的"双 miss 通过"确实掩盖了端口 1 未验证；
3. `random_block` 改为 `range(0,64,2)`：跨行要求 `start & 0x20`，原范围永远不满足。

### 12.3 上游对照

GitHub API 显示 ICache 路径最新提交是 `f1a649e0c`（2026-10-14，exception(1) 传递）与
`bbd8a9b7f`（2026-10-14，ECC bank select 的 end offset），二者都已在 HEAD `893e1580`
内；HEAD 之后上游没有新的 ICache 修复可借。

### 12.4 本轮结束后的数字

- 子模块 toggle：**144,604/150,192 = 96.28%**；control 未翻转 **61 条**：
  - **56 条结构不可达**：`bankSel_1[4:7]` 16（跨行时 `{start[5]^end[4], end[3:2]}` 高 2 位
    相消 → 第二行最多 bank 0..3）、`firstRange[0]/totalRange[0]` 2（有效取指范围必含 bit0）、
    `fullva` 符号扩展 30（位 0 块对齐零、50..63 是 bit49 副本）、单阵列 bank 的
    `doSpread`/`selectedOH` 8（`~0` 恒 1）；
  - **5 条开放（liveness 采样）**：`s1_sramValid_REG`×2、`s2_mshrHits_valid`×2、
    `s2_hasSend_1` 的 1→0。功能用例已证明对应行为（stage-2 回填满足请求、端口 1 发出
    miss、端口 0/1 独立），但这几个内部寄存器的翻转未在采样窗口内出现，保留为开放项。
- 整块 ICache：未覆盖 49,553 toggle 中 **35,674 条**现在能指向字节相同子模块 DUT 的命中
  点（上一轮 35,442），开放 13,643 条；branch 仍为 530 模块覆盖 + 434 不可达 + 3 开放。

### 12.5 结论

第六轮没有发现新的 RTL 缺陷（当时 `prefetch.i` 仍是唯一 XFAIL；第七轮按上游 issue 复核时发现了第二个，见 §13），但发现并修正了
**3 处验证代码/用例缺陷**（2 处 agent、1 处用例数据；框架未改），补了 **4 个功能点**
（复位语义）与 22 条用例。剩余项的分母
未剔除：结构不可达逐条给出 RTL 表达式与位宽推导，5 条 liveness 采样项明确标为开放，
没有声称覆盖。


## 13. 第七轮：按上游 issue 复核软预取路径（发现第二个 RTL 缺陷）

### 13.1 上游核查（2026-10-20）

| 项 | 结果 |
|---|---|
| `git fetch origin kunminghu-v3` | `origin/kunminghu-v3` = `6705b6368`（2026-10-19 23:04，仅 XSCache 子模块 bump） |
| HEAD 之后涉及 ICache 的提交 | **无** |
| HEAD 与 origin 在 `frontend/icache` 的差异 | **无**（`git diff --stat` 为空） |
| 上游 issue #6674（open，2026-10-05） | `prefetch.i` 程序触发 `ICacheMetaArray` 断言“2 read setIdx must be in the different interleaved bank!” |
| 上游 PR #6691（open，2026-10-09） | “Fixes #6674, the related ICache-top softprefetch selection is removed.” |
| 修复进入本工程 HEAD？ | **否** |

### 13.2 根因与复现

`ICacheImp.scala` 在软件预取有效时：

```scala
prefetcher.io.fromFtq.valid       := softPrefetchValid || io.fromFtq.toPrefetch.valid
prefetcher.io.fromFtq.bits        := io.fromFtq.toPrefetch.bits        // req(1) + twoPrefetchCase 保留
prefetcher.io.fromFtq.bits.req(0) := Mux(softPrefetchValid, softPrefetch, ...)
io.fromFtq.toPrefetch.ready       := prefetcher.io.fromFtq.ready && !softPrefetchValid
```

`ready` 被拉低，但预取流水仍以“软件预取 + FTQ req(1) + FTQ case”的合并请求 fire。实测：

- 软件预取 `0x4080`（block 0x102，复位后 stale `vSetIdx=0`）；
- FTQ Interleave issue：req0 `0x4040`（block 0x101，set 0x01 奇）、req1 `0x4000`（block 0x100，set 0x00 偶）；
- `fromFtq.toPrefetch.ready` 连续 **24 拍为 0**；
- 仍观测到 block **0x100** 的 acquire（source 6）——FTQ issue 的第二个 block 在握手完成前被预取；
- 合并请求只对软件预取做 ITLB 翻译，跨页时第二块会用软件预取的页标签；
- stale set 0（偶）与 req1 set 0x00（偶）落在同一 interleaved bank，正是 #6674 的断言条件。

### 13.3 登记与影响

- 功能点 `ICACHE-ICACHE-030`：“A pending software prefetch must not consume an
  unaccepted FTQ prefetch issue”，strict XFAIL，复现 `results/xreactor-ic-ic30-2`；
- 与 `ICACHE-ICACHE-012`（stale `vSetIdx`）是同一段 ICache-top 选择逻辑的两个症状，
  上游用 PR #6691 整体移除；
- 修复合入后 strict XFAIL 会变成 XPASS，提醒复查。

### 13.4 第七轮后的数字

- 功能点 **137**：**135 PASS + 2 XFAIL**；
- 用例 **278 passed + 2 xfailed**（串行 `results/xreactor-full-30`、并行 `results/xreactor-full-31`）；
- 整块 ICache toggle：90,929/140,398 = **64.76%**（新用例多覆盖 84 个位方向）；
- 子模块 toggle 不变：144,604/150,192 = **96.28%**；
- 整块缺口对账：module-covered 35,601、structural 236、open 13,632（branch 仍 530/434/3）。

### 13.5 第八轮后的数字（按经验文档复核用例）

第八轮没有新增 RTL 缺陷路径，但补了组合/边界用例（`METABANK-011`、`METAARRAY-012`、
`DATAARRAY-011`、`REPLACER-003/004`、`MSHR-006`、`MAINPIPE-015`），并把 WayLookup 的
flush×写场景登记为第三个 XFAIL（`WAYLOOKUP-020`，模块级潜在缺陷，集成中不可达）：

- 功能点 **142**：**139 PASS + 3 XFAIL**，0 NOT_RUN；
- 用例 **290 passed + 3 xfailed**（串行 `results/xreactor-audit-full-3`、
  并行 `results/xreactor-audit-full-4`，两者 `coverage_complete=true`）；
- 整块 ICache toggle：90,930/140,398 = **64.77%**；
- 子模块 toggle 不变：144,604/150,192 = **96.28%**；control 未翻转仍为 61 条
  （56 条结构不可达 + 5 条 liveness 采样开放项）——新增用例覆盖的是已有位方向的
  新组合，不是新的位。

## 8. 复现

```bash
cd /home/xyl/kmh-v3-test/icache-verify-kunminghu-v3
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 1 --output results/xreactor-full-20 -- tests
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 4 --output results/xreactor-full-21 -- tests

python3 tools/coverage_breakdown.py results/xreactor-full-20
python3 tools/coverage_breakdown.py results/xreactor-full-20 --dut waylookup --list branch
python3 tools/coverage_ledger.py   results/xreactor-full-20
```
