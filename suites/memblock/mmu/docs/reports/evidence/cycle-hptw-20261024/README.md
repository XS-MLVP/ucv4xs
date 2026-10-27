# HPTW 独立叶级覆盖闭环证据（2026-10-24）

最终 run：`results/hptw-final-02`（21 用例 PASS，完整审计与覆盖数据库在该目录）。

| 文件 | 轮次 | 行覆盖 | branch | toggle | 功能 |
|---|---|---|---:|---:|---:|
| `hptw-before-audit.json` | 首轮 `hptw-tests-02` | 130/133 = 97.74% | 77/98 | 1123/5270 | 77.78% |
| `hptw-mid-audit.json` | 中期 `hptw-tests-04` | 133/133 = 100% | 95/98 | 2450/5270 | 91.67% |
| `hptw-final-audit.json` | 最终 `hptw-final-02` | **133/133 = 100%** | **97/98** | **5069/5270 = 96.19%** | **100%** |
| `hptw-final-functional.json` | 最终功能覆盖（32 samples） | — | — | — | — |

首轮缺口是 l2Hit 分支、bitmap 请求/响应、内存 mask 和 payload 位未枚举；补 l2/l3 hit、
bitmap fromSP/ptes、PMP MMIO、CSR 源、高地址、NAPOT/PBMT 与位扫描后闭合到当前值。
唯一 branch 缺口是时间零 `initial if (reset)` 的隐式 else（HPTW.sv:420）；残余 toggle
已逐项分类在 `docs/reports/hptw-20261024.md`。compact 审计保留总数与逐文件行覆盖，
完整未覆盖点在最终 run 的 `coverage-audit.json`。


## 第二阶段补充（2026-10-25）

新增 `test_hptw_reset_without_flush_observation`：accessFault 结构上不在同步复位
块内，但 seed 1（及 2..8）下复位后未 sfence 的首次合法走表仍 gaf=0 且完成三次
表读；PMP 拒绝走表 gaf=1 且无读；再次复位后合法走表成功。未复现功能性 spurious
fault，known-issue 以 rtl-hygiene-observation 保留。
