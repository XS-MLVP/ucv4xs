# 已验证叶子模块的同进程完整回归

`results/leaves-regression-02`：**87/87 PASS**，8个真实独立 DUT 构建、16个完整 reached/checked 功能组。所有适用语义情形命中，全部原生插桩本体/真实流水辅助行命中；RAR 三个零延迟辅助块仍保留无DA的工具边界，不算0/0覆盖。

| 组 | 独立 DUT | 通过用例 | 适用语义 checked |
|---|---|---:|---|
| FreeList | RAR/RAW/Replay/Uncache 四变体 | 52 | 23/23；其余各26/26 |
| CAM | RAR地址/RAW地址/RAW字节 三变体 | 24 | 21/21、25/25、24/24 |
| AgeDetector | LSQ本地40项版本 | 11 | 26/26 |

运行使用同一 pytest/xreactor 管理进程，但每例仍是独立原生 DUT 和独立参考；**不是父块组合或整体LSQ验证**。该回归验证公共 fixture/runtime 改动和新增模块没有破坏已有叶子结果，不重开已完成语义范围。

证据：

- `results/leaves-regression-02/execution/manifest.json`：committed，pytest_exitstatus=0，87原生输入、8构建、16功能组，coverage_complete/cleanup_complete。
- `results/leaves-regression-02/line-audit.json`：各DUT逐项分母/缺口，最终无插桩行缺口。
- `results/leaves-regression-02/evidence-check.json`：已核验全部产物/build身份、45个冻结源码文件的SHA-256、checked≤reached、运行名及build ID一致。
- 同目录 `verification-source/`、`source-evidence.json`、`command.json`、`pytest.xml`、`console.log` 与 `cases/` 保存实际实现、命令、结果和波形。

第一次整套收集 `leaves-regression-01` 发现多个测试子目录具有相同 `test_basic.py`/`test_extended.py` 模块名，pytest默认导入模式产生 collection mismatch，尚未执行 DUT 测试。保留其真实错误；修正 `pytest.ini` 为 `--import-mode=importlib` 后在新目录完整重跑，未删除缓存、改名遮掩或修改RTL。先前各模块独立运行证据保持有效。

复现（在 `memblock-hash/lsq/`，run名必须新建）：

```sh
python3 -B tools/run.py --name leaves-recheck-<唯一后缀> --workers 1 -- tests/freelist tests/cam tests/age
python3 -B tools/coverage_audit.py leaves-recheck-<唯一后缀>
python3 -B tools/verify_run.py leaves-recheck-<唯一后缀> --require-semantic-complete --require-line-complete
```

后续业务子块、LoadQueue/StoreQueue/LsqWrapper 仍未通过，不能将87例作为整体覆盖率分母。
