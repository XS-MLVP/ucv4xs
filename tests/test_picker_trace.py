"""Pinned parser must preserve declaration identity across split functions. MPL-2.0."""
from pathlib import Path
import shlex
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def trace_parser(tmp_path_factory):
    build = ROOT / '.tools/build/picker'
    flags = build / 'src/parser/CMakeFiles/parser.dir/flags.make'
    if not flags.exists():
        pytest.skip('requires ucv setup native tool build')
    options = {}
    for line in flags.read_text().splitlines():
        if ' = ' in line:
            key, value = line.split(' = ', 1)
            options[key] = shlex.split(value)
    directory = tmp_path_factory.mktemp('trace-parser')
    source = directory / 'driver.cpp'
    source.write_text('''#include "common.hpp"
#include <iostream>
namespace picker { bool is_debug = false; char *lib_random_hash = nullptr; }
int main(int argc, char **argv) {
    std::vector<std::string> files(argv+1, argv+argc);
    auto events = picker::parser::verilator::detail::parse_v5_048(files);
    for (const auto &event : events)
        if (event.kind == picker::parser::verilator::detail::trace_event_kind::declaration)
            std::cout << event.slot << ":" << event.name << "\\n";
}
''')
    program = directory / 'driver'
    command = ['c++', *options['CXX_DEFINES'], *options['CXX_INCLUDES'], '-std=c++20', '-O2',
               '-I'+str(ROOT/'.tools/sources/picker/src/parser/verilator_trace'), str(source),
               str(build/'lib/libparser.a'), str(build/'lib/libappimage.a'), '-o', str(program)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return program


def declaration(number, name):
    return f'VL_TRACE_DECL_BIT(tracep,c+{number},0,"{name}");\n'


def test_split_calls_keep_scope_independent_of_filename_and_definition_order(trace_parser, tmp_path):
    # The child closes its parent's scope and opens a sibling; the root then
    # resumes in that sibling. A file scan and a per-call stack both get this wrong.
    first = tmp_path/'trace_0.cpp'
    last = tmp_path/'trace_12.cpp'
    first.write_text('''void VTop__trace_init_sub__child(VTop* vlSelf, Trace* tracep) {
VL_TRACE_POP_PREFIX(tracep);
VL_TRACE_PUSH_PREFIX(tracep,"right",0,0,0);
'''+declaration(2, 'same_leaf')+'}\n')
    last.write_text('''void VTop__trace_init_sub__root(VTop* vlSelf, Trace* tracep) {
VL_TRACE_PUSH_PREFIX(tracep,"Top",0,0,0);
VL_TRACE_PUSH_PREFIX(tracep,"left",0,0,0);
'''+declaration(1, 'same_leaf')+'''VTop__trace_init_sub__child(vlSelf, tracep);
'''+declaration(3, 'after_call')+'''VL_TRACE_POP_PREFIX(tracep);
VL_TRACE_POP_PREFIX(tracep);
}
''')
    expected = ['1:Top.left.same_leaf', '2:Top.right.same_leaf', '3:Top.right.after_call']
    for files in ((first,last),(last,first)):
        result = subprocess.run([trace_parser,*files],check=True,capture_output=True,text=True)
        assert result.stdout.splitlines() == expected


def test_unresolved_split_call_is_a_hard_error(trace_parser, tmp_path):
    source = tmp_path/'broken.cpp'
    source.write_text('''void VTop__trace_init_sub__root(VTop* vlSelf, Trace* tracep) {
VTop__trace_init_sub__missing(vlSelf, tracep);
}
''')
    result = subprocess.run([trace_parser,source],capture_output=True,text=True)
    assert result.returncode != 0
    assert 'Invalid trace initialization call' in result.stderr


def test_flat_declaration_fixture_remains_supported(trace_parser, tmp_path):
    source = tmp_path/'flat.cpp'
    source.write_text('VL_TRACE_PUSH_PREFIX(tracep,"Top",0,0,0);\n'+declaration(7,'bit')+
                      'VL_TRACE_POP_PREFIX(tracep);\n')
    result = subprocess.run([trace_parser,source],check=True,capture_output=True,text=True)
    assert result.stdout.splitlines() == ['7:Top.bit']
