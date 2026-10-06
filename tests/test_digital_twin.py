from machine_vision.ui.digital_twin import DigitalTwinWidget, ProcessStage


def test_digital_twin_process_state(qt_app):
    twin = DigitalTwinWidget()

    twin.set_process_state(ProcessStage.VISION, conveyor_running=False)

    assert twin.stage == ProcessStage.VISION
    assert twin.conveyor_running is False
    assert twin.decision is None


def test_digital_twin_records_final_decision(qt_app):
    twin = DigitalTwinWidget()

    twin.set_process_state(ProcessStage.COMPLETE, decision="REJECT")

    assert twin.stage == ProcessStage.COMPLETE
    assert twin.decision == "REJECT"


def test_digital_twin_camera_presets(qt_app):
    twin = DigitalTwinWidget()

    twin.set_view("top")

    assert twin.pitch == 73.0
    assert twin.distance == 12.0


def test_digital_twin_six_axis_joint_control(qt_app):
    twin = DigitalTwinWidget()

    twin.set_joint_angle(5, 145)

    assert len(twin.robot_angles) == 6
    assert twin.robot_angles[5] == 145


def test_digital_twin_layer_visibility(qt_app):
    twin = DigitalTwinWidget()

    twin.set_layer_visible("vision_zones", False)

    assert twin.layer_visibility["vision_zones"] is False


def test_digital_twin_rejects_unknown_layer(qt_app):
    twin = DigitalTwinWidget()

    try:
        twin.set_layer_visible("unknown", False)
    except ValueError as exc:
        assert "Unknown Digital Twin layer" in str(exc)
    else:
        raise AssertionError("Unknown layers must be rejected")
