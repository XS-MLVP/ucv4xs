# 统一回归12：2203例实测1982 PASS / 221 FAIL，仍未验收

## 实际结果，而不是preflight预期

`lsq-progress-regression-12`实际完整运行2203节点，**1982 PASS / 221 FAIL**，38个
真实原生DUT、76功能组、504份启动/结束源一致。原命令未使用`-k`/deselect或开启
trace/wave；实际默认0逐拍JSON、0波形。pytest退出1保留，不能因下面审计退出0叫PASS。

```sh
python3 -B tools/run.py --name lsq-progress-regression-12 --workers 4 -- tests --tb=short
python3 -B tools/capture_end_sources.py lsq-progress-regression-12
python3 -B tools/coverage_audit.py lsq-progress-regression-12
python3 -B tools/audit_progress_summary_v13.py
```

真实结果：[manifest](../../results/lsq-progress-regression-12/execution/manifest.json)、
[JUnit](../../results/lsq-progress-regression-12/pytest.xml)、
[源门禁](../../results/lsq-progress-regression-12/end-source-check.json)、
[v13摘要门禁](../../results/lsq-progress-regression-12/evidence-check-summary-v13.json)。

## 门禁证明了什么

- 本轮精确节点集合等于回归11原2036 + S4-03的89 + plain01的78；不是选绿色节点。
- 2116个主journal的完整串行化流SHA与字节数多重集合相等，实际共460700记录；
  其余87个基础fixture没有这种主journal，不伪造额外轨迹。
- 38个DUT分别核对原DA行全集、RTL source SHA与各基线命中并集，全部保持。
- 221个普通失败的节点和首个失败主签名全部保持；不会被默认关闭日志变成PASS。
- 76组功能覆盖的已命中集合保持；Wrapper仍76/82 checked，LoadQueue仍60/63。
  上级114/114本体行命中不代表59595/59602闭包或整个功能通过。

默认摘要主journal共1328508字节；完整流仍在线检查/哈希但没有写出39068408336字节
逐拍JSON。该值是未保存的串行化流字节数，**不是**扣除全部coverage/源快照后测得的
磁盘总节省值。与原已独立审计基线的SHA相同是重复性/诊断等价证据，**不是**对未
保存新raw的独立离线逐拍语义重放。

## 仍保留的失败与准入边界

RAR release错位、合法SID复用污染、strict被disabled反馈错误解除、Forward别名/
mask范围/完整SQ代、WB错误位、split wline、zero所有权和完成顺序等仍FAIL。完整
八种子/八类型随机没有因此验收，正条件公平流不替代失败的原完整域种子。

旧S4/ordinary绿色定向的普通LD hyper/poison和过早年轻trap准入问题不由摘要相等
修复。新独立精确ROB头程序的84 PASS见[精确S4报告](lsq-s4-precise-20261019.md)，
**它在12启动后新增，未包含于本次2203节点**。local-only reset同样另有独立目录；
不能追溯把它们算入本次统一回归。

所有RTL/Chisel保持固定开源版本；未来新范围合并回归、剩余normal producer随机、
其他128/旧代、local-only域扩展和最终全层次请求→功能→检查→DA→补例审计仍必需。
本报告不关闭任何未验收任务或整体目标。
