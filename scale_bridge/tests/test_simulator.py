import ast
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from scale_bridge.ids701 import IDS701StreamParser
from scale_bridge.simulator import (
    IDS701Simulator,
    MemoryTransport,
    PseudoTerminalTransport,
    PseudoTerminalUnavailableError,
)
from scale_bridge.simulator import simulator as simulator_module


def parse_chunks(chunks):
    parser = IDS701StreamParser()
    return [result for chunk in chunks for result in parser.feed(chunk)]


def test_simulator_core_scenarios_match_ids701_byte_stream():
    transport = MemoryTransport()
    simulator = IDS701Simulator(transport, interval=0)
    simulator.stable_zero()
    simulator.stable_gross("0.80")
    simulator.unstable_gross("3.82")
    simulator.negative()
    simulator.overload()
    simulator.net_mode("3.02")
    simulator.malformed()
    results = parse_chunks(transport.chunks)
    assert [result.status for result in results[:6]] == ["ST", "ST", "US", "ST", "OL", "ST"]
    assert [result.mode for result in results[:6]] == ["GS", "GS", "GS", "GS", "GS", "NT"]
    assert results[3].weight == Decimal("-0.08")
    assert results[4].overload
    assert results[6].decode_status == "NOT_DECODED"
    assert results[6].weight is None


def test_partial_multiple_disconnect_and_reconnect_scenarios():
    transport = MemoryTransport()
    simulator = IDS701Simulator(transport, interval=0)
    simulator.partial("3.82")
    simulator.multiple("1.00", "2.00")
    results = parse_chunks(transport.chunks)
    assert [result.weight for result in results] == [
        Decimal("3.82"),
        Decimal("1.00"),
        Decimal("2.00"),
    ]
    simulator.disconnect()
    with pytest.raises(ConnectionError, match="disconnected"):
        simulator.stable_zero()
    simulator.reconnect()
    simulator.stable_zero()
    assert parse_chunks(transport.chunks[-1:])[0].weight == Decimal("0.00")


def test_simulator_module_does_not_import_posix_dependencies_at_module_import_time():
    source = Path(simulator_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    module_imports.update(
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert {"pty", "tty", "termios"}.isdisjoint(module_imports)
    IDS701Simulator(MemoryTransport(), interval=0).stable_zero()


def test_pseudo_terminal_transport_fails_cleanly_on_windows(monkeypatch):
    monkeypatch.setattr(simulator_module, "os", SimpleNamespace(name="nt"))
    with pytest.raises(PseudoTerminalUnavailableError, match="only on POSIX"):
        PseudoTerminalTransport()


@pytest.mark.skipif(os.name != "posix", reason="POSIX pseudo-terminal behavior")
def test_pseudo_terminal_transport_preserves_posix_behavior():
    transport = PseudoTerminalTransport()
    try:
        assert transport.device
        assert transport.master_fd is not None
        assert transport.slave_fd is not None
    finally:
        transport.disconnect()
