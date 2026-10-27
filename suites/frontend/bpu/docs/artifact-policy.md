# 诊断轨迹与覆盖率产物

## 历史测量回收与单轮大小（2026-10-16）

最新完整失败诊断为 `production-utage-usefulness-events-20261016-v1`：18852项，
18824 PASS/25 FAIL/3 XFAIL；最终目录约169.63 MiB，十份DAT共64,029,798字节，
worker输入已回收。另回收57项被替代测量、约241.97 MiB，分析与日志保留。
源码epoch与最终424项专项相同，正式报告不覆盖。旧测量按下述最新完整轮策略
回收，原因、日志、定义审查与资格结论保留；当前状态以`results/RETENTION.md`为准。

前一完整失败诊断为 `production-main-latest-age-20261016-v2`：18754项，
18726 PASS /25 FAIL /3 XFAIL，最终目录约170 MiB（含缺口账本/定义审查），十份
最终DAT共64,028,875字节，worker输入已回收。
首轮相同任务因会话中断未提交，不作为覆盖证据；已按精确清单删除441个原始
测量文件、释放约3.02 GiB；另回收56个被替代的覆盖率载荷、约281 MiB，
日志、原因和资格结论保留。最新测量及正式/物理比较依赖保留，详情见
[`results/RETENTION.md`](../results/RETENTION.md)。以下167 MiB记录属于前轮，
仍不是167 GiB；临时峰值与最终保留大小继续区分。

用户授权仅保留最新完整回归的测量产物，删除历史覆盖率表、生成的覆盖率
HTML、波形及原始场景轨迹，保留原因分析、缺陷结论、日志和复现脚本。
前一完整诊断为 `production-feature-domains-20261016-v2`：全目录约167 MiB，
并非167 GiB；普通生产回归最终产物应以1 GiB以内为目标，默认不开原始输入、
完整功能数据库或逐周期轨迹。该大小目标不是已经实现的运行时硬磁盘配额。
并行采集的临时表峰值可能超过1 GiB；异常中断会保留输入供定位，不能把这些
输入默认永久保留。定位后按用户授权的最新完整测量保留策略回收，日志和原因
分析保留。本轮被替代的中断尝试与前轮覆盖率由独立清理清单记录。

旧正式报告及生产/物理比较基线仅保留仍被入口引用的汇总和LCOV，不保留其
worker DAT或逐例功能快照。最新诊断仍有25个普通FAIL，不能冒充通过基线。
历史manifest和receipt保留的是当次执行事实，其路径不再表示原始文件仍可用；
已删除的测量载荷只能重跑生成。最新完整诊断文件保持不变。

清理使用 `tools/prune_result_artifacts.py`：先预览精确选择，再验证选择未变化、
无进程正在读取候选文件，然后逐文件删除；不递归删除整个回归目录。所有
保留文件在删除前后校验SHA256。清理清单和结果见
`results/artifact-retention-20261016-plan*.json`。

## 2026-10-16：当前生产由 xreactor 托管

`python3 tests/run_all.py` 默认调用 `xreactor run`，不再安装项目旧 native
collector。功能覆盖自动从对象捕获，worker 压缩 checkpoint 仅在运行期间存在；
最终每个 DUT build 一份完整 DAT/LCOV。manifest 提交后回收 worker 输入，普通
测试 FAIL 仍保留非零判定并可生成诊断报告，不冒充合并失败或验证通过。

默认不写逐 case 功能 JSON，不导出最终完整功能 JSON，也不导出逐周期轨迹。
分别用 `--keep-coverage-inputs`、`--export-coverage-json`、`--dump-trace` 显式开启
调试保留；最后一项同时保留 worker 输入。纯模型/schema 测试不贡献 DUT 功能
测量，显式序列化单元测试不受影响。项目只保留功能点判定与原生源行归因。
详见[职责、输出树和资格状态](xreactor-managed-runner-20261016.md)。

下文的 `--artifact-run`、`--rtl-retention` 和项目 collector 说明属于普通 pytest
兼容/`--engine=legacy` 路径及历史资格，不是当前 managed 生产入口。

## 默认行为

普通 pytest 回归不导出完整逐周期轨迹。断言、driver/monitor、参考模型比较、
功能覆盖与功能点结果继续执行；原生 RTL 行、分支、toggle 覆盖继续收集。

需要诊断时，在现有 pytest 命令中显式增加 `--dump-trace`，例如：

```sh
pytest tests/bpu/testcase/test_sc_common_history_training.py --dump-trace
```

完整轨迹统一导出为 `.json.gz`。导出入口位于 `bpuverify/common/env/trace.py`，
开关由 `bpuverify.common.pytest.artifacts` 管理，串行与 xdist worker 使用相同规则。
关闭时不序列化、不解析路径、不创建轨迹文件；开启时流式压缩，完整写入成功
后才发布，不覆盖已有轨迹。普通失败仍由 pytest 报告，不会自动打开全量导出。

直接串行运行 `pytest` 也会自动创建 `results/pytest-<uuid>/` 隔离目录，
不再覆盖根目录的正式功能点报告或原生清单；成功和失败选跑均适用。
collect-only 不创建测量目录，也不改已有报告。并行仍要求显式
`--artifact-run`，生产入口会自动提供。

这不是停用内存中的检查数据：现有 scoreboard 和功能覆盖继续使用实时快照。
低层显式 trace codec 仍可供诊断工具调用，但普通场景的 22 个落盘入口均已
接入默认关闭的导出策略。波形运行时默认关闭的策略未变。

## 为什么原生覆盖率累计很大

实际抽查的 BPU 单份原生文件约 23 MiB、132900 个点，其中：

| 类型 | 点数 | 文本字节 |
|---|---:|---:|
| toggle | 109866 | 20167311 |
| line | 9278 | 1506991 |
| branch | 13756 | 2303236 |

Verilator 写出的是整张覆盖表，不是逐周期轨迹。每次都包含路径、层级、
点位元信息和零计数项；单份大小不会随仿真周期线性增长。
测试使用独立 DUT，每个实例结束时导出一份，再叠加历史回归、快照与备份，
才累计到几十 GiB。串行运行同样数量的实例，也会产生同样数量的原始文件；
并行主要改变峰值与 worker 输出目录。

现在生产 pytest 默认采用 `--rtl-retention=merged`：DUT 创建前分配独立路径，
每批约 16 份输入在测试 teardown 后调用该 DUT 构建记录的 Verilator 原生
合并器，每个 run/DUT 保留一份完整聚合表。成功提交后才回收已消费输入；
意外失败测试的 raw 保留。点位、零计数、元信息和覆盖类型均不筛选。
合并或发布失败时保留输入并使回归失败，不继续重复合并已提交批次。

诊断时显式增加 `--rtl-retention=raw` 可保留每例原始文件；这与
`--dump-trace` 是两个独立开关。`--rtl-batch-size=16` 可调整批次大小。
此机制由生产 `bpuverify.common.pytest.features` 安装；禁用该插件的旧隔离诊断入口
仍保持原来的 raw 语义，不自动冒充已完成的并行生产迁移。

十模块各两项真实场景分别在 raw／merged 模式通过，全部 native 点表、
计数、LCOV 与缺口摘要逐字节／逐字段一致；完整 framework／scoreboard
5810 项通过。详见 [原生保留策略资格结果](../results/native-retention-qualification/qualification.json)。

完整刷新入口为 `python3 tests/run_all.py`，统一调用 `tools/refresh_coverage.py`，
默认使用 **最多32个独立 worker**（不超过 CPU 亲和性允许的核心数），自动创建
新的 `results/regression-*` 目录并冻结
源码、DUT 和执行依赖。`--workers=1` 可做串行诊断，`--run-dir=results/新目录`
可指定输出目录；`--source-epoch` 可追加已有源码清单，不再要求人工维护清单。
它校验完整收集与执行身份、已知 XFAIL、十模块分母和历史 hit 不丢失，
只读取本次 worker receipt 明确列出的 FC/RTL 输入；完整通过后才发布汇总。
全量回归通过不等于全部物理路径或独立动态审计已经完成。

单个用例组的快速并行迭代直接使用正式插件：

```sh
python3 -m pytest -n 32 --maxschedchunk=1 --max-worker-restart=0 \
  --artifact-run=results/新的局部运行目录 tests/bpu/testcase/test_integrated_abtb_counters.py
```

并行必须提供新的 `--artifact-run`；直接 `pytest -n 32` 会拒绝执行，避免共享
旧输出目录。目录按 run/worker/完整 nodeid 的 SHA256 隔离，DUT 在 worker 内
创建，不跨进程共享实例。controller 校验每个 worker 的完整收集、三阶段报告、
退出码与产物哈希，再统一写功能点和覆盖率 manifest。缺 receipt、崩溃、损坏或
收集不一致会失败，不会自动重跑掩盖错误。系统依赖见 `requirements.txt`，
生产运行不依赖 `/tmp` 试点的包或输出重定向 shim。

原生保留策略现在按 **worker/DUT** 分批聚合，最后由 controller 对所有 worker
的同名 DUT 再做 native 合并。worker 数增加会增加少量聚合表和 pending 原始
表的峰值，默认并行度上限为32，不自动占满本机256个CPU。32个worker各两份
真实BPU实例的资源资格共64PASS；每个native实例约256个线程，实际cgroup线程
上限629145，且需考虑其他进程占用。完整逐周期轨迹仍默认关闭。

正式入口显式设置 `--dist=load --maxschedchunk=1`。xdist 初始仍保留每个 worker
所需的 current/next 两个未完成用例，此后逐例补发，避免默认数百用例的大块
锁在少数worker。已完成场景的实测耗时约220秒（五alias）与778秒（final NT），
不能从已完成用例总百分比线性推算剩余时间。资源限制更紧时可显式降低workers。

原生 LCOV 的当次入口以 `rtl-line-coverage.json` 每个 DUT 的 `lcov_file`
为准，不能猜测根目录文件或扫描历史目录。完整刷新会自动同步十模块 canonical
LCOV；对历史报告手动修复时，用
`python3 tools/sync_published_lcov.py --publish` 将十模块 LCOV 原子同步到
`results/rtl-lines/`；不加 `--publish` 时仅检查，发现过时文件返回非零。
工具预先校验十模块齐全、pytest 成功、LCOV 的完整 SF/DA 身份及报告的
hit/total；源文件变化、重复源行、缺输入或 symlink 均拒绝发布。
这只是同步已有测量，不产生新的覆盖率贡献。

## 本次验证与版本边界

旧审计已按用户授权终止；不把取消记为审计完成。保留了修改前的 23 份源码，
用于还原当时的轨迹导出改动；它们不证明后续所有修改版本都可精确恢复。
下列轨迹策略资格结果绑定当时的 1221 文件源码清单，不代表当前完整源码身份。

2269 项契约／回归通过，默认关闭的 SC、ABTB、bypass、RAS 四个真实
memory-direct 场景通过，显式开启的 SC 对照通过。默认轨迹数为零。
SC 原生覆盖文件逐字节一致；功能覆盖 schema、bin、计数、来源内容一致，
仅独立运行的 UUID 及其派生快照哈希不同，两份快照均通过完整性验证。

详见 [验证报告](../results/coverage-artifact-policy-v1-readonly.json)。
现有全量覆盖率报告属于旧源码版本；本次局部验证不冒充新版本全量刷新，
也没有新增物理覆盖 bin 或缩小覆盖率目标。

## 集成计数场景的内存与计时（2026-10-11）

五 alias、final-not-taken、later-taken 场景默认使用独立的流式覆盖校验器，
保留 reset/输入推导、全部 counter/PLRU/shadow/SRAM 比较，不再在场景结束后
保存并重放全部完整状态网格。两套校验器与全部物理 way 要求都通过后，才提交
任何功能覆盖计数。中途或末尾失败都不会获得部分覆盖信用。

历史查询保留 tick 索引及关联所需的紧凑见证；最近8帧保留完整诊断状态。
这不是整个历史固定内存：关联见证仍随观察周期增长。开启 `--dump-trace`
仍保留完整历史用于无损导出，不走紧凑历史路径。

每例仅增加一份小型 `timing.json`，记录成功状态、总时长与阶段累计时长，
不记录逐周期值。`coverage.counter_validate` 和 `coverage.bypass_validate`
嵌套于 `stimulus_and_live_checks`，不能把所有阶段相加作为总时间。
写计时文件失败不会遮蔽原有 checker 异常。

通用静态采样与比较快路径在 xreactor 实现，不放在 testcase 中。
静态 sampler 缓存 Bundle 结构、信号宽度和访问器，不缓存信号值或 X/Z；
信号重绑定后须重新编译 sampler，monitor 重启会自动重编译。
普通 `Bundle.sample()` 保持动态语义。

三个相同 bank0/set0 原生场景的对照中，pytest 总时长从789.17秒降到440.49秒；
6份功能覆盖 schema/计数一致，132900个原生点（含零计数、line/branch/toggle）
的 key 和全部计数一致。原观察窗口未缩短。提前结束窗口的另一次实验虽通过
断言和功能覆盖检查，但少命中54个映射行，故未合入；不能只凭 FC 不丢 bin
来批准缩短场景。

可复核证据与精确可回退补丁位于
[运行时优化记录](../results/case-runtime-optimization-20261011-v1/promotion.json)。

## 旧临时产物清理（2026-10-10）

按用户要求删除了旧逐周期 JSON、重复原生覆盖率、报告／DUT 备份和过时的
工具测试副本，共约 189.4 GiB，包含 17 个过时测试文件。清理后磁盘约有
306 GiB 可用。当前源码、正式测试、DUT、系统安装、工具链与必要重跑脚本保留。

旧 `results-before-memory-direct.tar` 备份已经删除，不能再视为可恢复归档。
历史汇总报告保留，但部分临时原始产物已按要求回收，需要时重新运行验证；
已终止的旧版本审计不能不经重新适配直接重启。

清理后 53 项框架契约测试和 1 项真实 memory-direct SC 测试通过，未导出
完整逐周期轨迹；SC 原生覆盖文件与清理前逐字节一致，功能覆盖仍正常导出。
精确删除范围见 [清理清单](../results/tmp-scoped-cleanup-v2.json)。

随后又清理了 3464 个旧临时文件（含 674 份与正式测试相同的副本），释放
16.06 GiB；旧 `formal-results.tar.gz` 也已删除，不能再用于恢复。当前源码、
正式测试、DUT 和运行中任务依赖保留，删除前后在跑回归绑定的 1224 个源码
文件哈希一致。详见 [追加清理清单](../results/tmp-scoped-cleanup-v3.json)。
