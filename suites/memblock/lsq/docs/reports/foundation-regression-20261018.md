# 基础阶段与VirtualLoadQueue的统一回归

`results/foundation-regression-01` 已实际完成 **109/109 PASS**，包含9个真实独立DUT构建、18个完整reached/checked功能组：原8个叶子模块87例与VirtualLoadQueue 22例。各DUT适用语义情形全部checked，各原生插桩本体/实际流水子块无剩余行缺口。

| DUT组 | 实际通过用例 | 最终语义checked |
|---|---:|---|
| 四个FreeList变体 | 52 | RAR 23/23，其余各26/26 |
| RAR/RAW地址与字节CAM | 24 | 21/21、25/25、24/24 |
| LSQ本地40项AgeDetector | 11 | 26/26 |
| 120项VirtualLoadQueue | 22 | 43/43 |

保留RAR地址CAM的三个零延迟直连模块无DA这一工具分母边界，不将0/0算作100%。这是一套跨模块回归，**不是把9个DUT连在一起的父块集成**，不能作为LoadQueue、StoreQueue或LsqWrapper通过证据。

证据路径相对 `memblock-hash/lsq/`：

- `results/foundation-regression-01/execution/manifest.json`：committed、pytest_exitstatus=0、109原生输入、9构建、18功能组、coverage_complete/cleanup_complete。
- `results/foundation-regression-01/line-audit.json`：每个真实DUT和辅助模块的行覆盖分母/缺口，全部适用功能情形。
- `results/foundation-regression-01/evidence-check.json`：实际验证所有产物/build身份、57个冻结源文件SHA-256、运行名/build ID及checked≤reached。
- 同目录`verification-source/`、`source-evidence.json`、`command.json`、`console.log`、`pytest.xml`、`cases/`保留真实代码、命令、结果和逐例波形；VLQ逐拍引脚日志也在各自case中。
- 各模块首轮、未覆盖行分类、补例及前后提升的详细证据仍见各自报告，统一回归不会覆盖或取代这些历史。

本次没有新增RTL变体或修改原始Chisel/RTL，也没有重开已完成模块的范围。下一阶段是保留真实FreeList/CAM验证LoadQueueRAR，再推进RAW、Uncache、Replay及上级组合。

```sh
python3 -B tools/run.py --name foundation-recheck-<唯一后缀> --workers 1 -- tests/freelist tests/cam tests/age tests/vlq
python3 -B tools/coverage_audit.py foundation-recheck-<唯一后缀>
python3 -B tools/verify_run.py foundation-recheck-<唯一后缀> --require-semantic-complete --require-line-complete
```
