# 运行测试与查看报告

本指南用于已存在的工程和用例。执行前应已安装锁定工具，并准备所选 DUT 的 RTL；
首次运行请先完成[MainBTB 教程](../tutorials/bpu-first-ut.md)，获取 RTL 见
[工作空间指南](workspace.md)。以下模板中的 `<suite>`、`<dut>`、`<test-nodeid>` 和结果
路径都需要替换；全部命令从仓库根执行。

## 1. 确认选择与当前构建

```sh
./scripts/ucv list <suite>
./scripts/ucv info <suite> --dut <dut>
./scripts/ucv doctor <suite> --stage run
./scripts/ucv build <suite> --dut <dut> --jobs 2
```

从 `info` 获取实际 `testbench`、测试路径和 smoke nodeid，不按 DUT 名猜目录。
`doctor` 检查工具环境，不替代 DUT 构建；`build` 才生成并核验当前配方的原生包和冒烟。
若已有匹配且完整的构建，工具可复用缓存；不要手改 active 链接或收据冒充新构建。

只选一个 DUT 可以避免要求其它 DUT 都已构建。不指定 `--dut` 会按所选工程的全部
DUT 做构建预检，即使 `--` 后只选了其中一个用例。

## 2. 先核对用例集合

```sh
./scripts/ucv run <suite> --dut <dut> --collect-only \
  --output results/<new-collection> -- <test-nodeid>
```

也可以把 `<test-nodeid>` 换成 `testbenches/<testbench>/tests`，或在 `--` 后使用
`-k <expression>` / `-m <expression>`。完整 nodeid 含参数时使用引号。

`--collect-only` 不执行测试、不要求所选 DUT 已有构建，但仍需要项目 Python/锁定运行
工具和可导入的测试依赖；internal 工程仍需要外部来源。收集完整也不是硬件结果：
当前报告将其标为 `hardware_verdict=INCOMPLETE`，`ucv run` 因此可返回 1。
应同时检查收集日志、用例列表和收据，不能只按进程退出码判定收集是否成功。

## 3. 运行并固定种子、并发和结果目录

```sh
./scripts/ucv run <suite> --dut <dut> --workers 1 --seed 1 \
  --output results/<new-run> -- <test-nodeid>
```

- `--` 后的路径相对**工程根**，不是仓库根。
- 每次 `--output` 必须是新目录；不指定时工具自动生成 `results/<时间戳-随机后缀>/`。
- `--seed` 进入运行收据和工程环境；测试自身的显式参数种子与 native 初始化种子不一定
  是同一件事，见[种子边界](../local-configuration.md#回归seed与原生初始化)。
- `--workers` 是顶层总预算。BPU 还按实际 native owner 分进程，不自行传 `-n` 或覆盖分区。
- 开始后不要修改所选工程的代码、合同、问题或 README；工程 Markdown 也参与源码身份校验。

### 同时选择多个 DUT

在 `build` 和 `run` 中重复 `--dut`，使预检覆盖用例实际加载的每个 DUT：

```sh
./scripts/ucv build <suite> --dut <dut-a> --dut <dut-b> --jobs 2
./scripts/ucv run <suite> --dut <dut-a> --dut <dut-b> --workers 2 \
  --output results/<new-run>
```

多个 DUT 共用参数化文件时，`--dut` 只限制测试文件/目录，**不自动过滤 fixture 参数**。
只跑某个变体须用带参数的完整 nodeid；否则应选择该文件可能加载的全部 DUT。
默认的 DUT 测试根还包含存在的 `shared/tests`；显式路径/nodeid 则按实际选择收集。

### 扩大到工程或公开集合

确认资源和构建范围后再扩大；下面两条是可选的不同范围，不是首次运行的必做步骤：

```sh
./scripts/ucv run <suite> --workers 4 --seed 1 --output results/<new-suite-run>
./scripts/ucv run public --require-unified-baseline --workers 8 --seed 1 \
  --output results/<new-public-run>
```

`public`、`full`、硬件分组的含义见[选择器参考](../reference/workspace.md#选择器与参数转发)。
当前 `full` 包含使用不同基线的 internal VAGQ，不能直接加严格统一基线选项。

## 4. 读取本次实际报告

```sh
./scripts/ucv report results/<new-run>
```

命令重新生成该目录的 `summary.json` 和 `summary.md`，不重新执行测试。省略路径时
读取 `.ucv/last-run.json` 指向的运行；多人协作或连续运行时应显式给路径，避免看错结果。

按以下顺序检查：

1. `run.json`：实际 DUT/pytest 选择、种子、有效基线、子进程命令和源码身份是否符合预期。
2. `summary.json` 的 `run_status`、`counts`、`hardware_verdict`、`gaps`：分开看执行结果与验收阻塞。
3. `cases/<任务>/cases.json`、`logs/<任务>.log`：定位具体 FAIL/ERROR，以及 setup/call/teardown 阶段。
4. 对应 Toffee `manifest.json` 与覆盖产物：核对是否完整提交、文件是否可用，不只看进度条。
5. 工程规格与问题记录：核对本次未覆盖的功能、配置和观察边界。

即使用例全 PASS，开放问题、缺失产物或未完成的收尾仍可能使硬件汇总为 `INCOMPLETE`。
`UNCERTAIN` 也不计 PASS；其单独存在可返回 0。判定与退出码见
[参考](../reference/workspace.md#报告字段与退出码)，结论含义见[维护与验收](../maintenance.md)。

## 5. 比较两次运行

```sh
./scripts/ucv report results/<new-run> --compare results/<prior-run>
```

旧目录须已有 `summary.json`；必要时先对旧目录执行一次 `ucv report`。该比较写回新目录
的汇总，不会改写旧运行或把当前问题状态追加到历史收据。

先看基线、验证源码、种子、DUT 和 pytest 选择是否可比，再看新增/删除/判定变化。
问题记录关闭、用例减少或两次 PASS 数相同，都不自动证明缺陷修复或刺激等价。
重叠选择的结果不能相加当作累计通过数。

## 常见阻塞

| 现象 | 下一步 |
|---|---|
| active DUT 与当前基线不匹配，或 native/RTL 哈希不符 | 按当前配置重新 `build`；保留旧凭据，不改收据或手动换链接 |
| 选择的文件可能加载未选 DUT | 使用完整参数化 nodeid，或补选实际所有 DUT |
| `Output must be new` | 改用新的输出目录，不删除旧证据来重用名字 |
| `source_changed_during_run` / 完整性 ERROR | 保留该次 ERROR；停止写入并冻结后，用新目录重跑所需选择 |
| 0 项收集、缺少 case receipt、覆盖未提交 | 检查收集/子进程日志；缺结果不能算通过 |
| 用例 PASS，但 report 返回 1 | 查看 `gaps`、开放问题和覆盖完整性，不用删除问题来变绿 |

仿真工具安装/编译问题另见[构建经验](../lessons/build-and-toolchain.md)，本地来源问题见
[本地配置](../local-configuration.md)。清理数据前应先确认用途与活动状态，并保留必要证据。
