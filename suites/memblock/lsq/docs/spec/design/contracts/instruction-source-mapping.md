# 指令来源到 LSQ 的映射与功能点分类

本合同回答一个问题：**哪些指令/上游事务能到达本工程的 LSQ DUT，它们在 LSQ 里被编码成什么，
哪些根本不来。** 它是 [behavior-equivalence 方法](../../../../../../../skills/design/behavior-equivalence.md)
第 1 步"来源到 DUT 的映射"的 LSQ 实例，也是 [kind × outcome 矩阵](kind-outcome-matrix.md)的
行来源。没有这份映射，"八类型随机"只是事务类型清单，无法证明指令域被覆盖。

适用范围：`public-a0c2a26cb`、DefaultConfig、本工程 38 个 DUT 的公开端口。
源码行号指锁定检出 `.cache/sources/f3ac6022…`。

## 1. 进入 LSQ 的指令族

LSQ 的分配入口是 `LsqWrapper.io.enq`：`needAlloc(1,0)` 为 1 走 LoadQueue，
为 2 走 StoreQueue（`LSQWrapper.scala:181-190`）。`needAlloc` 由 dispatch 按 FuType 决定
（`Dispatch.scala:733-740`）：

| ISA 指令族 | FuType | dispatch 判定 | LSQ 入口 | LSQ 内编码 | 域 |
|---|---|---|---|---|---|
| LB/LBU/LH/LHU/LW/LWU/LD/LQ | `ldu` | `isLoadVec`（非 prefetch）→ `needAlloc=1` | LoadQueue enq | `size`=0..4、`mask`、`fuOpType` | 本层 |
| SB/SH/SW/SD | `stu` | `isStoreVec` → `needAlloc=2` | StoreQueue enq | `size`、`byteMask`、`cross16Byte`、`isUnalign`、`tlbMiss` | 本层 |
| HLV/HLVU/HLVX/HSV | `ldu`/`stu`（`isH` 位，`Opcode.scala:457-465、607-609`） | 同普通 load/store | 同上 | **没有指令级字段**；`isHyper` 只来自 TLB 异常的 `isHyper`（`NewStoreUnit.scala:336`、`NewLoadUnit.scala:1583`） | 本层仅覆盖"异常携带的 hyper 位"；HLV/HSV 语义本身在 LDU |
| 向量 load：vle*/vlse*/vlxei*/vle*ff | `ldu`（`LduOpcodes`，`Opcode.scala:475-535`） | `needAlloc=1`，`numLsElem`=flows | LoadQueue enq | 每条 uop 的 `numLsElem`（flow 数）、`size`、`mask`；非活跃尾用 `vecInactive` | 本层（首次向量路由的可达性仍按 `lsq-normal-mixed-source-jobs.md` 的 NMIX-INSTR 保留为未证明） |
| 向量 store：vse*/vsse*/vsxei*、vsur/vsux（含 segmented vsseg） | `stu`（`StuOpcodes`，`Opcode.scala:619-680`） | `needAlloc=2` | StoreQueue enq | `numLsElem`、`wline`、`cross16Byte`、第二页 UQ | 本层（segmented 组合见 §4 缺口） |
| CBO.clean/flush/inval/zero | `stu` + `uopCbo`（`Opcode.scala:681-684`） | `isStoreVec` → `needAlloc=2` | StoreQueue enq | `cboType = LSUOpType.getCboOpcode(op)(3,1)`；`CBO.clean=0b000→0`、`flush=001→1`、`inval=010→2`、`zero=011→3`（`Opcode.scala:591-596`、`LSQCommon.scala:51-64`） | 本层 |
| 普通 store 的"dcache 探测 miss" | — | — | SQ `dataEntries.prefetch` | `port.cacheMiss && staReValidVec(j)`（`NewStoreQueue.scala:1819-1823`），**不是** Zicbop | 本层（仅标志位，无独立功能点） |

### 1.1 与测试 actor 的 8 个 kind 的对应关系

`testbenches/lsq_wrapper/tests/mixed_owners.py:32` 的 8 类是**事务类型**，不是指令族：

```python
KINDS   = ("cached","nc_load","mmio_load","io_load","store","nc_store","io_store","cbo")
WEIGHTS = (30, 12, 3, 2, 36, 6, 4, 7)
```

其中 `nc_*`/`mmio_*`/`io_*` 的区别来自**内存属性**而非 opcode：

| kind | 内存属性 memory_type | Scala 判定 | 典型 PMA/PBMT |
|---|---|---|---|
| `cached`/`store` | 0 | `isCacheable = !bit0 && !bit1` | 普通可缓存 |
| `nc_*` | 1 | `isPbmtNC = bit0 && !bit1` | PBMT=NC |
| `mmio_*` | 2 | `isPbmtIO = !bit0 && bit1`，`isMMIO = bit1` | PBMT=IO |
| `io_*` | 7 | `isDeviceRegion = bit2` | 设备区、非内存后备 |

（`LSQCommon.scala:36-46`；`mixed_owners.py` 只驱动 `nc/mmio/memBackTypeMM` 三个公开位。）

因此：**同一条 `SD` 可以是 `store`、`nc_store`、`io_store` 三类之一**。这决定了分类矩阵必须
"指令维度 × 属性维度"两轴，不能只用 8 个 kind 代表指令域。

## 2. 不进入 LSQ 的指令族（出域结论，含证据）

| 指令族 | 结论 | 证据 |
|---|---|---|
| AMO*（amoadd/swap/…） | **不分配 LSQ**：dispatch `enqLsqIO.req(i).valid := fire && !isAMOVec(i)`（`Dispatch.scala:741`），FuType=`mou` | 由 `AtomicsUnit` 直接经 `dcache.io.lsu.atomics` 完成（`MemBlock.scala:1224`） |
| LR/SC | 同上（`AmoOpcodes`，`Opcode.scala:742-746`） | 同上 |
| Zicbop `prefetch.i/r/w` | **不分配 LSQ**：`isLoadVec` 显式排除 `LSUOpType.isPrefetch`（`Dispatch.scala:675-676`）→ `needAlloc=0` → LoadQueue enq valid 恒 0 | 由 LoadUnit 的软件预取路径处理（`NewLoadUnit.scala:157-165、188-206`，`dcacheReq.cmd := M_PFR`） |
| fence / fence.i | 不分配；经 sbuffer flush 影响 LSQ 状态 | `MemBlock.scala:1178-1187` |
| CSR / 其它非访存 | 不涉及 | 无端口 |

### 2.1 AMO 与 LSQ 的**接口义务**（未覆盖，登记）

AMO 不进 LSQ，但与 LSQ 有两条真实约束，本工程当前不建模：

1. `AtomicsUnit.io.flush_sbuffer.empty := stIsEmpty`，而 `stIsEmpty = sbuffer.flush.empty && uncache.flush.empty`
   （`MemBlock.scala:1181-1182、1225`）——AMO 要等 Sbuffer/Uncache 排空。
2. AMO 完成时 `atomicsUnit.io.flush_sbuffer.valid` 与 `cmoFlush`/`fenceFlush` 互斥驱动 sbuffer flush
   （`MemBlock.scala:1178-1187`）。

这两条属 `MemBlock`/`AtomicsUnit` 组合域，单 DUT UT 观测不到；上游 #6597 正是"分段向量 Store + AMO
触发 VSQ 断言"，说明该交互在整核可达。**登记为出域+缺口，不写成"AMO 无关"。**

## 3. LSQ 内部真正要分类的维度

按 `behavior-equivalence.md` 第 2 步，LSQ 的功能点维度不是指令名，而是下面六组：

| 维度 | 取值 | 承载字段 | 已有覆盖 |
|---|---|---|---|
| 操作类别 | load / store / cbo / NC / MMIO / IO | `needAlloc`、`fuOpType(0)`、`memoryType` | 8 kind 随机 + 定向 |
| 地址/粒度 | size 0..4、16B 内偏移、跨 16B、跨页、非对齐 | `size`、`byteMask`、`cross16Byte`、`isUnalign`、UQ 第二页 | 定向 + 随机 |
| 身份/年龄 | SQ/LQ/ROB 指针、回绕、former/latter、SID/MID | `sqIdx`、`robIdx`、`lqIdx`、`id` | 定向 + 随机 |
| 权限/属性 | cacheable / NC / IO / MMIO、hyper | `memoryType(2,0)`、`nc`、`mmio`、`isHyper` | 8 kind 随机 |
| 资源状态 | Sbuffer credit、队列满、replay 池、checkpoint | 各种 valid/ready、`handleFinish` | 定向 |
| 取消/复位/并发 | redirect、nuke、local reset、同拍竞争、回绕 | `redirect`、`reset`、多 lane | 定向 |

**响应结果域（clean/fault/tag_error/refill/tlb_miss）是第 7 组，此前没有单列**，见
[kind × outcome 矩阵](kind-outcome-matrix.md)。这次的 MMIO Store 漏检正是缺了这一轴。

## 4. 未分类项与缺口（不得默认"不存在"）

| 项 | 状态 | 依据 |
|---|---|---|
| 向量首次路由是否真能被 LoadUnit 以向量形式发起 | **未证明**（合同已登记） | `lsq-normal-mixed-source-jobs.md` NMIX-INSTR：`NewLoadUnit:180-211` 首次 issue 固定 scalar 且 `DontCareVectorFields`；测试仍跑原 16B 输入但单独标注 |
| segmented 向量 store（vsseg）+ AMO 组合 | **缺口** | 现有 VSQ 激励只给 `flows` 计数，无"多寄存器分段 store + AMO"序列；上游 #6597 |
| 向量 store 越过 SQ 物理窗口 | **出域** | 上游 #6652/#6653：`VecIssueQueue` 缺 `sqIdx` 窗口检查，属 backend |
| Zicbop 预取的权利检查（Zicbop 不应产生异常） | **出域** | 上游 #6832 第 3 项；LSQ 不分配，看不到 |
| AMO 的 sbuffer 排空接口义务 | **出域+缺口** | §2.1 |

## 5. 三向对账：规格 / Scala / 生成端口

本节回答一个方法问题：**功能语义到底从哪一层找？** 三个来源职责不同，不能互相替代。

| 层 | 只在这一层能拿到 | 用它定答案的后果 |
|---|---|---|
| **规格**（ISA、总线协议、接口合同） | "必须发生什么" | — 这是唯一合法的 oracle 来源 |
| **Scala**（锁定检出） | **设计意图**：状态机有哪些态、字段想表达什么、哪条分支合法。生成 Verilog 里只剩 `_GEN_6`、`uncacheState == 3'h3` | 用实现给自己出题，模型与 RTL 同错（`testbenches/forward/model.py` 抄 `s2FullOverlap` 就是先例） |
| **生成 Verilog / Picker** | **能驱动、能观测的物理面**：端口名、位宽、方向。`dut/<dut>/signals.json` 就是这一层 | 同上，而且看不到意图 |

两者不对称：`--default-layer-specialization=disable` 丢掉了 Chisel verification layer，
`NewStoreQueue.scala` 里 27 处 `assert`/`XSError` 在生成 `PhysicalStoreQueue.sv`/`DeqModule.sv`
里 `$fatal` 计数为 **0**。所以"只从 Verilog 找"连设计者认为什么必须成立都看不到；
"只从 Scala 找"则会把被裁剪的字段当成可观测。

### 5.1 规则

每读一个字段，必须同时回答三问：

1. 规格/合同要求它可观测或被驱动吗？
2. Scala 里谁写它、谁读它？
3. 生成 DUT 的端口里它在不在？

第 3 问为"否"时**必须判定**，二选一：

- **被裁剪且有理由**（常量折叠、`debugEn=false`、消费者不需要）；
- **未驱动/未接入**（缺陷）。

不允许跳过第 3 问，也不允许用"端口就长这样"当理由——那是 `observation-precision`
明令禁止的关闭理由。

### 5.2 机械化检查

工具：`tools/audit_scala_rtl_fields.py`

- `--report`：按 class 体（brace matching）取本模块的 `io.*` 链，压平后与
  `signals.json` 做**形状级**比对（去掉 lane 下标、折叠括号），并剔除两类已知噪音：
  Scala 集合成员（`.map/.get/.fire/...`）和"整体 bundle 赋值"（名字是某端口的严格前缀）。
  **仅用于人工分诊，不是断言。**
- `--strict`：校验 `manifest/critical-fields.json`——每个功能点依赖的字段必须声明
  `port`（必须存在）或 `absent`（必须不存在 + 写明理由）。门禁见
  `testbenches/lsq_wrapper/tests/meta/test_critical_fields.py`（5 项）：`absent` 的字段一旦出现就失败，强制重开判定。

### 5.3 当前实测（`public-a0c2a26cb`，38 个 DUT）

```
duts compared: 38   scala-only shapes: 377
其中 62 项含 debug/diff/topdown ；315 项待分诊
两个 DUT 为 0：age_replay、unalign_queue
```

抽查已确认的类别（**不声称 315 项都已判定**）：

| 类别 | 例子 | 判定 |
|---|---|---|
| firtool 折叠常量/未用字段 | `deq_module` 的 `io_toUncacheBuffer_resp_ready`（Scala 写 `:= true.B`）、`io_toUncacheBuffer_req_bits_cmd` | 良性 |
| 叶子未消费的 IO | `uncache_entry_*` 的 `io_uncache_req_bits_cmd`/`_data`/`resp_ready`（每 DUT 13 项） | 良性，但说明该叶子没有这条观测路径 |
| Chisel 聚合成员 | `io_allocateReq`、`io_validCount`、`io_lqFull` | 良性（端口用别的名字导出） |
| 命名重映射 | `io_enq_canAccept` → wrapper 用 `lqCanAccept`/`sqCanAccept` 聚合 | 良性，需登记映射 |
| **未驱动字段** | **`deq_module` 的 `io_toUncacheBuffer_resp_bits_denied` / `_corrupt`** | **缺陷**（见下） |

**这个工具在 MMIO Store 缺陷上给出的是直接命中**：`deq_module` 的 16 项 scala-only 里，
`io_toUncacheBuffer_resp_bits_denied` 与 `_corrupt` 正是 `NewStoreQueue.scala:1087/1095`
要读的两个字段。它们不存在的原因是生产者没驱动（`Uncache.scala:118-128` 只驱动
`nderr`/`error`）。也就是说，**如果把三向对账当成常规步骤，这个缺陷在写用例之前就会
以"字段缺失"的形式暴露**，而不是等到构造出随机激励才发现。

## 6. 验收

- 指令域每一族在本表有且只有一个"本层/出域/未证明"结论；新增指令族（如 Zacas、Zabha）必须补行。
- 出域结论必须有 Scala 依据（哪个模块承接），不能只写"没测"。
- 本层条目必须在 [kind × outcome 矩阵](kind-outcome-matrix.md)里有对应行，且至少一个 nodeid 或明确缺口。
- 与 8 kind 的对应关系保持"属性维 ≠ 指令维"的区分；不得用 kind 名代替指令覆盖结论。
- 每个功能点依赖的字段必须在 `manifest/critical-fields.json` 有 `port`/`absent` 声明，
  且 `audit_scala_rtl_fields.py --strict` 无问题；`absent` 项一旦出现在端口里，门禁失败。
