# 默认诊断和过量存储纠正

## 原因不是框架强制

自写LSQ fixture原先在`tests/*/conftest.py`无条件`.open("x")`逐拍JSON，`native.py`
也无条件设置FST文件名；每轮又重复保存所有大JSON。这是本工程的实现/保留策略错误，
不是Picker或xreactor必须如此，也不意味着完整验证必须长期保留每轮原件。

现默认`tools/run.py`和直接pytest fixture均**不开逐拍JSON、不写wave**，只保存小摘要。
原生DUT、参考/输出比较、原UID与业务断言、行覆盖/语义覆盖继续执行，不因减少日志而
屏蔽FAIL。全流SHA只检查重跑/诊断影响，不替代未保留轨迹的独立离线语义审计。

## 已实际验证

`lsq-diagnostics-default-01`真实79节点，**78 PASS / 1个原SID FAIL**；499启动/结束源
一致。147份旧共享参考文件内容未改（只改native诊断基础设施并新增小摘要实现）。
独立`diagnostics-default-audit-v1.json`核验全部4186拍完整串行化流SHA与旧原生原件
相等，避免459700054字节逐拍JSON；主journal摘要仅50607字节。实际0 JSONL、0wave。

显式trace/wave仍是调试开关，绝不默认全套启用；trace按journal限大小。上限做了
隔离的stream单元检查，但本轮显式native trace试跑被权限门禁拒绝，**未执行，也未
创建该run目录**，未绕过或换命令重试。不能将其记作native开关覆盖证据。

## 实际清理，不再保全每个旧路径

`results/storage-audit-v3.json`最终核验：

- 历史`results/`从约262GiB降为791941120字节，约**755MiB**；磁盘可用约**375GiB**。
- 175个旧已结束运行删除52680份冗余case/wave/中间coverage文件，未逐份归档。
- 旧`lq-joint-impact-01`manifest仍是running但已无活动LSQ runner；02已真实结束。
  仅清除该孤立旧目录4954635253字节中间物，不改写其manifest为committed/PASS。
- 主基线及必要大行报告共3857个唯一压缩对象、116342277字节；对象SHA全部再核验，
  创建时逐个解压核对原SHA/大小。90个冗长行报告从约1.20GiB压缩为约15.8MiB。
- 冻结源的重复物理副本共享存储，所有内容/SHA不变；未删除RTL、用例或FAIL报告。
- 最终未压缩逐拍JSONL和wave均为0。清理早期仅空目录symlink处理/报告路径的错误
  已记录并纠正；原子payload操作有效，不以这些清理报错虚构功能缺陷。

旧报告是当时实际审计，不承诺所有旧原件仍驻留。目录的`retired-intermediates-v1.json`
表示完整中间轨迹已删除；`storage-index-v1.json`或`reports-storage-index-v1.json`表示
选定证据可通过`lsq_evidence_archive_v1.py audit`临时展开复核。不能把被清理原件继续
冒称随手可读或伪造一份新轨迹来替代。

统一回归11已真实1821/215，全部215普通FAIL保留。S4源准入/精确ROB头trap、完整随机、
其他128/local-only恢复和最终全范围审计仍未完成；日志节制不缩小原验证目标。
