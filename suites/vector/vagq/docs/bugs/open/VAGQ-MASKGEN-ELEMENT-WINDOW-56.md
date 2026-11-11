# VAGQ-MASKGEN-ELEMENT-WINDOW-56：MaskGen 元素窗口策略仍保留 56 个 native 反例

状态：**当前记录的真实 FAIL，未登记 XFAIL，根因未确认**。`results/ucv-vagq-20261031`
记录 1 FAIL，对应用例
[tests/maskgen/testcase/test_element_windows.py](../../../tests/maskgen/testcase/test_element_windows.py)::test_segment_element_windows_and_policies；
失败在迁移前已存在，本轮没有修复或用豁免隐藏。

## 问题

该用例按字段无关的 destination window 和 mask policy 扫描 MaskGen 的公开输出，报告
**56/9024** 个 native policy mismatch。当前失败信息指向 `elemActiveMask` 与独立窗口
模型不一致；完整字段（merge/agnostic/window）与全部输出之间的差异分类见用例生成的
`element-window-summary.json`。

## 独立预期

RVV 的 destination element window 应由指令的 EEW/EMUL、字段、vl/vstart、v0 掩码和
vma/vta 决定，与实现内部的字段主序寄存器索引无关。对每个公开请求，独立窗口模型应给出：

- 正确的 destination window；
- merge write mask；
- agnostic mask（body 中 masked 字节和 tail 的并集）；
- 与字段布局无关的元素归属。

DUT 的 `elemActiveMask`、`mergeWriteMask`、`elemAgnosticMask` 必须与独立模型一致。
达到某个覆盖 bin 不是通过条件。

## 复现与对照

```sh
./scripts/ucv run vagq --workers 1 -- tests/maskgen/testcase/test_element_windows.py::test_segment_element_windows_and_policies
```

- 失败用例保留真实 FAIL，不使用 expected-count waiver。
- 同文件的 scoped repair 用例只检查已修正的 merge/window 字段，不替代全输出验收。
- 需要把 56 个反例按请求参数、输出字段和是否属于不可达/保留布局分类，确认是 RTL
  policy 缺陷还是独立模型/合法域问题；分类前不把根因写成已确认 RTL 缺陷。

## 范围与证据

- 该失败只覆盖 MaskGen 公开合同与指定扫描矩阵，不自动外推到 VAGQ 顶层或整核。
- 当前 internal 基线、native 构建身份和运行选择以运行收据为准；本次文档整理没有重跑。
  同一 1 FAIL 也记录在根 [docs/status.md](../../../../../../docs/status.md)。
- 相关合同：[Design spec](../../spec/design/README.md) 与
  [Verification spec](../../spec/verification/README.md)。
- 用例：[tests/maskgen/testcase/test_element_windows.py](../../../tests/maskgen/testcase/test_element_windows.py)。

```ucv-bug
{
  "id": "VAGQ-MASKGEN-ELEMENT-WINDOW-56",
  "title": "MaskGen 元素窗口策略保留 56/9024 个 native policy mismatch",
  "kind": "investigation",
  "versions": [
    {
      "baseline": "internal-d4566d58a",
      "status": "open",
      "evidence": [
        "suites/vector/vagq/tests/maskgen/testcase/test_element_windows.py",
        "docs/status.md"
      ],
      "note": "results/ucv-vagq-20261031 记录 1 FAIL；迁移前已存在，未登记 XFAIL，根因待确认"
    }
  ]
}
```
