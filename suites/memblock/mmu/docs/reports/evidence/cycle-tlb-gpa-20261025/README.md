# TLB GPA/getGpa 重放证据（2026-10-25）

新增用例 `test_gpa_replay_for_all_stage_gpf`（`tests/tlb/test_tlb.py`）验证：

- allStage 条目 S1 有效、G 阶段 page fault；
- TLB 发起 `ptw.req.getGpa=1` 请求 GPA；
- GPA 响应后返回 `gpf=1`，`gpaddr = ((s1_ppn<<3)|ppn_low)<<12 | offset`；
- 重放请求不再发起普通走表。

| 阶段 | run | 用例 | 行覆盖 | branch | toggle | 功能 |
|---|---|---:|---:|---:|---:|---:|
| 第一阶段 | `tlb-sweep-12` | 24 | 3644/3657 = 99.64% | 1089/1104 | 18716/23074 | 100% |
| **本轮** | **`tlb-gpa-tests-06`** | **25** | **3655/3657 = 99.945%** | **1094/1104** | **18785/23074** | **100%** |

残余 2 行为时间零 initial 复位块；GPA 相关 13 行已全部覆盖。

文件：`tlb-before-audit.json`、`tlb-final-audit.json`、
`tlb-final-functional.json`；完整数据库在 `results/tlb-gpa-tests-06/`。
