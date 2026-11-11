# RAS BOS：从4个原生缺口到显式退休丢失故障场景

## 需求和合法性边界

此前发布的 `production-sparse-boundaries-20261013-v1` 中，RAS 为565/585。
剩余20键不能都归为既有enable-metadata缺陷：16键有局部守卫/顶层译码排除
条件，另4键 `rtl/ras/RasStack.sv:598,600,601,602` 属于非push退休距离回收。
完整585分母保留。既有 `BPU-RAS-008` strict XFAIL不变。

源头为 `XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/RasStack.scala:378–381`：
push退休直接令BOS等于该分支的pre-operation TOSW；否则有效退休距离大于2
时令BOS等于该TOSW减1，距离不大于2则保持。指针为16槽加一代位，按模32
运算，本场景始终限制有效队列窗口不超过16。

不能伪造action=0普通分支退休来命中回收路径。`ftq/CommitQueue.scala:43–45`
只接受非None的RAS action，`Ftq.scala:510–513`向BPU提供该队列的退休信息。
在完整有序call/return通知下，普通call会持续推进BOS，不能仅因端口接受某
种payload就称其为正常FTQ生命周期。

新 `BPU-RAS-016` 因此明确使用**独立模块公开端口的通知丢失故障注入**：
照常投递speculative call，但有意不发送其中一或两次call退休通知；随后
发送真实return或call及其真实pre-operation metadata。此测试不声称FTQ
正常流会产生这六种输入，也不证明上游通知丢失的系统级恢复正确性。

## 最小语义场景

固定不同返回地址；用正常已退休临时call/return对保留一个base frame。
前缀只用于形成两个指针代关系，不枚举8个提交栈槽或16个推测队列槽。

| 代关系 | 前缀结束TOSW/BOS | 丢失通知后距离2 | 丢失通知后距离3 |
| --- | --- | --- | --- |
| 同代 | 5/4 | return保持BOS=4 | return回收至6；call优先采用7 |
| 跨代 | 16/15 | return保持BOS=15 | return回收至17；call优先采用18 |

距离2丢弃一次call通知，距离3丢弃两次。三种结果×两种代关系，共6个
有区别的功能上下文，不是物理地址笛卡尔积。

丢失通知的frame从未写入commitStack。非push回收后，如果其推测项被排出
有效范围，公开top应回退到对应**保留的提交单元**，不能期望那个未提交
地址仍然存在。本场景检查该降级行为，再实际return到base frame；各模式
继续正常call/return并检查幸存top、SSP/SCTR及完整状态保持。

## 分层和检查

- 静态Bundle：`ras/monitor/observation.py`在已有只读memory-direct绑定中加入BOS；
  不使用VPI，不写内部信号，不修改RTL/DUT或xreactor。
- 动态驱动：已有RasAgent/PulseDriver提交结构化公开端口事务。
- 参考：`ras/model/retirement.py`将通知可能不连续的retirement storage与
  distinct-call speculative queue分开建模。预期来自输入与数学指针状态，
  不从DUT已观察结果反推。旧ordered/repeated-call模型保持原作用域。
- 比较：`ras/scoreboard/retirement.py`使用xreactor Scoreboard，同事件比较
  全部8个保留单元、nsp、BOS、完整公开top/redirect/commit metadata、pending
  retire payload。Mismatch直接抛异常，由pytest判失败并显示上下文。
- 场景支持：`ras/case/retirement_gap.py`检查所有有效输入、每个周期、已注册
  commit到child storage的延迟及timingTop下一周期的范围更新。
  向外暴露有语义的 `check_gap`，testcase没有edge、gather或硬编码等待。
- 功能覆盖：6上下文×6契约=36 bins；仅在全部比较成功后采样。
  模型/状态篡改/每格必需性/输入作用域共107项新增纯测试。

新模型刻意排除重复计数、SSP容量回绕、超过16条的有效队列和任意旧redirect。
这些场景不能靠它的PASS推断通过。保留旧模型、旧需求和7项strict XFAIL。
默认仅写6条紧凑摘要和功能覆盖，不导出逐周期JSON或波形。

## 资格与发布

首个真实DUT候选1 PASS，RAS模块检查293 PASS、1既有strict XFAIL。
独立资格 `results/ras-retirement-gap-qualified-20261013-v1` 已退出0，1 PASS，
36/36语义格闭合。`tools.coverage_delta`在相同RTL/信号schema下逐键归因：
恰好新增 `RasStack.sv:598,600,601,602`，每键计数2，对应两种代关系下的
非push距离3回收。隔离场景本身472/585，不能替代全量覆盖率。
见该目录 `functional-line-delta.json`。

完整生产 `results/production-ras-retirement-gap-20261013-v1` 已退出0并发布：
14,810 PASS、7既有strict XFAIL、0 SKIP；299功能点全执行，292 PASS、7 XFAIL。
64进程pytest442.96秒，完整刷新656.10秒；210功能组，198组全满。
RAS为569/585，精确新增同样4键，十DUT零旧键丢失。其余9 DUT指标不变，
shadow选择cross仍29/30，MicroTAGE9904/11053。剩余RAS16键与原局部排除集合
完全相同；保留585分母，不把它称为全RTL可达性证明。

重新核验64份worker receipt、14,817测试生命周期、968功能覆盖输入、
相同1,730文件源码epoch、独立增量、根报告/HTML/LCOV和production profile索引。
见该运行 `retirement-increment-audit.json`。独立全动态审查和总体目标仍为false，
不能把本轮一致性核对称为独立全动态审计。独立资格的未命中不是全量回退，
旧历史覆盖union也不能当成本次覆盖。
