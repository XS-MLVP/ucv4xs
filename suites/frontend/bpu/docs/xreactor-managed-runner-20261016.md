# 生产入口迁移到 xreactor managed runner

当前最新完整诊断已切到`production-feature-domains-20261016-v2`，功能点报告版本2
分开硬件与环境契约，见[事件定义与复验](verification-point-semantics.md)。本文后半的
迁移资格数字属于此前轮次；历史测量载荷已按最新保留策略回收，可用性以
`results/RETENTION.md`为准，不能把原manifest路径视为当前仍有原始输入。

## 入口与职责

`tests/run_all.py` → `tools.refresh_coverage` 默认选择 managed engine →
`python -m xreactor run`。不是在旧 collector 上叠加第二个 collector。

| 职责 | 当前归属 |
| --- | --- |
| pytest/xdist worker 启动、重启禁用、完整收集检查 | xreactor |
| covergroup 自动捕获、worker checkpoint、合并与 HTML | xreactor |
| picker DUT 发现、完整原生点表校验、批次与跨 worker 合并 | xreactor |
| manifest 提交与已消费输入回收 | xreactor |
| DUT 初始化、memory-direct、driver/monitor/model/checker | BPU 验证代码，语义不变 |
| 功能点 ID 与 pytest 判定关联 | BPU 项目插件 `common/pytest/managed.py` |
| 原生 DA/S-span、wrapper 区分及 Scala 功能归因 | BPU `common/coverage/rtl.py`，直接读取最终 DAT，不再合并 worker |
| 冻结源码、精确 JUnit 身份、正式报告保护 | 项目生产协调入口 |

框架分支仍是 `dev/coverage-v2`。合入上游 `8aadf44`，保留本地接纳修复
`b130a3c`；公开集成扩展固定为 `2461d0f`，见 `dependencies/versions.json`。
没有复制私有 collector、monkeypatch coverage、关闭异常或放宽合并校验。
picker/xcomm、ABI 3、coverage protocol 5 和已构建 DUT 均未更改。

## 不把纯测试算作 DUT 覆盖率

项目为 `tests/<dut>/testcase/` 场景启用功能测量，其余 schema、编码、driver、
monitor 和纯模型测试使用公开的
`pytest.mark.xreactor_functional_coverage(False)`。原生 DUT 发现不受该标记影响。
路径分类是本项目的测量范围，不是框架对 verification role 的限制。

序列化单元测试仍可显式导出到 `tmp_path` 来验证零计数、分母和错误证据；其
covergroup 不进入生产功能合并。真实 DUT 场景不再调用逐 case JSON 导出。
项目通过自己的导出策略 helper 控制这件事，没有替换框架的 `write_json()`。
不要把 synthetic 与真实测量共用 collection/session 级可变 covergroup。
测量场景内部仅用于断言的辅助组使用公开的 `instantiate(..., capture=False)`；
它们仍参与原有采样和 assertion，不成为另一份测量，也不放宽 schema 校验。

框架新增公开 `pytest_xreactor_coverage(config, functional, native,
pytest_exitstatus)`，controller 在提交前调用一次。项目只读取内存中的合并结果，
记录紧凑摘要、功能矩阵门禁与 DUT build 映射；不再序列化再加载整份数据库。
hook 抛异常会拒绝提交并保留可用输入，不会把比较失败变成成功。
公共 DUT factory 使用公开 `xreactor_register_dut` 回调，在创建时登记导出归属；
即使用例内提前 close/释放实例，也不会漏掉该 DUT。自动 fixture 发现仍保留，
重复发现同一实例不会重复计数。初始化、时钟和 Finish 所有权没有交给 collector。

## 输出与调试

```sh
python3 tests/run_all.py --workers 32
python3 tests/run_all.py --workers 8 --select tests/tage/testcase
python3 tests/run_all.py --workers 1 --select tests/bpu/testcase/test_main_service.py --keep-coverage-inputs
```

默认输出：

```text
results/<new-run>/
  source-epoch.json, owner.json, collection.log, pytest.log, pytest.xml
  exit.json, summary.json, test-results.json, feature-points.json
  rtl-line-coverage.json, rtl-lines/<dut>.info
  execution/
    manifest.json, coverage.html
    feature-points.json, functional-summary.json, rtl-coverage-manifest.json
    native/<build-id>/coverage.dat, coverage.info
```

每个 DUT build 只保留一份完整 DAT，不随 worker 数增长；toggle、零点和所有
计数仍完整保留。`execution/_workers` 只在运行中存在，提交成功后回收。不同
build 不允许伪装成一个 DUT 基线。原生 DA 与 `v_line` 仍分开统计。

需要时显式使用 `--keep-coverage-inputs` 保留 worker 输入，
`--export-coverage-json` 保留一份最终功能数据库；`--dump-trace` 才导出逐周期
轨迹，并同时保留 worker 输入。默认不生成这三类调试数据。

普通测试 FAIL 不等于 coverage 合并失败：完整失败回归也可以提交诊断覆盖率并
回收输入，pytest 非零状态、功能点 FAIL 和 HTML 标题均保留。崩溃、坏收据、
坏点表、计数和不正确、hook 拒绝或不完整收集则不提交并保留可用输入。
生产入口不自动覆盖五份正式报告，完整通过也不代表全部验证目标完成。

普通 `pytest` 及 `--engine=legacy` 暂保留兼容/历史复现路径；它们不是当前生产
引擎。旧证据读取器保留供历史报告复核，不参与 managed worker 合并。

## 资格状态

xreactor runner/coverage/protocol/transfer：379 PASS，3 个 subtest PASS。
最终框架/模型门禁14851 PASS、兼容71 PASS、独立Main093场景1 PASS，均与
完整生产18642项/64worker同一2117文件epoch。

[生产终态](../results/production-xreactor-managed-20261016-v2/exit.json)：
18614 PASS/25普通FAIL/3strict XFAIL，无ERROR/SKIP/XPASS。全部旧18620节点及
341功能点判定精确保持（322PASS/17FAIL/2XFAIL），新增22合同全PASS。
owner605.62秒，包含合并/HTML的pytest阶段576.24秒，aging415.92秒；不能与
旧流程不含后处理的pytest时间直接作加速比，也不宣称受控的merge性能倍率。

1277原生输入完整接纳，每DUT计数与旧轮一致，URAS为29；提前关闭实例通过
公共factory回调恢复，而不是忽略漏采。十DUT原生DA、v_line、分母、构建完全
保持；BPU33754/46541，v_line2392/8236。单独Main场景与旧流程132900个原生
点及所有计数完全相等，包括toggle与零点，不只是命中集合相同。

每run最终10份DAT共64028649字节（约61.1MiB），完整新run实测约167MiB；旧轮
worker输入约3.86GiB、319份DAT。没有逐case功能JSON或默认最终功能数据库，
`_workers`已回收；缩小来自去重/聚合，不删原生点。功能合并仅由框架负责，
项目公开hook直接读内存，不再追加旧的1182输入离线合并。

自动捕获恢复了旧流程异常前未导出的组：当前349组/318满。旧345组中343组
比例完全保持；UTAGE update routes50.1074→56.3574%、allocation routes
50.0732→50.6226%，来自已经比较通过、但后来FAIL导致末尾export未执行的样本。
这些采样位于完整useful状态/输出比较之后，不能解释为新功能或RTL修复。
新增可见的4个既有组分别为RAS87.5%、RAS-enable0%、TAGE captured迁移42.5%、
UTAGE shadow49.3056%，均未满；旧27个未满实例都保留，当前未满共31。
功能点通过率仍94.43%。纯模型/schema测量为零，原生fixture发现照常进行。

首轮完整迁移曾因4个ABTB辅助局部schema与全量同名而拒绝合并，且UTAGE默认
诊断文件缺父目录带来一个额外FAIL；没有降低校验或改成XFAIL。辅助组现在显式
`capture=False`，UTAGE轨迹仅`--dump-trace`时导出；两项ABTB及一项UTAGE真实
回归通过后重新完成全量，普通失败恢复为原25项。首轮失败记录保持原样。

RTL/DUT/SDK的528项hash、detached XiangShan状态及五份正式报告保持不变。
本轮是完整失败诊断，不是RTL通过或整个验证目标完成。
见[差分资格](../results/production-xreactor-managed-20261016-v2/migration-qualification.json)
与[全点计数等价](../results/xreactor-managed-qualified-20261016-v2/native-equivalence.json)。

已清理被替代 RAS-016 旧 worker 原始输入 4139842049 字节，保留其汇总证据；
另清理19个无活动引用的旧临时 probe/candidate/debug 目录，共7664文件、约257MiB。
旧原始输入与临时文件不可原地恢复。最新 MainBTB 旧基线完整输入、正式报告、
当前源码和正在执行的新 run 均未清理。
首轮失败的64个原生中间目录另回收2756934246字节，保留全部64份压缩功能
checkpoint及收据和schema失败日志；另清理6轮过时原型的34个最终DAT约242MiB，
保留其LCOV/HTML/日志，最终资格组不动。两类清理都有明确pruned记录，不能把
历史manifest的inputs-retained当成清理后仍可访问所有raw的承诺。
