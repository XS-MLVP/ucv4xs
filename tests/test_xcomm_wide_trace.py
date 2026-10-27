"""Wide Verilator word expressions must read the live native model. MPL-2.0."""
from pathlib import Path
import os
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_wide_trace_words_are_live_bounded_and_read_only(tmp_path):
    prefix = Path(os.environ.get('UCV_XCOMM_TEST_PREFIX', ROOT/'.tools'))
    includes = Path(os.environ.get('UCV_XCOMM_TEST_INCLUDE', prefix/'include'))
    if not (prefix/'lib/libxspcomm.so').exists():
        pytest.skip('requires ucv setup native SDK')
    source = tmp_path/'wide.cpp'
    source.write_text(r'''
#include "xspcomm/xexpr.h"
#include "xspcomm/xsignal_cfg.h"
#include <cassert>
#include <memory>
#include <stdexcept>
using namespace xspcomm;
int main(){
    uint32_t memory[17] = {};
    XData wide(532, XData::InOut), scalar(32, XData::InOut);
    wide.BindNativeData(reinterpret_cast<uint64_t>(memory));
    ExprEngine e;
    e.RegisterExternalSignal("Top.phr", &wide);
    e.RegisterExternalSignal("scalar", &scalar);
    int roots[17];
    for(int i=0;i<17;i++) roots[i]=e.CompileExpr("Top.phr["+std::to_string(i)+"U]", nullptr);
    for(int iteration=0;iteration<3;iteration++){
        for(int i=0;i<17;i++) memory[i]=(0xdeadb000U + i) ^ (iteration*0x10101U);
        for(int i=0;i<17;i++) assert(e.Eval(roots[i]) == (memory[i] & (i==16 ? 0xfffffU : 0xffffffffU)));
    }
    int mixed=e.CompileExpr("0x1fffU & (Top.phr[0U] ^ (Top.phr[16U] >> 3U))", nullptr);
    assert(e.Eval(mixed)==(0x1fffU & (memory[0] ^ ((memory[16]&0xfffffU)>>3))));
    for(const char* bad : {"Top.phr[17]", "Top.phr[18446744073709551615ULL]", "Top.phr[-1]", "Top.phr[scalar]", "Top.phr[1+1]", "Top.phr[1", "scalar[0]"}){
        bool rejected=false;
        try { e.CompileExpr(bad,nullptr); } catch(const std::exception&) { rejected=true; }
        assert(rejected);
    }
    const std::string yaml=R"yaml(
variables:
  - name: Top.phr
    offset: 0
    mem_bytes: 68
    rtl_width: 532
    type: VlWide<17>
signals:
  - name: Top.low
    kind: projection
    rtl_width: 13
    type: SData
    source: Top.phr
    expr: 0x1fffU & Top.phr[0U]
)yaml";
    XSignalCFG cfg(yaml, reinterpret_cast<uint64_t>(memory));
    std::unique_ptr<XData> low(cfg.NewXData("Top.low"));
    assert(low && low->IsOutIO() && !low->IsVPIBinded() && low->W()==13);
    memory[0]=0x12345678U;
    assert(low->U()==(memory[0]&0x1fffU));
    memory[0]=0x87654321U;
    assert(low->U()==(memory[0]&0x1fffU));
}
''')
    program = tmp_path/'wide'
    subprocess.run(['c++','-std=c++17','-UNDEBUG','-I'+str(includes),str(source),
                    '-L'+str(prefix/'lib'),'-Wl,-rpath,'+str(prefix/'lib'),'-lxspcomm','-o',program],
                   check=True,capture_output=True,text=True)
    subprocess.run([program],check=True,capture_output=True,text=True)
