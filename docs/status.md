# 结构整合阶段状态

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


仓库名称为 `ucv4xs`，定位是基于 UnityChip 的香山单元测试；命令与 Python 导入名保持 `ucv`。

**2026-10-31 工程根命名空间更新**：十工程实现已直接迁入 suites.<group>.<suite>，
移除重复 *verify/common 包装；runner、插件、ROOT、工具、安装元数据、文档和 skill
一起调整。45806 个有序收集 nodeid 与迁移前完全一致，根测试 96 PASS，结构与资产/skill
审计通过；FTQ/ICache/IFU 的本轮全量判定分别为 109 PASS+2 XFAIL、291 PASS+3 XFAIL、
144 PASS+2 FAIL+1 UNCERTAIN，其他工程按明确子集回归。此次不是全部事务迁移或全部
硬件验收完成；范围、证据及产物隔离复跑见
[工程根重构记录](lessons/suite-namespace-refactor-20261031.md)。下文历史运行仍归原日期与源码。

**2026-10-31 复核更正**：下文“全工程布局迁移完成”只证明 fixture 接线与部分句柄
收口。P.p_* / P.io(...) 是端口别名，不是事务抽象；IFU/LSQ/LSU/MMU/DCache/VAGQ
仍有引脚级耦合，不能宣称全部事务架构迁移完成。历史构建/回归原数和真实失败不改写。
目录取舍、skill 修正和 22 个散落仿真产物的清理见
[结构与 skill 复核](lessons/structure-skill-review-20261031.md)。

本阶段按当前优先级交付可维护的仓库结构，不以全部硬件用例通过为门槛。十个工程、132 个 DUT 已进入同一独立 Git 仓库；唯一公共命令为 `ucv`，公共 Python 包为 `src/ucv/`，验证框架统一使用 toffee。

## 已完成的结构范围

- `frontend`、`memblock`、`vector` 分组及十个独立验证包、pytest 根目录。
- 根 → 分组 → 工程的完整命名基线继承，未知/不完整引用报错，禁止 DUT 单独覆盖源码或配置。
- 公开九工程统一 commit `893e1580b705d81f113c30c7a05734e09a08050e`；VAGQ 通过本地来源接入 internal `d4566d58a5ace1f6a5df4409b37a84b971f48e43`。所有工程使用 DefaultConfig。
- `list`、`doctor`、`setup`、`prepare`、`build`、`run`、`report` 入口，锁定依赖、独立源码检出、Chisel 生成和闭包提取、构建及冒烟、worker 预算和来源记录。
- 基线、DUT、工具链及选项参与缓存身份；运行使用新结果目录；工程进程隔离、BPU 原生 DUT 进一步隔离。
- 生成文件、本地配置、工具安装、internal 实现和大结果不进入 Git；134685 份历史证据由按工程拆分的哈希索引记录。

## 结构检查与已取得的执行证据

此前结构验收时根 `tests/` 共 29 PASS，包含继承优先级、错误引用、混合基线、缓存隔离、真实 pytest 用例选择、RTL 闭包、失败分类及两个锁定工具补丁的检查；新增整芯片生成跨工程复用、override 隔离及拒绝旧 BPU 独立生成配置的检查。资产审计通过，未发现公开源文件依赖旧框架导入或工作区符号链接。2026-10-30 UNCERTAIN 本地适配后的根测试为开发环境 54 PASS，旧 `.venv` 50 PASS / 4 SKIP（4 项需要新 Toffee）；资产审计仍通过。

统一入口已验证公开环境检查、混合基线拒绝、Sbuffer 显式单用例执行和 BPU 显式单用例分区收集。标签 `v0.1.0-structure` 的 122 个 DUT 已使用锁定工具链构建并通过独立进程冒烟，其中 BPU 当时使用独立生成入口；该证据不代表当前整芯片 BPU 的重建验收。全新源码检出、独立 Python 3.12 虚拟环境且没有工具/构建缓存时，23 项结构测试通过，4 项依赖原生 SDK 的测试明确跳过；基线与资产检查通过，缺少工具或 internal 来源会明确报错。此检查不声称完成空缓存的全工程硬件重建。

本次 `ucv4xs` 更名后已在新路径重建虚拟环境、原生工具和全部 122 个 DUT，并全部通过独立进程冒烟；其中 BPU 十个 DUT 均来自与其他公开工程共享的完整香山 RTL。生成阶段复用经过哈希核验的整芯片 RTL 缓存，本次没有重新执行空缓存 Chisel 生成。Sbuffer 显式单用例为 1 PASS，BPU 指定用例恰好收集 1 项，两次运行均无产物完整性缺口。记录见 [本轮结构调整证据](history/structure-update-20261027.json)。

旧虚拟环境、工具构建目录和原生 DUT 凭据保存在本地 `.history/`，具体映射记录在本轮证据中。原 `v0.1.0-structure` 标签及其历史记录保持不变。

## 硬件与适配状态

锁定工具链下既有六个公开非 BPU 工程的完整回归已结束，逐用例判定与迁移前一致，报告无产物完整性缺口。下表另附 IFU 的最新本地开发环境结果；不表示其他工程也已切换该环境重跑：

| 工程 | PASS | FAIL | XFAIL | SKIP | UNCERTAIN |
|---|---:|---:|---:|---:|---:|
| ICache | 290 | 0 | 3 | 0 | 0 |
| LSQ | 2325 | 250 | 0 | 0 | 0 |
| DCache | 210 | 0 | 3 | 0 | 0 |
| MMU | 408 | 0 | 0 | 0 | 0 |
| Sbuffer | 31 | 0 | 0 | 0 | 0 |
| LSU | 522 | 7 | 0 | 0 | 0 |
| IFU（本地开发运行） | 144 | 2 | 0 | 0 | 1 |
| VAGQ（internal） | 433 | 1 | 0 | 33 | 0 |

2026-10-29 新增 frontend/FTQ 工程，按 `Ftq → {ResolveQueue, CommitQueue}` 真实实例化层次提取三个 DUT。2026-10-30 将验证包重组为每 DUT 一个 agent（agent / driver / monitor / checker / transaction 分层），测试只提交事务，引脚所有权在 fixture 边界检查；同一轮补齐顶层物理槽 × 分支槽 × 来源矩阵。实际运行 `results/ftq-final-20261030b` 为 109 PASS、2 XFAIL（strict）、0 FAIL、0 SKIP；原生覆盖为 `resolve_queue` 100.0% 行 / 99.9% 分支 / 89.2% toggle、`commit_queue` 100.0% / 99.8% / 100.0%、`ftq` 100.0% 行 / 99.6% 分支 / 84.4% toggle。`ftq` 闭包行覆盖达到 100%，上一轮记录的顶层 IFU 命中 fallback 枚举缺口（R-02）关闭；剩余分支只有三个初始化 reset else 和三个顶层结构不可达的同拍 IFU 合并臂。2 个 XFAIL 不是通过：ResolveQueue 在第 9 条分支解析（或同拍超量组）时越过 8 槽容量，回绕覆盖已有分支；合法依据是 DefaultConfig 的 BPU meta 有 10 个位置。缺陷复现、根因行和建议修复见 [ResolveQueue 分支槽溢出](../suites/frontend/ftq/docs/bugs/resolve-queue-branch-overflow.md)，案例见 [覆盖率下容量缺陷](lessons/ftq-resolve-capacity-20261029.md)。责任边界、等价类、追溯、残余和运行证据见 [FTQ 工程 README](../suites/frontend/ftq/README.md) 与 [验证包结构](../suites/frontend/ftq/docs/architecture.md)。此结论只适用于 `public-893e1580b` + DefaultConfig 和本次原生包，不改变其他工程历史判定。

2026-10-29 新增 frontend/IFU 工程，按 `Ifu → {RvcExpander, InstrBoundary, PredChecker, IfuUncacheUnit, FrontendTrigger, IfuPerfAnalysis}` 的真实实例化层次提取七个 DUT，并按自底向上顺序验证：六个内部子模块逐一闭环后，再用组合模型验证顶层。第三轮按“观察点精度”重扫生产者/消费者宽度，发现并保留一个真实 RTL 偏差：`FrontendTrigger` 的 `tdata2` 比较只用低 50 位，而 CSR 暴露 `RW(63,0)`，`tdata2 ≥ 2^50` 时 EQ/GE 会在真实 PC 上误命中、LT 全不命中。实际运行 `results/20261030T022604Z-107cb685` 为 144 PASS、**2 FAIL**、**1 INCOMPLETE**（硬件用例 114 + 环境门禁 30），硬件 53/55 PASS + 1 FAIL（`IFU-TR-002`）+ 1 INCOMPLETE（`IFU-TOP-011`，只覆盖一种 carry 位置）、验证环境 5/5。两条反例保留为 FAIL，未登记 XFAIL；未证明范围（R-01..R-12）以机器可读残余登记在 `verification_plan.json`，插件在“有 blocking 残余却全 PASS”或“有 FAIL 却无 blocking 残余”时报一致性错误；`ucv run`/`ucv report` 会把残余写入 `run.json`、`summary.json` 和 `summary.md` 的 Residual register（本轮 13 条、blocking+open 1 条），并规定“全 PASS 但仍有阻塞残余”时判定降为 INCOMPLETE；残余 R-13 记录复现、根因与修复方向（全宽比较，或把 CSR 高位 WARL 化并改合同），见 [FrontendTrigger tdata2 宽度](../suites/frontend/ifu/docs/bugs/frontend-trigger-tdata2-width.md)。此前一轮 `results/20261029T133533Z-d193f454` 的 142 PASS 只覆盖 `tdata2` 高位为 0 的配置。第二轮按执行/复核方法补充了独立 oracle 区分力、负对照、pruned 端口审计、双向追溯、激励合法性与 guard 交接探测；等价类矩阵、观察点/比较器对账、退出标准与残余 R-01..R-13 分别在 [行为矩阵](../suites/frontend/ifu/docs/behavior-matrix.md)、[观察点对账](../suites/frontend/ifu/docs/observation-coverage.md)、[退出与残余](../suites/frontend/ifu/docs/exit-criteria.md) 中。基线之后的上游变更复核发现 `b716aade`（基线后第 57 个提交）修复了重定向 PC 的 guard 位截断，本地基线是其 pre-image；该交接面限制以 `IFU-ENV-005` 探测并登记为出域残余，不计入硬件 PASS，详见 [上游复核](../suites/frontend/ifu/docs/upstream-review-20261029.md)。原生覆盖（行/分支/toggle）：`rvc_expander` 100.0/100.0/95.9%、`instr_boundary` 100.0/99.4/91.8%、`pred_checker` 100.0/95.8/99.8%、`uncache_unit` 100.0/93.8/100.0%、`frontend_trigger` 100.0/99.4/95.2%、`perf_analysis` 100.0/95.5/17.4%、`ifu` 顶层 100.0/99.8/87.6%。七个 DUT 的生成 RTL 行覆盖均为 100%，剩余分支臂全部定位为结构不可达（`ENABLE_INITIAL_REG_` 一次性初始化块的复位 else 臂、槽 0 必属第一块、第 36 lane 被置 0）；`perf_analysis` 的 toggle 上限由端口裁剪决定（76 个理由位只暴露 10 个，可达位已 100% 覆盖）。功能点语义、逐轮缺口分类、观察点精度扫描与残余处置见 [IFU 功能点](../suites/frontend/ifu/docs/functional-points.md)、[覆盖率闭环](../suites/frontend/ifu/docs/coverage-loop.md) 和 [退出与残余](../suites/frontend/ifu/docs/exit-criteria.md)。此结论只适用于 `public-893e1580b` + DefaultConfig 与本次原生包。

BPU 已切换为从与其他公开工程共享的完整 DefaultConfig 香山 RTL 提取十个 DUT，删除 `recipes/` 独立生成入口及相关分支。模型、激励和源代码审计继续适配整芯片实际端口。此前独立生成 DUT 的构建和回归记录仅作历史对照。2026-10-29 迁移适配修复后的全量纯模型诊断（显式排除 2600 个原生 DUT 用例，24 worker，结果目录 `results/pytest-pure-final-20261029`）为 38353 PASS、74 FAIL、0 ERROR、7 SKIP；此前 1222 FAIL、9 ERROR 已收敛到该结果。修复覆盖整芯片 8 槽反馈载荷、5/9 TAGE 选择器与 16 个寄存器、矩阵分母、五 way MBTB 深度、整芯片生成文件名及 PHR/RAS 静态审计锚点。剩余 74 FAIL 集中在 `test_short_revisit`、`test_entry_protection` 和 `test_early_positive_protection`：这些程序仍按 MinimalConfig 的“短表 table0、长表 table1”身份写预期，DefaultConfig 的实际 5/9 历史会把同名原件选到 table1，随后长项训练覆盖该短身份。该组需按新表映射重新设计场景，不能用放宽断言或登记 XFAIL 代替。尚未执行完成当前最终源码的 BPU 全量原生回归。

BPU 同一历史 RTL 上的框架比较保存在 `history/bpu-framework-verdict-comparison.json`：大部分原生 DUT 判定一致，MicroTAGE 有一个 strict XFAIL 变为 FAIL，覆盖率打包完整性亦未认证。历史产物是 MinimalConfig，不能证明新 DefaultConfig 的硬件正确性。

### BPU 模块级自底向上闭环进展（2026-10-29）

开始按实际模块层次推进模块级 UT 闭环，先完成两个叶子模块：

- **MicroBTB（UBTB）**：`results/ut-ubtb-gap2-20261029` 为 49 原生 PASS、168 纯模型 PASS；`MicroBtb.sv` 行 805/806（99.88%）、分支臂 102/104、toggle 完整位 2019/2020。未覆盖的 1 行和 4 个分支臂均已给出局部守卫证明（hit 蕴含 useful≠0；初始时间复位 else；内层互斥 else），toggle 剩余位为公共 API 恒零的半字地址最高位。整芯片裁剪的 `prediction.valid`、常量 `sramResetDone/trainReady`、FastTrain 无 mispredict 叶均由适配层按语义重建。报告：`suites/frontend/bpu/docs/ubtb-module-review-20261029.md`。
- **MicroRAS（URAS）**：`results/ut-uras-gap3-20261029` 为 29 原生 PASS、4 已归档真实 RTL FAIL（BPU-BUG-05 禁用门控 1 项、BPU-BUG-10 返回并调用 3 项）、137 纯模型 PASS。`MicroRas.sv` 行 73/73（100%）、分支臂 30/31、toggle 完整位 439/440（99.8%）；剩余 arm 为初始时间复位 else，剩余位为 GuardedPc 地址 bit0。迁移适配修复了无 enable 引脚、属性叶展平、常量状态端口和跨 reset 的边界对齐；新增全 50 位地址/位置 16/31/S2→S3 存储路径用例。报告：`suites/frontend/bpu/docs/uras-module-review-20261029.md`。

两个模块的 FAIL 均原样保留，未添加 XFAIL 或删除用例。其余叶子/中层模块（ABTB、TAGE、ITTAGE、SC、UTAGE、MBTB、RAS、Bpu）继续进行同样的闭环。

### BPU 模块级闭环补充：AheadBTB 与 MicroTAGE（2026-10-30）

- **AheadBTB**：`results/ut-abtb-gap3-20261030` 为 **93 原生 PASS / 1 FAIL**、1896 纯模型 PASS / 7 SKIP。唯一 FAIL 是已归档 `BPU-BUG-09`（同 set 两条间接分支的目标修正选错 way），迁移前即存在。设计行覆盖 **11621/11621（100%）**，写缓冲/替换器子模块行覆盖均 100%；toggle 完整双向位 **7601/9261（82.1%）**。已适配整芯片稀疏 PHR（仅索引 2）、根级 `result_entries`、被删的 `s3_fire`/`trainReady`/`fastTrain.mispredict` 与 `toMicroTage` 被裁 sideband 叶；新增写缓冲四槽全宽身份与极端 set 清理用例。报告：`suites/frontend/bpu/docs/abtb-module-review-20261030.md`。
- **MicroTAGE**：整芯片端口适配已完成（稀疏 PHR 索引 2/7 与 1/2/5/6、4 行训练元数据、被删 `meta.valid`、仅 taken/kind 的 ABTB sideband），初始 **269 个 setup ERROR 全部消除**。`results/ut-utage-probe9-20261030` 为 **229 原生 PASS / 39 FAIL / 1 XFAIL**（迁移前 232/35/3），其中 35 个 FAIL 与迁移前逐条一致，仅新增 4 个（useful 地址矩阵 2 项、历史碰撞 1 项、功能覆盖门禁）。纯模型负对照仍有按旧 33 折稠密 metadata 构造的夹具待迁移。功能点闭环尚未完成，未写成通过。报告：`suites/frontend/bpu/docs/utage-module-review-20261030.md`。

### IFU / Toffee UNCERTAIN 本地迁移（2026-10-30）

按用户确认，直接修改本地 Toffee Git 检出，未提交、打 tag、推送或制作 Toffee patch。
从源码构建并安装 `uc-toffee 2.0.1.dev1+uncertain.a886d1c12444` 到独立
`.venv-uc-toffee`（已有 `uc-xcomm 1.1.1`，pip check 通过），原 `.venv` 与原生 DUT
不替换。实际源码/安装哈希由本机配置与开发凭据校验，公共原生构建锁保持原义。

`@pytest.mark.uncertain(reason=..., reference=...)` 的声明、`U`/详细状态、session 摘要、
失败优先和 manifest 计数均由 Toffee 负责；ucv 与 IFU 功能点报告复用其分类。
UNCERTAIN 不计入 PASS，但本身不导致非零退出；执行/产物未完成仍为 INCOMPLETE。
完整复验 `results/20261030T-uncertain-uc-toffee` 为 **144 PASS / 2 FAIL / 1 UNCERTAIN**，
硬件 53 PASS / 1 FAIL / 1 UNCERTAIN，环境 5/5，整体 FAIL / exit 1。
与第三轮用例集合及原生构建相同，仅 carry 用例从旧声明式 INCOMPLETE 迁移为 UNCERTAIN；
line/branch/toggle 命中数和分母均不变，R-09/R-13 不关闭。另有真实 carry 用例 2-worker
运行为 1 UNCERTAIN / exit 0，覆盖正常提交。Toffee 全量 1165 PASS + 3 subtest PASS，
ucv 开发环境根测试 54 PASS。版本、完整哈希和边界见
[UNCERTAIN 迁移核验](../suites/frontend/ifu/docs/uncertain-migration-20261030.md)。
上方第三轮的 1 INCOMPLETE 为历史状态，原收据未改写。


### 全工程布局迁移完成（2026-10-31）

> 保留原轮次结果；“pin fields=0”是旧扫描遗漏别名和 keyword 的结果，不是实际零
> 耦合。现审计已修正，六工程标为 needs-adapter；fixture 条目数也不能称作 DUT owner 数。

本轮把剩余七个工程的 pytest 接线、pin 访问与自检分类全部收敛到同一契约，并完成新工具链
下 132 个 DUT 的重建。

**布局契约**：`scripts/audit-suite-layout.py` 检查四项——根 owner fixture 可达、
无嵌套 conftest / `env/pytest.py`、功能 testcase 无原生 DUT 访问、`selftest` 已注册。
审计同时区分“原生访问”（`.dut`/`.pins` 属性链）与“pin 字段字面量”（`"io_*"`）；
迁移后十工程两者均为 0。

| 工程 | 根 owner fixture | 功能用例 | 迁移内容 |
|---|---:|---:|---|
| BPU | 13 | 397 | 复用上一轮；selftest 插件改共享 `ucv.pytest_selftest` |
| FTQ | 4 | 20 | 同上 |
| ICache | 13 | 44 | 同上 |
| IFU | 7 | 8 | 新增 `ifuverify/common/pins.py`；根 conftest 暴露 7 个 harness fixture |
| DCache | 2 | 15 | 工程根 conftest 删除，fixture 集中在 `tests/conftest.py`；step/refresh/reset 收回 runtime；Queue env 移出 testcase |
| LSQ | 31 | 165 | 11 个嵌套 conftest 合并到根；`common/pins.py`；按目录分派的同名 fixture |
| LSU | 2 | 23 | 工程根 conftest 删除，fixture 到 `tests/conftest.py`；`perf_value()` 替代直接读端口 |
| MMU | 52 | 22 | 工程根 conftest 删除；387 处 `execution(env.dut)` 改为 `execution(env)`；bit sweep 移入 runtime |
| Sbuffer | 7 | 2 | 工程根 conftest 删除；31 处 `execution(env.dut)` 改为 `execution(env)` |
| VAGQ | 14 | 54 | 根 fixture 到 `tests/conftest.py`；`NativeSplit` 移入 `vagqverify/split/native.py` |

`tests/test_suite_layout.py` 把审计固化为根测试；`ucv.pytest_selftest` 统一注册
`selftest` marker，替换 BPU/ICache 各自的插件副本。

**pin schema**：六个工程的 `common/pins.py` 成为唯一写 `io_*` 的地方
（IFU 51 个、LSQ 199 个、LSU 75 个、MMU 21 个、VAGQ 49 个、DCache 1 个常量）。
功能测试改用 `P.p_*` 与 `P.io(...)`，f-string 按 Python 3.12 token 边界替换。

**构建**：`ucv build public --require-unified-baseline --jobs 64` 完成 118 个公开 DUT；
BPU `tage` 与 `bpu` 顶层随后同样 `BUILT + SMOKE PASS`。`ucv build vagq` 完成 12 个
internal DUT。`ucv build sbuffer` 另行完成 2 个。**132/132 DUT 均有本次冒烟收据**（按当前 `cache_key` 逐个核对 DUT 链接与 `build.json.smoke`）。

**实际回归**（真实判定，未改写）：

| 工程 | 结果 | 说明 |
|---|---|---|
| 根 `tests/` | 67 PASS | 含新增布局门禁 9 项 |
| IFU | 144 PASS / 2 FAIL / 1 UNCERTAIN | 2 FAIL 为已归档 `FrontendTrigger tdata2` 宽度缺陷 |
| LSU | 522 PASS / 7 FAIL | 与迁移前同一失败集合 |
| DCache | 210 PASS / 3 XFAIL | 3 个 strict XFAIL 保留；布局迁移后重跑 |
| MMU | 408 PASS | 全通过；迁移后复跑 `tests/l2 tests/tlbn` 331 PASS、`tests/tlb tests/tlbfa tests/wrapper` 64 PASS |
| Sbuffer | 31 PASS | 全通过 |
| ICache | 291 PASS / 3 XFAIL | 与迁移前一致 |
| FTQ | 109 PASS / 2 XFAIL | ResolveQueue 容量缺陷未修 |
| LSQ | 2325 PASS / 250 FAIL | `results/ucv-lsq-final-20261031`：manifest `committed`、`coverage_complete=true`、`ucv report` 无产物缺口；计数与迁移前逐项一致 |
| VAGQ | 433 PASS / 1 FAIL / 33 SKIP | 统一入口 `results/ucv-vagq-20261031`；1 FAIL 与迁移前同一用例 |

**覆盖率与产物完整性**：三个通过统一入口执行并生成 manifest 的工程均为
`state=committed`、`coverage_complete=true`、`ucv report` 无缺口——Sbuffer 5 个原生
覆盖率产物、LSQ 77 个、VAGQ 25 个，三者都生成 `coverage.html`。其余工程的判定来自
直接 pytest 运行，没有本次统一合并的原生覆盖报告，因此不引用旧覆盖率数字。

VAGQ 的 1 FAIL 是 `tests/maskgen/testcase/test_element_windows.py::test_segment_element_windows_and_policies`
（56/9024 个 native policy mismatch，`elemActiveMask` 与独立窗口模型不一致）。该失败在
迁移前已存在，本轮保留为 FAIL，未登记 XFAIL。

## 文档与本地空间整理

已补齐 README、仓库协作约定 `AGENTS.md`、项目工作流 skill、历史验证经验和编译构建经验入口。2026-10-28 按用户要求回收一轮异常 BPU 调试留下的 224 个覆盖率文件，约 25.8 GiB；日志和原状态保留，删除文件清单见 [回收记录](history/storage-reclamation-20261028.json)。该清理不产生新的硬件验收结论；覆盖率按字节控制与异常自动回收仍待实现。

## 后续工作

FTQ 的 ResolveQueue 分支槽溢出缺陷需单独修复并复验（当前 2 个 strict XFAIL）；顶层闭包行覆盖已在 2026-10-30 达到 100%，R-02 关闭，但剩余分支/toggle 缺口与 R-01 仍需分开陈述。当前保留这些缺口，不以 XFAIL 或放宽检查替代修复。BPU 剩余短/长表场景重设计、其完整生产回归、全新环境空构建缓存下的全工程链路，以及最终硬件失败和覆盖缺口分析继续单独推进。现有失败、XFAIL 和 SKIP 均保留，未以删除用例或扩大豁免替代验证。

`v0.1.0-structure` 标记结构阶段交付。完整“迁移与重建验收”仍为 NOT_CERTIFIED；硬件判定以各次实际运行报告为准。证据路径与哈希见 `history/structure-evidence.json`，不将结构通过改写为硬件通过。

### BPU 模块级闭环补充：TAGE / ITTAGE / SC / RAS / UTAGE（2026-10-30）

本轮在整芯片 DefaultConfig 生成 RTL 上完成五个模块的端口迁移与验证；所有运行目录、覆盖率 JSON 和模块报告均保存在 `suites/frontend/bpu/docs/` 与对应 `results/` 目录。

| 模块 | 原生判定 | 纯模型 | 行覆盖 | 分支臂 | toggle | 证据 |
|---|---|---:|---:|---:|---:|---|
| TAGE | 247 PASS / 1 XFAIL（既有） | 867 PASS | 4978/5308 = 93.78% | 2841/3154 = 90.08% | 27837/66424 = 41.91% | `results/ut-tage-probe4-20261030`、`docs/tage-module-review-20261030.md` |
| ITTAGE | 42 PASS / 3 FAIL（迁移前同判定） | 122 PASS | 2126/2190 = 97.08% | 1218/1670 = 72.93% | 18955/212758 = 8.91% | `results/ut-ittage-final-20261030`、`docs/ittage-module-review-20261030.md` |
| SC | 61 PASS / 0 FAIL | 403 PASS | 4556/5245 = 86.86% | 1878/2256 = 83.24% | 29135/41226 = 70.67% | `results/ut-sc-final-20261030`、`docs/sc-module-review-20261030.md` |
| RAS | 23 PASS / 5 FAIL / 1 XFAIL（与迁移前逐条一致） | 565 PASS | 804/838 = 95.94% | 282/316 = 89.24% | 3911/7218 = 54.18% | `results/ut-ras-final-20261030`、`docs/ras-module-review-20261030.md` |
| UTAGE | 234 PASS / 35 FAIL / 1 XFAIL（35 FAIL 与迁移前逐条一致） | 4050 PASS | 11279/11286 = 99.94% | 3725/3734 = 99.76% | 8758/11384 = 76.93% | `results/ut-utage-final-20261030`、`docs/utage-module-review-20261030.md` |

- UTAGE 新增功能点 `BPU-UTAGE-028`（整表 useful aging）与用例：先用真实分配把表 0 全部 512 个 useful 单元置 1，再用 126 次失败分配跨越低 tick bit7，证明一次 aging 对 4 bank × 128 set 的全部非零单元各减一。`BypassShadowBuffer` 的 512 个 aging 行由未覆盖变为全命中，模块行覆盖从 95.53% 提高到 99.94%。剩余 7 行是各模块初始化复位 else 臂。
- UTAGE 的 35 个 FAIL 与迁移前 FAIL 集合**逐条一致**（new=0、fixed=0），两个 strict XFAIL（useful address matrix、tag width）因真实修复转为 PASS；保留的 XFAIL 是 shadow 满替换。
- TAGE 未覆盖集中在“多槽 alternate 选择”和“同拍双路写合并/满队列强制写回”，归类为已有功能点的**情况枚举缺失**；BIST/DFT toggle 不计入功能判定。
- ITTAGE 的 383 个未覆盖分支臂全部在 `MbistPipeIttage`（扫描/DFT 域）；3 个原生 FAIL 与迁移前一致，属未发布快照/region 目录语义的待归因项。
- SC 原生全部通过；剩余缺口是全局计数器双向饱和与写缓冲合并/满队列的情况枚举。
- RAS 恢复了独立的 `io.enable` 驱动并修复 `meta_ras` 回灌投影和复位边界；`RasStack` 提交队列的 33 行未覆盖，对应尚未补的重复提交/回绕语义，且与 4 个 return-and-call 真实 FAIL 同域。

### MBTB 与 Bpu 顶层：尚未闭环

- **MainBTB（MBTB）**：整芯片适配已完成（0 setup ERROR），当前 `results/ut-mbtb-probe7-20261030` 为 **99 PASS / 26 FAIL**（迁移前 116/10）。26 FAIL 集中在 shadow owner/depth、cleanup overlap、full-capacity 与 shared-service 场景：这些场景仍按旧 2-way/旧坐标假设读取写缓冲 shadow，需要按 DefaultConfig 的 4-way LRU 与 `AddrField` 几何重写独立模型。行覆盖 3664/12114（30.25%）不代表通过，而是多处场景在准备阶段失败导致深层写缓冲/VictimBTB 未执行。报告：`docs/mbtb-module-review-20261030.md`。
- **Bpu 顶层**：整芯片生成的 `Bpu` DUT **不含** `toFtq.prediction.bits.target_addr`（生成 RTL 只导出 startPc/taken/endPosition/s2Override/s3Override），而现有 adapter 按旧接口绑定 target，导致 setup ERROR。该端口差异需要单独决定：把预测目标作为不可观测域并在 DUT 内部观察点取证，或重建包含 target 输出的生成入口；在决定前不把 Bpu 顶层写成通过。`ahead/abtb/ubtb` 等组合用例尚未重新运行。

### 依赖升级与验证包布局重构（2026-10-30）

- **环境升级**：`.venv` 已从 `pytoffee 2.0.1.dev1` / `xspcomm 0.3.0.dev3` 升级到
  `uc-toffee 2.1.0` / `uc-xcomm 1.1.1`，ABI 3、coverage protocol 5 不变；
  `pytest 9.2.0`、`pytest-asyncio 1.4.1`、`pip 26.2.2` 等基础依赖同步到当前最高兼容版本。
  锁文件、`.tools/sources` 和 `.tools/receipt.json` 一致；xcomm 宽 trace 补丁在新 tag
  上仍可应用并保留哈希。
- **能力核对**：正式版 `uc-toffee 2.1.0` 已提供 `toffee.outcomes`、
  `toffee._pytest_outcomes` 和 UNCERTAIN，不再依赖本地开发版；根测试由旧环境
  `50 PASS / 4 SKIP` 变为 **58 PASS / 0 SKIP**。`ucv.runtime` 按锁定的 `distribution`
  读取版本，并保留旧分发名回退；`ucv setup` 使用新分发名和 CMake 版本。
- **布局重构**：BPU 10 个 DUT、ICache 11 个 DUT 的 agent fixture 已集中到各自 pytest
  根，删除 `bpuverify/*/env/pytest.py`、`icacheverify/*/env/pytest.py` 和所有子目录
  转发 conftest；`tests/framework` 自动标 `selftest`。新增 `wait_cycles` /
  `write_with_flush` agent API，功能 testcase 不再直接访问 `.dut`/`.pins`。
- **审计**：`scripts/audit-suite-layout.py` 报告 BPU/FTQ/ICache 为 `ok`；IFU、DCache、
  LSQ、LSU、MMU、Sbuffer、VAGQ 仍为 backlog（旧扁平 harness、物理端口名或嵌套
  conftest）。backlog 不是通过项，迁移方案与验收见
  [布局审计案例](lessons/suite-layout-audit-20261030.md)。
- **实际验证**：根 `pytest -q tests` **58 PASS**；BPU `tests/ubtb/testcase`
  **45 PASS**、`tests/ubtb/scoreboard` **132 PASS**、`tests/ras/testcase/test_push_pop.py`
  **5 PASS**、`tests/sc/testcase/test_directions.py` **2 PASS**；ICache
  `tests/waylookup/testcase/test_flush.py` **7 PASS / 1 XFAIL**（既有 strict XFAIL
  保留），全工程收集 293 项。BPU 8 个 DUT（abtb/ittage/mbtb/ras/sc/ubtb/uras/utage）、
  `icache/waylookup` 和 Sbuffer 两个 DUT 均为新工具链 `BUILT + SMOKE PASS`。
  统一入口 `ucv run sbuffer --workers 1` 为 **31 PASS**，manifest `committed`、
  `coverage_complete=true`，`ucv report` 判定 PASS 且无产物缺口。
- **边界**：工具锁变化已改变构建缓存身份。BPU 的 `tage` 与 `bpu` 顶层在 20/30 分钟
  构建窗口内未完成，保持旧缓存、未写成 PASS；其余 121 个 DUT 的构建/冒烟、全工程
  原生回归和覆盖率合并**未执行**。旧 DUT 收据不再作为新工具链证据，本轮不产生新的
  全量硬件通过结论。
