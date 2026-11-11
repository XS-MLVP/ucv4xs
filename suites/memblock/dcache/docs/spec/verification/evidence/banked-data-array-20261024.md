# BankedDataArray UT 报告（2026-10-24）

> 数字仍以本报告的独立运行为准；在 2026-10-25 的全量回归
> `results/full-regression-09`（193 passed，61 功能组 100%）中，本 DUT 的分母未变，
> 结论继续有效；ECC 覆盖组口径已在文末修正（新增 2 个用例，合计 20 个）。

## 1. 结论

| 项 | 结果 |
|---|---|
| 运行 | `results/bda-initial-21`（18 用例，固定 seed 1） |
| 功能覆盖 | **100%**（read / write / line / conflict / ecc 五组） |
| DUT 行覆盖 | **100%**（1843 / 1843 唯一 DA 行） |
| 分支覆盖 | **1093 / 1100 = 99.36%** |
| Toggle 覆盖（DUT-only） | **90458 / 105848 = 85.46%** |
| 参考模型 | 256 set × 4 way × 32 bank 的 16-bit 行存储 + bank/set 地址函数 |

## 2. 功能点与用例

| 功能点 | 用例 |
|---|---|
| BDA-FP-001 读端口 bank 选择与返回窗口 | `test_read_window_all_ports_and_ways`、`test_three_ports_independent` |
| BDA-FP-002 32 bank × 4 way 独立存储 | `test_all_banks_and_ways_are_independent`、`test_full_storage_sweep` |
| BDA-FP-003 写掩码与复制写端口 | `test_wmask_and_dup_valid_gate_each_bank`、`test_mask_class_matrix`、`test_duplicate_address_high_bits` |
| BDA-FP-004 写后读可见性 | `test_write_visibility_timing` |
| BDA-FP-005 整线读与输出保持 | `test_readline_way_mask_and_stall`、`test_readline_masks_and_pseudo_error` |
| BDA-FP-006 读-读 bank 冲突 | `test_read_read_bank_conflict_oldest_wins`、`test_three_port_conflict` |
| BDA-FP-007 读-线 / 写-读冲突 | `test_read_line_and_write_hazards`、`test_write_read_conflict` |
| BDA-FP-008 data ECC / 伪错误注入 | `test_pseudo_error_all_banks`、`test_mbist_bypass` |
| 合法随机混合 | `test_random_traffic` |

## 3. 实测语义（与直觉不同之处）

1. **bank 地址是 `addr[5:1]`，set 低 6 位是 `addr[11:6]`**：两者独立。返回窗口的 8 个
   bank 从 `bank & ~7` 开始，bankMask 也是按**绝对 bank 号**索引，不是窗口内偏移。
2. **写请求在下一拍提交**：写有效拍之后的读若命中单端口 hazard 会等待；`ready` 恢复后
   读到的是新数据。
3. **整线读的响应寄存器需要 `can_go=1`**：fire 后一拍若 `can_go=1 && can_resp=1` 才
   打入新数据；`can_resp=1 && can_go=0` 会用分页缓冲重新捕获输出，其内容由之前的
   stall/更新序列决定。
4. **读-读冲突按 lqIdx 最老获胜**：败者下一拍 `rr_bank_conflict_slow=1` 且
   `bank_conflict_slow=1`；ready 不受影响。3 端口同拍冲突时也按同一规则选出唯一胜者。
5. **`read_error_delayed` 在本生成配置下对功能数据也常为 1**：全零数据写回后读 0，
   但读在途时 8 个 bank 的 ECC 错误位都为 1；读结束后回到 0。该行为与 data ECC 解码的
   `^ecc_data` 整体奇校验项一致，疑似 SECDED 码字/解码约定不匹配，已记入
   `manifest/known-issues.json`（BDA-ECC-DELAYED-FLAG），本轮不把它当作功能通过条件，
   功能检查以原始数据逐位一致为准。
6. **MBIST/DFT 旁路**：32 个 array 槽位（0..31）可单独写读 88-bit 原始行，`all` 广播
   可同时写所有 bank；读回需要 3 拍。

## 4. 覆盖率闭环

| 运行 | 用例 | 功能 | 行 | 分支 | Toggle |
|---|---:|---:|---:|---:|---:|
| `bda-initial-01` | 4 PASS / 8 FAIL | — | — | — | — |
| `bda-initial-13` | 12 PASS | 92.3% | 1807/1843 | 890/1100 | 53262/105848 |
| `bda-initial-15` | 13 PASS | 100% | 1807/1843 | 890/1100 | 53305/105848 |
| `bda-initial-17` | 15 PASS | 100% | 1815/1843（过程行 0） | 998/1100 | 87809/105848 |
| `bda-initial-21` | **18 PASS** | **100%** | **1843/1843** | **1093/1100** | **90458/105848** |

缺口归因与补充：

- 首轮失败是**验证模型地址函数错误**（bank 误用 `addr[10:6]`）与未初始化 SRAM 行被当作
  期望 0；修正 `dcache_bank(addr)=addr[5:1]`、所有被读 line 先 prime 后闭合。
- 功能缺口：`bank_mask` 的 none/partial、写掩码/复制端口组合、`line.rmask` 单/部分、
  `conflict.kind` 的 write-read、`ecc.result` 的 error —— 补 `test_mask_class_matrix`、
  `test_write_read_conflict`、`test_pseudo_error_all_banks` 后到 100%。
- 行缺口：MBIST pipe 寄存器（545-555）由 `test_mbist_bypass` 覆盖；readline 的
  `stall & can_go` 与 `can_resp & !can_go` 由保持用例覆盖，最终 100%。
- 分支剩余 7 项：时间零 `initial` 的 else（MBistPipe、5 个 SRAMTemplate、SRAM 模型）
  与 `array_256x88` 门控恒等条件（`E=1 ⇒ RW0_en=1`），均不可由运行期激励到达。
- Toggle 残差 15390 点：`initial_random_state`（SRAM 未访问行的随机初值）3168、
  `ecc_data_delayed` 未读到的 bank/way 与写数据高位 7047、公共端口未用高位/复制地址
  2918、其它内部 2080。属于“未遍历的存储单元/未使用的地址高位”，不是功能点缺失。

## 5. 证据

- `results/bda-initial-21/manifest.json`、`functional-coverage.json`、`coverage-audit.json/.md`
- `manifest/rtl-sha256.json`（`banked_data_array` 16 个 RTL 文件）
- `results/builds/20261024T112723388181Z-banked_data_array/report.json`
- `manifest/known-issues.json`：`BDA-ECC-DELAYED-FLAG`

## 2026-10-25 更新：ECC 覆盖组口径修正 + 2 个用例

复核发现原 `bda.ecc` 覆盖组把 `result = clean/error` 当作期望，而本生成配置下
`read_error_delayed` 对功能正确数据也置 1（known-issue BDA-ECC-DELAYED-FLAG）。
这条“错误”预期是用错误假设写进覆盖组的，已改为：

- `context`：read / line（普通 8-bank 读、32-bank 整线读）
- `check`：roundtrip（功能数据逐位往返）/ injected_xor（伪错误注入按 bank 异或）

新增用例（合计 20 个）：

1. `test_ecc_error_flag_clears_after_read`：正确数据读回逐位一致，且读结束后
   8 个 bank 的 `read_error_delayed` 必须回 0（防未来修复回退）。
2. `test_readline_data_and_flag_clear`：整线读数据逐位一致，`readline_error_delayed`
   读后回 0。

这样 ECC 功能点的通过标准不再依赖有缺陷的标志值，而是“数据正确 + 注入生效 +
标志可清除”。

## 2026-10-26 更新：BDA-ECC-DELAYED-FLAG 关闭（非缺陷）

上一轮把「正确数据读回时 `read_error_delayed=1`」记为待确认问题。本轮定位清楚：

| 场景 | 读回数据 | 8 个 error 位 |
|---|---|---|
| 从未写过的 set/way | 0x8b8e / 0xebb1 / …（随机） | 全 1 |
| 经编码器写全零后 | 全 0 | 全 0 |
| 写其它地址后 | 与模型一致 | 全 0 |

未写过的 SRAM 行数据与 ECC 无对应关系，解码报错是 ECC 的正常检测结果。用例一直
先 `prime` 再用编码写路径初始化，因此功能结论不受影响。

改用例：`test_zero_line_has_no_ecc_error`（新增）、`test_ecc_error_flag_clears_after_read`
与 `test_readline_data_and_flag_clear` 现在都断言 `error_delayed == 0`。
功能点 `BDA-FP-008` 的通过标准恢复为「数据逐位一致 + 伪错误注入生效 + 已写行无错」。
