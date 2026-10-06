from __future__ import annotations

import socket
import threading
import time

from machine_vision.ui.conveyor_panel import ConveyorPanel


def wait_until(qt_app, predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qt_app.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("GUI did not reach the expected state")


def test_gui_requires_stop_ack_and_syncs_udp_commands(qt_app):
    """Exercise real worker threads, UDP replies and priority STOP without a motor."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2)
    port = server.getsockname()[1]
    commands = []

    def fake_esp32():
        try:
            for _ in range(6):
                data, peer = server.recvfrom(128)
                command = data.decode()
                commands.append(command)
                if command == "PING":
                    reply = "PONG"
                else:
                    action, speed = command.split(":")
                    if action == "FWD":
                        time.sleep(0.05)  # Allow STOP to be pressed while awaiting ACK.
                    reply = f"ACK:{command} (State: {action} Speed: {speed})"
                server.sendto(reply.encode(), peer)
        finally:
            server.close()

    thread = threading.Thread(target=fake_esp32)
    thread.start()
    panel = ConveyorPanel({"host": "127.0.0.1", "port": port})
    states = []
    panel.state_changed.connect(lambda state, _speed: states.append(state))
    try:
        panel.ping_button.click()
        wait_until(qt_app, lambda: panel._online and not panel._workers)
        assert not panel.forward_button.isEnabled()  # PONG contains no motor status.
        panel.stop_button.click()
        wait_until(qt_app, lambda: panel.state == "STOP" and not panel._workers)
        assert panel.forward_button.isEnabled()
        panel.forward_button.click()
        assert not panel.host.isEnabled()
        panel.stop_button.click()
        wait_until(
            qt_app, lambda: len(commands) == 4 and panel.state == "STOP" and not panel._workers
        )
        assert commands == ["PING", "STOP:0", "FWD:150", "STOP:0"]
        assert states[-1] == "STOP"
        assert panel.host.isEnabled()
        panel.forward_button.click()
        wait_until(qt_app, lambda: panel.state == "FWD" and not panel._workers)
        assert not panel.reverse_button.isEnabled()
        assert panel.shutdown() is None
        assert commands[-2:] == ["FWD:150", "STOP:0"]
        assert panel.state == "STOP"
    finally:
        panel.shutdown()
        panel.close()
        thread.join(timeout=2)


def test_missing_ack_keeps_gui_unknown(qt_app):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    panel = ConveyorPanel({"host": "127.0.0.1", "port": server.getsockname()[1]})
    try:
        panel.stop_button.click()
        wait_until(qt_app, lambda: not panel._workers)
        assert panel.state == "UNKNOWN"
        assert not panel.forward_button.isEnabled()
        assert panel.stop_button.isEnabled()
    finally:
        panel.shutdown()
        panel.close()
        server.close()
