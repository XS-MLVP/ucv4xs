# 覆盖率闭环

## 口径

`tools/coverage_report.py` 从 `ucv run` 生成的 `manifest.json` 读取：

- **line**：优先使用该次运行的 LCOV `DA` 行计数；没有 LCOV 时退回原生 `v_line`
  点的 `l`/`S` 行号。只统计真实 RTL 文件。
- **branch**：原生 `v_branch` 臂，保留生成 RTL 文本。
- **toggle**：原生 `v_toggle` 转移 bin，并另报“曾变化信号位”数。
- **排除** Picker 生成包装 `*_top.sv` 的 DA/行点：这些是 DPI/端口胶水，不是设计
  逻辑。没有 line/branch 点的真实文件明确标为 N/A，不按 100% 计入分子。

整芯片生成缓存
`d7c6bc4d17651fc1bd92ac39c469410a6bb91215f46c1efcfaf1ec66a72e972d` 的 RTL
哈希与三个 DUT 闭包相同（见[验证报告](../reports/verification-report.md)）。

## 结果（seed 1 = seed 2）

| DUT / 文件 | line | branch | toggle | 曾变化位 |
|---|---|---|---|---|
| `instr_uncache_entry` / `InstrUncacheEntryDut.v` | 37/37 (100%) | 13/14 (92.86%) | 628/664 (94.58%) | 314/332 |
| `instr_uncache_resp_arbiter` / `InstrUncacheRespArbiterDut.v` | 0/0 N/A | 0/0 N/A | 144/144 (100%) | 72/72 |
| `instr_uncache` / 顶层结构 + Entry + Arbiter | 37/37 (100%) | 13/14 (92.86%) | 1165/1230 (94.72%) | 584/615 |

顶层逐文件：

| 文件 | line | branch | toggle | 说明 |
|---|---|---|---|---|
| `InstrUncacheDut.v` | 0/0 N/A | 0/0 N/A | 395/422 | 顶层只有端口/实例；Verilator 不产生 line/branch 点 |
| `InstrUncacheEntry.sv` | 37/37 (100%) | 13/14 (92.86%) | 626/664 | 真实 Entry 子模块 |
| `Arbiter1_InstrUncacheResp.sv` | 0/0 N/A | 0/0 N/A | 144/144 | 纯组合 assign，无 line/branch 点 |

## 未覆盖行

**0 行。** 三个 DUT 的所有被插桩 RTL 行均命中；LCOV 的 `LF/LH` 与原生行表一致。

## 未覆盖分支

唯一未命中臂：

```text
InstrUncacheEntry.sv:161  else  if (reset) begin
```

它属于生成 RTL 的 `ENABLE_INITIAL_REG_` 初始化块：`initial` 只在 time 0 执行，
而仿真/smoke 在该块内都置 `reset=1`，所以 `else` 臂没有合法仿真路径。归因为
`R-COV-INIT`（结构不可达，非功能分支）。本轮没有通过修改 RTL 或删除分支制造
覆盖。

## 未覆盖 toggle

Entry（18 位）与顶层（31 位，含 Entry 同名信号）：

- `*_address[0]`、`*_address[1]`、`*_address[2]`：2B 对齐固定 bit0=0，
  8B 对齐固定低 3 位为 0；
- `*req*_addr_addr[42..46]` / `reqReg_addr_addr[42..46]`：对应字节地址
  43..47 位；DefaultConfig 的合法物理地址上限为 2^43，合法激励不会置位；
- `auto_client_out_a_bits_address[43..47]`、`io_mmioAcquire_bits_address[43..47]`：
  同上；A bit47 由 Scala `Cat` 宽度固定为 0（`R-ADDR47`）。

这些不是缺少功能场景，而是合法地址域/对齐常量的边界。归因为 `R-COV-TOGGLE`。
没有用非法非对齐地址或超出 PMA 映射的高位地址追求数字。

## 闭环过程

1. 首版定向 + 随机后，`instr_uncache_entry` line 37/37、branch 13/14，
   顶层 toggle 1158/1230；缺口全部是可解释的高位地址/对齐位。
2. 增加 `test_top_high_legal_address_toggles_address_bit_42`，在合法上限内驱动
   bit42，顶层 toggle 从 **1158 → 1165**（bits 579 → 584）；Entry 数字不变。
3. 重新运行 seed 1、seed 2 完整集合，结果均为 68 PASS + 0 UNCERTAIN（68 nodeid），
   nodeid 一致；覆盖数字两 seed 相同。
4. R-FLUSH 收口不改变任何激励：`INC-FLUSH-012` 从硬件 UNCERTAIN 改为环境结构
   检查点，仍不驱动 flush；覆盖分母保持 13/14，未用激励或非法地址改数字。

## 证据位置

完整逐点表与 HTML 在忽略目录：
`results/instr-uncache-seed1-flush-closure/coverage.json`、
`results/instr-uncache-seed2-flush-closure/coverage.json`；
可入库摘要见 [覆盖率摘要](coverage-summary.md)。
