# 验证工作组织与当前状态

更新于 **2026-11-17**。当前登记 **29 suite / 336 DUT / 336 独立 testbench 实现包**。
公开工程继承 `public-e716c7658 / DefaultConfig`；VAGQ 使用外部
`internal-d4566d58a / DefaultConfig`。有效基线、数量与选择范围以 `ucv list/info` 为准。

## 当前结构与入口

**模块树是管理主轴，DUT＋合同绑定与验收，suite 用于代码维护与执行。** 各工程
`docs/spec/verification/README.md` 提供生成的 DUT 工作索引，链接合同与实现入口；
负责人、当前工作、下一步、阻塞及证据沿用合同正文或关联任务。未知负责人保持待认领。
资产数量、骨架数量和已收集标签通过率不代表合同完成比例；无需另维护功能链路进度。

已采用前述模块树的 **354 条身份记录**（339 条公开模块/定位、13 条 internal 文档定位、
2 条历史切点），保存在根配置引用的[模块目录](modules.json)。全部 336 个 DUT 通过
workspace.module_id 唯一关联；目录与测试选择仍按工程配方。`ucv modules list/check/diff/apply`
提供持久身份、版本观察、变更对账和历史承接，命令与输入见[维护契约](reference/modules.md)。
所有 DUT 已有独占 testbench 和测试根，schema2 拒绝多个 DUT 指向同一实现包。
`ucv init --module-id` 独立生成环境、测试和 smoke，同族身份仍可用于管理归组。

| 分组 | suite | 职责 |
|---|---|---|
| frontend | `bpu`、`ftq`、`ifu`、`ibuffer`、`instr_uncache`、`icache`、`frontend_top` | 独立验证包与真实 Frontend 集成对象 |
| backend | `ctrl`、`int_region`、`fp_region`、`vec_region` | 后端控制及三类 Region |
| memblock | `lsu`、`lsq`、`sbuffer`、`dcache`、`mmu`、`prefetch`、`frontend_bridge` | 访存、翻译、预取及 MemBlock 内前端总线桥 |
| cache | `l2`、`llc` | CoupledL2 与 OpenLLC |
| bus | `ncb`、`peripheral` | CHI/AXI 桥与 MemMisc 外设互联 |
| soc | `aia`、`plic`、`debug`、`timer`、`clock_reset`、`mbist` | 独立系统服务合同 |
| vector | `vagq` | internal VAGQ，独立基线与外部证据 |

具体链接见 [仓库工程入口](../README.md#工程与基线)。各工程 `docs/spec/design/README.md`
记录当前 Chisel 定义/生成位置、RTL top、父实例及接入状态；`workspace.json` 保存资源关联
和带观察基线的 `binding`。这些观察不是单 DUT 基线覆盖，也不代替构建凭据。

- FTQ、IFU、IBuffer、InstrUncache 恢复独立维护和 pytest 根，各自 shared/env 回归所属包。
  原 DUT、场景、功能 ID、问题 ID 和严格生命周期保留；通用报告复用 `ucv.pytest_features`。
- `frontend_top/frontend` 与 `frontend_bridge/frontend_bridge` 各有独立合同草案与工作入口；
  前者承担真实 Frontend 组合性质，后者承担 MemBlock 内三路缓冲及组合性质，均待实现。
- 原 `backend_exec/backend_issue` 回归各自 Region；CtrlBlock 的 DecodeStage 按实际实例
  归控制块。公共 NewPipelineConnectPipe 独立绑定，不与 internal VAGQ 混同。
- SMS、Stream/Stride、Berti 归 `prefetch`；`L2Cache/L2Slice` 是 MBIST 流水生成名，归 `mbist`。
- Region 保留维护边界，调度/读寄存器/写回等各 DUT 分别认领；当前均为骨架，不宣称已
  实现联合环境。父子集成责任、参数差异和共享范围写在规格正文，父级包含不等于覆盖。

第一版原有 **266 DUT** 与新增 **70 个**父级/参数变体切点全部保留；本轮 336 个 top/export
配方及 binding 观察逐项无差异。未实现项仍保留显式失败 smoke；目录迁移未增加功能 PASS。
旧新对应、归档路径、源码快照和生成收据哈希见
[第一版切分记录](history/ut-split-20261116.json)和
[本次工作组织调整](history/ut-management-20261116.json)。2026-11-13 的
[表格导入记录](history/kmh-ut-import-20261113.json)作为历史来源保留；其中仅凭名称或多数票
得到的归属、`covered_by` 等字段不能作为当前覆盖证据。

## 集合与基线边界

| 集合 | suite 数 | 用途 |
|---|---:|---|
| `public` | 13 | 保持原选择的 140 DUT；含骨架，运行需显式选择 DUT |
| `full` | 14 | `public` 加 VAGQ，152 DUT，混合基线 |
| `public_all` | 28 | 全部 324 个公开 DUT，统一基线资源/结构检查 |
| `all` | 29 | 所有登记工程，336 DUT，含 internal VAGQ |

公开检查使用 `--require-unified-baseline`；`full/all` 因 VAGQ 基线不同会被统一基线检查拒绝。
历史 `public-a0c2a26cb` 等基线结果不转记为新基线已复验。

**两项明确的历史接口缺口：**

- `ftq/commit_queue`：当前源码和完整 RTL 无 CommitQueue；提交逻辑已在 Ftq 内。保留旧实现
  与历史配方，待重新审查父级提交合同，未自动改绑。
- `mmu/tlbn`：当前源码和完整 RTL 无 TLBNonBlock；load/store/prefetch 的三个 TLB 变体分别
  建骨架。旧多端口合同不能直接当作变体已适配。

其余 322 个公开 DUT top 在该次完整生成中存在；存在和来源可定位不证明端口兼容或硬件正确。

## 最近核验

### 公开基线 RTL release（`xiangshan-e716c7658`）

2026-11-19 为默认基线 `public-e716c7658` 发布整芯片 RTL 包，按既有规则执行：
来源是 `.cache/generated/1016962d…/rtl`（2026-11-13 生成），不从 DUT 闭包拼装；
包内 2002 个 `*.sv`、22 个 `*.v`、firtool 自带 `filelist.f`（2024 项，其中 23 项带
`./` 前缀，原样保留）、`BUILD-PARAMETERS.json`、上游许可、逐文件 `SHA256SUMS`
和 README。

验证链（发布前后各一段）：

- 解压副本 `sha256sum -c`：**2028 个文件全部通过**
- `verilator 5.052 --lint-only -Wno-fatal -f filelist.f --top-module XSTop -I.`：
  **exit 0**，2025 个模块，266.6 s
- `compare_rtl`：包内 RTL 与本机整芯片生成**逐字节一致**
- 重新下载校验：压缩包 SHA-256 一致（`2064fed7…`），解压后 2028 项逐文件校验和与
  首次上传时完全相同
- **压缩包可复现**：`publish-rtl-release.py` 固定 tar 成员元数据与 gzip 头部，
  同一输入重建得到同一 SHA-256；首次上传因带文件 mtime 与 gzip 时间戳不可复现，
  已替换为可复现版本，内容未变（逐文件校验和一致，先前的 lint 结论仍适用）
- `ucv prepare sbuffer --dut sbuffer --rtl-source release` → **PREPARED**

效果：默认基线不再需要 Java 17 或本机 Chisel 生成，也是 Linux aarch64 上唯一可用的
准备路线。登记在 `baselines/rtl-releases.json`，用 `scripts/publish-rtl-release.py`
可重复暂存与打包。记录见
[发布记录](history/rtl-release-e716c7658-20261119.json)。

边界：这不改变任何模块级结论；既有 PASS/FAIL 仍属于各自基线、日期和主机架构。
本次仍未在 aarch64 上执行任何步骤。

### 主机架构支持（Linux aarch64）

2026-11-19 让工具链接受 `Linux aarch64`，与 `Linux x86_64` 并列。改动集中在架构身份
和获取路径，不涉及验证语义：

- 新增 `src/ucv/host.py` 作为唯一的架构判断入口：机器名规范化（`arm64`/`amd64` 等别名）、
  支持集合、ELF `e_machine` 读取、架构相关的下载地址。`setup`、`doctor`、`validation`
  和 `sources` 都从这里取，不再各自比较字符串。
- **构建缓存身份加入 `machine`**。生成的 DUT 包内含原生库，架构不同必须视为不同产物；
  这条同时修掉了"同一 key 在 x86 与 ARM 之间复用"的隐患。代价是升级后所有旧缓存
  一次性失效。
- `.tools/receipt.json` 记录 `machine`/`system`，`installed_tools` 拒绝架构不符的安装；
  缺该字段的旧收据明确要求重跑 `ucv setup`，不静默放行。
- `verilator_seed` 与 `firtool` seed 在使用前读取 ELF 架构，换机器复用 seed 会在
  复制阶段报出原因，而不是留下跑不起来的二进制。
- 修掉 `install_generation_tools` 的 mill 获取：原来下载 `mill-dist-0.12.17.jar` 并当作
  可执行文件，任何架构都不可用。现在下载 Maven 上的架构中立启动脚本
  （`mill-dist-0.12.17-mill.sh`），由它自己解析平台，含 aarch64。
- **`firtool` 是硬边界**：CIRCT 的 `firtool-1.149.0` 只有 `linux-x64` 与 `macos-arm64`，
  没有 `linux-arm64`（1.140/1.149/1.150 一致）。因此 aarch64 上不能从 Chisel 生成 RTL，
  只能用已发布 RTL 包或自备 firtool。三条失败路径都会点明这个原因。

新增测试：`tests/test_host.py`（29 项：别名规范化、支持集合、ELF 架构读取、外来 seed
拒绝、firtool 仅 x86_64、mill 启动器选择）、`tests/test_installed_tools.py`（5 项：
收据架构校验）以及 `tests/test_baselines.py` 中的架构入 key 一项。

已验证：公共工具回归 **474 PASS**（原 426，新增 48）；`ucv check`、`ucv modules check`
通过；`ucv setup` 在新收据格式下成功并记录 `machine=x86_64`；`ucv doctor --stage run`
通过；`sbuffer`（2 个 DUT）与 `lsq/deq_module` 在加入架构身份后的新 key 下
**BUILT + SMOKE PASS**；LSQ `deq_module` 实跑 **13 passed / 3 failed**，与升级前一致，
失败的仍是开放缺陷 `DEQ-WB-001`。

**未验证**：没有在真实 aarch64 主机上执行任何一步。上面的结果是 x86_64 上的回归，
证明改动没有破坏现有平台；aarch64 上的编译、Verilator 源码构建、Picker 补丁等价性
和 336 个 DUT 的重建全部**尚未执行**，不能算作已验证支持。操作路径见
[Linux ARM 主机准备](how-to/linux-arm-host.md)。

### 工具链升级到 Toffee 2.3.0 / xcomm 2.0.0 / Picker 3.0.0

2026-11-18 按上游发布把锁从 `uc-toffee 2.1.0`（ABI 3）升到 `uc-toffee 2.3.0`、
`uc-xcomm 2.0.0`（ABI 6）、`picker 3.0.0`，Python 依赖同步到 `pip 26.3`、
`pytest-asyncio 1.5.0`、`scikit-build-core 1.1.2`；`setuptools-scm` 保持 9.2.2，
因为上游 toffee/xcomm 的构建要求都是 `>=8,<10`。

- 工具锁参与构建缓存身份，`.cache/duts` 中 **438 个 ABI 3 时期的构建全部失效**，
  必须按新身份重建；旧收据不再代表新工具链的结果。
- **Picker 的 trace 调用图补丁已退役**：Picker 3 在上游索引 trace helper 体并解析调用图，
  覆盖了原补丁的跨兄弟函数 prefix 栈场景，`tests/test_picker_trace.py` 改为直接验证上游实现。
  xcomm 的宽字补丁上游仍无对应实现，继续保留并已在新版本上验证可应用。
- Picker 3 用单一 `<top>.xscfg` 配置库取代 `signals.json` 与 `<top>_offset.yaml`。
  套件不再保留这两个派生文件，统一经 `ucv.xscfg` 读取：`ports` 取自 `metadata.ports`
  （与原 `signals.json` 逐字节等价），地址映射取自 `variables`，`direct` 别名按上游语义
  已并入 `variables` 而非 `signals`。原先在构建时重新序列化旧文件的做法已删除。
- 新增 `ucv.xscfg` 只做读取，并提供一个仅供测试/对照组构造合成库的写入器；
  `tests/test_xscfg.py` 用上游 `picker config` 与 `xspcomm.XSignalCFG` 双向验证它。
- 查出并修掉一个既有的环境缺陷：`ucv setup` 的原生库安装只增不删，`.tools` 下三处
  目录累积了历次 ABI 的 `libxspcomm.so.*` 并被整体拷进 DUT 包。现在安装前清理，
  SDK 布局也从锁的 `package_version`/`native_abi` 派生。
- 清理了升级后不可达的缓存（`.cache` 32 GB → 9.3 GB，回收 22.7 GB）：437 个 ABI 3 时期的
  DUT 包、28 个孤立/历史生成目录、2 个历史源码检出。保留当前两个基线的完整 RTL 与检出、
  两个新锁下已验证的 DUT 包和全部镜像，因此 DUT 重建仍不需要重跑 Chisel。
  只删可重建或可再获取的生成态，未改动任何提交的报告、判定或哈希索引；
  删除清单与不可用边界见[存储回收记录](history/storage-reclamation-20261118.json)。

已验证：`ucv setup` 成功且 `receipt.tools == dependencies/versions.json`；
`validate_runtime()` 报 `2.3.0 / 2.0.0 / ABI 6`；公共工具回归 **426 PASS**（含 Picker 解析
3 项实际执行）；`sbuffer/sbuffer` 与 `lsq/deq_module` 在新身份下 **BUILT + SMOKE PASS**；
LSQ `deq_module` 收集 **PASS**。

未验证：其余 436 个 DUT 尚未重建，硬件执行只覆盖上述两个 DUT 的原生冒烟与 LSQ 收集，
任何旧报告都不能当作新工具链的通过证据。

### 运行环境

2026-11-17 已修复本机 `.venv` 的 Toffee 身份不一致。依赖源码恢复为锁定的
`f57150021791535d4b2fd01056c106f0cad53177`（2.1.0），从干净检出构建 wheel 重装；
安装包的 47 个源码/模板文件与锁定源码集合及哈希完全一致，原有 5 个旧文件残留已清除。
开发分支检出及旧安装包保存在 `.history/environment-repair-20261117-6m1f1xcg/`。

- `pip check`、`ucv doctor mmu --stage run` 与 `--stage generate` 通过，公共工具回归 **426 PASS**。
- `mmu/ptwfilter` 在 `public-e716c7658 / DefaultConfig` 下重新构建，原生冒烟 **PASS**；
  复用的是经哈希核验的本机完整 RTL 缓存。
- 统一入口实际运行 `test_single_request_issue_match_and_release`，seed 1、worker 1，
  **1 PASS**，setup/call/teardown 均通过，运行前后源码身份一致。
- `run_status=PASS`；MMU 的 8 项开放问题使 `hardware_verdict=INCOMPLETE`，
  `run/report` 均退出 1。此结果只证明上述有限选择与环境链路，整体仍未签核。

完整命令、修复前后记录、wheel、构建凭据与运行报告在
`results/environment-repair-20261117-6m1f1xcg/`，审计入口为其中的 `verification.json`。
以下迁移记录中的 Toffee 阻塞和硬件执行数 0 保留其当次含义。

### 既有共用实现的独立化

2026-11-17 根据用户要求，将 LSQ 的 FreeList/CAM/UncacheEntry、MMU 的 Repeater/Filter 与
Bitmap/BitmapCache、VAGQ 的两种 Pipeline 拆为独立实现，共涉及 **29 DUT、6 组旧共用包**。
LSQ 为 38/38、MMU 为 22/22、VAGQ 为 12/12；全仓 **336 DUT / 336 testbench** 一对一。
当前记录在[独立化索引](history/per-dut-migration-20261117.json)，完整证据在
`results/per-dut-migration-20261117/`。

| 检查 | 实际结果与边界 |
|---|---|
| 全仓身份与结构 | 354 条模块身份、336 个 top/export/binding 保留；7 条模块记录只追加当前 README 引用；三个工程配方逐字节保持 |
| 公共工具 | **426 PASS**；包含拒绝共用 testbench、路径多后继和报告临时根隔离 |
| LSQ 收集 | **2,608 → 2,608**；476 节点迁移，无参数/标记/场景损失；23 个单 DUT 隔离对照通过，相关 shared 自检 8 PASS |
| MMU 收集 | **438 → 444**；原 52 个硬件场景保留，两个跨 DUT 自检拆分多出 2 项，另加 4 个 checker 自检；相关离线检查 42 PASS，12 项隔离控制通过 |
| VAGQ 收集 | **476 → 521**；原节点全部保留，新增 45 个启动边界 selftest；相关离线检查 117 PASS，12 个独立根在仅有各自合成元数据时收集集合一致 |
| 统一对账 | 三工程原 **3,522** 节点全部有承接，当前 **3,573** 节点；零丢失、零重复承接。1,217 份当前 Python 字节与子 agent 核验证据一致 |
| 现行门禁 | 全登记 `ucv check`、布局、Skill/framework、资产及公开统一基线检查通过 |
| 硬件执行 | MMU/PTWFilter smoke 在运行前被 Toffee 检出身份检查拒绝，CLI 退出 2；本轮硬件测试执行数 0 |

VAGQ 的六个 fixture 按使用时读取元数据，单 DUT loader 只核验所选 DUT；显式联合场景保留
全部参与对象的 RTL 核验。该边界通过合成元数据/收据正负控制，尚未取得新的 internal 硬件结果。
旧文档、判定与哈希清单保留；新路径支持多后继，精确旧 nodeid 依真实收集映射，不将旧结果
自动转记为新通过。原 633 条根导航保留，新增 626 条；另有 35 条与本次三工程无关的旧导航目标
当前不可达，已在对账中列出，未为其猜测替代路径。

根回归曾因子进程发现仓库级 pytest 配置而出现 **424 PASS / 2 FAIL**；补齐测试临时根配置后，
同样的仓库内临时目录双 worker 对照为 2 PASS，外部临时目录完整回归为 426 PASS。
意外生成的合成报告已核对 6 个测试 nodeid、确认无打开句柄并归档，原失败日志和处置记录保留。

### 此前的身份采用与入口审计

2026-11-17 的采用、重放和工具检查在 `results/module-lifecycle-20261117/`。
并行入口审计分别在 `results/module-lifecycle-20261117-frontend-memblock/` 和
`results/module-lifecycle-20261117-backend-system/`：

- 354 个 ID 与父级关系沿用已确认草案；336 项 DUT 关联完备。相同公开/internal 观察重放均为零变化。
- 公共工具回归 **411 PASS**，含 65 项生命周期和 38 项 per-DUT 初始化/关联控制；
  全登记结构、布局、Skill/framework、资产及公开统一基线检查通过。首次全回归发现旧 Skill
  数量断言仍为 4，更新为实际 5 篇待审核方法后全量通过，原失败日志保留。
- 336 个 DUT 的已登记目录、环境、测试与规格路径存在；其中 199 个仍为显式失败骨架，
  125 个为公开既有资产，12 个为 internal 既有资产，均未因此得到新的硬件验收。
- 27 个 suite 直接 pytest 收集成功，共 6,595 节点；BPU、ICache 均在启动时被
  `Pinned toffee source checkout changed` 拒绝，退出码 4。收集成功不是锁定环境或硬件验收。
- 当时 29 个 DUT 共用 6 组 testbench（LSQ 3 组、MMU 2 组、VAGQ 1 组）；审计逐项留下
  精确参数/文件/nodeid 入口，随后按上述独立化迁移完成拆分。
- 200 个 DUT 已登记 smoke（其中 199 个是失败占位），其余 136 个未登记 smoke。
  VAGQ 独立 selector 仍依赖全工程端口元数据及 shared loader 的全 DUT RTL 检查；干净单 DUT
  资源隔离当时尚未证明。工程硬件测试执行数为 0；本次后续合成隔离控制见上节。

以下保留 2026-11-16 结构迁移的证据边界。

命令、日志和对账保存在 `results/ut-management-20261116/`；前一版证据仍在
`results/ut-split-20261116/`，两次独立记录：

| 检查 | 实际结果与边界 |
|---|---|
| 公共工具回归 | **308 PASS**；含工作索引保留人工正文、变体独立行、旧观察/top 不符，以及通用报告的 UNCERTAIN/ERROR、自检分域与单/双 worker 对照 |
| 全登记结构 | `ucv check all`、布局 `--strict`、Skill/framework、资产审计、`git diff --check` 通过 |
| 公开基线 | `ucv list public_all --require-unified-baseline` 通过，28 suite |
| 收集对账 | 调整前后 **2,029 节点**完全对应（原 2,024＋5 个既有骨架）；参数、标记、fixture 名称归一导入路径后无差异 |
| Python 实现 | 360 份搬迁实现/测试/工具，AST 按明确命名空间与资源路径归一后无差异；通用报告插件单独由回归核验 |
| 历史证据与已有工作 | 538 份受保护资料逐字节一致，包含先前 532 份历史资料及既有 LSQ 修正/基线等；633 条位置映射无循环 |
| 定向自检 | 同一 942 项选择仍为 **940 PASS / 2 FAIL**；FTQ 675 PASS、IFU 238 PASS/1 FAIL、IBuffer 19 PASS、InstrUncache 8 PASS/1 FAIL |
| 统一收集入口 | **阻塞**：Toffee 本机检出 commit 与锁定清单不符，运行前身份检查拒绝，未生成受管回归收据 |
| 直接 pytest 收集 | 六个调整包全部收集：933 / 940 / 83 / 68 / 1 / 4；只证明当前安装环境可收集，不是锁定环境验收 |

2026-11-16 审计时 `.tools/sources/toffee` 为 `e80f2a0b10406feda466e270ce8ab4f362bdb088`；
2026-11-17 入口审计观测为 `a8e2e884a4fb675bc4c6f8227b14e92e44a9221c`。
清单仍锁定 `f57150021791535d4b2fd01056c106f0cad53177`；两轮均未改动依赖检出或锁。
前次两个自检失败分别缺少以下资源，本次未重跑或关闭：
`suites/frontend/ifu/dut/ifu/signals.json` 和
`suites/frontend/instr_uncache/rtl/instr_uncache/InstrUncache.sv`，真实 FAIL 保留。

## 未完成范围与历史判定

- 当前对象认领与合同评审仍需推进；Frontend/FrontendBridge 已给出责任草案，其余骨架
  尚未实现完整合同、事务环境、独立 oracle/checker 和功能覆盖。
- 模块增量维护的迁移控制使用合成基线；真实新旧设计合同的语义承接仍待核查，线上表同步未执行。
- 本次结构拆分未执行全部 DUT 原生构建、冒烟、功能回归或覆盖签核；迁移后的 native/RTL
  入口须由当前配方重新准备和构建。旧 native/RTL 在第一版结果目录归档，本轮 Fetch 原树
  在 `results/ut-management-20261116/retired-fetch/` 保留；原结果沿用原身份。
- 既有模型适配、真实 FAIL/XFAIL/SKIP、BPU 开放问题、LSQ/DCache/MMU/LSU/VAGQ 的观察及
  集成缺口，继续由各自规格与稳定问题记录维护。结构检查通过不关闭它们。
- 2026-11-10 的事务适配和结构验收日志仍在 `results/transaction-adapters-20261110/`、
  `results/testbenches-all-20261110/`、`results/testbenches-bpu-20261110/`；各选择重叠不累计。
  迁移前状态页原文包含于本次源码快照，旧日期、基线、失败与未认证范围保持原义。
- ICache 历史清理的 249 个 bytecode 未保留逐文件删除清单，这一原有审计缺口仍保留。

历史证据从 [经验索引](lessons/README.md)及[来源索引](history/evidence-index.json)进入。
整体硬件验收仍为 **NOT_CERTIFIED**。
