"""Tests for the SPICE netlist parser."""

import pytest

from netlist2image.core.parser import parse_netlist
from netlist2image.core.models import AbstractNetlist


def test_parse_rc_circuit():
    text = """\n* Simple RC\nV1 in 0 DC 5\nR1 in out 1k\nC1 out 0 100n\n.END\n"""
    netlist = parse_netlist(text)
    assert len(netlist.elements) == 3
    assert netlist.elements[0].id == "V1"
    assert netlist.elements[0].type == "V"
    assert netlist.elements[1].value_numeric == pytest.approx(1000.0)
    assert netlist.elements[2].value_numeric == pytest.approx(1e-7)
    assert "GND" in netlist.nodes
    assert netlist.nodes["GND"].is_ground
    assert netlist.nodes["GND"].spice_name == "0"


def test_parse_bjt_with_model():
    text = """\nVcc vcc 0 12\nQ1 coll base emit 2N3904\n.model 2N3904 NPN\n.END\n"""
    netlist = parse_netlist(text)
    q1 = [e for e in netlist.elements if e.id == "Q1"][0]
    assert q1.model == "2N3904"
    assert q1.pins == ["coll", "base", "emit"]


def test_ground_alias_normalization():
    text = """\nR1 a GND 1k\nR2 a VSS 2k\nR3 a 0 3k\n.END\n"""
    netlist = parse_netlist(text)
    assert len(netlist.nodes) == 2  # a and GND
    assert "GND" in netlist.nodes
    assert netlist.nodes["GND"].spice_name in {"GND", "VSS", "0"}


def test_parse_error_tracking():
    text = """\nV1 in 0 5\nBADLINE\nR1 in out 1k\n.END\n"""
    netlist = parse_netlist(text)
    assert len(netlist.parse_errors) == 1
    assert "BADLINE" in netlist.parse_errors[0]
    assert len(netlist.elements) == 2


def test_subcircuit_instance():
    text = """\nXU1 in out opamp\n.END\n"""
    netlist = parse_netlist(text)
    assert len(netlist.subcircuit_instances) == 1
    assert netlist.subcircuit_instances[0].name == "XU1"
    assert netlist.subcircuit_instances[0].subcircuit == "opamp"
    x_elem = [e for e in netlist.elements if e.id == "XU1"][0]
    assert x_elem.type == "X"
