# HMI and Digital Twin design

## Operator screen

The desktop HMI is optimized for one-glance operation at the conveyor cell:

- Device strip: camera, vision runtime, controller, data store, and remote channel.
- Session KPIs: processed parcels, QR scan success, pass, reject, and cycle time.
- Live vision: A6 label ROI, quality gate, manual inspection trigger, and focus peaking.
- Interactive 3D process twin: conveyor, presence sensor, camera gantry, active parcel,
  sorting bins, and a six-axis robot.
- Current result: waybill, logo, damage status, destination bin, and classification reason.
- Event/alarm tabs: traceability without hiding the live process.

Unavailable integrations deliberately show `NOT CONFIGURED`; the screen never presents a
simulated controller or remote connection as live.

The 3D view supports left-drag orbit, right-drag pan, wheel zoom, double-click reset,
four camera presets, and independent J1-J6 angle sliders. It is software-rendered by PyQt,
so it does not require an OpenGL driver or a separate 3D engine.

## Engineering workspace

The dedicated Digital Twin tab follows a plant-engineering layout:

- a permanent cell/status command bar;
- a Scene Explorer for selecting conveyor, vision gantry, camera, robot, and bins;
- a dominant 3D viewport with orbit/pan/zoom camera controls;
- an Inspector/Telemetry panel for live state, robot joints, and asset readiness;
- restrained blue for selection, green for normal operation, amber for warning, and red
  only for faults or rejected parcels.

The current software scene remains the safe fallback. `assets/digital_twin/scene_manifest.json`
separates model file paths, transforms, named nodes, and telemetry bindings from the GUI.
The Qt Quick 3D scene template is stored at
`src/machine_vision/ui/qml/DigitalTwinView.qml`; it is commissioned only after real assets
pass the handoff checklist in `docs/3d_asset_handoff.md`.

## Runtime state model

| State | Trigger | Conveyor | Operator meaning |
| --- | --- | --- | --- |
| `IDLE` | Camera disconnected | Independent UDP command state | Camera unavailable |
| `DETECT` | Camera streaming | Independent UDP command state | Waiting for manual inspection |
| `VISION` | Inspection started | Independent UDP command state | QR/logo/damage pipeline running |
| `ROUTING` | Reserved for future automation | Not commissioned | Sorter integration pending |
| `COMPLETE` | Inspection finished | Independent UDP command state | PASS, REJECT, or MANUAL_REVIEW |

The ESP32 tab controls the conveyor manually with UDP. Its ACK updates the displayed
command state; PONG proves communication only. UNKNOWN must remain visible when no ACK
is available. Camera actions and vision results never send motor commands. Robot joints
remain a simulation. See `docs/esp32_contract.md` for the actual firmware protocol.

## Recommended remote architecture

```text
Camera + sensor -> Python/OpenCV station -> local event store
                              |             |
                              +-> ESP32/PLC +-> MQTT or OPC UA gateway
                                                   |
                                      Remote read-only dashboard
```

The desktop HMI remains the local source of operational truth. A remote dashboard should
consume timestamped telemetry and events; it should not directly drive the conveyor in the
first release. If remote commands are added later, require authentication, role-based access,
an explicit local/remote mode, command acknowledgement, and physical safety interlocks.

## Minimum telemetry contract

Publish one station snapshot on every state change and a heartbeat every 2-5 seconds:

```json
{
  "station_id": "MV-01",
  "timestamp": "2026-09-29T10:00:00+07:00",
  "mode": "AUTO",
  "stage": "VISION",
  "camera": "ONLINE",
  "controller": "NOT_CONFIGURED",
  "remote": "ONLINE",
  "conveyor_running": false,
  "parcel_id": "SPXVN012345678",
  "decision": null,
  "destination_bin": null,
  "quality": {"laplacian": 141.2, "motion": 1.4, "gate": "READY"},
  "counters": {"total": 128, "pass": 119, "reject": 6, "review": 3},
  "alarm": null
}
```

Do not transmit full camera frames continuously unless they are explicitly needed. Prefer a
low-rate preview or a captured evidence image for failures to reduce bandwidth and exposure.
