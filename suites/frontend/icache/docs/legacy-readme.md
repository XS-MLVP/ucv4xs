> 迁移前历史说明。当前命令与基线见仓库根 README；以下记录不代表重建版本验收。

# icache-verify-kunminghu-v3

XiangShan **kunminghu-v3** 的 ICache 验证工程。与 `bpu-verify-kunminghu-v3`
同一套工具链和目录约定：picker memory-direct DUT、xreactor 组件、pytest 用例。

整块 ICache 与它的子块是**平级 DUT**，不是父子关系，这样外层适配或兄弟子块的
改动不会悄悄改变另一个子块的测试面。

## 1. 依赖版本（本机实际使用）

| 组件 | 版本 |
|---|---|
| xreactor | `2461d0f`（`dev/coverage-v2`，本地领先远端 5 个提交） |
| xcomm / xspcomm | `c39db66` / `0.3.0.dev3`，native ABI 3，coverage protocol 5 |
| picker | `2.0.0-HEAD-4dd442c-2026-10-12` |
| Verilator | 5.052（`/opt/verilator-5.052`） |
| RTL 来源 | XiangShan `kunminghu-v3` @ `893e1580` |

`dependencies/xreactor`、`dependencies/picker`、`dependencies/xcomm` 是指向
BPU 工程同一份检出的符号链接，`dependencies/versions.json` 记录确切提交，
`icacheverify.common.env.runtime` 在 pytest 启动时校验上述版本，不一致立即失败。

## 2. 目录

```text
icacheverify/
├── common/              # 跨 DUT 设施：bundle/driver/monitor/env/coverage/pytest
├── waylookup/           # ICacheWayLookup
├── replacer/            # ICacheReplacer
├── mshr/                # ICacheMshr
├── databank/            # ICacheDataBank
├── metabank/            # ICacheMetaInterleavedBank
├── metaarray/           # ICacheMetaArray
├── dataarray/           # ICacheDataArray
├── missunit/            # ICacheMissUnit
├── mainpipe/            # ICacheMainPipe
├── prefetchpipe/        # ICachePrefetchPipe
└── icache/              # 整块 ICache（集成 DUT）

每个 DUT 内部：
  agent/main.py       组件组合与对用例开放的 API
  bundle/ports.py     静态信号绑定
  transaction/types.py 普通数据类
  driver/             编码与驱动适配
  monitor/            被动采样与解码
  model/              独立参考语义
  checker/            比较与状态检查
  case/               可复用场景与向量
  env/pytest.py       fixture 定义
  coverage/           功能覆盖定义

tests/
├── conftest.py
├── framework/         公共设施与目录契约测试
└── <dut>/testcase/test_*.py
```

## 3. RTL 与 DUT 构建

每个 DUT 只保留所需的 RTL 闭包，放在 `rtl/<dut>/`，不喂整个 SoC：

```sh
python3 tools/dep_closure.py --rtl /home/xyl/kmh-v3-test/soc-split/rtl \
    --top ICacheWayLookup --out rtl/waylookup/filelist.f --report

python3 tools/build_dut.py waylookup --jobs 16     # 单个
python3 tools/build_dut.py --jobs 16               # 全部 11 个
```

`build_dut.py` 使用与 BPU 相同的 picker 选项（`--rw mem_direct -w memory-direct.fst -c`），
并在安装到 `dut/<dut>/` 前做两件事：检查包文件齐全，且子进程能实例化并走两个时钟。

依赖闭包规模（用于控制单次构建时间）：

| DUT | 顶层模块 | RTL 文件数 |
|---|---|---|
| waylookup | 已构建 | 队列/指针/flush/异常锁存/refill 修正 | 24 项，13 功能点 | **通过**，行覆盖 94.72% |
| replacer | 已构建 | tree-PLRU + 端口分派 + victim 反馈 | 10 项，7 功能点 | **通过**，行覆盖 95.26%（缺口逐行取证） |
| mshr | 已构建 | 单条目 MSHR + 事件驱动 MissUnitHelper | 9 项，8 功能点 | **通过**，行覆盖 96.43% |
| databank | 已构建 | way-mask 写 / 全 way 读 SRAM 模型 | 5 项，5 功能点 | **通过**（行覆盖受插桩限制，见 docs/sram-dut-coverage-limitation.md） |
| metabank | 已构建 | 元数据 + 有效位 + 全清模型 | 6 项，6 功能点 | **通过**（同上） |
| metaarray | `ICacheMetaArray` | 13 |
| dataarray | `ICacheDataArray` | 24 |
| missunit | `ICacheMissUnit` | 21 |
| mainpipe | `ICacheMainPipe` | 3 |
| prefetchpipe | `ICachePrefetchPipe` | 3 |
| icache | `ICache` | 65 |

## 4. 运行

**必须通过 `xreactor run` 启动**，不要直接调用 `pytest`。managed runner 负责
worker 调度、covergroup 自动捕获、原生覆盖率合并与输入回收；绕过它会丢失
DUT 登记和覆盖率门禁。

```sh
export PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src

python3 -m xreactor run --workers 1 \
    --output results/xreactor-waylookup-$(date -u +%Y%m%dT%H%M%SZ) \
    -- tests/waylookup/testcase

python3 -m xreactor run --workers 4 --output results/xreactor-parallel \
    -- tests/waylookup/testcase
```

需要看用例的 `print` 时，把 `-s` 放在 `--` 之后：

```sh
python3 -m xreactor run --workers 1 --output results/xreactor-debug -- -s tests/waylookup/testcase
```

每次运行的产物（禁止复用同名目录）：

```text
results/<run>/
  manifest.json, feature-points.json, functional-summary.json
  rtl-coverage-manifest.json, coverage.html
  native/<build-id>/coverage.dat, coverage.info
```

已验证结果（`results/xreactor-full-1`，`--workers 4`，`-- tests`）：

| 项 | 值 |
|---|---|
| 用例 | **19 passed**（11 个 WayLookup 场景 + 8 个目录/设施契约） |
| 功能点 | **6/6 PASS**，0 NOT_RUN |
| 原生 RTL 行覆盖 | 1316 / 2914 = **45.16%**（`ICacheWayLookup` 生成的 `WayLookupDut.v`） |
| DUT 登记 | 4 个 worker，原生输入 3/3/2/… 已合并并提交 |

覆盖率数字是**行**覆盖率，不等于功能点通过率；剩余未命中行主要是异常/inline
断言与未覆盖的 `updateStall` 路径。

## 5. 当前进度

| DUT | DUT 包 | 参考模型 | 用例 | 状态 |
|---|---|---|---|---|
| waylookup | 已构建 | 环形队列 / flush / refill 元信息修正 | 24 项，13 功能点 | **通过**，行覆盖 94.72%（`docs/waylookup-coverage-closure.md`） |
| replacer | 已构建 | tree-PLRU + 端口分派 + victim 反馈 | 10 项，7 功能点 | **通过**，行覆盖 95.26%，缺口逐行取证（`docs/replacer-coverage-closure.md`） |
| mshr | 已构建 | 单条目 MSHR + 事件驱动 MissUnitHelper | 9 项，8 功能点 | **通过**，行覆盖 96.43% |
| databank | 已构建 | way-mask 写 / 全 way 读 SRAM 模型 | 5 项，5 功能点 | **通过**（DUT 级逻辑无行点，见 `docs/sram-dut-coverage-limitation.md`） |
| metabank | 已构建 | 元数据 + 有效位 + 全清模型 | 7 项，7 功能点 | **通过**，语句覆盖 98.63% |
| metaarray | 已构建 | 交织 bank 路由 + 有效位模型 | 8 项，8 功能点 | **通过**，语句覆盖 98.63% |
| dataarray | 已构建 | bank 交织路由 + 多行请求模型 | 9 项，8 功能点 | **通过**，语句覆盖 100% |
| missunit | 已构建 | — | — | 仅有结构 |
| mainpipe | 已构建 | — | — | 仅有结构 |
| prefetchpipe | 已构建 | — | — | 仅有结构 |
| icache | 已构建 | — | — | 仅有结构 |

`verification_plan.json` 目前是 version 1（只登记功能点 ID），共 **39 个功能点**。
version 2 要求的语义事件合同与 reached/checked 覆盖绑定尚未编写。

最近一次全量：`results/xreactor-full-3`（`--workers 4 -- tests`）—— **63 passed**，
硬件功能点 **39/39 PASS**，0 NOT_RUN。

#### WayLookup 已覆盖的功能点

| ID | 内容 | 用例 |
|---|---|---|
| ICACHE-WAYLOOKUP-001 | 入队/出队保序、payload 保持 | `test_residency.py` |
| ICACHE-WAYLOOKUP-002 | 双端口同拍入队 | `test_residency.py` |
| ICACHE-WAYLOOKUP-003 | `write.ready = free >= FetchPorts` 的容量保留 | `test_residency.py` |
| ICACHE-WAYLOOKUP-004 | 全清 flush | `test_flush.py` |
| ICACHE-WAYLOOKUP-005 | stage-3 flush 的 drop/keep 条件 | `test_flush.py` |
| ICACHE-WAYLOOKUP-006 | 异常锁存阻塞写入，flush 释放 | `test_flush.py` |

### 从 RTL 实测得到的两条关键语义

这两点与直觉相反，已写进 agent 注释，避免后续误判为 RTL 缺陷：

1. **写端口容量保留**：`write.ready = 空闲条目 >= FetchPorts`，即使只写单端口，
   32 条队列也只接受 31 次写入，最后 1 条永远留给可能的双端口拍。
2. **stage-3 flush 判定是"不晚于"**：`!isAfter(s3, tailFtqIdx)`。重定向 FTQ 索引
   比队尾条目的索引**旧**时要丢弃队尾（队尾属于错误路径）；比它新时保留。
   并且该信号每保持一个时钟沿就丢一条，必须只给单沿脉冲。

## 6. 已知边界

- `ICacheWayLookup` 的 `update` 端口需要 meta 命中比较才能建模，
  当前 `update.valid` 固定为 0；`updateStall` 读阻塞路径尚未覆盖。
- SRAM 类 DUT（databank/metabank/metaarray/dataarray）内部保留为独立
  `SRAMTemplate` 模块，未做工艺映射，时序与真实 SRAM 不同。
- `ICacheMainPipe`、`ICachePrefetchPipe` 在 RTL 上游仍活跃（2026-10 仍有修复），
  接口可能变动，用例应晚于其他子块推进。
