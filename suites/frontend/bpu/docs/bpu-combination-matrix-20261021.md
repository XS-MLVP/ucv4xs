# 上级 BPU 组合矩阵（2026-10-21）

> 按 ICache 经验组织：先列输入来源，再逐格检查“同拍交叉”。
> 本文件只登记**能指向具体用例文件**的已覆盖格与**显式未验证**格；
> 不把子模块通过、也不把历史功能点通过当作组合证据。

## 一、输入来源分组

| 组 | 来源 | 公开端口 |
|---|---|---|
| A | 取指请求 / 启动 PC | `io.fromFtq`（startPc、stageCtrl） |
| B | MainBTB 结果 | `io.fromMainBtb.result` |
| C | AheadBTB 结果 | `io.fromAheadBtb` |
| D | FastTrain 反馈（携带 ITTAGE/TAGE/SC/ABTB/UTAGE meta） | `io.train` |
| E | 重定向 | `io.fromFtq.redirect` |
| F | 使能门控 | `io.enable` |
| G | PHR / 历史更新 | `phr` 接口 |
| H | 更新写端口 | 内部 write 端口 |
| I | 复位 | `reset` |

## 二、同拍交叉格（只列有具体文件证据的格）

| 格 | 组合 | 证据文件 | 判定 |
|---|---|---|---|
| A×A | 重叠/背靠背取指 | `tests/bpu/testcase/test_backpressure.py`、`test_concurrent_stream.py` | 已覆盖 |
| A×B | 取指与 MainBTB 命中 | `tests/bpu/testcase/test_meta_coherence.py` | 已覆盖 |
| A×C | 取指与 AheadBTB 槽 | `tests/bpu/testcase/test_abtb_fasttrain.py`、`test_abtb_s3_correction.py` | 已覆盖 |
| A×D | 取指与同拍训练 | `tests/bpu/testcase/test_fresh_feedback.py`、`test_batch_feedback.py` | 已覆盖 |
| A×E | 取指与重定向 | `tests/bpu/testcase/test_redirect_disable.py`、`test_stalled_redirect.py` | 已覆盖 |
| B×D | MainBTB 与学习同拍 | `tests/bpu/testcase/test_adjacent_feedback.py`、`test_cross_pc_feedback.py` | 已覆盖 |
| C×D | AheadBTB 与学习同拍 | `tests/bpu/testcase/test_abtb_cross_region_repair.py` | 已覆盖 |
| D×D | 相邻两笔训练 | `tests/bpu/testcase/test_dual_retirement.py`（如存在）、`test_batch_feedback.py` | 已覆盖 |
| D×F | 训练与禁用 | `tests/bpu/testcase/test_redirect_disable.py`、`test_early_source_isolation.py` | 已覆盖 |
| D×H | 训练与写端口争用 | `tests/bpu/testcase/test_early_source_arbitration.py`、`test_ittage_selection.py` | 已覆盖 |
| E×F | 重定向与禁用同拍 | `tests/bpu/testcase/test_redirect_disable.py` 的 INT-006 | 已覆盖 |
| E×D | 重定向与训练反馈同拍 | `tests/bpu/testcase/test_composition_redirect_training.py`（`BPU-INT-110`） | 已覆盖（事件建模）：同拍启动两个脉冲驱动，实测 tick520 中模型同时构造 Redirect 与 Feedback；不声称碰撞后学习状态一定正确 |
| B×C 位置冲突 | Ahead 与 Main 同拍都 taken 但位置不同（早级 taken@2、Main taken@4） | `tests/bpu/testcase/test_conditional_prefix.py`（弱 provider 四个 profile，`BPU-INT-032/034/044/048`） | 已覆盖（仲裁）：检查器在选中原件的中间拍断言 `cycle.middle_repair=1`、Main 位置为 4 且目标为独立间接目标 C，并在最终拍断言发布预测仍是更早的 taken@2 条件分支 D。该程序同时逐拍比较 `ahead` 与 `main_metadata`，因此是真实的 B×C 位置冲突格；专用 witness `test_composition_main_ahead.py` 仍未构造该格，两者不互相替代 |
| 多预测器同拍撤销（生效） | 单一顶层重定向后，AheadBTB 与 MicroTAGE 两窗口在下一无损比较拍都必须为空 | `tests/bpu/testcase/test_composition_shared_redirect.py`（`BPU-INT-108`） | 已覆盖（撤销生效）：5 个重定向比较拍之后各有 1 个后续比较拍，`ahead.meta_valid`、四个 `ahead.*.valid`、四个 `early_direction.*.valid` 全为 0，`raw_hits` 无 1；且存在重定向前真实命中（tick 434，`ahead_hits=[0,0,1,0]`）的配对，排除空转。`results/bpu-upstream-20261021-v8`（100 PASS，epoch 3055 changed=0） |
| G×H PHR 更新与写回同拍 | Ahead 写回与路径历史推进同拍时，下一笔 AheadBTB 读的索引来源 | `tests/bpu/testcase/test_composition_redirect_training.py`（`BPU-INT-112`） | 已覆盖：tick 520 同拍（origin`355292480`→live`1421169985`），索引用原件特征 0 而非推进后 1；两候选坐标 `(0,1)`/`(1,1)` 不同；tick 528 DUT 实际 row/bank 等于原件坐标；其后无其它读落在同一坐标。8 项负对照固定可区分性。`results/bpu-upstream-20261021-v12` |
| C×H 缓冲清理可见性 | AheadBTB 同一行两份内容相同的副本，清理写回在读优先单端口 bank 中缓冲 | `tests/bpu/testcase/test_conditional_prefix.py`（`BPU-INT-111`） | 已覆盖（组合可见性）：tick 940–970 的 15 个比较拍放行 `ahead.1.valid/micro_valid/meta_hit`、`early_direction.1.valid` 与两个 fast 变体，全部要求与 way3 的 position/kind/action/target_low 完全相同且参考已发出该 row/way 失效；方向/目标/位置/修复字段仍逐字段比较。16 拍读空闲后重读同一行，旧 way 期望与实际均为 0 |

### G×H 同拍格（已构造，2026-10-21）

PHR 历史更新与预测器写回同拍时，写回的 tag 是否使用旧历史。

**内容侧早有硬件证据**：`BPU-INT-028`（`tests/bpu/testcase/test_history_feedback.py`）
在同一 PC 上建立两个不同 PHR 上下文，分别训练后分别回读：原上下文 provider 计数 2、
另一上下文 4；`BPU-INT-106` 的 `joint_train_folds` 更在**每个训练拍**把 DUT 的 TAGE
训练历史与训练原件的 folds 逐项比较。

**同拍格现由 `BPU-INT-112` 构造**（`test_composition_redirect_training.py` 的
`test_next_aheadbtb_index_uses_the_redirect_origin_history`）：

| 层 | 断言 | 实测 |
|---|---|---|
| 同拍发生 | 该拍同时有 Redirect 与 Feedback，且路径历史推进 | tick 520，origin `355292480` → live `1421169985` |
| 索引来源 | 下一笔 AheadBTB 读的四位特征等于原件特征 | `index_used=0 == origin_feature=0` |
| 可区分 | 两候选给出不同 (bank,row)，且 `index_used != live_feature` | origin `(0,1)` vs live `(1,1)` |
| 硬件侧 | 呈现该读的比较拍，期望与 DUT 实际 row/bank 都等于原历史坐标 | tick 528：期望 row1/bank0，实际 row1/bank0 |
| 可归属 | 其后没有其它选择读落在同一坐标 | 后两笔读坐标不同 |

必须等“后面某一拍”：重定向当拍呈现帧已无效（tick 520 `frame_valid=False`），
该读要到 tick 528 才呈现 row/bank；在当拍断言就是造 RTL 不满足的期望。

负对照 `tests/bpu/scoreboard/test_redirect_training_index_witness.py`（8 项纯检查）
固定“16 个原件特征都存在可区分目标”与 `coordinate()` 与独立公式一致。

证据：`results/bpu-upstream-20261021-v12`（65 PASS，epoch 3056 `changed=0`）。

**已撤回的错误尝试**（供后续参考）：在 FTQ 无有效在途条目时裸驱动同拍重定向，
DUT 返回未初始化预测（大 target），这是激励前提错误；正确做法是嵌入真实预测流，
本轮即按此完成。

## 三、显式未验证的格

以下格**没有**任何用例把两个来源放在同一个采样沿竞争同一份状态；
仅时间上先后发生的两个操作不算组合。

1. **B×C（比较见证已有；位置冲突由另一程序覆盖）**：`BPU-INT-109` +
   `tests/bpu/testcase/test_composition_main_ahead.py` 现在证明存在 **29** 拍同时比较
   `ahead` 与 `main_metadata`，其中 **13** 拍两边都有真实命中，且 **3** 拍
   （tick 400/402/404）早级来源属于 AheadBTB 来源并同时存在 S2 选择——即仲裁给出了
   确定答案而非静默退回 fallthrough。见 `results/bpu-upstream-20261021-v4/README.md`。

   该 witness 程序本身没有构造位置冲突：29 个双窗口比较拍 `repair2=0`。但这不等于
   B×C 位置冲突格未被覆盖——`test_conditional_prefix.py` 的弱 provider 程序在同一
   PC 上让 Ahead 预测 taken@2（target D）、Main 预测 taken@4（indirect C），检查器
   断言 `middle_repair=1`、Main 目标为 C、最终发布预测仍为更早的 taken@2 条件分支 D，
   四个弱 profile 全部通过。因此位置冲突的**取舍**已由该程序覆盖；专用最小 witness
   仍未构造，不能把两者混为同一份证据。
2. **多预测器同拍撤销（比较与生效两层都已有证据）**：ABTB 与 UTAGE 的
   `io.redirect` 已分别在子模块内验证（`BPU-ABTB-054`、`BPU-UTAGE-026`）。
   `BPU-INT-108` + `tests/bpu/testcase/test_composition_shared_redirect.py` 现在证明：
   (a) 顶层同一个 `io.fromFtq.redirect` 在**同一拍**被独立检查器对**两个窗口同时比较**
   （5 拍，其中 1 拍 ABTB 有真实命中）；(b) 每个重定向拍之后的**下一无损比较拍**，
   `ahead.meta_valid`、四个 `ahead.*.valid`、四个 `early_direction.*.valid` 全为 0，
   `raw_hits` 无 1，且存在重定向前真实命中的配对（tick 434）。
   仍然不证明的是“撤销后重新查询能恢复原 provider”——那由两个子模块用例分别承担。
   见 `results/bpu-upstream-20261021-v6/README.md`。
3. **SC×TAGE 共享统计与 tag 隔离（已覆盖，本轮更正）**：此前登记为“未联合断言”，
   这是**假阴性**。`BPU-INT-023`（`tests/bpu/testcase/test_sc_same_way_feedback.py`）
   已经构造了完整的共享/隔离对照：

   - `SC_SAME_WAY_POSITIONS` 的两个条件分支落在**同一个 SC way**（共享权重列）；
   - 两个分支的 TAGE provider 在 `(table, way)` 上**不同**（`baseline_providers[0][:2]
     != baseline_providers[1][:2]`，计数同为 2），即 tag 隔离；
   - 只训练一个分支：4 拍不越过 SC 阈值（`(0,0,0)`），8 拍才越过（`(0,1,1)`）；
   - 同一 4 拍内训练两个分支：**4 拍**即越过同一阈值（`(0,1,1)`），证明 SC 权重列
     确实被两分支共享累加；
   - 上述每一步之后 `tage_provider_signatures(...)` 都**逐一等于**基线，证明 TAGE
     provider 身份与计数不受 SC 共享列影响。

   也就是说“SC 共享列加速、TAGE 按 tag/表-way 隔离”两侧都有断言，并且有“单分支 8 拍
   vs 双分支 4 拍”的定量对照与 TAGE 不变控制。该用例实测 PASS（本轮单独复核
   `pytest tests/bpu/testcase/test_sc_same_way_feedback.py`：1 passed，11.25 s）。

## 四、检查器审计（组合层）

| 项目 | 结论 |
|---|---|
| 全局静音 | 未发现整段关闭；已发现的放行都在子模块内且为事件/字段级 |
| 死开关 | 已发现并修复两处：ABTB `io.redirect`、UTAGE `io.redirect`；组合层是否还有同类问题**未系统排查** |
| 死字段 | 子模块 checker 逐字段比对；组合层 `bpu.owned-pipeline` 的字段覆盖**未核对** |
| 计数 | 子模块按握手沿/Transfer 计数；组合层按 tick 关联，未发现按电平计数 |
| 有界放行 | 新增一处：`BPU-INT-111` 的 AheadBTB 缓冲清理可见性。放行条件为（a）额外 way 与参考命中 way 的 position/kind/action/target_low 完全相同，（b）参考 memory 已无效且持有同一 bank/row/way 的失效版本，（c）只删除 absence 标记（`valid/micro_valid/meta_hit/hit`），预测字段不参与。每个 bank/row/way 另设 64 拍上限，超出即判失败。每次放行记录 tick、bank、row、way、幸存 way 与字段；4 个 compressed-entry profile 各 15 拍/30 项（tick 940–970），conditional-entry profile 为 0。16 拍预测保持的空闲窗口后重读同一行 16 次，旧 way 的期望=实际=0。5 类负对照共 10 项纯检查全部拒绝放行 |

## 五、结论

- 组合矩阵的空档集中在**预测器之间的同拍交互**与 **PHR 更新/预测器写回同拍**。
- 多预测器同拍撤销已从“只证明比较发生”推进到“下一拍两窗口确实为空”。
- 这些格不能靠增加 bank/set 补，需要专门的多源同拍程序。
- 本轮**没有**为这些格写用例，因此它们仍是未验证状态；不声称上级组合已完成。
