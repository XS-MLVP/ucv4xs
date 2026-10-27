# Replay checkpoint 全池补例：叶子、真实 LoadQueue 与 LsqWrapper

结论：**该补例家族的三层真实运行已验证，整体 LSQ 仍为 ACTIVE_NOT_ACCEPTED。**
固定 RTL、native build 与三类分母未变，不修改 RTL/Chisel、不替换真实下级。

## 请求到证据的检查矩阵

| 请求 / 功能点 | 实现与真实检查 | 可复核产物 |
|---|---|---|
| 先定义微架构情形 | checkpoint 全 1→0；两轮各占满 120 项；输出握手不当作释放；真实反馈与新 UID 复用 | `docs/contracts/replay-checkpoint-pool.md`，在新测试实现前建立 |
| 独立公共接口模型与 Picker/X Reactor | 原 fixture 的 DriveStable/RisingEdge 逐拍检查继续执行；新增见证仅取公开 replayQueueIdx、LQ/ROB、checkpoint、反馈和完成 | `tests/replay/test_pool_payload.py`、`tests/load_queue/test_checkpoint_pool.py`、`tests/lsq_wrapper/test_checkpoint_pool.py` |
| 从子块推进真实父级 | Replay、完整 LoadQueue、完整 LsqWrapper 分别 native 运行；父级没有外驱内部 head/full/SQ ready | 三组独立 baseline/after 的 `execution/manifest.json`、`pytest.xml`、`command.json` |
| 容量、背压、时序、正常释放 | 两轮每个公开 slot 恰好握手一次，所有原 UID 正常反馈后排空；Replay 在握手完、反馈前仍 full/allocated | 各 after 的 `cases/**/checkpoint-pool-witness.json`；每层累计 240 UID |
| 三类覆盖分母与源位置 | 每对同 build/同点集，无新增未命中；15360 个 checkpoint 位方向点完整命中，逐点含原源位置；锁定分析器交叉核对 | `directed-gap-closure-*-v1.json`、`checkpoint-pool-evidence-v1.json`、原始 `coverage.dat`/`coverage.info` |
| 不隐藏真实 FAIL | 重新执行三层现存 strict 用例，与 regression15 逐节点归一化全文比较 | `checkpoint-failure-retention-01`：1 PASS/7 FAIL；`checkpoint-wrapper-failure-retention-01`：1 PASS/1 FAIL |
| 不用定向绿色集替代统一结果 | regression15 不重跑、不并入定向命中或节点；历史 227 FAIL 全部保留 | `results/lsq-progress-regression-15/failure-preservation-audit-v1.json` 与 38 行最终矩阵 |

## 同一 native build 的前后结果

以下每行是**独立 DUT 的独立实验**，不可跨行相加当作一个分母。
“原始 line 点”与“LCOV 原始源码行”不是同一个单位，分开报告。

| DUT | PASS 前→后 | 原始 line 点前→后 | toggle 前→后 | branch 前→后 | LCOV 原始源码闭包行前→后 |
|---|---:|---:|---:|---:|---:|
| LoadQueueReplay | 9→10 | 1785→1785 / 2290 | 42000→56329 / 79904 | 5099→5102 / 5448 | 29412→29452 / 30500 |
| LoadQueue | 3→4 | 700→700 / 3426 | 73287→82586 / 204148 | 7928→7928 / 16440 | 35030→35030 / 50520 |
| LsqWrapper | 1→2 | 243→532 / 3654 | 100150→113538 / 322010 | 8905→9161 / 18670 | 29843→35590 / 59602 |

三层各有两生命周期完整公开槽号集合 `0..119`，真实反馈和完成累计 240 UID；
每层的真实 Replay `uop_N_perfDebugInfo_runahead_checkpoint_id[bit]` 都有
`120 × 64 × 2 = 15360/15360` 个位方向点命中。

结果目录（baseline 与 after 均为 fresh，包含相同旧节点，after 多一个新例）：

- `results/replay-checkpoint-pool-baseline-01/` → `results/replay-checkpoint-pool-after-01/`
- `results/lq-checkpoint-pool-baseline-01/` → `results/lq-checkpoint-pool-after-01/`
- `results/lsq-checkpoint-pool-baseline-01/` → `results/lsq-checkpoint-pool-after-01/`

每个 after 的 `checkpoint-pool-evidence-v1.json` 验证原始 artifact SHA、
固定 RTL 闭包 SHA、baseline/after 源集合摘要相同、全部旧节点保留、
真实 pytest 计数、原始点集及 LCOV 源码行集合。可执行：

```sh
python3 -B tools/audit_checkpoint_pool_v1.py
python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15
```

运行证据默认只有摘要、compact witness 和覆盖率，不保存逐拍 JSON、波形或完整源副本。
原始 source aggregate 证明每次运行启动/结束一致，不声称当前工作区和过去完整源集合永远一致；
复现依赖工作区与既存受锁源文件。`audit-history/` 按 SHA 保留派生索引修订前的原始字节。

## 对 regression15 真缺口的对照，而不是合并

同 DUT、同 build、相同原始点全集下，取 regression15 未命中点与本次 after 命中点的交集：

- Replay：12269 个原 toggle 缺口在定向 after 中观察到命中。
- LoadQueue：8358 个。
- LsqWrapper：7715 个。

这是集合对照；不生成跨目录合并 coverage，不从 regression15 官方缺口数中扣减。
本轮 branch 增益来自各自定向 baseline 的不足；三个 after 都未命中 regression15
原未命中的 branch 点，因此不声称关闭了统一回归的 branch 缺口。

## 修正与剩余边界

1. 历史两单条 metadata 用例未断言同槽号，不能仅凭名字声明复用。其 raw 结果不变；
   新全池见证补足这项能力，gap summary 显式记录原项语义限制。
2. Wrapper 新例是完整真实层次中的 **load-only 容量情形**。Store 分支保持真实连接，
   但本例无 Store，不把它提升为混合 Store/共享总线整体通过；原 82 个 Wrapper 功能情形不删减。
3. `strict-full-pool` 仍在 tick312 出现 `io_replay_0_valid` 实际1、期望0；
   另外 Replay/LoadQueue 的7个严格依赖 FAIL也保留，未新增 skip/xfail 或放宽模型。
4. 统一 regression15 仍为 2103 PASS/227 FAIL、38 native DUT、76功能组，
   保留20条 line 边界、235610个 toggle 缺口与563个 branch 缺口。它们仍需后续合法补例或具体边界审计。
