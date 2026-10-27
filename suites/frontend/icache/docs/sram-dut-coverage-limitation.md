# SRAM 类 DUT 的行覆盖情况（DataBank / MetaBank / MetaArray / DataArray）

四个 DUT 都是“一个薄包装 + 若干 SRAM 宏”。此前的 63.74%–96.32% 不是包装内联导致的
不可达，而是**功能点缺失**：MBIST 测试访问端口在 DUT 顶层完整存在且是公开输入，却从未
被任何用例驱动。补上四个 BIST 功能点后，四个 DUT 合计达到 **6518/6522 = 99.94%**。

## 最终实测（`results/xreactor-sub-1`，140 passed）

| 文件 | 语句覆盖 | 剩余可执行缺口 |
|---|---|---|
| `DataBankDut.v`（ICacheDataBank） | 100% | 0 |
| `MetaBankDut.v`（ICacheMetaInterleavedBank） | 658/659 | 1 条：零宽 `bd_array` 直连 |
| `ICacheMetaInterleavedBank.sv`（MetaArray 的 bank 0 实例） | 658/659 | 1 条：同上 |
| `SRAMTemplate.sv`（单阵列 bank 的两个实例） | 58/60 | 2 条：零宽 `mbistBd_array` 直连 |
| 其余 MbistPipe / SRAMTemplate / 数据 bank 实例 | 100% | 0 |

“剩余 4 条”全部是同一形态：

```verilog
wire bd_array = boreChildrenBd_bore_array;   // array 端口宽度为 0
wire mbistBd_array = boreChildrenBd_bore_array;
```

`dut/metabank/signals.json` 与 `dut/metaarray/signals.json` 中这些 bank 的
`boreChildrenBd_bore.array` 的 `High = -1`，即 **0 位宽**。该 bank 只有一个 SRAM 宏，
不存在可选择的第二个 array；零宽信号的取值恒为 0，不存在 0→1 翻转，Verilator 的
行点因此永远不会命中。这是结构性不可达，不是缺少用例。

## 缺失的功能点（本轮补出）

| 功能点 | 语义 | 用例 |
|---|---|---|
| `ICACHE-DATABANK-006` | 数据 bank 的每个 way 宏都能被测试口单独选中；测试口写入的字对功能读路径可见；广播写覆盖全部 way | `test_bist_port_reaches_each_way`、`test_bist_broadcast_covers_all_ways`、`test_bist_port_reads_back_a_written_word` |
| `ICACHE-METABANK-008` | tag 宏可经测试口写入并读回，广播选择同样到达 | `test_bist_port_reaches_the_tag_array`、`test_bist_broadcast_selects_the_banks_macro` |
| `ICACHE-METAARRAY-009` | 两个 interleaved bank 各有独立测试选择；写入互不串扰 | `test_bist_port_reaches_each_interleaved_bank`、`test_bist_broadcast_reaches_each_bank` |
| `ICACHE-DATAARRAY-009` | 8 个 bank × 4 个 way 全部可独立选中；测试写对功能读可见 | `test_bist_port_reaches_every_bank_and_way`、`test_bist_broadcast_writes_all_ways_of_a_bank` |

## BIST 访问的地址/选择语义（从公开端口与 SRAM 宏接口确认）

- 测试写使用的 SRAM 地址是 `addr_rd`（`RW0_addr = mbistBd_ack ? mbistBd_addr_rd : ...`），
  不是 `addr`；测试读也用同一地址。
- array 选择编码是按 bank 全局编号：DataBank 为 4..7（way 0..3），DataArray 第 b 个 bank
  为 `4 + 4*b .. 4 + 4*b + 3`；MetaArray bank 1 为 2..3（bank 0 宽度 0，只有 0）。
- 上电后 SRAM 宏会先做 256/128 拍的清零清扫（`_resetState`）。BIST 访问必须等
  `write_ready`/`read_ready` 变高，否则测试写会被清扫覆盖——这是本轮先遇到并修正的
  测试环境问题，不是 RTL 缺陷。
- 测试读的回读数据在 ack 之后两拍才出现在 `outdata`；读回比较必须等够这两拍。

## 结论

四个 SRAM DUT 的全部**可执行**语句已覆盖；剩余 4 条是零宽端口直连，已给出
`signals.json` 宽度证据。此前把 63%–96% 归因为“包装被内联”是不正确的，按功能点倒推
后这些缺口全部消失，符合“覆盖率未满即功能点定义有缺陷”的方法论。
