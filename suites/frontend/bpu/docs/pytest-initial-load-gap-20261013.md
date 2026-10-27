# 生产并行回归：初始任务配对仍有优化空间

进程并行已进入完整生产入口，不再只是试点：10个 DUT、完整功能点、每个 worker
的收据和原生覆盖合并均由 `tools.refresh_coverage` 统一执行。代表坐标生产范围的
首个发布全量为64进程、pytest759.11秒；后续未发布v1为749.24秒。
最新已发布v2为755.34秒（含合并/门禁的完整刷新为965.16秒），没有实施本文的调度优化。

本轮只读检查发现一个剩余调度问题，不在运行中改动冻结源码：

- `bpuverify/common/pytest/scheduling.py` 将有 runtime hint 的用例按耗时降序排列。
- runner 使用 xdist `--dist=load --maxschedchunk=1`。
- 当前已安装 xdist 的 `LoadScheduling.schedule()` 在初始分配时仍执行
  `node_chunksize = max(node_chunksize, 2)`，给每个 worker 一段连续的两个用例。
- 因此最慢的 useful-aging 与 direction-recovery 被一起交给第一个 worker；
  后续动态分配不能拆开已经排入同一 worker 的 current/next 两项。

v1实际 call 为 useful-aging408.82秒、direction-recovery312.07秒，二者相加
720.89秒，接近 pytest749.24秒的关键路径。第二慢的独立 MicroTAGE full-useful
为430.87秒。这里不是CPU核心数不足，也不能靠继续增加worker消除最初的配对。

可优先验证的修正是确定性的“长用例 + 纯检查”初始排列：把有高耗时 hint 的
用例分别与一个无 DUT fixture 的纯契约检查配成一对，其余集合仍完整保留。
这样无需修改 xreactor、绕过 pytest driver/monitor、复制 xdist 私有调度实现，
也不需要拆掉一个功能场景内部依赖的状态序列。收集入口、controller 和所有
worker 必须产生完全相同的 nodeid 顺序，串行入口也要保持可重复。

实施前仍需：

1. 单测覆盖原集合/唯一性/稳定顺序、runtime hint 校验、没有足够纯检查时的退化行为。
2. 真实 xdist 小回归确认最慢两项被不同 worker 接受，不能只测列表排列。
3. 完整同范围回归通过原有收据/原生无回退/功能矩阵门禁后测量耗时。

这只是已定位的后续优化，没有实现或声称新耗时。不能拿两个时长的最大值直接
当作未来完整回归时间，也不能为赶时间跳过既有缺陷用例或物理覆盖分母。

## 实施与资格验证（2026-10-13）

上述确定性配对已实现于 `bpuverify/common/pytest/scheduling.py`。有耗时 hint
的场景仍降序起跑；每项后接一个没有 feature marker、没有 DUT/agent transitive
fixture、没有正耗时 hint 的契约检查（有候选才配对）。所有剩余项的相对顺序
保持不变，候选不足时保留其余降序场景，没有改变测试集合或新增调度器。
缺少 fixture closure 信息时不当作契约候选，避免误判自定义 item。

现有和新增调度契约 **36 PASS**：集合/唯一性、幂等和稳定顺序、hint 校验、
候选不足、DUT fixture 闭包排除、controller/worker相同 collection hash，以及
实际2-worker xdist 初始分配中两项长场景确属不同 worker。独立场景测试与相关
模型/读回/恢复负向检查合计116 PASS。

`production-sparse-wrap-20261013-v1` 使用相同64worker完整生产范围测量。
结束前不发布新的耗时承诺；既有755.34秒 pytest、965.16秒完整刷新仍是上轮实测。

### 完整同范围测量已结束并发布

`production-sparse-wrap-20261013-v1` 实际14,616 PASS、7 strict XFAIL、0 SKIP，
64份worker收据完整、十DUT原生零回退，296个功能点全部执行。pytest实测
**444.77秒（7分25秒）**，完整刷新**655.00秒（10分55秒）**；相对上轮
755.34/965.16秒分别缩短**41.12%/32.14%**，且增加60项PASS检查，没有删减测试。

真实controller evidence中的useful-aging为gw0、direction-recovery为gw1，
call分别416.63/321.04秒；独立MicroTAGE full-useful为gw4、431.63秒。
单场景耗时没有减少，本轮收益来自消除起始串排。所有 worker 的收集哈希一致，
不修改xreactor或xdist实现，不新建task queue，不把known-XFAIL当成SKIP跳过。
公开结果见 [完整终态](../results/production-sparse-wrap-20261013-v1/exit.json)。
