# MissTrack UT 报告（2026-10-24）

> 数字仍以本报告的独立运行为准；在 2026-10-25 的全量回归
> `results/full-regression-11`（202 passed + 3 xfailed，61 功能组 100%）中，本 DUT 的分母未变，
> 结论继续有效。根因/语义修正记录见 `functional-point-audit-20261025.md`。

## 1. 结论

| 项 | 结果 |
|---|---|
| 运行 | `results/mt-initial-10`（13 用例，固定 seed 1） |
| 功能覆盖 | **100%**（spec / event / table / lifecycle） |
| DUT 行覆盖 | **934 / 934 = 100%** |
| 分支覆盖 | **172 / 174 = 98.9%**（2 项不可达，见 4.2） |
| Toggle 覆盖（DUT-only） | **12054 / 12804 = 94.14%** |

## 2. 功能点与用例

| 功能点 | 用例 |
|---|---|
| MT-FP-001 安装 resident | `test_install_produces_resident_entry` |
| MT-FP-002 分配 pending / owner 退休 | `test_alloc_pending_and_owner_retirement` |
| MT-FP-003 s2 命中训练 | `test_s2_hit_training` |
| MT-FP-004 S0→S1 查询 | `test_reset_and_unknown_candidate`、`test_datapath_bit_sweep` |
| MT-FP-005 多命中抑制 | `test_multi_hit_suppression` |
| MT-FP-006 失效/清除 | `test_invalidate_resident_and_not_pending`、`test_clear_suppresses_and_empties` |
| MT-FP-007 事件合并/优先级 | `test_event_priority_and_coalescing`、`test_events_refresh_all_existing_entries` |
| MT-FP-008 替换/age | `test_victim_selection_and_age_saturation` |
| MT-FP-009 retained 气泡 | `test_retained_result_on_bubble` |
| 合法随机混合 | `test_random_traffic` |

## 3. 实测语义（与直觉不同之处）

1. **顶层只引出 valid/candidate**：resident/pending/mshr_id 是内部分类，验证时以
   “candidate=0” 表示表项命中，以 candidate=1 表示 UNKNOWN。
2. **同拍不同 line 的事件竞争单端口 RRArbiter**：install 与 alloc 指向不同 line 时
   两者不会都写入；RRArbiter 从 `lastGrant+1` 开始轮转，因此 alloc（事件 1）会先于
   install（事件 0）获得插入机会。已有记录的事件更新优先于插入。
3. **retained/retainedMulti 无复位**：仿真时间 0 的随机值会让“S1 有效但上一拍没有
   S0”的查询产生不确定的抑制。真实 load 流水不会这样驱动；验证在 S1 前保证 S0 有效，
   并在功能点中记录该寄存器的无复位性质。
4. **替换策略使 slot15 长期不被选中**：age 饱和后同 age 取最低索引；slot15 是最后
   被填充、通常最年轻的槽，稳定状态下不会被淘汰。位扫描用例通过 clear+逐项填充，
   让每个槽都能被写入不同地址值。

## 4. 覆盖率缺口逐项归因

### 4.1 行覆盖

934/934 全部命中：包括事件更新、victim 选择、owner 退休、invalidate/clear、
RRArbiter 全部插入路径。

### 4.2 分支（2 项未覆盖）

| 位置 | 分支 | 归因 |
|---|---|---|
| `MissTrackDut.v:4758` | 时间零 `initial` 的 else | 只在仿真时间 0 执行一次 |
| `RRArbiter8_MissTrackEntry.sv:181` | `? 3'h5` 三元选择 | RRArbiter 的第 5 号请求（training lane0）组合优先级路径；本 DUT 的 8 事件组合下，获仲裁的总是更早的请求或 fallback，未观察到该分支。RRArbiter 的其余 17 个分支均覆盖，属复用库单元的低风险盲区 |

### 4.3 Toggle（DUT-only 750 点未覆盖）

| 类别 | 数量 | 归因 |
|---|---:|---|
| `retained_*_block_paddr` | 129 | retained 只在 S0 有效时写入；随机查询大多未命中表项，block 载荷为 0。已用三 lane 随机查询改善，剩余高位需要“匹配表项的随机 block”才能双向翻转 |
| `oldestVictimOH` | 16 | 替换 one-hot 的 16 个槽位中，slot15 在稳态下因 age tie 规则永不被选中（见 3.4），对应位不会有效 |
| `entries_8..15` 的 idx/way/mshr/hash | 约 600 | 固定 16 项填充模式下部分高位字段只被写过单方向；不影响功能检查 |

所有功能点与行覆盖已闭合；toggle 残差是生命周期/替换策略与载荷随机性造成的观测限制，
不是新的功能点缺失。

## 5. 证据

- `results/mt-initial-10/manifest.json`、`functional-coverage.json`、`coverage-audit.json`
- `manifest/rtl-sha256.json`（`miss_track` 3 个 RTL 文件）
- `results/builds/20261024T112723389513Z-miss_track/report.json`
