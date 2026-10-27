# 当前已实现范围统一回归：188通过、7个RAR已知失败

**本次不是LSQ整体通过，也不是绿色回归。** `lsq-progress-regression-01` 在同一个pytest/xreactor进程运行当前已实现的全部195个用例，覆盖11个独立原生DUT；结果 **188 PASS / 7 FAIL，退出码1**。7个失败都精确对应RAR-REL-001，未添加skip、xfail或修改预期。

| 当前已实现测试族 | 用例数 | 结果 |
|---|---:|---|
| 四个FreeList | 52 | 52 PASS |
| 三个CAM | 24 | 24 PASS |
| AgeDetector_36 | 11 | 11 PASS |
| VirtualLoadQueue | 22 | 22 PASS |
| LoadQueueRAR | 54 | 47 PASS / **7 FAIL** |
| LoadQueueRAW | 32 | 32 PASS |
| 合计 | **195** | **188 PASS / 7 FAIL** |

命令为 `python3 -B tools/run.py --name lsq-progress-regression-01 --workers 1 -- tests`。这里“全部”仅指当时已经实现的测试，不包括尚未实现的UncacheEntry/Replay/Store或真实父块组合；没有用独立DUT集合代替整体连接验证。

## 覆盖与缺陷没有互相抵消

11个独立DUT的原始本体插桩行均完整命中，实际带插桩的下级也完整；零延迟直连辅助模块无DA的边界仍保留。22个reached/checked功能组完整收集，只有RAR的三个checked情形未通过：

- `RAR-RELEASE.previous`
- `RAR-RELEASE.previous_isolated`
- `RAR-RELEASE.no_expired_window`

其他10个DUT的既定语义均checked。RAR仍是55 reached / 52 checked；三个lane的孤立前拍release漏报及两拍前过期release误报，在统一进程中再次复现。它们没有因其他DUT通过或RAR行覆盖100%而被豁免。详见 [RAR报告](rar-20261018.md) 和 `manifest/known-issues.json`。

## 实际证据门禁

`tools/audit_progress_run.py lsq-progress-regression-01` 已实际核验：

- committed manifest、coverage_complete和cleanup_complete，195个JUnit条目，无skip或error；各测试族数量与上表一致。
- 11个原生构建、22个功能组；原生产物、build.files及83个冻结验证源/合同/manifest文件SHA-256一致。
- 全部原始插桩行/实际下级分母及缺口和run身份一致，checked不超过reached。
- 7个失败的完整nodeid和实际/期望nuke方向与开放问题逐一一致；没有新增或被隐藏的非RAR失败。

审计输出为 `evidence_audited_with_failures`、suite_acceptance=`NOT_PASS`。该门禁证明产物与失败记录可审计，不是功能豁免，也不调用仅接受全通过运行的verify_run去制造绿色状态。

证据目录：`results/lsq-progress-regression-01/`，含command/JUnit/console、原生LCOV、功能JSON/HTML、`line-audit.json`、`evidence-check.json`、逐例引脚/波形和冻结源码/审计器。

后续继续全部UncacheEntry ID、LoadQueueUncache/Replay、Store分支、LoadQueue/StoreQueue/LsqWrapper真实组合，RAR验收保持未完成。原始开源Chisel和RTL未作迎合测试的修改。
