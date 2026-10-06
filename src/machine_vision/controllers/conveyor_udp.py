"""UDP adapter for the ESP32/W5500 conveyor firmware.

The protocol has no transaction ID. Every request uses a fresh UDP socket, checks
the peer address, and accepts only the reply matching that request.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass

_ACK = re.compile(r"^ACK:(FWD|REV|STOP):(\d{1,3}) \(State: (FWD|REV|STOP) Speed: (\d{1,3})\)$")


@dataclass(frozen=True)
class ConveyorReply:
    command: str
    state: str | None
    speed: int | None
    raw: str


def validate_endpoint(host: str, port: int) -> tuple[str, int]:
    host = str(ipaddress.IPv4Address(host.strip()))
    if not 1 <= port <= 65535:
        raise ValueError("UDP port phải trong khoảng 1–65535")
    return host, port


def make_command(action: str, speed: int = 0) -> str:
    if action == "PING":
        return "PING"
    if action == "STOP":
        return "STOP:0"
    if action not in {"FWD", "REV"}:
        raise ValueError("Lệnh băng tải không hợp lệ")
    if not 1 <= speed <= 255:
        raise ValueError("Tốc độ PWM phải trong khoảng 1–255")
    return f"{action}:{speed}"


def parse_reply(command: str, payload: bytes) -> ConveyorReply:
    raw = payload.decode("ascii", errors="strict").strip()
    if command == "PING":
        if raw != "PONG":
            raise ValueError(f"Phản hồi PING không hợp lệ: {raw!r}")
        return ConveyorReply(command, None, None, raw)
    match = _ACK.fullmatch(raw)
    if match is None:
        raise ValueError(f"ACK không hợp lệ: {raw!r}")
    action, requested_speed, state, actual_speed = match.groups()
    expected_action, expected_speed = command.split(":", 1)
    speed = int(actual_speed)
    if (
        action != expected_action
        or requested_speed != expected_speed
        or state != expected_action
        or speed != int(expected_speed)
    ):
        raise ValueError(f"ACK không khớp lệnh {command}: {raw!r}")
    return ConveyorReply(command, state, speed, raw)


def exchange(host: str, port: int, command: str, timeout_s: float = 0.6) -> ConveyorReply:
    host, port = validate_endpoint(host, port)
    if command != "PING":
        action, separator, speed_text = command.partition(":")
        if (
            not separator
            or not speed_text.isdigit()
            or make_command(action, int(speed_text)) != command
        ):
            raise ValueError("Lệnh băng tải không hợp lệ")
    if not 0 < timeout_s <= 5:
        raise ValueError("Timeout phải trong khoảng 0–5 giây")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(timeout_s)
        client.sendto(command.encode("ascii"), (host, port))
        payload, peer = client.recvfrom(512)
    if peer != (host, port):
        raise ValueError(f"Phản hồi từ nguồn khác: {peer}")
    return parse_reply(command, payload)
