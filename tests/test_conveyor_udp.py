from __future__ import annotations

import socket
import threading

import pytest

from machine_vision.controllers.conveyor_udp import (
    exchange,
    make_command,
    parse_reply,
    validate_endpoint,
)


def test_commands_and_endpoint_are_strict():
    assert make_command("PING") == "PING"
    assert make_command("STOP") == "STOP:0"
    assert make_command("FWD", 150) == "FWD:150"
    assert validate_endpoint("127.0.0.1", 8120) == ("127.0.0.1", 8120)
    with pytest.raises(ValueError):
        make_command("REV", 0)
    with pytest.raises(ValueError):
        validate_endpoint("not-an-ip", 8120)


def test_ack_must_match_requested_action_and_speed():
    reply = parse_reply("FWD:150", b"ACK:FWD:150 (State: FWD Speed: 150)")
    assert (reply.state, reply.speed) == ("FWD", 150)
    assert parse_reply("PING", b"PONG").raw == "PONG"
    with pytest.raises(ValueError):
        parse_reply("FWD:150", b"ACK:REV:150 (State: REV Speed: 150)")
    with pytest.raises(ValueError):
        parse_reply("STOP:0", b"ACK:STOP:0 (State: FWD Speed: 150)")


def test_udp_exchange_with_local_fake_esp32():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(1)
    port = server.getsockname()[1]

    def respond():
        try:
            payload, address = server.recvfrom(128)
            assert payload == b"STOP:0"
            server.sendto(b"ACK:STOP:0 (State: STOP Speed: 0)", address)
        finally:
            server.close()

    thread = threading.Thread(target=respond)
    thread.start()
    reply = exchange("127.0.0.1", port, "STOP:0")
    thread.join(timeout=2)
    assert (reply.state, reply.speed) == ("STOP", 0)
