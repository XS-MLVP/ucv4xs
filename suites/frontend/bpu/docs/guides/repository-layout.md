# 验证代码目录与职责

验证框架是锁定的 `uc-toffee`（导入名 `toffee`），原生配套源码为 `uc-xcomm`
和 Picker，精确版本见 `dependencies/versions.json`。它们不放入 `suites.frontend.bpu`；
依赖升级、能力核对和安装边界见项目工作流及待审核方法文档。

当前采用 workspace schema 2：打开 `testbenches/<dut>/` 即可找到该验证对象的
环境、参考模型、检查器与用例；实际共用组件集中到 `testbenches/shared/`。
完整生成与检查契约见[全仓规范](../../../../../docs/reference/module-layout.md)。

```text
suites/frontend/bpu/
├── testbenches/
│   ├── bpu/               # 顶层 BPU，包括内部预测器组合
│   ├── mbtb/              # MainBTB；其余八个独立 DUT 同级
│   └── shared/            # 确实跨 DUT 复用的组件
│       ├── env/           # 加载、执行、绑定、驱动、采样、pytest 接线
│       ├── transactions.py
│       ├── checker/       # 通用预测比较、请求寿命检查
│       ├── coverage/      # 原生覆盖收集、解析与导出机制
│       └── tests/         # 共享组件和工程工具的自检
├── conftest.py             # 唯一 fixture / 插件注册入口
├── pytest.ini             # testpaths = testbenches
├── tools/                 # 离线报告汇总、覆盖归因、审计命令
└── docs/                  # 设计/验证规格与正式问题

testbenches/tage/           # 以 TAGE 为例
├── env/
│   ├── agent/main.py       # 对用例开放的事务 API 与生命周期
│   ├── bundle/ports.py     # 静态信号结构与绑定
│   ├── driver/            # DUT 专属编码／驱动
│   └── monitor/           # 被动采样与响应解码
├── transactions/types.py
├── model/                 # 独立参考语义
├── checker/               # 比较与状态检查
├── coverage/              # DUT 的行为覆盖定义
└── tests/
    ├── testcase/          # 功能场景入口，只调用 agent 事务 API
    ├── scenarios/         # 复用步骤、向量和场景准备
    └── …                  # 该 DUT 的绑定、模型、checker 错误对照
```

六种职责在 DUT 与 shared 中同名同义。除 `tests/` 为目录外，其余职责按复杂度选择
文件或同名包。例如共享周期事务只用 `transactions.py`；目前没有共享参考模型，
因此没有 `shared/model`。单 DUT 多处调用的工具仍归该 DUT。

`shared` 实现依赖 Toffee / ucv，不能反向导入具体 DUT 或工程 tools；共享自检可
检查真实接线。`plain_sampler`、覆盖回放和场景计时分别归 BPU 的 `env/bundle`、
`coverage`、`tests/scenarios`。BPU/MBTB 的具体参数轴归各自 `tests/regression.py`，
由根注册；整工程覆盖义务汇总由 `tools/parallel_coverage.py` 接入 Toffee 回调。

## 分层边界

- Bundle 是静态信号结构，不执行时序；`transactions` 是普通数据，不能与信号 Bundle 混为一谈。
- Driver 执行主动驱动、接受时机与 idle 恢复；编码器与驱动适配放在 `driver/`。
  通用异步／多周期／overlap 能力由 Toffee 提供。
- Monitor 被动采样，decoder 不生成 expected、不比较结果。
- Agent 组合这些组件，提供 `predict/train/submit/drain` 等上层 API。
- Env 负责 DUT／Execution／组件的创建、释放和观察作用域。
- Model 生成参考结果；Checker 使用同一比较机制做直接或异步检查，异常到达 pytest。
- `tests/scenarios` 保存可复用场景；pytest 用例只选场景、表达检查和覆盖意图。
- 功能覆盖与功能点通过率分别统计；目录调整不改变这两者的含义或分母。

不新增 Interface 层。静态绑定属于 Bundle，时序行为属于 Driver／Monitor，
组合与生命周期分别属于 Agent／Env。

集成 BPU 的内部模块不是新的 DUT，放在对应角色的子目录，例如：

```text
suites/frontend/bpu/testbenches/bpu/model/abtb/
suites/frontend/bpu/testbenches/bpu/env/monitor/abtb/
suites/frontend/bpu/testbenches/bpu/checker/abtb/
suites/frontend/bpu/testbenches/bpu/tests/scenarios/lifetimes/abtb/
suites/frontend/bpu/testbenches/bpu/tests/scenarios/abtb/
suites/frontend/bpu/testbenches/bpu/coverage/abtb/
```

SC、bypass、RAS、PHR 同理。独立 ABTB 的组件则属于 `testbenches/abtb/`，
不再与集成 BPU 的内部 ABTB 混放。

## 查找与运行

按实际职责导入，不再从几百行的根包 re-export 表中取所有符号：

```python
from suites.frontend.bpu.testbenches.tage.env.agent.main import TageAgent
from suites.frontend.bpu.testbenches.tage.transactions.types import TageLookup
from suites.frontend.bpu.testbenches.tage.env.monitor.write import TageWriteActivityMonitor
```

从仓库根使用统一入口：

```sh
./scripts/ucv info bpu --dut tage
./scripts/ucv run bpu --dut tage --collect-only --workers 1
./scripts/ucv run bpu --dut tage --workers 1 -- testbenches/tage/tests/testcase
./scripts/ucv run bpu --workers 1 -- testbenches/shared/tests
```

选跑不会覆盖全量报告；全量必须通过完整收集、worker 收据、源码冻结、
native／功能覆盖合并和无退步门禁才能发布。默认不导出逐周期轨迹或波形。

`ucv check` 约束目录和 shared 的依赖方向；
`testbenches/shared/tests/framework/test_repository_layout.py` 检查 fixture 唯一注册和
功能用例 API 边界。共享自检保留 `selftest` 分类，十 DUT 的 native binding 自检
仍分别归属各 DUT，其原生库仍在隔离进程中加载。

2026-10-10 的旧迁移记录在 `results/directory-migration-20261010/`；本次整理的收集
映射、归属审查与运行记录在仓库 `results/testbenches-bpu-20261110/`。
历史路径通过 `docs/path-migrations.json` 导航，冻结记录的 nodeid、哈希与判定保持原义。
