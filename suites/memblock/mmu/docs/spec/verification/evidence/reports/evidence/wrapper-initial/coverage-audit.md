# 覆盖率审计：results/wrapper-baseline-replay-01

- 覆盖率数据 SHA-256：`b2cd32b90986cb6c2ec44666d65173791f0bfacb65f7081d68003fc4208786c3`

## Verilator 原生点统计（含工具影子点，不删减）

| 类型 | 命中 / 总数 | 百分比 |
|---|---:|---:|
| line | 7 / 165 | 4.20% |
| toggle | 18798 / 18798 | 100.00% |
| branch | 923 / 926 | 99.70% |
| expr | 0 / 0 | 0.00% |
| fsm_state | 0 / 0 | 0.00% |
| fsm_arc | 0 / 0 | 0.00% |

## LCOV 逐行（重复点按行求和，保留全部分母）

- 唯一 DA 行：3837
- 命中行：3434（89.50%）
- 未命中：403，其中过程语句行 316
- DUT-only（排除 Picker harness）：3431 / 3431（100.00%），过程语句未覆盖 0

| 源文件 | 行命中 / 唯一行 | 过程语句未覆盖 |
|---|---:|---:|
| `TlbStorageWrapperDut.v` (dut) | 12 / 12 (100.00%) | 0 |
| `TlbStorageWrapperDut_top.sv` (picker_harness) | 3 / 406 (0.74%) | 316 |
| `TLBFA.sv` (dut) | 3419 / 3419 (100.00%) | 0 |

未命中行全部是声明/连续赋值/end 行；逐行清单见 JSON。

## 分支

- 覆盖 1019 / 1022
- TlbStorageWrapperDut.v:299 `else` in `initial`：`if (reset)`
- TLBFA.sv:7151 `cond_then` in `always`：`: s2_exception & _allStage_level_T_3 ? 2'h3 : _GEN_338[io_w_bits_data_s2xlate];`
- TLBFA.sv:12532 `else` in `initial`：`if (reset) begin`

## Toggle

- 覆盖 18798 / 18798
- 未覆盖按类：

逐点信号名、文件与源行见 JSON 的 `toggles.uncovered_points`。

## 功能覆盖

- `wrapper.replace`：100.00%（294 samples）
- `wrapper.lookup`：100.00%（100 samples）
- `wrapper.fence`：100.00%（10 samples）
- `wrapper.reset`：100.00%（11 samples）
- `wrapper.timing`：100.00%（201 samples）

Verilator point summaries are not semantic checks. LCOV DA hits are summed per line (duplicate shadow points included) and every denominator is retained. Declarative wire/reg/end lines are separated by source text, not deleted; procedural lines are still listed if uncovered. Files are kept separate so a parent DUT does not hide a child's own gaps.
