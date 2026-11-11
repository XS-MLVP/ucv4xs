# 覆盖率审计：results/tlb-baseline-replay-01

- 覆盖率数据 SHA-256：`1b8f4e1c7cda94a6703cd2a736142e5ccecd98ddae721a607be4c8de53d1a830`

## Verilator 原生点统计（含工具影子点，不删减）

| 类型 | 命中 / 总数 | 百分比 |
|---|---:|---:|
| line | 14 / 216 | 6.50% |
| toggle | 18716 / 23074 | 81.10% |
| branch | 993 / 1008 | 98.50% |
| expr | 0 / 0 | 0.00% |
| fsm_state | 0 / 0 | 0.00% |
| fsm_arc | 0 / 0 | 0.00% |

## LCOV 逐行（重复点按行求和，保留全部分母）

- 唯一 DA 行：4169
- 命中行：3647（87.48%）
- 未命中：522，其中过程语句行 415
- DUT-only（排除 Picker harness）：3644 / 3657（99.64%），过程语句未覆盖 13

| 源文件 | 行命中 / 唯一行 | 过程语句未覆盖 |
|---|---:|---:|
| `TlbDut.v` (dut) | 145 / 158 (91.77%) | 13 |
| `TlbDut_top.sv` (picker_harness) | 3 / 512 (0.59%) | 402 |
| `DelayN_3.sv` (dut) | 16 / 16 (100.00%) | 0 |
| `DelayN_5.sv` (dut) | 52 / 52 (100.00%) | 0 |
| `TLBFA.sv` (dut) | 3419 / 3419 (100.00%) | 0 |
| `TlbStorageWrapper.sv` (dut) | 12 / 12 (100.00%) | 0 |

### 未覆盖过程语句行（必须逐项定位）

| 文件:行 | 源码 |
|---|---|
| TlbDut.v:701 | `if (_readResult_T_12)` |
| TlbDut.v:702 | `need_gpa_vpn <= 38'h0;` |
| TlbDut.v:704 | `need_gpa_vpn <= req_out_0_vaddr[49:12];` |
| TlbDut.v:708 | `resp_gpa_gvpn <=` |
| TlbDut.v:710 | `? _GEN_16` |
| TlbDut.v:714 | `? {io_ptw_resp_bits_s1_entry_ppn, _GEN_17}` |
| TlbDut.v:715 | `: _GEN_18[io_ptw_resp_bits_s1_entry_level];` |
| TlbDut.v:877 | `else begin` |
| TlbDut.v:878 | `resp_s1_level <= io_ptw_resp_bits_s1_entry_level;` |
| TlbDut.v:879 | `resp_s1_isLeaf <=` |
| TlbDut.v:881 | `& io_ptw_resp_bits_s1_entry_v;` |
| TlbDut.v:882 | `resp_s1_isFakePte <=` |
| TlbDut.v:884 | `& ~io_ptw_resp_bits_s1_af;` |

## 分支

- 覆盖 1089 / 1104
- TlbDut.v:446 `cond_then` in `unknown`：`_GEN_3 ? io_ptw_resp_bits_s1_entry_level : io_ptw_resp_bits_s2_entry_level;`
- TlbDut.v:505 `cond_then` in `unknown`：`? ptw_resp_bits_reg_s1_entry_level`
- TlbDut.v:703 `if` in `always`：`else if (_readResult_T_22)`
- TlbDut.v:705 `else` in `always`：`if (_GEN_9) begin`
- TlbDut.v:710 `cond_then` in `always`：`? _GEN_16`
- TlbDut.v:710 `cond_else` in `always`：`? _GEN_16`
- TlbDut.v:714 `cond_then` in `always`：`? {io_ptw_resp_bits_s1_entry_ppn, _GEN_17}`
- TlbDut.v:714 `cond_else` in `always`：`? {io_ptw_resp_bits_s1_entry_ppn, _GEN_17}`
- TlbDut.v:798 `cond_then` in `always`：`_GEN_3 ? io_ptw_resp_bits_s1_entry_level : io_ptw_resp_bits_s2_entry_level;`
- TlbDut.v:875 `else` in `always`：`if (_GEN_9) begin`
- TlbDut.v:968 `else` in `initial`：`if (reset) begin`
- TLBFA.sv:7150 `cond_then` in `always`：`? io_w_bits_data_s1_entry_level`
- TLBFA.sv:7151 `cond_then` in `always`：`: s2_exception & _allStage_level_T_3 ? 2'h3 : _GEN_338[io_w_bits_data_s2xlate];`
- TLBFA.sv:12532 `else` in `initial`：`if (reset) begin`
- TlbStorageWrapper.sv:299 `else` in `initial`：`if (reset)`

## Toggle

- 覆盖 18716 / 23074
- 未覆盖按类：
  - `other`：4358

逐点信号名、文件与源行见 JSON 的 `toggles.uncovered_points`。

## 功能覆盖

- `tlb.lookup`：100.00%（301 samples）
- `tlb.ptw`：100.00%（510 samples）
- `tlb.exception`：100.00%（8 samples）
- `tlb.sfence`：100.00%（27 samples）
- `tlb.reset`：100.00%（29 samples）

Verilator point summaries are not semantic checks. LCOV DA hits are summed per line (duplicate shadow points included) and every denominator is retained. Declarative wire/reg/end lines are separated by source text, not deleted; procedural lines are still listed if uncovered. Files are kept separate so a parent DUT does not hide a child's own gaps.
