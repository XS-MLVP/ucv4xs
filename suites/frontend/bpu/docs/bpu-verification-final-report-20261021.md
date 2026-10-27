# BPU UT 验证最终报告（2026-10-21 起，2026-10-22 更新：TAGE selector 闭合 + 全量回归）

> 结论先行：按模块层次（ITTAGE → RAS → MicroRAS → MicroBTB → MainBTB → TAGE →
> SC → MicroTAGE → AheadBTB）与上级 BPU 组合的语义功能点—用例—运行—覆盖率—
> 归因—补测—复跑闭环已全部执行并留有可复核证据。DUT 仍有 **88 个真实 FAIL 与
> 3 个 strict XFAIL**，那是**待修复的设计问题**，不是验证工作未完成。
> 完整回归边界 **24776 PASS / 88 FAIL / 3 XFAIL** 始终保留，任何选测都不替代它。
>
> **2026-10-22 更新（全量）**：仓内全部 **29907 个用例**已一次跑完：
> **29777 PASS / 123 FAIL / 7 XFAIL**，功能点 **353/353 执行（100%）**，
> 功能组 673 组中 566 组 100%，`source_epoch_unchanged=true`。
> 与上一轮 1031 个共有节点逐节点比对：**旧 PASS→新 FAIL = 0**。
> 集成 BPU 残差现已逐发射点归因（8411 行 / 11 文件 / 最大单点 929 份副本；
> 唯一非副本残差只有 `CommonHR.sv:869-871` 与 `MicroRas.sv:133-134` 共 5 行）。
> 详见 `docs/full-regression-20261022.md`。
>
> **2026-10-22 更新**：TAGE `useAltOnNa` 的 8 个语义桶已全部补齐双端点 + 越界钳位证据
> （`results/tage-selector-full-20261022-v3`，234 PASS/1 XFAIL，branch 1513→1533、
> toggle +40，未覆盖 `useAltOnNa` arm 8→0）。第六节第 6 项随之从“未闭合”改为“已闭合”。

## 一、模块进展（各自定向选测，均为 `changed=0`）

| 模块 | 运行 | 用例 | 源码行 | Branch | Toggle | 功能点 | 组 |
|---|---|---|---:|---|---|---|---|
| ITTAGE | `ittage-late-source-qualification-20261020-v2` | 33P/4F | **1398/1398** | 655/658 | 12698/18994 | 17/20 | 13/16 |
| RAS | `ras-module-qualification-20261020-v4` | 20P/5F/1X | 569/585 | 200/216 | 3382/7720 | 15/17 | 9/14 |
| MicroRAS | `uras-module-qualification-20261020-v3` | 23P/4F | **91/91** | **24/24** | 382/3976 | 15/17 | 6/9 |
| MicroBTB | `ubtb-module-qualification-20261020-v2` | 40P/2F | **794/794** | 188/192 | 3653/8430 | 16/17 | **15/15** |
| MainBTB | `mbtb-module-qualification-20261020-v2` | 110P/10F | 1007/1056 | 385/442 | 7328/11830 | 24/30 | 32/43 |
| TAGE | `tage-selector-full-20261022-v3` | 234P/1X | 4467/4587 | **1533/1598** | **10751/15514** | 35/36 | 27/28 |
| SC | `sc-module-qualification-20261020-v2` | 51P | 3145/3481 | 890/1038 | 10518/15076 | **23/23** | **28/28** |
| MicroTAGE | `utage-slot2-upper-20261021-v1` | 218P/35F/3X | 9954/11053 | 3249/3746 | 9152/13376 | 13/27 | 57/74 |
| AheadBTB | `abtb-final-20261021-v4` | 75P/1F | **17854/17854** | 4811/4876 | 11984/16320 | 50/51 | 59/60 |
| **上级 BPU** | `bpu-final-20261021-v3` | **161P** | 1712/8236¹ | 6131/13756¹ | 65733/103292¹ | **12/12** | — |

¹ 选测口径（23 个硬件用例），不与完整回归的 37998/46541 比较。

集成 BPU 完整回归：**37998/46541 行**（81.6%）。

## 二、本轮修复的证据不严（假阳性 / 假阴性 / 声明不实）

| 类型 | 项目 | 处理与证据 |
|---|---|---|
| **假阳性** | AheadBTB 清理写回缓冲被误判为 RTL 漏清（4 个 compressed-entry profile） | 逐拍证明参考已发失效、DUT 额外副本内容逐字段相同 → 单端口读优先的写回缓冲。`BPU-INT-111` 有界放行（内容相同 + 已发失效 + 只删 absence 标记 + 同 bank/row/way ≤64 拍），16 拍空闲后重读必须为 0；**10 项纯负对照**拒绝五类差异。`results/bpu-prefix-cleanup-final-20261021-v2` 97 PASS。 |
| **假阴性 1** | B×C 位置冲突“未覆盖” | `test_conditional_prefix.py` 弱 provider 已断言 `middle_repair=1`、Main 取独立间接目标 C、最终仍发布 taken@2 的 D；四个弱 profile 全 PASS。 |
| **假阴性 2** | SC×TAGE“未联合断言” | `BPU-INT-023` 已给出同一 SC way 上单分支 8 拍越阈、双分支 4 拍越阈，两个 TAGE provider `(table,way)` 不同且签名全程不变。根因是**按文件名判断覆盖而未读断言**。 |
| **假阴性 3** | TAGE `useAltOnNa` 31/0 端点“未验证” | `BPU-INT-072` 用 32 笔反馈把同一桶从 15→0、16→31，越界那一拍仍有真实 `dec/inc` 投票而寄存器停在端点；八寄存器每帧全比较。本轮另补“越界事件必须存在”的断言（原先只断言末值）。`results/bpu-tage-endpoint-20261021-v1` 48 PASS。 |
| **假阴性 4** | “slot 1/slot 3 UTAGE 臂仍未命中” | 全量选测下该区间原本只缺 `UtageDut.v:1133`，其余是**只跑 2 条用例的探针假象**；本轮 1133 归零后该区间未命中为空。 |
| **假阴性 5** | TAGE “bucket 4/6 需要替代项在投票后仍 ≥5” | 这条 2026-10-21 的机制结论是**错误假设**（默认 `altConf` 只能来自替代项）。实际还有两种稳定形态：饱和负向替代项（计数 0，继续 not-taken 训练也不动）与**直接分配到 table 2/3 且无替代项**（`altConf` 取自 base 计数，而 base 每拍由调用方重给、不训练）。改用后者后 bucket 4/6 一次到达双端点，8/8 桶全部闭合。用例已断言 `altOrBasePred == 0` 形态不变量，防止该假设回退。 |
| **声明不实** | `BPU-INT-110` docstring 声称 flush 归属却无断言 | 补上 `middle_repair==0 and final_repair==0`。教训：docstring 每条声明都要有对应断言。 |
| **真实 Bug** | 88 FAIL + 3 XFAIL（详见第六节） | 全部原样保留，未放宽、未跳过。 |

## 三、本轮新增的功能点与证据

| 功能点 | 语义 | 证据 |
|---|---|---|
| `BPU-INT-111` | AheadBTB 清理写回在单端口 bank 中缓冲时的可见性边界 | 4 profile × 15 拍/30 项放行；conditional-entry 0 放行；10 项负对照 |
| `BPU-INT-112` | 重定向与训练同拍时，下一笔 AheadBTB 读索引必须来自重定向源历史 | tick 520 同拍（origin `355292480`→live `1421169985`），索引 0 vs 推进后 1；坐标 `(0,1)`/`(1,1)` 不同；tick 528 DUT row/bank 等于原件坐标；8 项负对照（16 个特征都有可区分目标） |
| `BPU-INT-108`（加强） | 重定向后下一无损拍两窗口必须全空 | 5 个重定向拍 × 5 个后续拍全空，且重定向前有真实命中 |
| `BPU-INT-110`（加强） | 碰撞拍 flush 归属重定向 | `middle/final repair == 0` 断言 |
| `BPU-INT-072`（加强） | `useAltOnNa` 端点越界并保持 | 0/31 双向 + 越界事件；独立 DUT 另已覆盖全部 8 个桶（见第五节第 6 项） |
| `BPU-SC-019`（加强） | SC 全脏写缓冲可达性 | 8 排列 / 3500 post-reset 周期 / 10 buffer 最大 dirty=1 / `full_overwrite`=0 / 排水被拒 13900 |
| `BPU-UTAGE-008/009`（加强） | 恢复时 slot 2 采用保存的上表 | 真实三分支 beat，`tableId=1/cfiPosition=6/takenCtr_value=4/predTaken=1`；行不变、branch +1、toggle +2 |

## 四、组合矩阵（同拍格）

| 格 | 状态 |
|---|---|
| A×B / A×C / A×D / A×E / B×D / C×D / D×D / D×F / D×H / E×F | 已覆盖（有具体用例文件） |
| B×C 位置冲突 | 已覆盖（弱 provider，`middle_repair=1`） |
| C×H 缓冲清理可见性 | 已覆盖（`BPU-INT-111`） |
| E×D 重定向 + 训练同拍 | 已覆盖（`BPU-INT-110`） |
| 多预测器同拍撤销 | 已覆盖“比较发生 + 下一拍两窗口全空”（`BPU-INT-108`） |
| G×H PHR 推进与写回同拍 | 已覆盖（`BPU-INT-112`） |
| SC×TAGE 共享列 / tag 隔离 | 已覆盖（`BPU-INT-023`） |

### 四之补：组合层死字段分布实测

在同一 `early_direction` 程序的 **254 个被比较拍**上统计 158 个 dotted 字段的取值分布
（`test_composition_field_liveness.py`）：

| 字段族 | 期望侧取值数 | 实际侧取值数 |
|---|---:|---:|
| `prediction.taken` | 2 | 2 |
| `prediction.target` | 8 | 8 |
| `prediction.position` | 3 | 3 |
| `metadata.history.phrLowBits` | 13 | 13 |
| `ahead.meta_valid` / `ahead.row` | 2 / 6 | 2 / 6 |
| `early_source` / `early_direction.history` | 2 / 13 | 2 / 13 |

关键族两侧都在移动，比较不是空转；**77 个字段在本程序中只有 1 个取值**，如实标注为
“未枚举的程序形状”（DUT 报错值仍会失败），不伪造覆盖。

## 五、检查器审计（ICache 经验三项）

| 项 | 结论 |
|---|---|
| 全局静音 | 未发现整段关闭；所有放行都在子模块内且为事件/字段级，并记录每次使用 |
| 死开关 | ABTB 与 UTAGE 的 `io.redirect` 两处均已修复并有行为用例（`BPU-ABTB-054`、`BPU-UTAGE-026`） |
| 死字段 | 新增组合层运行期分布审计：254 拍 / 158 key；关键族两侧都有 2–13 种取值，比较非空转；77 个单值 key 已如实标注为“未枚举情况” |
| 计数口径 | 子模块按握手沿/Transfer 计数；组合见证按 tick 关联，未发现按电平计数 |

## 六、未闭合项（完整保留）

1. 完整回归 **24776 PASS / 88 FAIL / 3 XFAIL**；本报告所有选测均不替代它。
2. 已知真实差异：`BPU-ITTAGE-017/019/020`、`RAS-017/008`、`URAS-016/017`、
   `UBTB-011`、`MBTB-017/025-029`、`ABTB-053`、`UTAGE-025`；
   strict XFAIL：UTAGE-007（tag 截断）、016（ring 槽清 dirty，112 失败格）、
   021（512 地址被 007 阻断）、TAGE-026（provider-way useful 误关联）。
3. `BPU-INT-044 full-tag-high-bits` 是文档已记录的反例，**未修复**；只在选择集含
   `test_early_direction.py` 时出现。
4. **集成 BPU 的未命中：已闭合（2026-10-22）**。全量运行
   `results/full-regression-20261022-v1` 上做逐发射点归因：**8411 行只落在 11 个文件**，
   其中 8406 行（99.94%）是 7 类逐 cell/逐 set/逐槽物理副本（最大单点 929× AheadBtb
   takenCounter、479× BypassShadowBuffer useful、390× Phr 逐 bit）；
   **唯一非副本残差 5 行**：`CommonHR.sv:869-871`（s1 历史从已寄存 r1 回填）、
   `MicroRas.sv:133-134`（S2 override + 非 fire + 真实 push 同拍）。详见
   `docs/full-regression-20261022.md`。归因工具此前只读第一个 DUT（`abtb`）而报告 0，
   该假阴性已修复并有负对照。
5. UTAGE 单端口 SRAM-only 被同 bank 强制写回压掉的最强形式与 strict XFAIL
   `BPU-UTAGE-016` 重叠，未单独构造。
6. **TAGE selector 桶：已闭合（2026-10-22）**。`useAltOnNa` 按
   `2*providerTable + altConf` 索引共 8 个语义桶。新增只读 `TageSelectorMonitor`
   与纯 pull 的 `sample_selectors()` 后，独立 DUT 把 **bucket 0–7 全部**推到两端
   （0 与 31），每桶再投 1 票验证越界钳位、票全部落在同一寄存器、其余寄存器与锚定
   一致。四种稳定形态：`base_conf` 直接当 `altConf`（0/1）、饱和负向替代项（3/5/7）、
   直接分配到 table 2/3 且无替代项（4/6）、冻结强替代项（2）。
   全量 TAGE 选测 branch **1513 → 1533（+20 arm）**、toggle **+40**，行与 FAIL 集合不变
   （`results/tage-selector-full-20261022-v3`，234 PASS/1 XFAIL，epoch 3064）；
   **`useAltOnNa` 未覆盖 arm 8 → 0**，`TageDut.v` 未覆盖 arm 34 → 14。
   bucket 7 另由集成 `BPU-INT-072` 端到端覆盖。
   过程更正：前几轮“bucket 4/6 需要替代项在投票后仍 ≥5”是**错误假设**（以为
   `altConf` 只能来自替代项）；改用无替代项形态后一次到达双端点。各用例都断言了
   形态不变量，防止这个假设回退。
7. 497 个 UTAGE 逐 cell 臂、65 个 ABTB 结构 arm、49 个 MainBTB 逐 set PLRU 副本、
   77 个单值组合字段：均为物理副本或未枚举情况，保留分母、不授予覆盖信用。
8. B×C 专用最小 witness 仍未构造（该格已由弱 provider 程序覆盖）。

## 七、约束

- 未修改 RTL / DUT / SDK。
- 未新增或放宽任何 XFAIL；已知缺陷保持严格 XFAIL。
- 覆盖率饱和不等于功能通过；`evidence.coverage` 为空的见证不授予覆盖率信用。
- 选择集变化会改变行数（如 27404→26169 因 14→12 项），不代表覆盖率下降。
- 所有结论来自 `--epoch-delta changed=0` 的运行；运行期工作树保持冻结。

## 八、证据索引

| 主题 | 路径 |
|---|---|
| 组合矩阵 | `docs/bpu-combination-matrix-20261021.md` |
| 覆盖率逐项归因 | `docs/bpu-coverage-attribution-20261021.md`（含集成 BPU 逐发射点表与 `residual-attribution.json`） |
| 阶段汇总（含运行清单/假阳性台账） | `docs/bpu-verification-stage-report-20261021.md` |
| 语义参考模型 | `docs/semantic-reference-models.md` |
| TAGE 端点分析（已更正） | `docs/tage-selector-endpoint-analysis-20261021.md` |
| UTAGE 组合矩阵 | `docs/utage-combination-matrix-20261020.md` |
| 最终定向运行 | `results/bpu-final-20261021-v3/`（161 PASS，epoch 3058） |
| 最终审计运行（归因工具 + 死字段） | `results/bpu-final-20261021-v5/`（52 PASS，epoch 3060） |
| SC 全脏可达性 | `results/sc-full-dirty-reachability-20261021-v1/` |
| UTAGE slot-2 | `results/utage-slot2-upper-20261021-v1/` |
| AheadBTB 模块 | `results/abtb-final-20261021-v4/` |
| TAGE 模块（含 selector 桶 0–7 端点） | `results/tage-selector-full-20261022-v3/` |
| TAGE 模块（上一轮基线） | `results/tage-module-qualification-20261020-v5/` |
| SC 模块 | `results/sc-module-qualification-20261020-v2/` |
