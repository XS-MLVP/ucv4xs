# Wrapper 覆盖丢失闭环：实际 native 贡献范围、逐点归因与完整 fresh 重跑

**结果：此前 2125 个 Wrapper toggle 旧命中丢失已定位并经真实重跑解决。根因是
四目录命令漏跑了同一 Wrapper build 的 41 个原节点，不是已证明的初始化、
随机上下文或工具合并故障。新的完整贡献范围运行有 1066 节点，897 PASS /
169 FAIL；原 1059 节点及失败全文保持，四个 DUT 的三类旧命中均无丢失。**

当前同范围覆盖单调性门禁 **PASS，未豁免**；旧 1025 节点运行的 `FAILED_OPEN`
结果、原 dat 和报告不改。统一 regression15 的 38 build、2330 节点、2103
PASS/227 FAIL、分母/缺口全集保持。整体仍为 **`ACTIVE_NOT_ACCEPTED`**。

## 1. 请求→检查→证据

| 要求/门禁 | 实际检查 | 产物 |
|---|---|---|
| 不从旧摘要推定根因 | 首先核对 manifest 的 native `input_files`，再按实际 primary journal 还原同 build 贡献节点；不是按测试目录名猜范围 | `tools/audit_native_contributor_scope_v1.py::contributors` 与统一 `native-contributor-scope-diagnosis-v1.json` |
| 新诊断前有合同 | 先定义只读观察时点、不扰动要求、差集归因和完整重跑要求；发现范围遗漏后在运行前补充明确贡献清单 | `docs/contracts/native-case-coverage-diagnosis.md` |
| 保持真实 DUT/检查 | opt-in 插件只在 fixture Finish 后、原 X Reactor `end_case` 前读取原导出 dat；不调用 DUT 方法、不改库/RTL/刺激/参考模型或计数 | `lsqverify/native_case_probe.py`；原 Picker native build 不变 |
| 观测器控制 | 原 `[aligned-0]` 节点开/关插件，source aggregate、三份 journal、全部 native 点计数及 dat SHA 相等 | `results/lsq-native-case-control-{off,on}-01/`，`native-case-probe-control-v1.json` |
| 定位到原节点和源点 | 原 25 节点（22 PASS/3 FAIL）定位运行未命中差集；遗漏 41 个实际贡献节点重跑覆盖全部 2125 差集且逐点计数相等 | `lsq-native-case-localize-01`、`lsq-native-case-omitted-contributors-01` 的逐 case compact 摘要与独立 audit |
| 保留真实失败 | 诊断原 12 FAIL 与 full 原 169 FAIL 的归一化全文不变；只归一化 Python 对象地址，不抹 assertion 值/载荷/栈行号 | 两运行 JUnit、manifest、failure digest 与统一 failure-preservation audit |
| 不 OR 伪装一次重跑 | 新命令实际执行全部 1066 节点；检查四 build 全部旧贡献者、source launch/end、point universe 和三类差集；原 2125 全部恢复 | `results/store-strict-contributor-regression-02/` 与 `store-strict-contributor-regression-evidence-v1.json` |
| 历史门禁不变绿 | 历史失败保留；当前门禁通过只引用新的同范围 fresh 证据，矩阵同时存历史失败和解决依据 | `post-regression-required-gates-v1.json` 的 `resolved_runtime_gates`、最终矩阵 |
| 不改变功能范围 | 原 PSQ/SQ/Wrapper strict 合同、四代 Store/Load 生命周期 witness 完整保持，不以补跑历史贡献者冒充新增功能 | 三组 strict after、1066 节点运行的三份 witness 与定向结果逐字相等 |

固定源仍是开源 `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`，
不使用 XiangShan-internal，不修改目标 RTL/Chisel、独立参考模型或工具安装。

## 2. 为什么 689 节点流相同，却有旧命中丢失

原 Wrapper native `input_files=730`，不是主目录节点数 689。真实贡献为：

| 原节点位置 | 节点 | PASS / FAIL | 此前四目录是否执行 |
|---|---:|---:|---|
| `tests/lsq_wrapper` | 689 | 596 / 93 | 是 |
| `tests/local_reset` | 15 | 15 / 0 | **否** |
| `tests/normal_mixed/test_original_seeds.py` | 8 | 2 / 6 | **否** |
| `tests/sq_endpoint/test_ldu_joint_phases.py` | 12 | 6 / 6 | **否** |
| `tests/sq_endpoint/test_wrapper_raw_boundary.py` | 6 | 6 / 0 | **否** |
| 合计 | **730** | **625 / 105** | 漏 41 个 |

四目录运行的 Wrapper 导出只有 691：原主目录 689＋新增 checkpoint、strict
各 1。原 2067 份 journal 相同只涉及那 689 个节点，不能推出完整 native 贡献
范围相同。缺失的 41 个原节点有独立语义合同/fixture，不能因为不在主目录
就从 Wrapper 功能或覆盖范围中删掉。

## 3. 实际差集归因（不是初始化分类豁免）

命令：

```sh
python3 -B tools/run_summary.py --name lsq-native-case-omitted-contributors-01 --workers 4 -- -p lsqverify.native_case_probe tests/local_reset tests/normal_mixed tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py
```

实际执行 **43 节点，31 PASS/12 FAIL**；其中 41 个 Wrapper native 贡献节点
为 **29 PASS/12 FAIL**，另 2 个是 `normal_mixed/test_source_ledger.py` 的旧
Python-only ledger 检查，不能算作 native DUT 覆盖贡献。

只读插件控制开关的 dat SHA 均为：
`7e4f339d30dcacf69c8e663cca5be73ca6175191738ba4ab96e64f11f6844e6a`。
对诊断运行的每份导出做独立核验：原节点结果/失败全文和公开/check/actor
journal 摘要全等；逐 case 目标位图 OR 与最终 dat 相等，三类计数和守恒。
这里的 OR 仅用于验证导出/合并守恒，**没有用 OR 生成最终 fresh 运行结果**。

| 原模块 | 实际贡献节点 | 命中的 2125 目标点（有交集） | 目标计数和 |
|---|---:|---:|---:|
| `local_reset/test_retained_old_responses.py` | 12 | 122 | 2056 |
| `local_reset/test_retained_population.py` | 3 | 578 | 2778 |
| `normal_mixed/test_original_seeds.py` | 8 | 439 | 2713 |
| `sq_endpoint/test_ldu_joint_phases.py` | 12 | 1209 | 8044 |
| `sq_endpoint/test_wrapper_raw_boundary.py` | 6 | 0 | 0 |

点集合有交集，不能把表中 hit 数相加当独立点总数。真实并集为 **2125/2125**，
且这 2125 个点的每个计数与 regression15 原计数完全相同，前后总计数均为
**15591**。差集身份 SHA：
`02745152ec8d03a8b3fc0fe1bd36d8db6a3de8adc33705aae55dda486b2bf03d`。
这形成了具体节点→实际导出→源点的归因，不把点改分类为初始化/不可达，
也不把补跑历史节点算作新功能覆盖增益。

## 4. 同范围 fresh 运行：1066 节点

```sh
python3 -B tools/run_summary.py --name store-strict-contributor-regression-02 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py
```

实际 **2546.09 秒**；1066 节点为 **897 PASS/169 FAIL，0 ERROR/0 SKIP**。
四 build 的原生输入从 184/66/79/730 变为 **185/68/81/732**，总计 1066。
primary journal 数与 manifest 原生导出数逐 build 相等；每个旧贡献节点保留，
完整 Wrapper 的原 **2190 份**公开/check/actor journal 记录数、字节数和 SHA 相等。

原 1059 个节点全部结果相同，169 FAIL 的前后归一化全文 SHA 都为：
`31bff24c501b3d000c5c9ae3eb572f8210133ff0218d0a89803f92451eec04cf`。
新增 7 个 PASS 是此前的 payload×3、strict×3、Wrapper checkpoint×1，
不是本轮新实现的 7 个功能，也不抵消原 FAIL。

所有下表分母、完整点全集、build 及固定源 SHA 均保持，三类旧命中无丢失。

| DUT | toggle 原→新 / 独立分母 | 新中 / 丢失 | branch 原→新 / 独立分母 | 原始 line 点 |
|---|---:|---:|---:|---:|
| ForwardModule | 28717→36329 / 40034 | 7612 / 0 | 54→54 / 54 | 2/2 |
| PhysicalStoreQueue | 70532→81886 / 86318 | 11354 / 0 | 1826→1830 / 1834 | 213/213 |
| StoreQueue | 78334→92398 / 102374 | 14064 / 0 | 2183→2191 / 2198 | 223/223 |
| LsqWrapper | 258044→275384 / 322010 | 17340 / **0** | 18592→18592 / 18670 | 3654/3654 |

LCOV 原始源码闭包行分别保持 **253/253、5817/5817、8968/8968、59595/59602**，
不与 raw line 点混写。恢复旧 2125 点不是额外新中点，不能再加到 17340 中。
当前同范围门禁 `PASS/required=true/waived=false`；原四目录 `FAILED_OPEN` 结果
仍存原位置，不更新其 dat、结果或报告字节。

## 5. 专项/全链复核和历史保留

```sh
python3 -B tools/audit_native_case_probe_v1.py --control lsq-native-case-localize-01 lsq-native-case-omitted-contributors-01
python3 -B tools/audit_native_contributor_scope_v1.py
python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15

# 默认继续返回 exit 1：这是原范围不等的历史门禁，不变成绿色
python3 -B tools/audit_store_strict_lifetimes_v1.py
```

全链先以 `--verify-historical-artifacts-only` 核验旧失败产物（任何 assertion
仍触发 `check=True` 失败），再强制重建新的完整贡献范围证据后，才判当前门禁。
不能把普通 Python 断言异常误认为已知历史门禁而继续。

全链 `post-regression-contributor-scope-01.log` 已 **exit 0**。这里表示证据检查
和当前单调性门禁完成，不是 169 FAIL 变为 PASS 或整个 LSQ 功能验收通过。
统一最终矩阵保持 38 DUT、18 条定向补例，当前门禁与历史失败解决链接均在；
原派生矩阵/摘要/失败报告按原字节 SHA 归档到各自 `audit-history/`。

再次全链运行 `post-regression-contributor-scope-idempotence-01.log` 同样 exit 0：
9 份关键报告 SHA 不变，44 份受检历史 artifact/manifest/失败报告字节 SHA 不变，
未新增重复归档。8 份相关 Python 源通过语法解析；19 份补例/观测辅助源的
无 skip/xfail 检查保持通过。历史失败门禁仍为 `FAILED_OPEN`，当前新运行门禁
仍为 `PASS`；报告刷新没有把二者混成一个结果。

## 6. 剩余真实范围

- 新完整结果仍有 PSQ **4432**、SQ **9976**、Wrapper **46626** 个非 wrapper
  toggle 缺口；SQ 仍有 2 个非初始化恢复状态 branch 缺口，Wrapper 原 78 个
  branch 缺口未因本次 scope 修正新增命中。不能把门禁修复当作功能闭环完成。
- 原统一 regression15 的 235610 toggle、563 branch 缺口库存仍保持原数，
  各定向交集只用于对照，不回填原分子、缺口分类或历史结果。
- 下一优先项仍是合法 SQ 窗口/低位地址、真实恢复和 Wrapper 业务/总线混合
  情形；RAR、Replay strict、Uncache SID、Forward 与父级真实 FAIL 继续开放。
- 没有生成逐拍 JSON、波形或完整源码副本；仅增加 compact per-case native
  摘要、目标位图和校验索引。未执行/声称 Git commit 或 push。
