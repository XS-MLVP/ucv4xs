# PTWRepeaterNB / PTWFilter 叶子闭环报告（2026-10-24）

> **可信度复核更正（2026-10-25）**：本报告保留旧 run 的历史指标；当前归因以
> `verification-soundness-20261025.md` 为准。原 5 个 strict XFAIL 的 DUT 缺陷归因
> 已被验证侧反证推翻；“100% sampled bins”不等于功能验收或不可达证明。


## 1. 范围与实例

这两个模块不是 L2TLB 内部实例，而是 ITLB 路径上的请求处理块：

| 模块 | 真实实例 | 文件 |
|---|---|---|
| `PTWRepeaterNB` | `Frontend.sv:inner_itlbRepeater2`、`MemBlock.sv:inner_itlbRepeater3` | `soc-split/rtl/PTWRepeaterNB.sv` |
| `PTWFilter` | `Frontend.sv:inner_itlbRepeater1` | `soc-split/rtl/PTWFilter.sv` |

DUT 用最小依赖闭包构建，RTL 为 `soc-split/rtl` 的字节级副本：

- `manifest/ptwrepeater-rtl.sha256`（ClockGate/DelayN_6/PTWRepeaterNB）
- `manifest/ptwfilter-rtl.sha256`（ClockGate/DelayN_6/PTWFilter）
- 构建：`results/builds/20261024T115030999840Z-ptwrepeater/`、
  `results/builds/20261024T115047936888Z-ptwfilter/`，均 `ok=true`。

功能点见 [functional-points-l2-leaves.md](../functional-points-l2-leaves.md) 的
RPT/FIL 部分。

## 2. PTWRepeaterNB

最终 run：`results/ptwrepeater-05`，7 用例 PASS，用时 <1 s。

| 指标 | 首轮 `-01` | 最终 `-05` |
|---|---|---|
| 功能覆盖 | 83.33% | **100%** |
| 行覆盖 | 72/72 | **72/72** |
| toggle | 1167/3114 | **3114/3114 = 100%** |
| branch | 7/8 | **7/8** |

覆盖缺口闭环：

1. 首轮 `stage` 只采样到 0/2，`hold` 未采样 required 的 held 路径；补了 stage
   扫描和响应保持/释放用例后功能覆盖到 100%。
2. 首轮 toggle 只有 37.5%，原因是 1 位信号的 Picker `mWidth` 返回 0，位扫描把
   全 1 掩码算成了 0；修正 `width=max(1,mWidth)` 后所有 payload 位都实际翻转。
3. 唯一未取 branch 是生成 RTL 时间零 `initial if (reset)` 的隐式 else
   （`PtwRepeaterNBDut.v:371`），不涉及运行时功能，记录为工具初始化分支，不豁免、
   不伪造。

## 3. PTWFilter

最终 run：`results/ptwfilter-final-16`，14 用例 PASS，用时约 1.6 s。

| 指标 | 首轮 `-03` | 最终 `ptwfilter-final-16` |
|---|---|---|
| 功能覆盖 | 75.00% | **100%** |
| 行覆盖 | 206/206 | **206/206** |
| toggle | 1938/4414 | **4411/4414 = 99.93%** |
| branch | 82/92 | **91/92** |

覆盖缺口闭环：

1. 首轮只匹配 noS2；补 onlyStage1/onlyStage2/allStage 响应键后，`stage` 4/4 和
   `match_resp` 全类覆盖，branch 从 82/92 升到 91/92。
2. 首轮没有触发 `issue_filtered`；补“响应与队头发射同拍”用例后该 0->1 路径被覆盖。
3. 首轮队列只填到 8 条但 drain 只验证了部分；补 8 项容量、8 条 outstanding
   inflight 计数、重复合并、错误响应不释放、四类 CSR changed flush 后功能覆盖 100%。
4. 残余 3 个 toggle 点：`issue_filtered_vmid_hit:1->0` 与
   `ptwResp_newMatchVec_onlyS2_hit_tag_match_1/2:1->0`。新增高 VPN 位 33..35、
   way 1..7、onlyStage2 tag/vmid 匹配方向用例后，toggle 从 4380 提升到 4411；
   剩余属于并发响应/边界情况枚举，不是整体功能缺失。未用不可达/伪造激励填点。
5. 唯一未取 branch 是时间零 `initial if (reset)` 隐式 else
   （`PtwFilterDut.v:1654`），同 RPT 的处理。

## 4. 证据

- 首轮/最终审计摘要与功能覆盖：
  `docs/reports/evidence/cycle-ptw-20261024/`
- 最终完整覆盖数据库与报告：`results/ptwrepeater-06/`、`results/ptwfilter-final-16/`
- 每次 run 都由 `tools/run.py` 生成 `manifest.json`（`state=committed`、
  `coverage_complete=true`），无波形，无 skip/xfail。

## 5. 复现

```sh
cd memblock-hash/mmu
python3 tools/build_dut.py ptwrepeater --jobs 8
python3 tools/build_dut.py ptwfilter --jobs 8
python3 tools/run.py --name ptwrepeater-06 --workers 1 tests/l2/test_ptwrepeater.py
python3 tools/run.py --name ptwfilter-final-16 --workers 1 tests/l2/test_ptwfilter.py
python3 tools/coverage_audit.py ptwrepeater-06
python3 tools/coverage_audit.py ptwfilter-final-16
```
