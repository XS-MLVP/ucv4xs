# 工程根命名空间重构（2026-10-31）

## 目标与执行顺序

用户确认工程根本身成为唯一 Python 命名空间，例如 suites.memblock.lsq，删除
lsqverify 等重复包装层。本次只改组织与定位，不以目录迁移冒充事务语义迁移。

1. 记录迁移前每个工程的收集 nodeid、源文件映射和资源锚点。
2. 将十个 *verify 包的实现提升到工程根；更新 imports、动态插件、runner 和工具入口。
3. 按职责命名共享模块，移除空泛 common 外壳；保留必要的兼容字段并明确其技术债。
4. 更新现行文档、skill、静态门禁；历史证据保留原路径/日期并提供迁移说明。
5. 核验逐 nodeid 收集、同进程跨工程导入、非仓库 cwd 导入、定向原生回归和资产边界。

## 约束

- 不动忽略目录中的原生包、RTL、历史结果或已有构建收据；不清除既有未提交代码。
- 不建立旧包名的 sys.modules 别名或通过 import common 维持短路径。
- 从 suites.<group>.<suite> 入口解析工程根，不再依赖随目录深度变化的 parents[n]。
- 物理端口兼容常量仍需后续真正的事务适配，本轮不得将其统计归零或改写既有失败。

## 实际布局与根因修正

十工程统一为工程根命名空间，例如：

```python
from suites.memblock.lsq import ROOT
from suites.memblock.lsq.deq.agent import PsqAgent
```

原 *verify 包内共 2022 个文件：2014 个实现/占位文件移至工程根，8 个冗余 common
初始化文件删除，原内容记录在证据中。没有重建整个工程，也没有修改生成 RTL、原生库
或构建成功凭据。额外解决三处反向依赖：

- LSQ local_reset/reference 从 tests 移回实现侧；原始冻结证据仍用当时源码键。
- BPU retained-owner 的五个复用函数移到 tage/case/retained_owner.py，诊断脚本
  与正式用例都引用实现，而非实现引用诊断测试。
- DCache/LSU 的 DUT 清单移到 inventory.py，原生装载与工具用全限定导入；不再
  向 sys.path 注入 tools 后 import duts，两个工程可以在同进程中保持不同清单。

复杂工程的 common 子职责拆为 ports、drivers、monitors、models、checkers、
transactions、runtime、coverage、pytest_plugins；小工程直接用 native.py、harness.py、
execution.py、fixtures.py 等。没有强制增加空角色目录。六工程的 legacy_pins.py
保留兼容技术债，审计仍统计其中 P 字段，不用改文件名规避事务门禁。

36 个随目录深度变化的实现资源锚点改为工程 ROOT；runner 和比较工具一起更新命名空间
搜索根与动态插件路径，源码身份包括 pyproject 和命名空间入口。suite_python_sources
统一源码清单扫描，显式排除生成物、结果和外部链接，避免旧包目录消失后静默漏记实现。

## 已核验的证据

- 十工程迁移前后 **45806 个有序 nodeid 完全一致**；BPU/LSQ 的参数 ID 保留原历史标识，
  仅作为测试身份，不提供旧包名导入别名。
- 根测试 **96 PASS**，包括跨工程同时导入、非仓库 cwd、DCache/LSU 清单不串用、
  不反向导入 tests、旧命名空间反例和 legacy_pins 反例。
- 安装 wheel 的实际内容逐项对账，无缺失或多余 Python 实现，不含 tests/tools/docs/
  manifest、RTL、DUT、结果或原生二进制；在隔离目录从 wheel 导入 11 个代表模块通过，
  没有使用当前检出的旧包别名。正常运行仍需检出配置与生成 DUT，不宣称 wheel 自带硬件。
- 结构审计、skill 审计、资产审计、pip check、git diff --check 通过；事务门禁按预期
  非零，保留 IFU 313、DCache 2、LSQ 1057、LSU 140、MMU 29、VAGQ 179 个引脚表达式。

首次正式入口运行在 results/ucv-namespace-final-20261031，各工程固定 seed=1、worker=1，
全部运行源码前后哈希相同、11 份任务 manifest 均 committed 且 coverage_complete=true。
这表示产物收集完整，不等于硬件覆盖闭环或全部功能通过。

| 工程 | 本次范围 | 判定 |
|---|---|---|
| BPU | 指定框架/模型与 TAGE 原生代表用例 | 561 纯/框架 PASS + 2 原生 PASS |
| FTQ | 全量 | 109 PASS / 2 XFAIL |
| ICache | 全量 | 291 PASS / 3 XFAIL |
| IFU | 全量 | 144 PASS / 2 FAIL / 1 UNCERTAIN |
| DCache | probe_queue / writeback_queue / ctrl_unit | 24 PASS |
| LSQ | freelist / local_reset / runtime | 73 PASS |
| LSU | load_s2 | 47 PASS / 1 FAIL |
| MMU | wrapper / tlb | 33 PASS |
| Sbuffer | 全量 | 31 PASS |
| VAGQ | organization / binding / lifecycle / manager protocol | 13 PASS |

IFU 的 R-13 是真实 blocking 残余，report.gaps 保留该项，不能写作“全部 gap 为空”；
其他工程本轮 report.gaps 为空。LSU 的硬件预取 miss 计数 FAIL 与既有失败一致。
不改变 XFAIL/UNCERTAIN 定义，不宣称部分选择证明 BPU/LSQ/VAGQ 等全量回归。

## 产物隔离与后续边界

首次定向运行发现 Picker 默认 memory-direct.fst 仍回写 BPU/FTQ/ICache/LSQ 工程根。
fixture 生命周期改用 pytest 临时 cwd；IFU 在本轮早些时候已完成同类隔离。受影响四工程
复跑使用新的 results/ucv-namespace-clean-final-20261031，首轮原始结果保留，不覆盖凭据。
复跑仍为 BPU 561 纯/框架 PASS + 2 原生 PASS、FTQ 109 PASS/2 XFAIL、
ICache 291 PASS/3 XFAIL、LSQ 73 PASS；四工程源码在运行期间均未变，5 份 manifest
均 committed、coverage_complete=true、report.gaps 为空。四个原有散落波形的哈希、
大小、mtime_ns 均未被复跑改写，证明默认文件写入已转移到临时 cwd。

确认没有活动原生测试或打开文件句柄后，删除本轮产生的 7 个散落波形/覆盖文件，
共 7765554 字节；逐路径、大小和 SHA-256 见
[本轮清理清单](../history/suite-namespace-cleanup-20261031.json)。这些散落文件已不可用，
不得再引用为证据；两轮受管结果和原生构建缓存均保留。源码树最终检查无此类残留。
最后两处 prepare_rtl 工具补导入发生在原生回归之后：已单独从仓库外 import-only
核验并复跑根测试，不把它写成又完成一次硬件构建或全工程重跑。

本次不继续尚未完成的事务语义迁移，不把旧 complete 目标重新开启；BPU 全生产原生
回归、VAGQ 穷举集合和已有硬件缺陷仍属明确未证明/未解决范围。skill 文件更新不表示
安装、启用或客户端已注册，也没有提交/推送任何 Git 变更。

文件级映射与收集哈希见 [本轮证据](../history/suite-namespace-refactor-20261031.json)，
逐源文件搬迁见 [JSONL 清单](../history/suite-namespace-moves-20261031.jsonl)。历史经验报告
保留日期、基线和结果边界；可点击的实现链接指向当前位置，不重标旧执行来源。
