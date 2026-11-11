# L2 中层块覆盖闭环证据（2026-10-24）

本目录汇总 PTW、BitmapCache、Bitmap、PMP、LLPTW 的轮次对比 compact 审计。
最终完整 run 与覆盖数据库分别在：

- `results/ptw-final-06`（30 PASS）
- `results/bitmapcache-final-06`（12 PASS）
- `results/bitmap-final-07`（16 PASS + 2 XFAIL）
- `results/pmp-final-04`（12 PASS）
- `results/llptw-final-04`（23 PASS + 1 XFAIL）

| 前缀 | 首轮/中期 | 最终 | 说明 |
|---|---|---|---|
| `ptw-*` | `ptw-tests-06` 行 515/530、toggle 12118/15344、branch 413/420 | 行 530/530、branch 418/420、toggle 12213/15344 | 补 full_gvpn 级别/NPOT、normal allStage identity-HPTW |
| `bitmapcache-*` | `bitmapcache-final-03` 行 314/323、功能 100% | 行 314/323、branch 124/148、toggle 6953/14174 | 补全 32 set/4 way、tag/data 极值；残余为 MBIST/initial/SRAM 结构 |
| `bitmap-*` | `bitmap-final-03` 行 1028/1415、功能 100% | 行 974/1415、branch 279/398、toggle 2190/6636 | 最终 run 含 2 个 strict XFAIL：back-to-back PMP 别名 + 并发 miss 停顿 |
| `pmp-*` | `pmp-final-01` 行 1988/2117、功能 91.67% | 行 2117/2117、功能 100% | 补 PMA cfg 字节语义/地址/mask、全 entry/位扫描 |
| `llptw-*` | `llptw-tests-02` 行 955/1955、功能 62.5% | 行 1656/1955、branch 359/407、toggle 4329/20770、功能 100% | 补 stage2/cache/slot；多 allStage 并发 strict XFAIL |

审计文件保留总数、逐文件行覆盖和功能覆盖；完整未覆盖点/分支/toggle 列表在最终 run 的
`coverage-audit.json`。本目录不保存波形或逐周期 dump。


## 第二阶段补充（2026-10-25）

- PTW full_gvpn 与 normal allStage 闭合，行 530/530=100%。
- PMA 配置语义（PMP leaf）与 L2TLB 顶层 PMA/PMP 页表属性交互闭合。
- Bitmap deny/allow 极性闭合；并发 miss 与 back-to-back PMP 别名保留 strict XFAIL。
- LLPTW 单 allStage slot 1..5 全通过；两个并发 allStage 在部分 HPTW/PTE 活动后停顿，
  保留 strict XFAIL。
