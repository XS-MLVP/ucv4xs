from __future__ import annotations

from types import SimpleNamespace

import pytest
from toffee import Bundle

from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_pulse
from tests.framework.fakes import Signal


def leaf(width: int = 1) -> dict[str, int | bool | str]:
    return {
        "_": True,
        "Pin": "input",
        "High": width - 1 if width > 1 else -1,
        "Low": 0,
    }


def fake_dut():
    return SimpleNamespace(
        clock=object(),
        io_request_valid=Signal(name="io_request_valid"),
        io_request_bits_data=Signal(
            width=8,
            name="io_request_bits_data",
        ),
        signal_tree={
            "io": {
                "request": {
                    "valid": leaf(),
                    "bits": {"data": leaf(8)},
                }
            }
        },
    )


@pytest.mark.feature("ENV-IF-001")
def test_signal_tree_binds_bundle_and_pulse_views():
    dut = fake_dut()

    bits = bind_bundle(
        dut,
        ("io", "request", "bits"),
        name="request.bits",
        tree=dut.signal_tree,
    )
    pulse = bind_pulse(dut, ("io", "request"), name="request", tree=dut.signal_tree)

    assert bits.name == "request.bits"
    assert bits.bits.data is dut.io_request_bits_data
    assert pulse.valid is dut.io_request_valid
    assert pulse.bits.data is dut.io_request_bits_data


@pytest.mark.feature("ENV-IF-001")
def test_pulse_binding_rejects_non_protocol_shape():
    dut = fake_dut()
    dut.signal_tree["io"]["request"]["extra"] = leaf()

    with pytest.raises(ValueError, match="exactly valid/bits"):
        bind_pulse(dut, ("io", "request"), name="request", tree=dut.signal_tree)


@pytest.mark.feature("ENV-IF-001")
def test_port_binding_accepts_scalar_payload_but_requires_name():
    with pytest.raises(ValueError, match="name cannot be empty"):
        PortBinding(object(), Bundle(data=Signal()), "")

    signal = Signal()
    assert PortBinding(object(), signal, "request").bits is signal
