"""File-reader qualification only; no DUT or architectural model."""
import pytest

from suites.vector.vagq.waveform import read_public_samples


pytestmark = pytest.mark.toffee_functional_coverage(False)


HEADER = '''$scope module TOP $end
$scope module VAGQDut_top $end
$var wire 1 ! clock $end
$var wire 1 ! clock_alias $end
$var wire 8 " address [7:0] $end
$upscope $end
$upscope $end
$enddefinitions $end
'''


def test_waveform_reader_preserves_aliases_vectors_and_timestamp_state(tmp_path):
    path = tmp_path / 'reader.vcd'
    path.write_text(HEADER + '#0\n0!\nbxxxxxxxx "\n#5\n1!\nb00100000 "\n#10\n0!\n')
    samples = read_public_samples(path, ('clock', 'clock_alias', 'address'))
    assert [sample['time'] for sample in samples] == [0, 5, 10]
    assert [sample['values']['clock'] for sample in samples] == [0, 1, 0]
    assert [sample['values']['clock_alias'] for sample in samples] == [0, 1, 0]
    assert [sample['values']['address'] for sample in samples] == [None, 32, 32]


def test_waveform_reader_rejects_missing_public_leaves(tmp_path):
    path = tmp_path / 'reader.vcd'
    path.write_text(HEADER + '#0\n0!\n#5\n1!\n')
    with pytest.raises(AssertionError, match='Public waveform leaves missing'):
        read_public_samples(path, ('reset',))


def test_waveform_reader_rejects_nonadvancing_capture(tmp_path):
    path = tmp_path / 'reader.vcd'
    path.write_text(HEADER + '#0\n0!\n')
    with pytest.raises(AssertionError, match='no advancing native waveform timestamps'):
        read_public_samples(path, ('clock',))
