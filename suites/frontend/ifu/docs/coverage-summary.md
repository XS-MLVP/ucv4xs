# IFU 覆盖率摘要（20261030T022604Z-107cb685）

基线 `public-893e1580b` / DefaultConfig；本文件由 `tools/coverage_summary.py`
从该次运行的完整 `coverage.json` 生成。完整原生表、逐点 JSON 与 HTML 位于
忽略目录 `results/` 下，不进入 Git。

| DUT | line | branch | toggle bin | 曾变化位 | 未覆盖行 | 未覆盖分支臂 |
|---|---|---|---|---|---:|---:|
| `DUTFrontendTriggerDut` | 193/193 (100.00%) | 155/156 (99.36%) | 7602/7982 (95.24%) | 3803/3991 | 0 | 1 |
| `DUTIfuDut` | 4053/4053 (100.00%) | 1648/1652 (99.76%) | 30590/34924 (87.59%) | 15918/17462 | 0 | 4 |
| `DUTIfuPerfAnalysisDut` | 711/711 (100.00%) | 21/22 (95.45%) | 112/644 (17.39%) | 56/322 | 0 | 1 |
| `DUTIfuUncacheUnitDut` | 43/43 (100.00%) | 15/16 (93.75%) | 546/546 (100.00%) | 273/273 | 0 | 1 |
| `DUTInstrBoundaryDut` | 90/90 (100.00%) | 153/154 (99.35%) | 2015/2196 (91.76%) | 1008/1098 | 0 | 1 |
| `DUTPredCheckerDut` | 105/105 (100.00%) | 23/24 (95.83%) | 15968/15998 (99.81%) | 7996/7999 | 0 | 1 |
| `DUTRvcExpanderDut` | 174/174 (100.00%) | 66/66 (100.00%) | 140/146 (95.89%) | 71/73 | 0 | 0 |

源报告 sha256: `49078ddec9a6cd0105a65c0f55e3fa44d16e999497b9de0126791ebb0204b72c`

## DUTFrontendTriggerDut 残留

- 未覆盖分支 L4582 `else`: `if (reset) begin`

## DUTFrontendTriggerDut 未跳变信号族（前 8）

| 信号族 | 未跳变位数 |
|---|---:|
| `triggerHitVec_lowPCVec_N_N[bit]` | 108 |
| `tdataVec_N_tdata2[bit]` | 43 |
| `triggerHitVec_lowPCVec_N[bit]` | 36 |
| `io_frontendTrigger_tUpdate_bits_tdata_tdata2[bit]` | 1 |

## DUTIfuDut 残留

- 未覆盖分支 L16849 `cond_then`: `select_35 ? s2_fetchBlock_1_ftqIdx_flag : s2_fetchBlock_0_ftqIdx_flag;`
- 未覆盖分支 L16851 `cond_then`: `select_35 ? s2_fetchBlock_1_ftqIdx_value : s2_fetchBlock_0_ftqIdx_value;`
- 未覆盖分支 L2465 `cond_else`: `_rvcExpanders_35_io_ill ? 32'h0 : _rvcExpanders_35_io_out_bits;`
- 未覆盖分支 L7914 `cond_then`: `? _GEN_3[s1_alignedInstrVec_0_index]`

## DUTIfuDut 未跳变信号族（前 8）

| 信号族 | 未跳变位数 |
|---|---:|
| `s1_compactedInstrVec_validOHReg_N_N` | 115 |
| `io_fromICache_req_bits_info_N_icacheMeta_gpAddr_addr[bit]` | 83 |
| `s1_icacheMetaIn_N_gpAddr_addr[bit]` | 83 |
| `s2_icacheMeta_N_gpAddr_addr[bit]` | 83 |
| `io_toIBuffer_bits_topdownInfo_reasons_N` | 75 |
| `io_perf_N_value[bit]` | 73 |
| `io_toIBuffer_bits_instrs_N[bit]` | 69 |
| `s2_expandedInstrDataVec_N[bit]` | 69 |
| …其余 122 族 | 1474 |

## DUTIfuPerfAnalysisDut 残留

- 未覆盖分支 L1117 `else`: `if (reset) begin`

## DUTIfuPerfAnalysisDut 未跳变信号族（前 8）

| 信号族 | 未跳变位数 |
|---|---:|
| `topdownStages_N_reasons_N` | 200 |
| `io_topdownOut_topdown_reasons_N` | 66 |

## DUTIfuUncacheUnitDut 残留

- 未覆盖分支 L160 `else`: `if (reset) begin`

## DUTInstrBoundaryDut 残留

- 未覆盖分支 L425 `cond_then`: `io_req_ifuData_blockSel[0] ? 5'(5'h0 - io_req_fetchBlock_0_size[4:0]) : 5'h0;`

## DUTInstrBoundaryDut 未跳变信号族（前 8）

| 信号族 | 未跳变位数 |
|---|---:|
| `io_resp_rawInstrVec_N_startOffset[bit]` | 31 |
| `io_resp_rawInstrVec_N_endOffset[bit]` | 26 |
| `startOffset_N[bit]` | 26 |
| `startOffset[bit]` | 5 |
| `io_req_ifuData_blockSel[bit]` | 1 |
| `io_resp_rawInstrVec_N_blockSel` | 1 |

## DUTPredCheckerDut 残留

- 未覆盖分支 L2870 `else`: `if (reset)`

## DUTPredCheckerDut 未跳变信号族（前 8）

| 信号族 | 未跳变位数 |
|---|---:|
| `io_req_bits_instrPcVec_N_addr[bit]` | 1 |
| `jumpTargetsNext_N_addr[bit]` | 1 |
| `seqTargetsNext_N_addr[bit]` | 1 |

## DUTRvcExpanderDut 未跳变信号族（前 8）

| 信号族 | 未跳变位数 |
|---|---:|
| `io_out_s_load_opc[bit]` | 2 |
