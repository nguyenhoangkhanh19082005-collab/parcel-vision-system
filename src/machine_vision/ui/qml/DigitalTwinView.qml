import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils
import QtQuick3D.Helpers

Item {
    id: root
    property url conveyorSource
    property url robotSource
    property url cellSource

    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            clearColor: "#07111b"
            backgroundMode: SceneEnvironment.Color
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        Node {
            id: cameraOrigin
            eulerRotation.x: -24
            eulerRotation.y: -38
            PerspectiveCamera {
                id: sceneCamera
                position: Qt.vector3d(0, 4.5, 11)
                clipFar: 1000
            }
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-42, -28, 0)
            brightness: 1.2
            castsShadow: true
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(-25, 145, 0)
            brightness: 0.45
        }

        GridGeometry { id: floorGrid; horizontalLines: 24; verticalLines: 24 }
        Model {
            geometry: floorGrid
            eulerRotation.x: -90
            materials: PrincipledMaterial {
                baseColor: "#1b2a38"
                roughness: 1.0
                lighting: PrincipledMaterial.NoLighting
            }
        }

        RuntimeLoader { source: root.conveyorSource }
        RuntimeLoader { source: root.robotSource }
        RuntimeLoader { source: root.cellSource }
    }

    OrbitCameraController {
        anchors.fill: parent
        origin: cameraOrigin
        camera: sceneCamera
    }
}
