# P1 叶块闭环汇总（2026-10-24）

P1 覆盖 DCache 的控制/标签叶块。四个 DUT 都按“功能点 → 用例 → 三类覆盖率 → 缺口归因
→ 补情形/补用例 → 重跑”的闭环推进，结论绑定固定 RTL 哈希、Picker 构建与 toffee 运行。

| DUT | 用例 | 功能覆盖 | 行覆盖 | 分支 | Toggle（DUT-only） | 报告 |
|---|---:|---:|---:|---:|---:|---|
| DuplicatedTagArray | 9 PASS | 100% | 90/90 = 100% | 76/80 | 15010/15428 = 97.29% | `duplicated-tag-array-20261024.md` |
| CtrlUnit | 13 PASS | 100% | 244/244 = 100% | 85/89 | 11444/12108 = 94.52% | `ctrl-unit-20261024.md` |
| MissReadyGen | 5 PASS | 100% | 0/0（纯组合） | 0/0 | 3512/3512 = 100% | `miss-ready-gen-20261024.md` |
| CounterFilter | 7 PASS | 100% | 311/311 = 100% | 49/50 | 622/622 = 100% | `counter-filter-20261024.md` |

## 覆盖率提升证据（同一 DUT 的前后对比）

| DUT | 首轮 | 修复后 |
|---|---|---|
| DuplicatedTagArray | 行 91.11%、branch 48/80、toggle 8962/17498 | 行 100%、branch 76/80、toggle 16967/17498 |
| CtrlUnit | 功能 62.5%、toggle 10074/12108 | 功能 100%、toggle 11444/12108 |
| MissReadyGen | toggle 3304/3512 | toggle 3512/3512 |
| CounterFilter | 功能 91.2%、行 238/311、 toggle 334/622 | 功能 100%、行 311/311、 toggle 622/622 |

## 缺口分类结论

- **整体功能点缺失**：CounterFilter 的容量语义最初定义为 15 项，实测合法在途上限是
  12（dequeue 延迟 4 拍）；已把功能点 CF-FP-005 改为“15 物理槽 / 12 在途”，并补
  满带宽与回绕用例。CtrlUnit 的“通道 valid 不看 bank”也是首轮功能点描述遗漏，已修正
  并补 bank=0 情形。
- **已有功能点情形缺失**：DuplicatedTagArray 的 MBIST 路径与全 set 边界、CtrlUnit 的
  data mask 全位翻转、MissReadyGen 的通道 2/3 高位 walking-bit 均属于此类别，直接补
  情形后闭合。
- **工具/结构边界**：时间零 `initial`、SRAM 门控时钟恒等条件、16→36 bit 零扩展高位、
  未使用的 TileLink opcode 编码、15 个合法 array ID 之外的 tag 槽位。均保留原始分母，
  在各自报告中逐项列出证据。

## 工程门禁

- 所有 DUT 构建均使用 `--rw mem_direct -w memory-direct.fst -c`，无 VPI/内部信号配置。
- 所有运行经 `tools/run.py`（toffee main runner），不直接调用 pytest 取证；正常运行不
  打开波形、不产生逐周期 dump。
- 四个叶块 DUT 的 `dut/<key>/` 包与 `manifest/rtl-sha256.json` 一一对应。
