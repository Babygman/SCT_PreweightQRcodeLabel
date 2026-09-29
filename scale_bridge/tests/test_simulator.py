from decimal import Decimal

import pytest

from scale_bridge.ids701 import IDS701StreamParser
from scale_bridge.simulator import IDS701Simulator, MemoryTransport


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
