# DuplicatedTagArray UT 报告（2026-10-24）

> 数字仍以本报告的独立运行为准；在 2026-10-25 的全量回归
> `results/full-regression-11`（202 passed + 3 xfailed，61 功能组 100%）中，本 DUT 的分母未变，
> 结论继续有效。根因/语义修正记录见 `functional-point-audit-20261025.md`。

## 1. 结论

| 项 | 结果 |
|---|---|
| 运行 | `results/dta-initial-11`（toffee runner，9 用例，固定 seed 1） |
| 功能覆盖 | **100%**（5 个语义覆盖组：read / write / conflict / reset / mbist） |
| DUT 行覆盖 | **90 / 90 = 100%** |
| 分支覆盖 | **76 / 80 = 95%**（剩余 4 项经证据判定为不可达） |
| Toggle 覆盖 | **16967 / 17498 = 96.96%** |
| 参考模型 | 256 set × 4 way tag 表 + 由 RTL XOR 常量实现的 SECDED 编码器 |

## 2. 功能点与用例对应

| 功能点 | 用例 |
|---|---|
| DTA-FP-001 复位扫描清零 | `test_reset_sweep_blocks_reads_then_clears_all_sets` |
| DTA-FP-002 四份副本读一致 | `test_all_ports_see_the_same_four_way_tags`、`test_back_to_back_reads_across_ports` |
| DTA-FP-003 set 独立寻址 | `test_set_independence_and_boundaries` |
| DTA-FP-004 way 掩码写 | `test_way_mask_and_set_class_matrix` |
| DTA-FP-005 单端口读写互斥 | `test_single_port_read_write_conflict` |
| DTA-FP-006 写后读可见性 | `test_single_port_read_write_conflict`、`test_all_ports_see_the_same_four_way_tags` |
| DTA-FP-007 SECDED 码字生成 | `test_ecc_codeword_is_linear_and_single_bit_sensitive` |
| DTA-FP-008 MBIST/DFT 旁路 | `test_mbist_bypass_reaches_every_bank` |
| 合法随机混合 | `test_random_legal_traffic` |

## 3. 实测语义（与直觉不同之处）

1. **复位是 256 拍扫描，不是异步清零**：释放 `reset` 后 `rst_cnt` 从 0 数到 255，每个
   时钟沿写一个 set 的全部 4 个 way；扫描完成前 `io_read_3_ready=0`。用例在扫描中
   连续 8 拍确认 ready=0，扫描后再读全部 256 set 确认零码字。
2. **读延迟 1 拍，MBIST 读延迟 3 拍**：功能读在请求沿后立刻返回 4-way 码字；DFT 读要
   经过 `ack` 拍、SRAM 读沿、`rdataReg` 沿三拍，`bore_outdata` 才更新。
3. **写占用端口时读被拒绝，`resp` 在冲突拍不可采样**：SRAM 单端口在写模式下输出行内容，
   不能把它当作读结果。用例只在 ready 为高时比较读数据。
4. **ECC 编码是线性 XOR 网络**：单 bit tag 的 36 个校验值互不相同；随机 tag 满足
   `ecc(a^b)=ecc(a)^ecc(b)`；tag=0 的码字为 0。

## 4. 覆盖率缺口逐项归因

### 4.1 行覆盖

DUT 行 90/90 全部命中。`DuplicatedTagArrayDut_top.sv`（Picker harness，3/457）不计入
DUT 行覆盖，单列保留。

### 4.2 分支（4 项未覆盖）

| 位置 | 分支 | 归因 |
|---|---|---|
| `MbistPipeDcacheTag.sv:240` | 时间零 `initial` 的 `if (reset)` else | 只在仿真时间 0 执行一次，运行期不可达；复位 always 路径已覆盖 |
| `TagSRAMBank.sv:102` | 同上 | 同上 |
| `SRAMTemplate_278.sv:123` | 同上 | 同上 |
| `array_256x86.sv:74` | `if (RW0_en)` 的假分支 | SRAM 时钟由 `E = rckEn \\| wckEn` 门控；`E=1` 必然推出 `RW0_en=1`，因此“有时钟沿但 RW0_en=0”在构造上不存在 |

四项都不是功能点缺失，也没有补功能用例的空间；原始分母保留。

### 4.3 Toggle（531 个点未覆盖）

| 类别 | 数量 | 归因 |
|---|---:|---|
| `sigFromSrams_bore_*`（hold/bypass/bp_clken/aux_clk/aux_ckbp/mcp_hold/ram_ctl/cgen） | 182 | SRAM DFT 广播控制，DCache 功能模式下恒 0；驱动 aux_clk/ckbp 会改变门控时钟，不属于功能行为 |
| `arrayReg` / `toSRAM_*_array` / `bd_array` 的 bit3..5 | 114 | 本 DUT 合法 array ID 仅 0x20..0x27（8 个 tag bank），bit3..5 在合法域恒 0；0x28+ 属于 data SRAM，不在本 DUT 范围 |
| `mbist_dft_ram_bypass` / `bp_clken` / `TE` 等 | 235 | 同上，DFT/时钟门控专用输入，功能模式恒定 |

这些点对应的不是遗漏的功能情形，而是 DFT/门控边界。功能读写的全部 tag/ECC/way/set
数据位、4 个读端口输出和 MBIST 数据通路都已被双向 toggle。

## 5. 证据文件

- `results/dta-initial-11/manifest.json`：运行提交记录（9 PASS，coverage_complete）
- `results/dta-initial-11/functional-coverage.json`：5 个覆盖组 100%
- `results/dta-initial-11/coverage-audit.json` / `.md`：line/toggle/branch 全量分母与逐行清单
- `manifest/rtl-sha256.json`：`duplicated_tag_array` 9 个 RTL 文件哈希
- `results/builds/20261024T104603980418Z-duplicated_tag_array/report.json`：Picker 构建记录
