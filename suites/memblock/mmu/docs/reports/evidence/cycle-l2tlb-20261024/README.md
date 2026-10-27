# L2TLB 顶层覆盖闭环证据（2026-10-24）

最终完整 run：`results/l2tlb-final-12`（40 用例 PASS + 1 strict XFAIL，完整审计
和覆盖数据库在该目录内）。本目录保存轮次对比用的 compact 审计：

| 文件 | 轮次 | 行覆盖 | branch | toggle |
|---|---|---|---:|---:|
| `top-before-audit.json` | 首轮 `l2tlb-tests-03` | 15502/22249 = 69.68% | 3607/6304 | 63583/255430 |
| `top-before-functional.json` | 首轮功能覆盖（粗粒度） | — | — | — |
| `top-mid-audit.json` | 中期 `l2tlb-final-01` | 16794/22249 = 75.48% | 4211/6304 | 91146/255430 |
| `top-final-audit.json` | 最终 `l2tlb-final-12` | **17081/22249 = 76.772%** | **4329/6304** | **96615/255430** |
| `top-final-functional.json` | 最终功能覆盖 100% | — | — | — |

说明：

- 首轮是第一次成功跑通真实 PTW/PtwCache 内存走表的集成 run；之后补了 4KB/2MB/
  allStage/HPTW、PMP、bitmap、sfence、背压、延迟等用例，得到中期和最终数字。
- 审计文件是 compact 摘要；完整未覆盖点、逐 branch/toggle 列表在最终 run 的
  `coverage-audit.json`。本目录没有波形或逐周期事务 dump。
- `L2TlbDut_top.sv` 是 Picker harness，未计入 DUT-only 分母。


## 第二阶段补充（2026-10-25）

最终 run 新增：Bitmap deny/allow、PMA/PMP 页表属性（C=1/R=1 允许，C=0 或 R=0
访问故障）、scoped sfence 重走、satp.changed+sfence。一项 strict XFAIL：
all-address sfence（rs1=0/rs2=0）返回旧 PPN 且不重走。>2 outstanding 在 mem_latency=7
下 4 个请求全部完成；零延迟双 beat 丢失已确认是 harness 时序。
共享叶子停顿的根因在 wrapper 层隔离为 0 空闲周期的 prefetch/LLPTW 交接。
