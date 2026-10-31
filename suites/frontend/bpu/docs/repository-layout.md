# 验证代码目录与职责

验证框架是锁定的 `uc-toffee`（导入名 `toffee`），原生配套源码为 `uc-xcomm`
和 Picker，精确版本见 `dependencies/versions.json`。它们不放入 `suites.frontend.bpu`；
依赖升级、能力核对和安装边界见项目工作流及待审核方法文档。

2026-10-10 已切换为「DUT → 组件职责」，不再把所有 Agent、端口、事务、
模型与场景平铺到 `suites/frontend/bpu/`。目录迁移不代表新的全量回归通过或覆盖率上涨。

```text
suites/frontend/bpu/        # import suites.frontend.bpu
├── __init__.py             # ROOT，不装载 DUT 或重导出领域符号
├── ports/                  # 共享 picker 信号绑定、方向、write mode
├── drivers/                # 项目对 toffee driver 的薄适配
├── monitors/               # 通用周期采样适配
├── transactions/           # 通用周期事务数据
├── runtime/                # DUT 创建、fixture、memory-direct、产物路径
├── checkers/               # 通用预测比较
├── models/                 # 地址、折叠历史等共享语义
├── coverage/               # 原生覆盖率、并行合并、相位审查
├── pytest_plugins/         # pytest 插件、证据、调度
├── abtb/                   # 独立 AheadBTB DUT
├── bpu/                    # 集成 BPU DUT
├── ittage/
├── mbtb/
├── ras/
├── sc/
├── tage/
├── ubtb/
├── uras/
└── utage/

suites/frontend/bpu/tage/    # 以 TAGE 为例
├── agent/main.py           # 组件组合、生命周期、对用例开放的事务 API
├── bundle/ports.py         # 静态信号结构与绑定
├── transaction/types.py    # 请求、训练、响应的数据类型
├── driver/                 # DUT 专属编码／驱动适配
├── monitor/                # 被动采样与响应解码
├── env/                    # DUT 专属环境辅助（不定义 pytest fixture）
├── case/                   # 可复用场景、向量和场景准备
├── model/                  # 独立参考语义
├── checker/                # 关联、比较及状态检查
└── coverage/               # 功能覆盖定义与审查

tests/
├── conftest.py             # 每个 DUT 唯一的 agent fixture 与公共插件
├── framework/              # 公共设施契约测试（自动标 selftest）
└── <dut>/
    ├── bundle/             # 绑定契约测试；原 interfaces/ 已改名
    ├── drivers/
    ├── monitors/
    ├── scoreboard/
    └── testcase/test_*.py  # pytest 场景入口，只调用 agent 事务 API
```

角色目录按实际实现创建。比如 MicroRAS 直接复用 `drivers/` 和
`monitors/`，不为对称而造空壳专用类或空目录。不再创建 common 包。

## 分层边界

- Bundle 是静态信号结构，不执行时序；`transaction` 是普通数据，不能与信号 Bundle 混为一谈。
- Driver 执行主动驱动、接受时机与 idle 恢复；编码器与驱动适配放在 `driver/`。
  通用异步／多周期／overlap 能力仍由 xreactor 提供，不在 BPU 工程重新实现。
- Monitor 被动采样，decoder 不生成 expected、不比较结果。
- Agent 组合这些组件，提供 `predict/train/submit/drain` 等上层 API。
- Env 负责 DUT／Execution／组件的创建、释放和观察作用域。
- Model 生成参考结果；Checker 使用同一比较机制做直接或异步检查，异常到达 pytest。
- Case 保存可复用场景；pytest 用例只选场景、表达检查和覆盖意图。
- 功能覆盖与功能点通过率分别统计；目录调整不改变这两者的含义或分母。

不新增 Interface 层。静态绑定属于 Bundle，时序行为属于 Driver／Monitor，
组合与生命周期分别属于 Agent／Env。

集成 BPU 的内部模块不是新的 DUT，放在对应角色的子目录，例如：

```text
suites/frontend/bpu/bpu/model/abtb/
suites/frontend/bpu/bpu/monitor/abtb/
suites/frontend/bpu/bpu/checker/abtb/
suites/frontend/bpu/bpu/env/abtb/
suites/frontend/bpu/bpu/case/abtb/
suites/frontend/bpu/bpu/coverage/abtb/
```

SC、bypass、RAS、PHR 同理。独立 ABTB 的组件则属于 `suites/frontend/bpu/abtb/`，
不再与集成 BPU 的内部 ABTB 混放。

## 查找与运行

按实际职责导入，不再从几百行的根包 re-export 表中取所有符号：

```python
from suites.frontend.bpu.tage.agent.main import TageAgent
from suites.frontend.bpu.tage.transaction.types import TageLookup
from suites.frontend.bpu.tage.monitor.write import TageWriteActivityMonitor
```

生产回归入口不变：

```sh
python3 tests/run_all.py                                  # 默认最多 32 进程
python3 tests/run_all.py --select tests/tage/testcase      # 同一隔离和检查机制
python3 tests/run_all.py --workers=8 --select tests/framework
python3 tests/run_all.py --workers=1 --select tests/uras   # 串行诊断
```

选跑不会覆盖全量报告；全量必须通过完整收集、worker 收据、源码冻结、
native／功能覆盖合并和无退步门禁才能发布。默认不导出逐周期轨迹或波形。

旧源码备份及映射位于 `results/directory-migration-20261010/`。
`tests/framework/test_repository_layout.py` 防止公共根目录重新平铺、
fixture 回流子目录 conftest、功能用例直接访问 `.dut`/`.pins`、支持模块回流
testcase 或重引入旧 Interface 目录。`tests/framework` 由 pytest 插件统一标记
`selftest`，不计硬件功能 credit；该标记不改变既有功能点判定。
