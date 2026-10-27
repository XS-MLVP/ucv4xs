# VSQ 合法深后缀取消：`cancelCount[3]` 高位与同槽复用

本轮在 [VSQ release→walk 合同](../contracts/vsq-release-walk.md) 上补充一个
独立的合法情况：连续10个真实 Store 通过公开 dispatch 后，以 redirect 保留
前两个、取消后8个uop UID，核对恢复尾为SQ2；恢复窗口结束后再派发1个新uop
UID（包含3个physical flow），复用第一个取消虚拟槽及3个物理flow位置并正常
退休。没有写入内部 `cancelCount`、state 或 entry array，不声称8个虚拟槽全复用。

## Directed before/after

`vsq-deep-suffix-baseline-02` 为3个既有 VSQ节点，`vsq-deep-suffix-after-02`
增加1个 `test_deep_suffix.py` 节点；四个节点均 PASS，同一 native build、同一点
全集，旧命中无丢失。

| 指标 | before→after / 分母 | 新增命中 |
|---|---:|---:|
| raw line | 7→7 / 8 | 0 |
| raw toggle | 1999→2264 / 10060 | 265 |
| raw branch | 220→227 / 364 | 7 |

定向目标为 `dut/virtual_store_queue/VirtualStoreQueueDut.v:4597`：

| point | before | after |
|---|---:|---:|
| `cancelCount[3]:0->1` | 0 | 1 |
| `cancelCount[3]:1->0` | 0 | 1 |

功能 bin `VSQ-REDIRECT.deep_suffix` reached/checked 均为0→1。测试实际断言
8个旧 UID 被取消且未完成、公开 recovery end 为2、新uop UID大于所有旧UID并
正常退休；不是只翻转 payload 的 smoke。

## 六-build fresh 完整贡献范围

完整命令与上一轮六-build范围相同，实际结果为：**1172 节点，1001 PASS /
171 FAIL，0 ERROR/SKIP**。基线为上一轮 `vsq-release-contributor-regression-01`
的1171节点，新增1个深后缀节点且通过；原171失败逐项保持。六个 native build
的旧命中无丢失，只有 VSQ build 有增益：

| DUT | toggle before→after / 分母 | 新增命中 |
|---|---:|---:|
| ForwardModule | 37654→37654 / 40034 | 0 |
| PhysicalStoreQueue | 83018→83018 / 86318 | 0 |
| StoreQueue | 95219→95219 / 102374 | 0 |
| LsqWrapper | 277863→277863 / 322010 | 0 |
| UnalignQueue | 836→836 / 908 | 0 |
| VirtualStoreQueue | 8665→8671 / 10060 | 6 |

VSQ 的 `cancelCount[3]` 两个方向在完整 build 中均为1；line/branch没有新增
命中，三类点全集保持。VSQ native contributor 从46→47，其余层贡献范围和
Wrapper公开流不变。完整证据为：
`results/vsq-deep-suffix-contributor-regression-01/vsq-deep-suffix-contributor-evidence-v1.json`。

## 失败和边界

- 上一轮已知两个 VSQ failure 的源行迁移已在上一轮范围证据中限定归一化；本轮
  相对于上一轮 raw failure 内容无变化，失败数仍171。
- 这只关闭 `cancelCount[3]` 的一个合法高位情形，不关闭 `15850 else` release
  等待分支；`15853 else` 仍仅有 post-reset state3静态边界证明，不是动态命中。
- 统一 regression15 仍保持2330节点/227 FAIL和原始分母；结果不回填统一 dat。
  其他恢复、异常、总线、跨页Load和剩余可达toggle/branch继续开放。

机器证据：
`results/vsq-deep-suffix-after-02/vsq-deep-suffix-evidence-v1.json`、
`results/vsq-deep-suffix-after-02/directed-gap-closure-virtual_store_queue-v1.json`。
