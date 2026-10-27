"""A postprocessor correction cannot relax exact collection identity."""
import xml.etree.ElementTree as ET

from _pytest.junitxml import bin_xml_escape
from _pytest.junitxml import mangle_test_address
import pytest
from tools import refresh_coverage as corrected



def xml(tmp_path, nodes, *, status=None):
    root = ET.Element('testsuites')
    suite = ET.SubElement(root, 'testsuite')
    for node in nodes:
        parts = mangle_test_address(node)
        case = ET.SubElement(suite, 'testcase', classname='.'.join(parts[:-1]),
                             name=bin_xml_escape(parts[-1]))
        if status:
            ET.SubElement(case, status[0], **status[1])
    path = tmp_path / 'pytest.xml'
    ET.ElementTree(root).write(path, encoding='unicode')
    return path


@pytest.mark.parametrize('suffix', ['', '[plain]', '[# SystemC::Coverage-3\\n]',
    '[a::b::c]', '[[nested]::value]', '[back\\slash]', '[literal&<quotes>]',
    '[汉字]', '[bad\x00xml]', '[del\x7f]', '[line\nnext]'])
@pytest.mark.parametrize('parent', ['', '::TestClass::Nested'])
def test_parameter_names_use_the_same_encoder_as_pytest(tmp_path, suffix, parent):
    node = f'tests/unit/test_example.py{parent}::test_one{suffix}'
    assert corrected.junit_verdicts(xml(tmp_path, [node]), [node]) == {node: 'PASS'}


@pytest.mark.parametrize('fault', ['unknown', 'duplicate', 'missing', 'failure', 'error', 'skip'])
def test_failed_partial_or_extra_execution_is_still_rejected(tmp_path, fault):
    node = 'tests/unit/test_example.py::test_one[a::b]'
    nodes = [node]
    status = None
    if fault == 'unknown': nodes = [node.replace('a::b', 'other')]
    elif fault == 'duplicate': nodes *= 2
    elif fault == 'missing': nodes = []
    elif fault in ('failure', 'error'): status = (fault, {})
    else: status = ('skipped', dict(type='pytest.skip'))
    with pytest.raises(ValueError):
        corrected.junit_verdicts(xml(tmp_path, nodes, status=status), [node])


def test_xml_encoder_collisions_are_rejected_not_guessed(tmp_path):
    nodes = ['tests/unit/test_example.py::test_one[\x00]',
             'tests/unit/test_example.py::test_one[#x00]']
    with pytest.raises(ValueError, match='ambiguous JUnit identity'):
        corrected.junit_verdicts(xml(tmp_path, nodes), nodes)


def test_strict_known_xfail_is_not_a_skip_or_a_pass(tmp_path):
    node = 'tests/unit/test_example.py::test_one'
    assert corrected.junit_verdicts(xml(tmp_path, [node], status=('skipped',
        dict(type='pytest.xfail'))), [node]) == {node: 'XFAIL'}
