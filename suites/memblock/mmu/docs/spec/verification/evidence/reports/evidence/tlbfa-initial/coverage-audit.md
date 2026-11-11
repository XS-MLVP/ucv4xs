# 覆盖率审计：results/tlbfa-baseline-replay-01

- 覆盖率数据 SHA-256：`53c231b36556f0420a7114e529e236e819c226e5ce2bf14f430f44d2d1111723`

## Verilator 原生点统计（含工具影子点，不删减）

| 类型 | 命中 / 总数 | 百分比 |
|---|---:|---:|
| line | 4 / 166 | 2.40% |
| toggle | 17766 / 17766 | 100.00% |
| branch | 920 / 922 | 99.80% |
| expr | 0 / 0 | 0.00% |
| fsm_state | 0 / 0 | 0.00% |
| fsm_arc | 0 / 0 | 0.00% |

## LCOV 逐行（重复点按行求和，保留全部分母）

- 唯一 DA 行：3836
- 命中行：3422（89.21%）
- 未命中：414，其中过程语句行 324
- DUT-only（排除 Picker harness）：3419 / 3419（100.00%），过程语句未覆盖 0

| 源文件 | 行命中 / 唯一行 | 过程语句未覆盖 |
|---|---:|---:|
| `TlbfaDut.v` (dut) | 3419 / 3419 (100.00%) | 0 |
| `TlbfaDut_top.sv` (picker_harness) | 3 / 417 (0.72%) | 324 |

未命中行全部是声明/连续赋值/end 行；逐行清单见 JSON。

## 分支

- 覆盖 1016 / 1018
- TlbfaDut.v:7151 `cond_then` in `always`：`: s2_exception & _allStage_level_T_3 ? 2'h3 : _GEN_338[io_w_bits_data_s2xlate];`
- TlbfaDut.v:12532 `else` in `initial`：`if (reset) begin`

## Toggle

- 覆盖 17766 / 17766
- 未覆盖按类：

逐点信号名、文件与源行见 JSON 的 `toggles.uncovered_points`。

## 功能覆盖

- `tlbfa.lookup`：100.00%（353 samples）
- `tlbfa.refill`：100.00%（232 samples）
- `tlbfa.ppn`：100.00%（150 samples）
- `tlbfa.payload`：100.00%（240 samples）
- `tlbfa.sfence`：100.00%（28 samples）
- `tlbfa.timing`：100.00%（401 samples）
- `tlbfa.touch`：100.00%（380 samples）
- `tlbfa.reset`：100.00%（33 samples）

Verilator point summaries are not semantic checks. LCOV DA hits are summed per line (duplicate shadow points included) and every denominator is retained. Declarative wire/reg/end lines are separated by source text, not deleted; procedural lines are still listed if uncovered. Files are kept separate so a parent DUT does not hide a child's own gaps.
