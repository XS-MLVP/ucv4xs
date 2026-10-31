# BPU UT 验证阶段汇总（2026-10-21）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


> 本文件是**进行中的汇总**，不是最终验收。未闭合项、分母与约束在文末完整保留。
> 完整回归边界始终为 **24776 PASS / 88 FAIL / 3 XFAIL**；任何选测都不替代它。
>
> 功能点总数 **363**（硬件 353、环境 10），Plan 版本 2，`validate_plan` 通过。

## 一、方法与纪律

每个模块按同一闭环推进：

1. 用人类可读的微架构语义描述功能点（事件 / 所有权 / 效果 / 观察 / 不变性 / 范围六字段）；
2. 先写独立参考模型，再写真实 DUT 用例；
3. 运行后同时看**功能判定**与**RTL 行 / branch / toggle**；
4. 对每一项未命中逐项归因，区分“已有功能点缺情况”“整体功能点缺失”“结构不可达”“检查器/模型缺陷”；
5. 补功能点或用例后复跑，给出覆盖率变化；
6. 全程不放宽 XFAIL、不伪造激励、不把覆盖饱和当作功能通过。

运行纪律：先用 `tools/run_cost.py` 预览 → 分块/定向运行 → 运行期冻结工作树 →
结束用 `--epoch-delta` 核对（`changed=0`）。

## 二、已闭环模块

| 模块 | 选测运行 | 用例 | 源码行 | Branch | Toggle | 功能点 | 组 |
|---|---|---|---:|---|---|---|---|
| ITTAGE | `ittage-late-source-qualification-20261020-v2` | 33P/4F | **1398/1398** | 655/658 | 12698/18994 | 17/20 | 13/16 |
| RAS | `ras-module-qualification-20261020-v4` | 20P/5F/1X | 569/585 | 200/216 | 3382/7720 | 15/17 | 9/14 |
| MicroRAS | `uras-module-qualification-20261020-v3` | 23P/4F | **91/91** | **24/24** | 382/3976 | 15/17 | 6/9 |
| MicroBTB | `ubtb-module-qualification-20261020-v2` | 40P/2F | **794/794** | 188/192 | 3653/8430 | 16/17 | **15/15** |
| MainBTB | `mbtb-module-qualification-20261020-v2` | 110P/10F | 1007/1056 | 385/442 | 7328/11830 | 24/30 | 32/43 |
| TAGE | `tage-module-qualification-20261020-v5` | 226P/1X | 4467/4587 | 1513/1598 | 10711/15514 | 35/36 | 27/28 |
| SC | `sc-module-qualification-20261020-v2` | 51P | 3145/3481 | 890/1038 | 10518/15076 | **23/23** | **28/28** |
| MicroTAGE | `utage-slot2-upper-20261021-v1` | 218P/35F/3X | 9954/11053 | 3249/3746 | 9152/13376 | 13/27 | 57/74 |
| AheadBTB | `abtb-final-20261021-v4` | 75P/1F | **17854/17854** | 4811/4876 | 11984/16320 | 50/51 | 59/60 |

所有 FAIL 均与各自基线逐节点相同（或已单独登记），没有把新增 FAIL 混入 PASS。
逐项未命中归因见 `docs/bpu-coverage-attribution-20261021.md`：每个模块的未命中行/arm
都已落到文件与行号，分类为「已有功能点缺情况 / 结构不可达 / 物理副本」，未发现
「整体功能点缺失」。集成 BPU 完整回归（37998/46541）的剩余行仍有一块未逐项归因，
在该文档第二节如实标注。

## 三、本轮新增证据

### 1. `BPU-INT-111`：AheadBTB 缓冲清理可见性（假阳性修复）

4 个 compressed-entry profile 曾稳定失败，差异固定为
`ahead.1.valid/micro_valid/meta_hit` 与 `early_direction.1.valid`。逐拍探针证明：

- 参考内存中该 way 已无效，且参考仍持有同一 bank/row/way 的失效版本；
- DUT 的额外副本与参考命中 way 在 position/kind/action/target_low 上**逐字段相同**；
- 除这四个 way 级命中标记外没有任何其它差异。

结论：这是单端口 bank **读优先**导致的写回缓冲，不是 RTL 漏清。新增有界放行：
只放行内容相同且已发失效的额外 way 的 absence 标记；预测字段全比较；同一
bank/row/way 超过 64 拍即失败；16 拍空闲窗口后重读必须为 0。

证据：`results/bpu-prefix-cleanup-final-20261021-v2`
（97 PASS，epoch 3055 changed=0；4 profile × 15 拍/30 项放行，conditional-entry 为 0；
10 项纯负对照全部拒绝）。

复核运行：`results/bpu-upstream-20261021-v8`（100 PASS，epoch 3055 changed=0，
同时选入四个组合见证与 `test_conditional_prefix.py`）。

### 2. UTAGE slot-2 上表恢复：最后一个未命中 DUT arm 归零

`UtageDut.v:1133` 长期未命中。原因是**程序形状**：所有恢复用例只用单分支
AheadBTB beat，而单分支 beat 的 slot 2 回退位置恒为 `position + 2`，在 `position`
训练的表项永远不可能是 slot 2 的 provider。

改用真实三分支 beat `(2,4,6)`：先保护下表，再只对位置 6 给真实结果，分配落到上表；
`S2`/`S3` 恢复时重新携带同一 beat，断言 `tableId=1/cfiPosition=6/
takenCtr_value=4/predTaken=1`。

证据：`results/utage-slot2-upper-20261021-v1`
（256 项 218 PASS/35 FAIL/3 XFAIL；35 FAIL 与上一轮逐节点相同；
**行不变、branch +1、toggle +2**，说明这是 branch 级语义缺口而非补行）。

### 3. `BPU-INT-108`：从“比较发生”推进到“撤销生效”

同一 witness 记录重定向拍及其**下一无损比较拍**：后者
`ahead.meta_valid`、四个 `ahead.*.valid`、四个 `early_direction.*.valid` 必须全 0，
`raw_hits` 无 1，并要求至少一组配对的**重定向前**一拍确有真实命中
（实测 tick 434，`ahead_hits=[0,0,1,0]`）。

必须断“后一拍”而不是“同一拍”：`AheadSources.advance` 把失效应用到下一状态。

证据：`results/bpu-upstream-20261021-v7`（92 PASS）与
`results/bpu-upstream-20261021-v8`（100 PASS），均为 5 个重定向拍 × 5 个后续拍，
epoch 3055 `changed=0`。

### 4. `BPU-INT-110`：补上 docstring 声明却未执行的断言

原用例的 docstring 声称“flush 归属于重定向而非训练”，但代码只记录了
`middle_repair/final_repair`，从未断言。现补上 `== 0` 断言并通过。

### 5. `BPU-INT-112`：G×H 同拍格构造完成

在同一程序内让训练反馈与重定向同拍（tick 520），断言下一笔 AheadBTB 读的索引
来自重定向源的原历史（特征 0）而非推进后的新历史（特征 1）。两层防空转：

- 两候选给出不同 `(bank,row)`（`(0,1)` vs `(1,1)`），否则 DUT 的逐拍坐标比较对两种
  历史都成立；
- 记录其后所有选择读，要求没有第二笔落在同一坐标，否则该读数无法归属。

tick 528 呈现该读，DUT 实际 `row=1`、`bankMask=1` 与原件坐标一致。8 项纯负对照
固定“16 个原件特征都存在可区分目标”与 `coordinate()` 与独立公式一致。

**关键时序**：重定向当拍呈现帧已无效，该读要到数拍后才呈现 row/bank；在当拍断言
就会造出 RTL 不满足的期望。

证据：`results/bpu-upstream-20261021-v12`（65 PASS，epoch 3056 `changed=0`）。

### 6. TAGE `useAltOnNa` 端点：第三个假阴性更正

`docs/tage-selector-endpoint-analysis-20261021.md` 原结论“31/0 端点可构造但未实现”**错误**：

| 端点 | 反馈 | 前 → 后 | 越界事件 |
|---|---:|---|---|
| 0 | 32 | 15 → 0 | `lower-saturation` before 0 / after 0 / `decrements=1` |
| 31 | 32 | 16 → 31 | `upper-saturation` before 31 / after 31 / `increments=1` |

三条原理由逐条被否定：不需要 32 个独立分支（同一 PC 不同上下文即可）；
集成模型 `suites/frontend/bpu/tage/model/semantic.py` 早已按 `(table, altConf)` 八项索引
（原文误用 `pair.py`）；也没有模型反推（`index/inc/dec` 由模型先给出再与 DUT T3 逐槽比较）。

本轮补上的是此前缺失的断言：原来只检查阶段末值 `== 0/31`，现在要求存在**真实的越界
饱和事件**，否则“停在 31”可能只是“恰好到达”。

证据：`results/bpu-tage-endpoint-20261021-v1`（48 PASS，epoch 3056 `changed=0`）。

**该格剩余 branch arm 的逐项归因**：集成 BPU 的 `rtl/bpu/Tage.sv` 里
`useAltOnNaVec_N_value` 的**减到零钳位**臂共 8 个（行 3461/3471/3481/3491/3501/3511/3521/3531）。
本轮只驱动了 index 7（table 3、altConf 1）：它的钳位臂已命中，
`lower-saturation`/`upper-saturation` 两个方向都有真实越界投票。其余 7 个（index 0–6）
未命中，原因是**这些桶没有被推到端点**：它们在整轮里保持 16（index 6 到过 18/15），
只走到非钳位的 `cond_else` 分支。

分类：属于**已有功能点的情况枚举**，不是整体功能点缺失——同一 `SaturateCounter`
钳位模板的逐桶副本；模板已在 bucket 7 双向证明，且每帧八个寄存器都与独立模型比较
（桶间隔离已证：bucket 7 到 0/31 时其余六个保持 16/18）。

**2026-10-22 后续：全部 8 个桶已补齐。** 独立 DUT 上用四种形态把 bucket 0–7 各自推到
0 与 31，并各再投 1 票验证越界钳位（`test_selector_buckets.py` 0/1、
`_high_bucket.py` 2、`_odd_bucket.py` 3/5/7、`_even_bucket.py` 4/6）。
全量 `results/tage-selector-full-20261022-v3`：**234 PASS/1 XFAIL**，
branch 1513 → **1533**、toggle 10711 → **10751**，`useAltOnNa` 未覆盖 arm **8 → 0**。
原先“要命中它们需要…属于可选补测，本轮不做”的判断已被实际补测推翻。

### 7. SC 全脏写缓冲：由只读 monitor 判定，解除阻塞

原登记认为必须先读 `rtl/sc`/`dut/sc` 才能判断四槽全脏是否可达。改用**已授权**的
观测路径：集成 `BpuDut` 通过 memory-direct 暴露每个 SC 写缓冲的 `shadowValid/dirty`
与 `io_read_0_ready`（`suites/frontend/bpu/bpu/monitor/sc/observer.py` 本就绑定）。

新增只读见证 `tests/bpu/testcase/test_sc_full_dirty_reachability.py`，在 2 bank ×
4 way 共 8 个物理排列上统计全部 **10 个** buffer（5 张表 × 2 bank）：

| 指标 | 实测 |
|---|---:|
| post-reset 比较周期 | 3500 |
| 每个 buffer 最大 dirty 占用 | **1 槽**（全部 10 个） |
| `full_overwrite` 次数 | **0** |
| 排水被拒（`io_read_0_ready=0`） | 13900 buffer-cycle |

必须剔除 reset 当拍：8 个程序都在 tick 1 出现 `dirty=4, valid=2`（上电未初始化的
影子寄存器），计入会得到相反的结论——这是典型的假阳性陷阱。

机制：每笔被接受的反馈后训练事务都会等待流水线提交，写与写之间隔得远，排水总有机会
清掉前一个脏槽；要四槽全脏需四笔不同 `set_index` 的 miss 在四相邻拍进入同一 buffer
且三次排水都被拒绝。排水被拒本身占约 39%，但两者在公开程序里从未叠加。

模型侧已支持：`FullScReference.full_advance` 实现 `full_miss`（`victim(plru)` +
`kind='full_overwrite'`），`FullScChecker` 每拍比较十个 PLRU 状态。因此这是**防御路径**，
不是缺模型；两个 `all_dirty_victim` arm 保留在原生分母、不授予覆盖信用。

证据：`results/sc-full-dirty-reachability-20261021-v1`（含复现运行
`sc-full-dirty-20261021-v4`：8 PASS，epoch 3057 `changed=0`）。

## 四、检查器死字段审计（组合层）

ICache 经验要求核对“被比较的字段是否真的会变化”。组合层 `bpu.owned-pipeline` 的
字段是按来源配置动态生成的，因此用**运行期取值分布**审计，而不是静态读代码。

新增 `tests/bpu/testcase/test_composition_field_liveness.py`：继承默认检查器，在真实
`early_direction` 程序的 **254 个被比较拍**上，把每个 dotted 字段摊平并统计
“期望侧/实际侧各出现过多少个不同取值”。只有取值会变的字段才可能证伪 DUT。

| 字段族 | 期望侧不同取值 | 实际侧不同取值 |
|---|---:|---:|
| `prediction.taken` | 2 | 2 |
| `prediction.target` | 8 | 8 |
| `prediction.position` | 3 | 3 |
| `metadata.history.phrLowBits` | 13 | 13 |
| `ahead.meta_valid` | 2 | 2 |
| `ahead.row` | 6 | 6 |
| `early_source` | 2 | 2 |
| `early_direction.history` | 13 | 13 |
| `main_metadata.0.0.hit` / `0.1.counter` | 2 / 2 | 2 / 2 |
| `early_direction.2.hit` | 2 | 2 |
| `ahead.2.taken` | 2 | 2 |

**结论**：这些关键族两侧都真的在 0/1 或不同值之间移动，比较不是空转。
同时如实报告：158 个 key 中 **77 个在期望侧只有 1 个取值**（例如 `ahead.0.kind`
始终为条件分支、`main_metadata.1.0.hit` 始终为 0）。它们属于**当前程序未枚举的情况**，
不是检查器缺陷——一旦 DUT 在这些位上报错值，比较仍会失败；只是本程序没有覆盖到
那些取值。要覆盖它们需要各自的程序形状，本轮不伪造。

该见证不授予覆盖率信用（`evidence.coverage` 为空）。

## 五、组合矩阵现状

| 格 | 状态 |
|---|---|
| A×B / A×C / A×D / A×E / B×D / C×D / D×D / D×F / D×H / E×F | 已覆盖（有具体用例文件） |
| B×C 位置冲突 | 已覆盖（`test_conditional_prefix.py` 弱 provider：`middle_repair=1`，Main 取 C，最终仍发布 taken@2 的 D） |
| C×H 缓冲清理可见性 | 已覆盖（`BPU-INT-111`） |
| E×D 重定向 + 训练同拍 | 已覆盖（`BPU-INT-110`，含 flush 归属断言） |
| 多预测器同拍撤销 | 已覆盖“比较发生 + 下一拍两窗口全空”（`BPU-INT-108`） |
| G×H PHR 更新与写回同拍 | **已覆盖（本轮构造）**：`BPU-INT-112` 在真实预测流内让训练反馈与重定向同拍（tick 520，origin`355292480`→live`1421169985`），断言下一笔 AheadBTB 读用原件特征 0 而非推进后 1；两候选坐标 `(0,1)`/`(1,1)` 不同，tick 528 DUT 实际 row/bank 等于原件坐标，其后无其它读落在同一坐标。`results/bpu-upstream-20261021-v12`（65 PASS，epoch 3056 changed=0），8 项负对照固定可区分性。 |
| SC×TAGE 共享列 / tag 隔离 | **已覆盖（本轮更正假阴性）**：`BPU-INT-023` 在同一 SC way 上给出单分支 8 拍越阈、双分支 4 拍越阈的定量对照，两个 TAGE provider 的 `(table,way)` 不同且全程签名不变。此前登记为“未联合断言”是错误结论。 |
| SC 全脏写缓冲 | **已判定（本轮）**：改用集成 BPU 已授权的只读 monitor（`shadowValid/dirty` + `io_read_0_ready`）测量 8 个物理排列共 3500 post-reset 周期，10 个 buffer 最大 dirty 均为 1、`full_overwrite` 0 次、排水被拒 13900 buffer-cycle。当前公开程序形状下四槽全脏不可达，属防御路径；模型已支持 `full_miss`。证据 `results/sc-full-dirty-reachability-20261021-v1`。 |

## 六、未闭合项（完整保留）

1. 完整回归仍为 **24776 PASS / 88 FAIL / 3 XFAIL**（24867 收集）；本文件所有选测均不替代它。
2. 已知真实差异：`BPU-ITTAGE-019/020`、`RAS-017/008`、`URAS-016/017`、`UBTB-011`、
   `MBTB-017/025-029`、`ABTB-053`、`UTAGE-025`；三个 UTAGE strict XFAIL：
   007（tag 截断）、016（ring 槽清 dirty，112 失败格）、021（512 地址被 007 阻断）；
   TAGE `BPU-TAGE-026` 为 strict XFAIL。
3. `BPU-INT-044 full-tag-high-bits` 是文档已记录的反例：它指
   `test_early_direction.py` 的 `pc=0x40000800` 那一份参数，只有在选择集包含
   `test_early_direction.py` 时才会出现（v5 出现、v8/v9 未选入）。这**不代表该反例
   已被修复**，只是没有在最近两轮定向运行的选择集里。
4. G×H 已由 `BPU-INT-112` 构造（见第四节）；SC×TAGE 已确认由 `BPU-INT-023` 覆盖；
   SC 全脏写缓冲已由只读 monitor 判定（见第四节）。
5. TAGE `useAltOnNa` 31/0 端点**已覆盖**（此前登记为“未验证”是假阴性）：
   `BPU-INT-072` 用 32 笔反馈把同一桶从 15 推到 0、从 16 推到 31，越界那一拍的
   `lower-saturation`（before 0/after 0/`decrements=1`）与
   `upper-saturation`（before 31/after 31/`increments=1`）都由模型与 DUT 逐项比较；
   八个寄存器每帧全比较。证据 `results/bpu-tage-endpoint-20261021-v1`（48 PASS，
   epoch 3056 changed=0）。原分析文档已更正。
   **2026-10-22 已补齐**：独立 TAGE DUT 上 bucket 0–7 全部到位（四种形态），
   每桶双端点 + 越界钳位，`useAltOnNa` 未覆盖 arm 由 8 降到 **0**
   （`results/tage-selector-full-20261022-v3`，234 PASS/1 XFAIL，epoch 3064）。
6. UTAGE 单端口 SRAM-only 被同 bank 强制写回压掉的最强形式仍未构造（与 UTAGE-016 重叠）。
7. UTAGE 剩余 497 个 branch arm 全在 `BypassShadowBuffer.sv`，按 (bank,set) 逐 cell 副本计；
   1099 行模板审计（367 奖励 + 366 惩罚 + 366 `else if` 头）不变。
8. ABTB 剩余 65 arm 为结构不可达（64 个每 set PLRU 链尾 + 1 个 WriteBuffer 三元 else），
   保留原生分母，不授予功能信用。

## 七、约束

- 未修改 RTL / DUT / SDK。
- 未新增或放宽任何 XFAIL；所有已知缺陷保持严格 XFAIL。
- 覆盖率饱和不等于功能通过；`evidence.coverage` 为空的见证不授予覆盖率信用。
- 选择集变化会改变行数（例如 27404→26169 因 14→12 项），不代表覆盖率下降。
- 运行期修改工作树会使整轮因 epoch 变化作废；本轮所有结论均来自 `changed=0` 的运行。

## 八、本轮运行清单（全部 `changed=0`）

| 运行 | 用例 | 用途 | epoch |
|---|---|---|---|
| `results/bpu-prefix-cleanup-final-20261021-v2` | 97 PASS | INT-111 放行与负对照 | 3055 |
| `results/utage-slot2-upper-20261021-v1` | 256 项：218 PASS / 35 FAIL / 3 XFAIL | UTAGE slot-2 端点臂 | 3055 |
| `results/bpu-upstream-20261021-v8` | 100 PASS | 8 个功能点 + 全部组合见证 | 3055 |
| `results/bpu-upstream-20261021-v9` | 50 PASS | SC×TAGE 复核 | 3055 |
| `results/bpu-upstream-20261021-v12` | 65 PASS | G×H（INT-112） | 3056 |
| `results/bpu-tage-endpoint-20261021-v1` | 48 PASS | TAGE 端点越界断言 | 3056 |
| `results/bpu-final-20261021-v1` | 152 PASS | 11 个功能点 + 3 个负对照文件 + 11 个框架合同 | 3056 |
| `results/bpu-final-20261021-v2` | 160 PASS | 12 个功能点（含 SC 全脏可达性） | 3057 |
| `results/bpu-final-20261021-v3` | 161 PASS | 追加组合层死字段审计（254 拍 / 158 key） | 3058 |
| `results/sc-full-dirty-20261021-v4` | 8 PASS | SC 全脏可达性复现（JUnit 承载数据） | 3057 |
| `tests/bpu/scoreboard` 定向 188 项 | 188 PASS | 检查器/放行/见证负对照 | — |

`BPU-INT-044 full-tag-high-bits` 反例只在选择集含 `test_early_direction.py` 时出现
（v5 有、v8/v9/v12 未选入）；它**没有被修复**，仍按文档保留。

## 九、假阳性/假阴性台账

| 类型 | 项目 | 处理 |
|---|---|---|
| 假阳性（测试侧） | AheadBTB 缓冲清理可见性（4 个 compressed-entry profile） | 证明是单端口读优先的写回缓冲；`BPU-INT-111` 有界放行 + 10 项负对照 |
| 假阴性 | B×C 位置冲突“未构造” | 弱 provider 程序已断言 `middle_repair=1` 与最终 taken@2；已更正矩阵 |
| 假阴性 | SC×TAGE“未联合断言” | `BPU-INT-023` 已有单/双分支越阈对照 + provider 签名不变；已更正 |
| 假阴性 | TAGE `useAltOnNa` 端点“未验证” | 32 笔反馈到 0/31，越界事件逐项比较；已补断言并更正 |
| 真实差异 | 8 个模块的 FAIL 与 3 个 strict XFAIL | 原样保留，未放宽、未跳过 |
| 声明不实 | `BPU-INT-110` docstring 声称 flush 归属却无断言 | 补上 `middle_repair==0 and final_repair==0` |

## 十、完成度审计（逐条对应到证据）

| 完成标准 | 证据 | 状态 |
|---|---|---|
| 每个模块有可读微架构语义功能点 | `verification_plan.json` 363 点（硬件 353）；`BPU-INT-108/109/110/111/112` 六字段合同齐全；`validate_plan` 通过 | 达成 |
| 每个新增/补强点有实际运行证据 | 见第三节 1–6；`results/bpu-prefix-cleanup-final-20261021-v2`、`bpu-upstream-20261021-v8/v9/v12`、`utage-slot2-upper-20261021-v1`、`bpu-tage-endpoint-20261021-v1` 全部 `changed=0` | 达成 |
| 行/toggle/branch 数据与逐项归因 | 第二节模块表（九个模块的运行/用例/三类覆盖/点/组）+ `docs/bpu-coverage-attribution-20261021.md`：逐模块把未命中行/arm 落到文件行号并分类；集成 BPU 剩余未逐项归因的部分在该文档第二节如实标注 | 达成（模块级逐项；集成剩余已标注） |
| 缺口补测后复跑并给出变化 | INT-111（4 profile 由 FAIL→PASS）、UTAGE slot-2（branch +1、toggle +2）、INT-108（新增后拍全空）、INT-112（G×H）、TAGE 端点（补越界断言） | 达成 |
| 区分 RTL 缺陷 / 模型缺陷 / 假阳性 / 假阴性 | 假阳性：INT-111;假阴性：B×C、SC×TAGE、TAGE 端点;真实差异：8 个模块 FAIL 与 3 个 strict XFAIL 原样保留 | 达成 |
| 组合矩阵同拍格、死开关、死字段、握手沿计数复核 | 矩阵 8 个同拍格全有用例;死开关 ABTB/UTAGE `io.redirect` 已修复并有行为用例;检查器逐字段比较;见证按 tick/Transfer 而非电平计数 | 达成 |
| 最终报告保留未闭合项、分母与约束 | 本文件第五节（8 项）与第六节（5 条约束）;完整回归 24776/88/3 始终保留 | 达成 |

**未达成的部分（如实保留，不属于本轮交付缺陷）**：

- SC 全脏写缓冲观测：已用只读 monitor 判定“当前公开程序形状下不可达”，不再阻塞；
  若要把该防御路径也验证到，需要专用的“四笔不同 set_index 的 miss 连续四拍”突发程序。
- UTAGE 单端口 SRAM-only 最强形式：与 strict XFAIL `BPU-UTAGE-016` 重叠，构造会与已知
  缺陷纠缠，未单独做；
- 7 个逐桶钳位 arm 与 UTAGE 497 个逐 cell arm、ABTB 65 个结构 arm：属于按物理副本的
  可选补测，已逐项分类，不授予覆盖信用，也不从分母扣除。

**结论**：本目标要求的验证闭环（语义功能点→用例→运行→覆盖率分析→缺口归因→补测复跑→
最终报告）已对 BPU 全部十个子模块与上级组合矩阵完成并留有可复核证据；DUT 仍有 88 个
真实 FAIL 与 3 个 strict XFAIL，这是**待修复的 RTL/设计问题**，不是验证工作未完成。
