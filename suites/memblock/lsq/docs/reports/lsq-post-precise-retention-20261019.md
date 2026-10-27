# 精确S4与本地reset之后的证据收整和复核

在全部相关运行已结束并完成语义/DA门禁后，只选择三份最终原生基线：回归12、
`lsq-s4-precise-03`、`lsq-local-reset-retained-02`。它们的40份累计native coverage.dat
按SHA去重压缩，未同时保留未压缩副本。未生成或归档任何新逐拍JSON/波形。

三个已被替代的前驱 `lsq-s4-precise-01/02` 和 `lsq-local-reset-retained-01` 的3份
累计native.dat实际删除246637601字节，**没有归档这些旧payload**。原manifest、
JUnit/5个检查器FAIL、源快照、命令、LCOV、UID汇总和覆盖原分母保持，旧native.dat
不能再声称直接可读；必要时按原冻结源重跑生成。5份重复大行报告47780400字节压为
1006493字节唯一对象，逐行CSV和小结果报告继续直接可读。

[实际收整记录](../../results/storage-post-precise-v1.json)、
[旧native删除清单](../../results/retire-native-predecessors-post-precise-v1.json)、
[清理后五门禁/固定源/实际大小审计](../../results/post-precise-end-audit-v1.json)。

清理后按唯一inode计`results/`实际分配825843712字节（约787.6MiB），逻辑内容
1085490067字节；当时磁盘可用402130952192字节。是该次审计点，不是持续实时值。
所有case目录实际0 JSONL/0wave；按需临时展开的native/报告已经自动清除。固定53份
RTL SHA、开源893e1580b tracked干净树、149共享参考文件和新报告链接再次核验。

## 当前基线如何按需复核

历史报告列的是当时实际命令；当前压缩布局请通过index展开必要文件，退出后自动清理：

```sh
python3 -B tools/lsq_evidence_archive_v1.py audit lsq-progress-regression-12 -- \
  python3 -B tools/audit_progress_summary_v13.py
python3 -B tools/lsq_evidence_archive_v1.py audit lsq-s4-precise-03 -- \
  python3 -B tools/audit_lsq_s4_precise_summary_v3.py lsq-s4-precise-03
python3 -B tools/lsq_evidence_archive_v1.py audit lsq-local-reset-retained-02 -- \
  python3 -B tools/audit_lsq_local_reset_v2.py lsq-local-reset-retained-02
```

DA前后比较还需旧的**行报告**而非已删除native.dat：S4 coverage-v2同时stage
`lsq-s4-precise-02`；local-reset coverage-v1同时stage `lsq-local-reset-retained-01`。
`tools/audit_lsq_post_precise_v1.py`已经实际自动展开这些所需对象并重跑五个门禁，全部
exit0；报告中回归12仍明确1982 PASS/221 FAIL，绝不是清理把失败变成绿色。

源/UID检查是在线实际执行，小事件门禁只重放保留下来的语义事件，不宣称未保存新
逐拍raw可独立离线重放。后续不再默认每轮保留全部旧原件；默认小摘要、FAIL、覆盖
与必要复现信息的策略不变，完整目标和所有未验范围也不改变。
