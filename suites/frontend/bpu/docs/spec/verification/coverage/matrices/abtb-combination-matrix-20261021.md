# AheadBTB 组合矩阵与检查器审计（2026-10-21）

> 结构沿用 ICache 验证经验：先按输入来源分组，再逐格检查“同拍交叉”。
> 每一格要么已有真实用例，要么显式登记为未验证并写出原因；不把覆盖率
> 或“模型里有字段”当作已覆盖。

## 一、输入来源分组

| 组 | 来源 | 公开端口/驱动 |
|---|---|---|
| A | 正常查询（S0→S1→S2→S3） | `io.startPc`、`io.stageCtrl`、`io.normalPathHist` |
| B | FastTrain 反馈（单拍/相邻） | `io.fastTrain` |
| C | S2/S3 纠正恢复 | `io.bpuS2Override` / `io.bpuS3Override`、`io.overrideStartPc` |
| D | 重定向 | `io.redirect` |
| E | 使能门控 | `io.enable` |
| F | 单端口 bank 读/写冲突 | `io.readValid`/`io.writeValid`（内部只读观测） |
| G | 替换策略 touch / victim | `AheadBtbReplacer` |
| H | 同位置重复命中清理 | `detectMultiHit` |
| I | 复位 | `reset` |

## 二、同拍交叉格

| 格 | 组合 | 用例/证据 | 判定 |
|---|---|---|---|
| A×A | 背靠背/重叠查询 | `test_pipeline_payload`、`test_semantic_reference`、`test_position_order` | **已覆盖**：按请求关联，逐笔比较 |
| A×B | 查询与反馈同一 set | `test_buffered_training`、`test_state_matrix` | **已覆盖**：读优先，写保持 pending |
| A×C | 查询与 S2 恢复同拍 | `test_override`、`test_flanked_recovery` | **部分覆盖**：顺序恢复已验证；与同拍反馈的组合未构造 |
| A×D | 查询与重定向同拍 | `test_redirect_flush`（本轮新增，PASS） | **已覆盖**：在途窗口整体无效，学习记录保留 |
| A×E | 查询与禁用同拍 | `test_enable` | **已覆盖**：禁用期不发布预测 |
| A×F | 读与强制写回同 bank | `test_state_matrix`、`drain_bank_writes` | **部分覆盖**：读优先已检查；`readValid & writeValid` 同 set 的替换状态交叉未单独构造 |
| A×G | 查询 touch 替换年龄 | `test_position_replacement`、`test_replacement` | **已覆盖**：查询不 touch；taken hit/提交才 touch |
| A×H | 同位置双重命中清理 | `test_multi_hit_cleanup`、`test_multi_hit_cleanup_pairs`（本轮新增） | **已覆盖**：四组 way 对 (0,2)(2,3)(1,3)(0,3) 都在 6 轮内出现并要求清理后只剩新副本 |
| B×B | 相邻反馈写同一 set | `test_buffered_training`、`test_state_matrix` | **已覆盖** |
| B×C | 反馈与恢复同拍 | `test_flanked_recovery` | **部分覆盖** |
| B×E | 禁用边界与在途反馈 | `test_enable` | **已覆盖** |
| C×D | 恢复与重定向同拍 | 探针 `test_probe_model.py`（已删）+ 本节记录 | **语义待确认**：见下"六" |
| E×I | 复位释放与首个查询 | `agent.reset()` + 每用例首查 | **已覆盖** |
| H×B | 清理写与反馈写竞争 | `test_multi_hit_cleanup_pairs` 的 drain 窗口 | **部分覆盖**：清理优先已观察，反馈同拍未构造 |

## 三、本轮修正的死开关：`io.redirect`

- `AbtbPorts` 早就绑定了 `io.redirect`，monitor 也解码 `redirect`，独立模型
  在 `advance` 里明确用它清 `frame.valid` 与 `read_ticket`。
- 但 `AbtbAgent` 的两处编码都硬写 `"redirect": 0`，**任何用例都没有驱动它**。
  这正是 ICache 经验里的“死开关”：代码看起来支持，实际没有激励。

修复：

1. `AbtbLookup` 增加 `redirect: bool`；
2. `_encode_lookup` 编码真实值，`submit_predict` 校验必须是显式 bool；
3. 新增 `test_redirect_flush.py`（PASS）：
   - 已训练记录命中后，在途查询遇到相邻拍重定向 → 该窗口 `meta_valid=0` 且全部 way `valid=0`；
   - 随后同 PC 查询仍命中，目标/位置/类型原样保留 → 撤销的是发布资格，不是学习；
   - idle 重定向脉冲不制造也不销毁记录。
4. 功能点 `BPU-ABTB-054` 写入 `verification_plan.json`。

检查器同步做了一处**收窄而非放宽**：当模型不再拥有有效 frame 时，不再要求
“必须有 owned transaction”，而是要求**实际响应必须是完整 flush**；一旦 DUT
发布了任何预测字段仍然失败。原先的 `no owned read transaction` 断言会把机制上
正确的 flush 报成错误。

## 四、检查器审计

| 项目 | 结论 |
|---|---|
| 全局静音 | ABTB 环境没有放行开关；`OBSERVE_ONLY` 已被默认 checker 取代 |
| 死字段 | `prediction_values` 对 `meta_valid/valid/micro_valid/taken/target/position/kind/action/strong/target_low/row/banks` 均有观测映射；未发现只在模型计算而从不比较的字段 |
| 死开关 | `io.redirect`（本轮修复）；`path_hash` 的 16 个取值由 `test_hash_*` 覆盖 |
| 计数方式 | 预测按 Scoreboard 每笔 Transfer 计数；训练按 `ActivityMonitor` 等待空闲，不是固定 sleep |
| 断言可见性 | 生成 RTL 已裁掉 Scala 断言；全部检查由公开输出与只读 bank 观测承担 |

## 五、仍开放的格

1. `C×D`：恢复与重定向同拍，二者的撤销优先级无公开证据。
2. `A×F` 的最强形式：`readValid & writeValid & 同 set` 时 PLRU 状态更新的顺序。
3. `A×C` / `B×C` 的同拍版本（现有恢复用例都是顺序的）。
4. 完整 FTQ 寿命与组合 BPU 仲裁不在本 UT 合同内。

## 六、C×D（恢复与重定向同拍）：一个未被确认的语义问题

本轮曾把“重定向必须吞掉同拍恢复”写成功能点 `BPU-ABTB-055`，并据此断言
`meta_valid=0`。逐拍探针否定了这个假设：

```
collision 提交后：
cycle 0 (tick 166)  actual_valid 0   model_meta_valid 0   <- 撤销当拍窗口
cycle 1 (tick 168)  actual_valid 1   model_meta_valid 1   <- 重放旧目标
cycle 2..5          actual_valid 1   model_meta_valid 1
```

**模型与 RTL 一致**：重定向只撤销当拍窗口，而这次请求本身带来的恢复重放
会在后续拍发布。这与 `BPU-ABTB-016/017` 的措辞并不冲突——那里禁止的是
“已消费/已撤销的旧资格在`redirect`之后复活”，而这里是**本次请求主动请求的修复**。

因此本轮：
- **撤回** `BPU-ABTB-055` 与该断言（不把假设固化成功能点）；
- 不把它记为 PASS（模型与 RTL 一致不自动等于语义正确）；
- 保留这个待确认问题：当 `redirect` 的目标与 `overrideStartPc` **不同**时，
  ABTB 仍发布一个属于旧目标的重放。BPU 顶层是否可能产生这种组合、消费端
  是否会因此取错目标，需要集成级证据；本轮只有 ABTB 独立 UT 的观察。

记录在案而不是猜结论，是这一格目前的处理方式。
