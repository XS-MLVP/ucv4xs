# 当前已实现范围统一回归02：28个DUT、651例，保留NOT_PASS

**实际结果：636 PASS / 15 FAIL，整体套件NOT_PASS。** `lsq-progress-regression-02` 在同一pytest+xreactor进程运行目前全部已实现651例、28个独立DUT，包括真实LoadQueueUncache父块。没有新增未知失败；也没有将已知失败豁免成绿色。

这不是完整LSQ范围或真实LoadQueue/StoreQueue/LsqWrapper组合的验收。Replay只有用例前合同及正在推进的构建/适配，不包含在651例中；Store分支和最终组合仍待完成。

## 1. 用例与功能结果

| 模块家族 | 独立DUT | 用例 | 结果 | 语义checked |
|---|---:|---:|---|---|
| FreeList | 4 | 52 | 52 PASS | 23/23、其余各26/26 |
| CAM | 3 | 24 | 24 PASS | 21/21、25/25、24/24 |
| AgeDetector_36 | 1 | 11 | 11 PASS | 26/26 |
| VirtualLoadQueue | 1 | 22 | 22 PASS | 43/43 |
| LoadQueueRAW | 1 | 32 | 32 PASS | 60/60 |
| UncacheEntry全16 ID | 16 | 384 | 384 PASS | ID0 75/75，其余各77/77 |
| LoadQueueRAR | 1 | 54 | **47 PASS / 7 FAIL** | **52/55** |
| LoadQueueUncache真实父块 | 1 | 72 | **64 PASS / 8 FAIL** | **40/42** |
| 合计 | **28** | **651** | **636 PASS / 15 FAIL** | 两块仍有未通过点，不跨DUT合计百分比 |

运行退出码1保留，committed manifest完整记录FAIL；没有skipped、xfail或额外error。DUT初始化种子1；各模块Python随机种子见各自冻结用例和报告。

## 2. 失败分类与范围

专用`audit_progress_run_v2.py`依据冻结问题清单核对每个完整nodeid、数量和actual/expected方向；该清单不被测试/模型读取，不构成功能豁免。

- **RAR-REL-001：7例。** 孤立release的前拍漏报和前两拍过期误报，三个load lane均复现；与原54例迭代结果一致。
- **LQU-SID-001：7例。** 合法SID回包后重用使旧未消费entry的数据或错误被新回包覆盖，SID0/3/15复现。不同SID、先消费再重用和同次合法合并回包的对照通过。
- **LQU-MMIO-IF-001：1例。** 仅UNIT-INTERFACE多MMIO selector边界；pending跨过两个未完成MMIO，不符合常规ROB许可代理，不声称合法架构流量可达。与前两项常规语义失败分开记录。

## 3. 覆盖和完整性门禁

- 28个原生构建全部在manifest及LCOV中对应，56个reached/checked功能组完整收集，checked不超过reached。
- 除LQU本体6条guarded default外，全部独立DUT本体和真实闭包原生DA均命中。RAR虽行满仍失败，不以行覆盖抵消。
- LQU保持本体1120/1126、真实22文件闭包3169/3175；三lane各data/paddr默认值有固定源哈希、匹配向量/使能/选择结构与4行真值表证明，见本运行`static-gap-proof.json`。不修改原RTL或覆盖分母。
- 功能缺口只保留RAR三个release情形与LQU两个情形（其中一项为明确域受限接口边界）；其余所有适用功能点checked完整。
- 核验全部产物SHA、build.files SHA、**111份冻结验证文件**及运行名/测试节点。旧195例审计器和旧运行未覆盖，采用新的版本化`tools/audit_progress_run_v2.py`。
- 回归结束再核对**101份已存在的运行Python/config/manifest文件**仍与启动快照一致，保存`runtime-source-consistency.json`。回归期间仅新增未被该套件导入的Replay事务适配和事后审计器，不修改正在执行的测试/参考；报告/合同后续文字不冒充运行时源码。

本回归门禁是范围/哈希/覆盖与失败方向审计，不宣称重写全部独立参考。更详细的逐拍历史证据分别保留于：VLQ `vlq-expanded-01`、RAR `rar-expanded-02`、RAW `raw-expanded-01`、entry `entry-expanded-01`、LQU `load-uncache-expanded-03`的`trace-audit.json`。LQU另有96个entry/type/bypass-lane成功s2的逐项见证。

## 4. 证据与复现

相对LSQ独立工程：

- `results/lsq-progress-regression-02/execution/`：committed manifest、原生coverage/LCOV、功能JSON/HTML。
- `results/lsq-progress-regression-02/{pytest.xml,console.log,command.json,line-audit.json,static-gap-proof.json,evidence-check.json,runtime-source-consistency.json}`。
- `results/lsq-progress-regression-02/{verification-source/,source-evidence.json,evidence-auditors/,cases/}`。

```sh
python3 -B tools/run.py --name lsq-progress-recheck-<新后缀> --workers 1 -- tests
python3 -B tools/coverage_audit.py lsq-progress-recheck-<新后缀>
python3 -B tools/audit_lqu_static.py lsq-progress-recheck-<新后缀>
python3 -B tools/audit_progress_run_v2.py lsq-progress-recheck-<新后缀>
```

当前v2审计器固定651例/28DUT范围；未来新增Replay或Store测试后应另开版本并扩大清单，不能删新测试维持老分母，也不能改写本历史结果。目标继续活动，RAR/LQU保持未验收；完整LSQ不能标记通过。
