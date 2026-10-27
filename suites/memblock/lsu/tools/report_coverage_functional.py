#!/usr/bin/env python3
"""Publish measured coverage and binary evidence decisions, never invent absence."""
from __future__ import annotations

from collections import Counter, defaultdict
import ast
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"results/failure-recheck-final-03"
OUT=ROOT/"review/failure_recheck_20261026/coverage-functional"
ORDER=["store_arbiter","store_trigger","store_delay","store_s0","store_s1","store_s2","store_s3","store_s4","new_store_unit","std_exe_unit","load_arbiter","load_trigger","load_datapath","load_s0","load_s1","load_s2","load_s3","load_s4","new_load_unit"]
PARENT_CATEGORIES={
    "new_store_unit":{
        "发射/优先级/顺序":["back_to_back_stores_stay_ordered","stin_issued_and_sq_address_written","stin_ready_follows_tail_priority"],
        "翻译/反馈/重放":["feedback_one_cycle_later","illegal_issue_forces_replay","tlb_miss_sets_tlb_miss_and_replay","tlb_request_same_cycle"],
        "未对齐/跨页/尾段":["cross_page_tail_requests_unalign_queue","unalign_head_injects_tail_through_s0","unalign_tail_reaches_sq_address"],
        "异常/触发器/设备访问":["exception_info_sideband","mmio_needs_exception_to_write_back","trigger_breakpoint_reaches_exception_info"],
        "写回/预取/向量":["no_writeback_for_prefetch","normal_store_is_clean","vector_has_no_rob_writeback","writeback_payload","writeback_three_cycles_later"],
        "取消/依赖/空闲":["idle_pipeline_is_quiet","lfst_update_same_cycle","nuke_query_same_cycle_as_sq_address","redirect_drops_beat_at_every_stage"]},
    "new_load_unit":{
        "数据/合并/写回":["aligned_dcache_data","cross_16b_head_tail_loopback","scalar_load_end_to_end","tail_data_merge","vector_load_writes_vector_rf","wakeup_and_rf_write"],
        "背压/仲裁/重放":["dcache_backpressure","fast_replay_reenters_pipeline","replay_lane_priority","replay_younger_dropped","tlb_miss_replay"],
        "取消/异常/触发器":["exception_info_record","no_write_on_redirect","redirect_kills_pipeline","tlb_fault_exception","trigger_breakpoint_propagates"],
        "依赖查询/回滚":["lq_write_cause_encoding","nuke_query_fields","rar_violation_rolls_back"],
        "预取/训练/性能":["perf_counter_delay","prefetch_hint","prefetch_train_pulse","sw_prefetch_path"],
        "非缓存/空闲":["idle_holds_outputs","uncache_bypass_read"]}}
CATEGORY_NAMES={"beat_kind":"仲裁拍型","scalar_ready":"标量反压","payload_group":"载荷字段组","shape":"载荷位型","isolation_case":"源隔离",
    "action":"触发动作","cbo":"缓存块操作","chain":"触发链","gate":"触发门控","multi":"多槽触发","priority":"优先级","scalar":"标量","vector":"向量","prf":"预取抑制",
    "boundary":"接口边界","delay":"时序延迟","former":"ROB半项顺序","kill":"取消/过滤","level":"重定向级别","redirect":"重定向","wrap":"环形绕回",
    "addrready":"地址就绪","align":"对齐","arb":"仲裁","cross4k":"跨页","illegal":"非法发射","pipe":"流水寄存/传递","tlb":"地址翻译","unalignhead":"未对齐头段",
    "exc":"异常","feedback":"反馈","lfst":"LFST依赖更新","nuke":"依赖冲突查询","queue":"队列交接","sqaddr":"SQ地址","tail":"尾段/头尾合并","trigger":"触发器",
    "head":"头段","memtype":"内存属性","sqre":"SQ重执行","mix":"混合情形","pipeout":"流水输出","stout":"Store写回","pass":"直通保真","rob":"ROB身份","sq":"SQ窗口/数据","valid":"有效位/分流",
    "entrance":"入口编码","field":"字段保真","isolation":"源隔离","ready":"就绪/背压","extend":"符号/零/浮点扩展","merge":"数据源合并优先级","meta":"元数据寄存","rotate":"字节偏移",
    "crossbank":"跨bank","dcache":"DCache请求/取消","fwd":"前递","is128":"128位请求","lane":"入口合成","order":"入口年龄顺序","perf":"性能事件等价检查","reg":"寄存器保持","wakeup":"唤醒",
    "datapath":"数据通路元数据","exception":"异常","forward":"前递","prefetch":"预取","replay":"重放","cause":"重放原因","fastreplay":"快速重放","matchinvalid":"前递匹配无效","nukequery":"依赖查询","prefetchtrain":"预取训练","rrbank":"RR bank冲突","uncache":"非缓存访问",
    "cancel":"取消/合并取消","concat":"头尾载荷拼接","excinfo":"异常地址信息","lq":"LQ/原因编码","rfw":"寄存器文件写","rollback":"顺序违例回滚","wb":"写回","cross:group_x_shape":"字段组×位型交叉"}


def semantic_category(owner,bin_name,point):
    if owner in PARENT_CATEGORIES:
        suffix=bin_name.split(".",1)[1]
        matches=[name for name,items in PARENT_CATEGORIES[owner].items() if suffix in items]
        if len(matches)!=1:
            raise ValueError(f"parent semantic category missing/ambiguous: {owner} {bin_name}")
        return matches[0]
    return bin_name.split(".")[0] if point=="case" else point


def read(p):
    return json.loads(p.read_text())


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def yn(value):
    return "是" if value else "否"


def cell(value):
    return str(value).replace("|","/").replace(chr(10)," ")


def write_csv(path,rows):
    if not rows:
        return
    with path.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def normal_bins(point):
    return [b for b in point["bins"] if b["kind"]=="normal"]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    functional=read(RUN/"functional-coverage.json")
    coverage=read(RUN/"coverage-audit.json")
    final=read(ROOT/"review/failure_recheck_20261026/final-audit.json")
    junit=list(ET.parse(RUN/"junit.xml").getroot().iter("testcase"))
    literals=defaultdict(list)
    for path in sorted((ROOT/"tests").rglob("test_*.py")):
        tree=ast.parse(path.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef):
                for item in ast.walk(n):
                    if isinstance(item,ast.Constant) and isinstance(item.value,str):
                        literals[item.value].append(f"{path.relative_to(ROOT)}:{item.lineno}::{n.name}")
    bins=[];groups=[];categories=defaultdict(lambda:dict(bins=0,hit=0,hit_events=0))
    owners={key:dict(groups=0,coverpoints=0,point_bins=0,point_hit=0,cross_bins=0,cross_hit=0,group_samples=0) for key in ORDER}
    for g in functional["groups"]:
        owner=g["instance"].split(".")[0]; info=owners[owner]
        info["groups"]+=1;info["group_samples"]+=g["samples"]
        counts={p["name"]:p for p in g["points"]}
        schemas={p["name"]:p for p in g["schema"]["points"]}
        group=dict(dut=owner,instance=g["instance"],description=g["schema"].get("description",""),samples=g["samples"],
            coverpoints=len(schemas),point_bins=0,point_hit=0,cross_bins=0,cross_hit=0,coverage=g["coverage"],sampling_backend=g["sampling_backend"])
        for name,s in schemas.items():
            info["coverpoints"]+=1
            for b in normal_bins(s):
                count=counts[name]["counts"].get(b["name"],0);goal=b.get("at_least",1);hit=count>=goal
                category=semantic_category(owner,b["name"],name)
                row=dict(dut=owner,group=g["instance"],kind="coverpoint_bin",point=name,category=category,bin=b["name"],
                    hits=count,goal=goal,sampled_goal_met=hit,independent_reached_checked_certified=False,
                    source_literal_refs=";".join(sorted(set(literals.get(b["name"],[])))))
                bins.append(row);info["point_bins"]+=1;info["point_hit"]+=hit;group["point_bins"]+=1;group["point_hit"]+=hit
                c=categories[(owner,category)];c["bins"]+=1;c["hit"]+=hit;c["hit_events"]+=count
        for schema,runtime in zip(g["schema"]["crosses"],g["crosses"]):
            if schema["ignore"] or schema["illegal"] or schema["include"] is not None:
                raise ValueError("This report must not silently approximate a constrained cross")
            expected=list(itertools.product(*[[b["name"] for b in normal_bins(schemas[n])] for n in schema["points"]]))
            raw={tuple(json.loads(k)):v for k,v in runtime["counts"].items()}
            for key in expected:
                count=raw.get(key,0);goal=schema.get("at_least",1);hit=count>=goal
                bins.append(dict(dut=owner,group=g["instance"],kind="cross_bin",point=schema["name"],category="cross:"+schema["name"],
                    bin=json.dumps(key,ensure_ascii=False,separators=(",",":")),hits=count,goal=goal,sampled_goal_met=hit,
                    independent_reached_checked_certified=False,source_literal_refs="generated Cartesian product from recorded schema"))
                info["cross_bins"]+=1;info["cross_hit"]+=hit;group["cross_bins"]+=1;group["cross_hit"]+=hit
                c=categories[(owner,"cross:"+schema["name"])];c["bins"]+=1;c["hit"]+=hit;c["hit_events"]+=count
        groups.append(group)
    per_dut=[]
    for key in ORDER:
        b=next(x for x in coverage["builds"] if x["key"]==key)
        row=dict(dut=key,**owners[key])
        for label,hit,total in [("line",b["lcov_lines_dut_only"]["covered_lines"],b["lcov_lines_dut_only"]["unique_lines"]),
                               ("branch",b["branches"]["covered"],b["branches"]["total"]),
                               ("toggle",b["toggles_dut_only"]["covered"],b["toggles_dut_only"]["total"])]:
            row[label+"_hit"]=hit;row[label+"_total"]=total;row[label+"_percent"]=round(hit/total*100,2) if total else None
        row["categories"]=[dict(category=k[1],description=CATEGORY_NAMES.get(k[1],k[1]),**v) for k,v in categories.items() if k[0]==key]
        per_dut.append(row)
    defects=[
        ("LSU-HWPF-MISS-001","硬件预取miss性能事件恒0",True,False,False,"01-LSU-HWPF-MISS-001.md；三种子miss反例普通FAIL"),
        ("VER-ASSERT-001","三处恒真断言",False,True,True,"inventory.json原始断言；当前tests无恒真断言"),
        ("VER-TAIL-001","S1尾段身份未统一检查",False,True,True,"旧检查器readback故障漏检、新检查器拒绝；最终独立复核通过"),
        ("VER-INPUT-001","错误输入键被静默忽略",False,True,True,"新增schema及错误键负对照；真实data字段保留"),
        ("VER-DATAPATH-001","头尾数据合并激励和独立检查不足",False,True,True,"相邻head/tail与真实公开数据的字节级检查通过"),
        ("VER-REACH-001","22个可达toggle误归为不可达",False,True,True,"合法父块用例命中22点，39664提升到39686，分母40024不变"),
        ("VER-NATIVE-001","factory创建DUT未自动登记覆盖",False,True,True,"spec-01 native_inputs=0；spec-02修正后=2，原生数据库1份"),
        ("VER-LOG-001","旧运行未保存逐节点日志与源码版本",False,True,False,"后续采集已修正；历史日志未恢复，因此整体证据修复闭环=否"),
        ("VER-SCHEMA-001","本轮新增schema曾拒绝真实bypass数据键",False,True,True,"strict-parent-01明确ValueError；schema补齐后相关节点通过"),
        ("VER-SENS-001","本轮故障对照脚本的测试名和挂接点错误",False,True,True,"sensitivity-01失败记录；sensitivity-02与最终38项通过"),
        ("VER-SWPREF-001","新增软件指令预取训练有效位预期错误",False,True,True,"final-02错误预期；noQuery语义纠正后final-03通过"),
        ("VER-FCOV-001","把手动bin100%当成独立reached/checked闭环",False,True,False,"多数observe无自动判断；报告已纠正，但逐bin独立证据重构未完成"),
    ]
    decisions=[dict(id=i,description=d,confirmed_rtl_bug=rtl,confirmed_verification_or_report_bug=ver,
                    remediation_completed=fixed,evidence=e) for i,d,rtl,ver,fixed,e in defects]
    history=[dict(run=x["run"],fail_observations=x.get("tests",{}).get("FAIL",0),
                  enough_evidence_for_rtl_vs_test_verdict=x["exit"]==2,
                  confirmed_rtl_bug=False,rtl_bug_ruled_out=x["exit"]==2,
                  historical_node_cause_proven=x["exit"]==2,
                  bug_report_disposition="不属于DUT执行失败" if x["exit"]==2 else "不计为确认Bug：原始证据不满足认定门槛",
                  evidence="collection failed before native DUT execution" if x["exit"]==2 else
                  "only failure count preserved; no original node traceback or failing-source revision; not admitted as confirmed RTL bug and not proof of no RTL bug")
             for x in final["historical_failures"]]
    totals=dict(duts=len(per_dut),groups=len(groups),semantic_display_subgroups=sum(len(x["categories"]) for x in per_dut),coverpoints=sum(x["coverpoints"] for x in per_dut),
        point_bins=sum(x["point_bins"] for x in per_dut),point_hit=sum(x["point_hit"] for x in per_dut),
        cross_bins=sum(x["cross_bins"] for x in per_dut),cross_hit=sum(x["cross_hit"] for x in per_dut),
        group_samples=sum(x["group_samples"] for x in per_dut),
        independent_reached_checked_certified_bins=0,
        spec_test_nodes=2,spec_test_pass=1,spec_test_fail=1)
    inputs={str(p.relative_to(ROOT)):digest(p) for p in [RUN/"functional-coverage.json",RUN/"coverage-audit.json",RUN/"junit.xml",ROOT/"review/failure_recheck_20261026/final-audit.json"]}
    spec_cases=[]
    for tc in junit:
        if 'test_spec_prefetch_miss' in tc.get('classname',''):
            miss=int(tc.get('name').split('[')[1].split(']')[0]);failed=tc.find('failure') is not None
            spec_cases.append(dict(node=tc.get('classname')+'::'+tc.get('name'),miss=miss,
                reached=True,checked=True,passed=not failed,expected=miss,actual=0,
                evidence='JUnit and raw-port assertion in tests/load_s2/test_spec_prefetch_miss.py'))
    assert len(spec_cases)==2 and sum(x['passed'] for x in spec_cases)==1
    result=dict(schema_version=1,run=str(RUN.relative_to(ROOT)),inputs_sha256=inputs,totals=totals,per_dut=per_dut,groups=groups,bins=bins,spec_cases=spec_cases,
        decisions=decisions,historical_evidence_decisions=history,
        warnings=["normal bins and cross bins have separate denominators",
                  "samples/hits are explicit sampling events, not unique transactions or independently proven functional checks",
                  "independent_reached_checked_certified=false means evidence not certified, not behavior untested",
                  "confirmed_rtl_bug=false does not mean rtl_bug_ruled_out=true",
                  "the failing hardware-prefetch specification check was added outside the historical functional-bin schema and is reported separately"])
    (OUT/"data.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10))
    write_csv(OUT/"functional-bins.csv",bins);write_csv(OUT/"bug-decisions.csv",decisions);write_csv(OUT/"historical-evidence-decisions.csv",history)
    write_csv(OUT/"coverage-per-dut.csv",[{k:v for k,v in row.items() if k!="categories"} for row in per_dut])
    write_csv(OUT/"spec-cases.csv",spec_cases)
    lines=["# 全量功能bin数据（最终run原始记录）","","固定run：`failure-recheck-final-03`。这是采样命中，不等同独立reached/checked；后者本报告未认证，不能标成已完成。所有原始bin均保留，不删分母。",""]
    for g in groups:
        lines += ["## "+g["instance"],"",g["description"],"","| 类型/功能点 | bin | 命中次数 | 门槛 | 达标 |","|---|---|---:|---:|---|"]
        for b in bins:
            if b["group"]==g["instance"]:
                lines.append(f"| {cell(b['kind'])}/{cell(b['point'])} | `{cell(b['bin'])}` | {b['hits']} | {b['goal']} | {yn(b['sampled_goal_met'])} |")
        lines.append("")
    (OUT/"all-functional-bins.md").write_text(chr(10).join(lines)+chr(10))
    report=["# 覆盖率、功能点分组与Bug是/否判定（2026-10-26）","","数据绑定 `failure-recheck-final-03`：582 PASS / 1 FAIL，RTL未改。每DUT保留原分母。**是/否只回答表头的具体命题；证据不足不能伪写成不存在Bug。**","","## 1. 逐DUT覆盖率与功能bin","","| DUT | 行 | branch | toggle | 功能bin命中/总数 | 交叉bin | 分组数 | 采样数 |","|---|---:|---:|---:|---:|---:|---:|---:|"]
    for x in per_dut:
        report.append(f"| {x['dut']} | {x['line_hit']}/{x['line_total']} | {x['branch_hit']}/{x['branch_total']} | {x['toggle_hit']}/{x['toggle_total']} | {x['point_hit']}/{x['point_bins']} | {x['cross_hit']}/{x['cross_bins']} | {x['groups']} | {x['group_samples']} |")
    report += ["",f"共{totals['groups']}个covergroup、{totals['coverpoints']}个coverpoint、{totals['point_hit']}/{totals['point_bins']}个普通bin、{totals['cross_hit']}/{totals['cross_bins']}个交叉bin。采样事件共{totals['group_samples']}，不是唯一事务数。0/0表示无该类插桩，不写成100%。","","## 2. 功能点语义分组与数据","","分组依据原bin名前缀；store仲裁按实际coverpoint及交叉分类，不重新定义原分母。","","| DUT | 语义子组 | bin命中/总数 | 命中事件总数 |","|---|---|---:|---:|"]
    for x in per_dut:
        for c in x["categories"]:
            report.append(f"| {x['dut']} | {c['description']}（{c['category']}） | {c['hit']}/{c['bins']} | {c['hit_events']} |")
    report += ["","## 3. 功能数据的检查边界","","全部普通bin与cross已采样达标；这是工具100%的含义。逐bin独立reached/checked认证：**否**，不是说所有行为都没测。可追到测试字面量的引用保留在CSV，静态引用也不等于动态检查证明。","","新增硬件预取miss规范测试单列：2个参数情形，均实际执行并检查；hit=0情形PASS、miss=1情形FAIL。它们没有偷偷并入旧bin分母。因此不能用旧功能100%掩盖1个真实FAIL。","","## 4. 每项已确认缺陷的是/否","","RTL列的否表示该条是验证/报告缺陷而不是一项已确认RTL缺陷，不代表整个模块无Bug。修复列对日志缺失仅指后续采集，不能恢复旧日志。","","| ID | 问题 | 确认RTL Bug | 确认验证/报告Bug | 修复闭环 |","|---|---|---|---|---|"]
    for d in decisions:
        report.append(f"| {d['id']} | {d['description']} | {yn(d['confirmed_rtl_bug'])} | {yn(d['confirmed_verification_or_report_bug'])} | {yn(d['remediation_completed'])} |")
    report += ["","## 5. 历史记录的二元证据结论","","不能从缺日志推导没有RTL Bug。下面给出明确的是/否：是否足以裁定、是否确认RTL Bug、是否已排除RTL Bug；不把后一列的否当成确认有Bug。","","| run | FAIL观测数 | 证据足以裁定 | 确认RTL Bug | 已排除RTL Bug |","|---|---:|---|---|---|"]
    for h in history:
        report.append(f"| {h['run']} | {h['fail_observations']} | {yn(h['enough_evidence_for_rtl_vs_test_verdict'])} | {yn(h['confirmed_rtl_bug'])} | {yn(h['rtl_bug_ruled_out'])} |")
    report += ["","前5个run共17次FAIL不能恢复逐nodeid根因；裁定证据是否充足=否。这不是‘Bug是否存在=否’。收集失败run在native DUT执行前失败，不能计成其RTL功能Bug。","","## 6. 可核对的数据文件","","- `review/failure_recheck_20261026/coverage-functional/data.json`：全部数据、输入SHA、分组和明确布尔字段。","- 同目录 `coverage-per-dut.csv`、`functional-bins.csv`、`bug-decisions.csv`、`historical-evidence-decisions.csv`：逐项原始数字。","- 同目录 `all-functional-bins.md`：每个普通/交叉bin完整名称、命中次数、门槛与达标是/否。","- `docs/bug-reports-20261026/README.md`：根因、源码、复现与证据限制。","","本次只生成展示数据，没有重跑已完成仿真，没有修改目标RTL、测试、覆盖bin或原结果目录。"]
    report=[line.replace("分组依据原bin名前缀；store仲裁按实际coverpoint及交叉分类，不重新定义原分母。",
        "叶子按原bin前缀、store仲裁按实际coverpoint/交叉分组；父块按原bin语义做穷尽互斥映射。139个展示子组不是新增covergroup，不重新定义原分母。")
        .replace("修复列对日志缺失仅指后续采集，不能恢复旧日志。",
                 "日志问题修复闭环=否：后续采集已修正，但历史日志不能恢复。")
        .replace("收集失败run在native DUT执行前失败，不能计成其RTL功能Bug。",
                 "这些记录的报告处理结论为：证据不满足认定门槛，不计为确认Bug；并非宣告RTL无缺陷。收集失败run在native DUT执行前失败，不计成其RTL功能Bug。")
        for line in report]
    path=ROOT/"docs/reports/coverage-functional-decisions-20261026.md"
    path.write_text(chr(10).join(report)+chr(10))
    assert len(per_dut)==19 and len(groups)==21 and all(b["sampled_goal_met"] for b in bins)
    assert len(bins)==totals["point_bins"]+totals["cross_bins"]
    assert all(type(d[k]) is bool for d in decisions for k in ("confirmed_rtl_bug","confirmed_verification_or_report_bug","remediation_completed"))
    print(json.dumps(dict(report=str(path.relative_to(ROOT)),totals=totals,confirmed_rtl=sum(d['confirmed_rtl_bug'] for d in decisions),
        confirmed_verification=sum(d['confirmed_verification_or_report_bug'] for d in decisions),source_results_unchanged=True),ensure_ascii=False))


if __name__=="__main__":
    main()
