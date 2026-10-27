# xreactor coverage-v2 迁移

依赖固定在 [versions.json](../dependencies/versions.json)。xreactor 使用
`dev/coverage-v2` 的 `2461d0fe75999fb8bf62ef61a92f38fe8231394d`，工作树位于
`dependencies/xreactor`；原 `/home/xyl/xreactor` 的 main 和未提交改动没有搬入或修改。
picker 使用 `4dd442c`，xcomm 使用目标分支 CI 固定的 `c39db665`。
配套版本为 xspcomm `0.3.0.dev3`、原生 ABI 3、coverage 协议 5。

2026-10-16 合入上游 managed runner，保留原 transaction 接纳修复；生产入口、
自动合并/回收及纯模型防污染见[迁移说明](xreactor-managed-runner-20261016.md)。
没有重建 DUT 或变更 SDK/ABI；下表中的旧项目并行 collector 已退出默认生产路径。

## 保留与替换

| 内容 | 迁移方式 |
| --- | --- |
| case、事务、编码、Agent、参考模型、Checker | 保留功能语义、异常和覆盖要求，不削减矩阵 |
| DUT 信号组织 | 读取标准 picker `signals.json`，使用 `Bundle.bind_tree`；不再注入 `dut.io` / `signal_tree` |
| 同步驱动所有权、并发互斥 | 使用原生 `SyncDriver`；项目只实现 `_drive_one` 的端口时序 |
| 异步单周期输入 | 使用原生 `AsyncSingleCycleDriver`，不另建任务引擎 |
| 周期快照接收 | 使用原生 `SamplingMonitor`，不再实现接收队列、溢出和关闭状态机 |
| 纯回调观察 | 使用正式 `@on(..., capture=...)` 订阅，不增加第二个队列 |
| Execution / backend | 按所有权关闭组件、Execution、backend、DUT；不修改调度器内部状态 |
| coverage | 使用框架正式定义、计数、合并、报告 API；已有 Core CoverGroupDef 并非废弃接口 |
| 通用并行、coverage 捕获/合并/回收 | 交给 xreactor managed runner，不叠加旧 collector |
| 功能点通过率与源行功能归因 | 保留薄项目插件，使用公开合并结果 hook；不接管框架 collector |
| reset-derived replay 与覆盖资格判断 | 保留独立模型验证；失败场景不能提交覆盖信用 |

不复制旧 xreactor 工作区补丁，也不向标准生成包补回层级对象。
TAGE 观察作用域换绑 Bundle 时按新数据节点重新编译采样器；旧快照仍不可变。

memory-direct 是唯一观测后端，不启用 VPI，不增加 internal DPI getter。
输入仍采用 `AsRiseWrite`，时钟保持立即写；测试不用知道 falling edge。
默认关闭逐周期 JSON 和运行时波形；编译 trace feature 仅用于重建信号映射。

## 安装与重建

先按 versions.json 获取三个仓库的精确提交。可以使用独立 clone 或工作树，
不要切换有未提交改动的现有仓库。完整源码应在 `dependencies/{xreactor,xcomm,picker}`。
picker 的 fmt、slang、yaml-cpp 依赖按其 `scripts/init.sh` 准备；本机复用了已有源码。

构建和系统级安装 Python 包：

```sh
SETUPTOOLS_SCM_PRETEND_VERSION_FOR_XSPCOMM=0.3.0.dev3 \
  BUILD_XSPCOMM_SWIG=python XSPCOMM_BUILD_WHEEL=1 CMAKE_BUILD_PARALLEL_LEVEL=8 \
  python3 -m pip wheel --no-deps ./dependencies/xcomm -w /tmp/bpu-coverage-v2-wheels
sudo python3 -m pip install --break-system-packages --no-deps /tmp/bpu-coverage-v2-wheels/xspcomm-0.3.0.dev3-*.whl
sudo python3 -m pip install --break-system-packages -r requirements.txt
```

picker 生成器还需要匹配的 C++ SDK，不能只更新 Python 包：

```sh
BUILD_XSPCOMM_SWIG=python cmake -S dependencies/xcomm -B dependencies/xcomm/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DSKBUILD_PROJECT_VERSION=0.3.0 -DSKBUILD_PROJECT_VERSION_FULL=0.3.0.dev3
cmake --build dependencies/xcomm/build -j 8
chmod -R a+rX dependencies/xcomm/build/python/xspcomm
sudo cmake --install dependencies/xcomm/build
NO_BUILD_XSPCOMM=1 cmake -S dependencies/picker -B dependencies/picker/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build dependencies/picker/build -j 8
sudo cmake --install dependencies/picker/build
```

重新生成并验证十个 DUT 后才安装；安装器保留旧 DUT 目录：

```sh
mkdir -p results/coverage-v2-build
python3 tools/rebuild_memory_direct.py --stage "$PWD/results/coverage-v2-build" \
  --dut abtb bpu ittage mbtb ras sc tage ubtb uras utage --jobs 16 --parallel 4
python3 tools/rebuild_memory_direct.py --stage "$PWD/results/coverage-v2-build" \
  --dut abtb bpu ittage mbtb ras sc tage ubtb uras utage --install
```

`tests/run_all.py` 不再注入旧 main 或 `/usr/local/share/picker/python` 到 PYTHONPATH。
pytest 启动时检查实际导入路径、包版本、ABI、协议和必要的引擎 API；
DUT 创建前再次检查生成包携带的 binding，旧 ABI 包明确报错而非尝试混用。

### 本机遗留 ABI 1 兼容性

当前 ABI 3 库、默认链接、Python 包和十个新 DUT 使用同一组固定依赖。
本次 SDK 升级发现，以下旧版本文件的内容已是 ABI 3，而文件名仍为 `0.1.0`：

- `/usr/local/lib/libxspcomm.so.0.1.0`
- `/usr/local/share/picker/lib/libxspcomm.so.0.1.0`
- `/usr/local/share/picker/python/xspcomm/libxspcomm.so.0.1.0`

旧 ABI 1 程序可能受影响；当前 ABI 3 验证不依赖这些旧版本入口。
用户选择暂不恢复，因此本轮不再修改旧 ABI 1 文件，也不把旧 ABI 兼容性标记为已修复。
旧 DUT 备份仍保留在本轮 `native-build/backup-dut/`，但恢复需单独授权。

## 验证入口

```sh
cd dependencies/xreactor
python3 -m pytest tests -q --require-xspcomm
cd ../..
python3 tests/run_all.py --workers=16 --select tests/framework
python3 tests/run_all.py --workers=64
```

`tests/framework/test_native_coverage_v2.py` 用真实 memory-direct MicroRAS 的 reset 引脚
验证混合值 point、共享时序程序、严格 native 采样，明确禁止 Python `sample()` 回退。
native coverage 的采样时钟使用 `dut.GetXClock()`；普通 driver 仍可使用已注册的 clock pin。

本轮记录位于 `results/coverage-v2-migration-20261012-v1/`。
框架自测、模块选跑和全量回归是不同验收层级；仅完整生产回归成功才能替换正式覆盖报告。

## 本轮验收结果

- xreactor 固定分支原生自测：**1,086 passed**。
- 生产入口 128 进程选跑：**14,419 passed、7 个既有 XFAIL、0 FAIL、0 SKIP**。
  pytest 执行约 22 分 18 秒，不含覆盖合并和报告生成。
- 独立 BPU 场景复测：604 passed、2 个既有 XFAIL；与上述选跑有重叠，不叠加计数。
- 大范围选跑后，仅补充版本化 `.so` 的冻结规则和四个契约测试，
  再用生产入口运行整个公共框架：**521 passed**，含十个真实 DUT 的 monitor 绑定检查。
- 349 个领域实现文件、220 个 pytest 场景文件保持原哈希。
  十个 DUT 的 RTL 哈希、信号声明和原始行覆盖分母均未改变。

大范围选跑结果见 [summary.json](../results/coverage-v2-migration-qualification-20261012-v1/summary.json)，
后续公共框架复测见 [summary.json](../results/coverage-v2-migration-final-framework-20261012-v1/summary.json)，
ABI 与安装哈希核对见 [runtime-and-native-validation.json](../results/coverage-v2-migration-20261012-v1/runtime-and-native-validation.json)。

本轮保留了原来的全部 case，但只运行集成 ABTB 的三个物理代表组合；
其余 **765 个组合未在新框架上重跑**，也没有用改分母或减少用例来宣称完成全量。
选跑收集到 204 个功能覆盖组，293 个功能点中 286 PASS、7 XFAIL；
这不是新的完整物理覆盖验收。集成 BPU 行命中为 32,631/46,541，低于旧完整报告，
是因为选跑范围较小，不能当作新的全量覆盖结果或迁移后全量退步结论。
正式发布报告保持不变，后续仍需独立完成全量回归／case 规模优化。
