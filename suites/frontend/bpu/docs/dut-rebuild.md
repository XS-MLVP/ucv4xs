# BPU DUT 重建与工具链检查

## 当前要求：memory-direct（2026-10-09）

所有 DUT 必须使用 `--rw mem_direct`，保持 `VPI=OFF`，不使用 `--internal`
导出 DPI getter。构建时开启 trace（`-w memory-direct.fst`），让 picker 从
trace 代码恢复 direct/projection/expr/const 只读映射并合入 offset YAML；
不能将优化过的信号等同于不可观测，也不应为此强制 `--public-flat-rw`。
生产 monitor 统一通过
`suites.frontend.bpu.runtime.memory_direct` 绑定；基地址为零、offset 不匹配或字段缺失均立即
报错，禁止退回 VPI，也不使用生成 wrapper 的共享内部信号缓存。

可复现构建入口（`<stage>` 必须是新建的绝对路径目录）：

```sh
python3 tools/rebuild_memory_direct.py --stage <stage> \
  --dut bpu abtb utage tage uras ras sc mbtb ittage ubtb --jobs 8 --parallel 4
```

构建和安装分开；先完成真实 DUT 冒烟验证，再运行同一命令加 `--install`。
安装器核对信号 schema、原始生成 RTL 指纹、native Python 绑定和 offset 表，
旧包保留在 `<stage>/backup-dut/`。本次 trace 映射构建目录为
`/tmp/bpu-memory-direct-trace-k8aQV8`，完成情况以该目录各 DUT 的
`*-build.exit.json`、`*-install.exit.json` 和回归记录为准，不能仅据启动日志
宣称迁移通过。旧 VPI 审计已按用户授权终止，其日志/报告保留为历史证据；
不与新的 memory-direct 原生覆盖数据混合。

以下工具链安装与历史回归结果描述各自当时的版本，不代表本次迁移已通过。

## 历史工具链记录

2026-10-07 已为覆盖率插桩相位修复重建并安装全部十个 DUT：采用已安装的
`/opt/verilator-5.052`，启用 VPI，关闭新增 expression/FSM coverage。
所有 RTL 与信号 schema 均与旧包一致；不切 picker/xcomm/RTL 分支，
不改变系统默认 Verilator。包内 `build-provenance.json` 记录编译器、
处理器路径和指纹，报告按包选择处理器，不能只依赖默认 PATH。
五种逐笔原样 RTL 复现及新旧映射四格对照见
[coverage-phase-audit.md](coverage-phase-audit.md)。本轮完整旧包备份在
`/tmp/bpu-coverage-v5052-26DlAX/backup-dut/`，旧报告曾位于 `reports-before/`；
这些过时副本已按用户要求于 2026-10-10 清理，不再是可恢复备份。
同次清理删除了 `/tmp/bpu-memory-direct-migration-4d4IEO/` 下的旧 DUT 副本，
保留当前仓库 DUT、正式测试和运行中任务依赖。清单见
`results/tmp-scoped-cleanup-v3.json`，需要旧产物时应重新构建或运行。
以下 2026-10-06 的系统 xcomm/picker 安装说明仍适用。

2026-10-06 已在本机把 xcomm ABI v3 安装到 `/usr/local`，安装与其模板匹配的
picker `2.0.0-xreactor-6f0f365-2026-10-02`，并从仓库 `rtl/` 重建全部十个
`dut/` 包。picker 源码工作树仍在 `master` (`e447bb8`)，xcomm 子仓库仍在
`xreactor` (`24adffc`)；**不要从 picker 当前 `master` 模板重建这些 DUT**，
该模板会生成与 xreactor 版 xcomm 不兼容的 `XPin` 绑定。

本次系统安装的 xcomm 来自 `picker/dependence/xcomm` 的 `xreactor`
分支，CMake 以 `BUILD_XSPCOMM_SWIG=python` 构建 C++ 库和 Python
绑定，再安装到 `/usr/local` 并运行 `ldconfig`。picker 使用已构建的
`2.0.0-xreactor-6f0f365-2026-10-02` 可执行文件，搭配同一分支的
`template/` 安装到 `/usr/local/share/picker/template`；不能只升级
可执行文件而保留旧模板。安装前已把旧系统产物备份，且未修改上述源码分支。

## 先检查系统工具链

```sh
picker -v
picker --show_default_template_path
picker --show_xcom_lib_location_python
PYTHONPATH=/usr/local/share/picker/python python3 -c 'import xspcomm as x; assert x.XTriggerEngine.CoverageVersion() == 3; assert hasattr(x.XTriggerEngine, "AttachCoverage")'
```

预期模板在 `/usr/local/share/picker/template`，Python 绑定在
`/usr/local/share/picker/python`。`picker --check` 的 Lua/Scala 项在当前安装
中缺失，但 BPU 只使用 Python，不能把这两项误判为 BPU 回归失败。

## 从 RTL 构建

在对应的 `rtl/<目录>/` 下运行 picker；`filelist.f` 使用相对路径，不能从
仓库根目录直接执行。必须启用 `-c`，否则不会有 Verilator RTL 覆盖数据。
例如只构建 MicroRAS 到一个新的 staging 目录：

```sh
cd /home/xyl/bpu-verify-kunminghu-v3/rtl/uras
env VERILATOR_ROOT=/opt/verilator-5.052/share/verilator \
  PATH=/opt/verilator-5.052/bin:$PATH \
  picker export MicroRas.sv --fs filelist.f --sname MicroRas \
  --tname UrasDut --tdir /tmp/bpu-dut-stage/uras \
  -c --rw mem_direct -w memory-direct.fst --vflag='--no-coverage-expr --no-coverage-fsm' \
  --lang python --cp_lib 1 --autobuild true
```

其余 DUT 使用完全相同的选项，只替换前三个名称和目标目录：

| 目录 | RTL 顶层 `.sv` / `--sname` | `--tname` |
| --- | --- | --- |
| `abtb` | `AheadBtb` | `AbtbDut` |
| `bpu` | `Bpu` | `BpuDut` |
| `ittage` | `Ittage` | `IttageDut` |
| `mbtb` | `MainBtb` | `MbtbDut` |
| `ras` | `Ras` | `RasDut` |
| `sc` | `Sc` | `ScDut` |
| `tage` | `Tage` | `TageDut` |
| `ubtb` | `MicroBtb` | `UbtbDut` |
| `uras` | `MicroRas` | `UrasDut` |
| `utage` | `MicroTage` | `UtageDut` |

`picker` 在某些示例测试失败时仍可能返回退出码 0，所以还要检查构建日志
是否含 `Error: Test failed` 或 `Traceback`。构建完成后，先验证每个 staging
包存在对应的 `_UT_*Dut.so`、`libUT*Dut.so`、`signals.json` 和生成的
`.v/.sv`；
导入并实例化 DUT，确认实例的 `io` 层次及包所导出
`xsp.XTriggerEngine.CoverageVersion() == 3`。若这次只更换工具链、
没有更换 RTL，则应对比新旧 `.v/.sv` 与 `signals.json` 是否一致。

全部检查通过后才将 staging 包移入 `dut/`，并把旧包保留到独立备份目录。
本次旧包保存在 `/tmp/xcomm-abi3-06UMed/backup-bpu-dut/`；旧系统 picker/xcomm
保存在 `/tmp/xcomm-abi3-06UMed/system-backup/`。这些是当前机器上的临时备份，
不是长期归档。生成的 coverage `.dat` 可能仍记录原 staging 绝对路径；
`suites.frontend.bpu.coverage.rtl` 会按 DUT 名称解析到当前 `dut/` 中的生成源文件。

## 回归

```sh
cd /home/xyl/bpu-verify-kunminghu-v3
PYTHONPATH=/home/xyl/xreactor/src:/usr/local/share/picker/python:/home/xyl/bpu-verify-kunminghu-v3 \
  python3 tests/run_all.py
```

最新完整结果是 1401 PASS、6 strict XFAIL、0 SKIP，计划功能点 254/254 已执行；
333 份本次 raw、146 功能 JSON、147 组和十份 LCOV/JSON/HTML 已核对同源/时效。
MainBTB 为 1056/1056（100%），TAGE 为 4397/4587（95.86%），SC 为
3145/3481（90.35%）。本轮没有重建或修改 RTL；TAGE-034 的 64 组合关闭
53 行，192 个 cross bin、117 项纯检查及八个普通 FAIL 负对照通过。其余九 DUT
和六项 XFAIL 不变，详见 `results/coverage-tage-retained-owner-refresh-audit.json`；
刷新后 1407-item collect-only 保持四份报告字节一致。原始行分母不扣除；TAGE
剩余 120 个局部分类行、70 行未分类，不能当作全 TAGE 验证完成。
上一阶段 MainBTB dirty/clean 清理与训练的
48 组合及 144 个断言后 cross bin 关闭最后 40 个 WriteBuffer 行，完整证据见
`results/coverage-mbtb-cleanup-overlap-refresh-audit.json`；1289-item collect-only 保持
四份报告字节一致。原 direct-feedback 刷新因资格审查主动停止，证据保留在
`/tmp/bpu-mbtb-replacement-formal-6g0FPy/interrupted-direct-feedback/`，不作为正式结果。
非弱条件邻项的 16 组有序诊断仍未计正式 PASS/XFAIL；resolve/redirect 源码
前提已检查，但完整 FTQ 动态资格仍待证明。MainBTB 原生映射行现已全部命中，
八个剩余分支按实际父模块常量连接分类，原生分母仍保留；证据见
`results/coverage-mbtb-branch-unreachable.json`。这不代表完整目标已完成。

独立清理诊断的 256 组合中 192 PASS、64 个零 key 错 owner 普通 FAIL；
四 bank 均复现，64 例真实同拍训练/flush。排空后邻 set 更新保留；通过的
诊断可额外命中 20 行，但不计正式覆盖，完整 FTQ 资格未证明，也不登记
新 XFAIL。见 `results/coverage-mbtb-flush-key-expanded-readonly.json`。入口
`python3 tests/mbtb/diagnostics/run_flush_key_probe.py` 隔离两类输出目录，
保留四份正式报告，并保存诊断源码快照；无需重新构建 DUT。
新的更早启动偏移在一个 bank 观察到联合零 key 的另一 set 更新被清理覆盖，
排空后仍丢失，不同于上述 delay 0/1 的 pending 首读；见
`results/coverage-mbtb-cleanup-routing-readonly.json`。其 raw 同样不计正式覆盖，
未登记新 PASS/XFAIL，也未证明完整 FTQ 资格。

上一阶段不同 key 双 pending entry 为 872 PASS、6 strict XFAIL、0 SKIP，
MainBTB 877/1056，关闭 20 行；完整证据保留在
`results/coverage-mbtb-entry-keys-refresh-audit.json`。

更早同 key pending 间接目标/carry 场景是 726 PASS、6 strict XFAIL、0 SKIP，
MainBTB 857/1056，关闭六行；完整证据保留在
`results/coverage-mbtb-entry-retarget-refresh-audit.json`。

以下 TAGE alternate 阶段结果是 528 PASS、6 strict XFAIL、0 SKIP，计划功能点 243/243 已执行；
统一 HTML 同时包含 136 个功能 covergroup 与十份当前原生 RTL 行报告，
SC 为 3145/3481（90.35%），TAGE 为 4335/4587（94.51%），
ITTAGE 为 1398/1398（100%）。新旧工具的映射范围不同，这不是按旧分母
关闭相应数量的缺口。正式清单、原始文件时效、LCOV／JSON／HTML 一致性与
已有局部不可达证明复核见 `results/coverage-tage-alternate-refresh-audit.json`。
同一 5.052 工具链中，MicroBTB 的完整 resolve 向量、同拍双源仲裁和连续
useful 恢复／重初始化转发场景关闭 34 行，当前为 794/794（100%）；
该轮其他九个 DUT 指标不变，五个 MicroBTB 分支点仍未命中。
后续 ITTAGE 独立 PLRU 参考与满表替换回读场景，在相同 RTL／工具链及
1398 行分母下再关闭两个 RegionWays 行；七个分支点仍未命中。
MicroRAS 中性修正及主 RAS 恢复场景再关闭两行，当前为 91/91（100%），
分支 21/24；该轮其他九个 DUT 指标不变。collect-only 不再写空正式报告。
SC 阈值上下界、资格及净增减场景再关闭三个顶层行，分支为 875/1038；
88 个新 cross bin 闭合，三项负对照检出，其他九 DUT 指标不变。
TAGE 八 resolve 槽位的 provider／资格矩阵再关闭 20 顶层行、增加 92 个分支，
376 个新 cross bin 闭合，四项负对照检出，其他九 DUT 指标不变。
TAGE alternate 精确配对状态、混合槽与重叠回读再关闭四个顶层 mux 行，
236 个 cross bin 闭合，四项负对照均普通失败，分支 1411→1421/1598。
这些轮次没有重建或修改 RTL：增量来自新 pytest 场景，SC/TAGE 原生分母
仍为 3481/4587，编译器、处理器及来源摘要不变。
该阶段 TAGE 有 252 个缺口，88 个仍对应原局部证明，另 24 个 key 复制赋值
已用精确守卫与四个内存负对照证明局部矛盾；SC 有 336 个缺口，
全部对应复核的局部矛盾赋值，未手动剔除分母，也不据此宣称所有功能闭环。
该阶段原始清单只含本次正式 322 份 dat；临时及 mutation 数据不计主表。
历史 alternate probe 仍不计正式 verdict；现在由 BPU-TAGE-029/030 的
独立模型、同事件只读 Bundle／Monitor 及原有异步 Scoreboard 正式检查。
缺少或歧义内部信号明确报错、不 skip，失败时恢复基本 binding 并回收
辅助驱动任务；该模型不覆盖完整分配／aging／FTQ 轨迹。
追加分类不改覆盖率，证据为 `results/coverage-tage-key-copy-unreachable.json`。
该阶段 WriteBuffer 140 个未分类行及其他预测器缺口仍待继续。实际 534 项
collect-only 保持四份正式报告字节一致，见
`results/coverage-tage-alternate-collection-protection.json`。
以下为旧 5.026 基线的场景增量记录。ITTAGE 增量来自地址 codec 修正、region
容量与两 bank pending 反馈场景；本轮没有修改或重新生成 RTL。
SC-018 的四索引 masked-way 更新关闭 74 行；SC-019 再检查每个 pending 行
内部的四 selector 合并、子集反向训练和所有邻项保持，关闭 82 行；1280
个 cross bin 闭合，漏 selector／错 selector／串行化负对照均检出。
SC-020 再将四行准备到真实 taken/used 全 1，更新排空并回读后用捕获
metadata 间隔式逐 way 反向重激活，再只恢复棋盘格两 way；所有未选
way／selector 保持，1024 个 cross bin 闭合。漏第四行、错捕获预测与
串行化准备三个负对照均普通 FAIL，恰好关闭原八个 clean-shadow 赋值行。
新被动 feedback monitor 属于验证 agent，不改变 RTL。原始分母保持不变，生成
WriteBuffer 中剩余 336 个源码行与已复核的局部不可达赋值精确对应，只另列
分析，不通过重建／改 RTL 刷覆盖率，也不宣称全 SC 功能验证闭环。
TAGE-024 的双 way／四索引 pending、useful 增加与未选 tag 保持关闭 112 行，
三种反馈适配层负对照均检出；剩余 317 行中的 40 个 hit／非 hit 矛盾赋值及
另外 48 个优先级排除矛盾赋值只另列分析，不剔除原始分母，另外 229 行仍需审查。
新优先级证明及重复运行入口见 `results/coverage-tage-priority-unreachable.json`
与 `python3 -m suites.frontend.bpu.tage.coverage.coverage_audit`。十个原生 LCOV 与 HTML／JSON
行计数一致，独立 probe 和负对照 `.dat` 不在正式清单中。
TAGE-025/026 的四索引／双向迁移对照再检查真实捕获 metadata 与无关 tag
useful 保持。捕获后无 reset，七拍反馈经被动 monitor 核对；新鲜组 120/120
cross bin 通过，捕获组八例共有 16 项 useful 误关联，保留 strict XFAIL 与
16 个未命中 bin，其他前提错误均普通 FAIL。仅证明单模块反馈契约，不宣称
集成 FTQ 调度可达；该轮没有重建 DUT 或改 RTL，原生 TAGE 行数没有增加。
`BPU-INT-017` 已用同一背压 S1 的双源目标切换验证，`BPU-INT-019`
已验证 ABTB 来源的低位差异 S3 修正，`BPU-INT-018` 的仅高位错误跨 4 MiB
集成修正则由真实 ABTB 命中复现为 strict XFAIL。MicroTAGE-015/016 又关闭 189
原生行，升至 5705/10712（53.26%），并由两表、四 bank、两模式的全部 16 组
公开读回暴露 shadow 更新未持久化的缺陷；独立 VPI staging 观测确认同槽 dirty
清理冲突，但不替换正式 DUT、不改 RTL。随后 MicroTAGE-017 的两轮精确
useful aging 与全部邻项保持检查关闭 4 行，升至 5709/10712（53.30%）；
60 个 cross bin 闭合，少 tick／少强化／错 useful 资格三个负对照均检出。
这轮也没有修改或重建 RTL。MicroTAGE-018 再按真实 PHR 窗口／XOR 折叠
扩展低四位激励限制，检查短历史共享与长历史独立、全邻项保持和 A0/A1
关联；144 个 cross bin 全命中，截历史／错 A1 两负对照均普通 FAIL。
新增 14 行升至 5723/10712（53.43%），原始分母不变，其他九个 DUT 汇总不变；
随后 MicroTAGE-019 用同高表 hash 不同 tag 的真实反馈完成替换和延迟捕获
counter 重建，720 个 cross bin 闭合，错 counter／错 tag／串行化三负对照
均普通 FAIL；新增 5 行升至 5728/10712（53.47%），无新缺口，其他 DUT
汇总不变。最新 HTML／JSON／LCOV 与 310 份正式 `.dat` 的时效／隔离审计
见 `results/coverage-tage-way-migration-refresh-audit.json`。这些轮次均
没有改动 RTL、picker/xcomm 分支或正式 DUT。六个 XFAIL 是已记录的 RTL
缺陷，不是重建失败。单独验证 xreactor：

```sh
cd /home/xyl/xreactor
PYTHONPATH=/home/xyl/xreactor/src:/usr/local/share/picker/python \
  python3 -m pytest -q -p no:cacheprovider --maxfail=1
```

当前结果为 881 PASS。

## MicroTAGE shadow 持久化诊断

以下碰撞计数是历史诊断结果，新迁移需要重新验证，不能自动继承结论。
当前诊断脚本只接受 memory-direct 包。为复核 `BPU-UTAGE-016`，
只在独立 staging 目录使用 `--rw mem_direct` 构建原 RTL，
不替换 `dut/utage`、不修改 RTL，也不将诊断 `.dat` 放入正式 pytest 清单。
以下将 `<stage>` 替换为新创建的临时目录绝对路径：

```sh
cd /home/xyl/bpu-verify-kunminghu-v3/rtl/utage
picker export MicroTage.sv --fs filelist.f --sname MicroTage \
  --tname UtageShadowDut --tdir <stage>/utage --rw mem_direct \
  -w memory-direct.fst --vflag='--no-coverage-expr --no-coverage-fsm' \
  -c --lang python --cp_lib 1 --autobuild true -j 4
cd /home/xyl/bpu-verify-kunminghu-v3
PYTHONPATH=/home/xyl/bpu-verify-kunminghu-v3:/usr/local/share/picker/python \
  python3 tests/utage/diagnostics/shadow_dirty_probe.py \
  --dut-package <stage>/utage --table 0 --mode adjacent --report <stage>/trace.json
```

重复两表 × `adjacent/serial` 共四次，均观察到 57 个 `cleanId == enqPtr` 的
写入碰撞，其中 15 次实际改变 counter，但新项 dirty 仍为 0；最后公开 SRAM
读回每组有七项计数器退回。证据摘要保存在
`results/coverage-utage-shadow-dirty.json`，完整公开 16-case 矩阵在
`results/utage/shadow-persistence-known-fail.json`。新诊断通过 native offset
直接绑定实际字段，名字中的 `TOP.` 仅为兼容现有观察 schema 的命名归一化。
这些内部观测只用于根因定位；正式回归仍通过 driver／monitor 的公开事务判定。
