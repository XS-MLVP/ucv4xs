# InstrUncache 覆盖率摘要

基线与配置：`public-a0c2a26cb` / DefaultConfig。完整原生表、逐点 JSON 和 HTML
位于忽略目录 `results/`；本文件只保留可审查的数字和缺口归因。

| DUT / 文件 | line | branch | toggle | 曾变化位 |
|---|---|---|---|---|
| `instr_uncache_entry` / `InstrUncacheEntryDut.v` | 37/37 (100%) | 13/14 (92.86%) | 628/664 (94.58%) | 314/332 |
| `instr_uncache_resp_arbiter` / `InstrUncacheRespArbiterDut.v` | 0/0 N/A | 0/0 N/A | 144/144 (100%) | 72/72 |
| `instr_uncache` / 顶层结构 + Entry + Arbiter | 37/37 (100%) | 13/14 (92.86%) | 1165/1230 (94.72%) | 584/615 |

顶层逐文件：

| 文件 | line | branch | toggle |
|---|---|---|---|
| `InstrUncacheDut.v` | 0/0 N/A | 0/0 N/A | 395/422 |
| `InstrUncacheEntry.sv` | 37/37 (100%) | 13/14 (92.86%) | 626/664 |
| `Arbiter1_InstrUncacheResp.sv` | 0/0 N/A | 0/0 N/A | 144/144 |

## 缺口

| 缺口 | 数量 | 归因 |
|---|---:|---|
| 未覆盖行 | 0 | — |
| 未覆盖分支 | 1 | `InstrUncacheEntry.sv:161` 的 `if (reset)` else；`ENABLE_INITIAL_REG_` 初始化块结构不可达（`R-COV-INIT`） |
| 未覆盖 toggle（Entry） | 18 位 | 地址 43..47 位（合法 PMA 上限 2^43）+ 对齐固定低 3 位（`R-COV-TOGGLE`） |
| 未覆盖 toggle（顶层） | 31 位 | 同上，含 A bit47 固定 0（`R-ADDR47`） |

顶层结构模块和纯组合 Arbiter 没有 line/branch 插桩；顶层行覆盖只统计真实被
插桩的 Entry 子模块。独立 Entry/Arbiter DUT 的构建提供各自证据，不能用顶层
`0/0` 推导“已覆盖”或“未覆盖”（`R-COV-TOOL`）。

seed 1 与 seed 2 的完整集合均为 **68 PASS + 0 UNCERTAIN**（68 nodeid），
覆盖数字一致。R-FLUSH 收口只改变证据分类（`R-FLUSH` → out-of-domain /
accepted-limited，`INC-FLUSH-012` → 环境结构检查点），不改变激励与覆盖分母；
与收口前的 coverage.json 逐项比较，line/branch/toggle 差值均为 **0**。
