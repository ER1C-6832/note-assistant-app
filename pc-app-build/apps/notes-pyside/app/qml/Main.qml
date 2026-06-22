import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: appWindow
    title: "Note Assistant"
    width: 1200
    height: 800
    visible: true

    // Placeholder main layout — will be replaced with
    // the three-panel design (sidebar, note list, detail)
    // as specified in the Pencil prototype.
    Rectangle {
        anchors.fill: parent
        color: "#f5f5f5"

        Text {
            anchors.centerIn: parent
            text: "Note Assistant"
            font.pixelSize: 24
            color: "#333"
        }

        Text {
            anchors {
                top: parent.verticalCenter
                topMargin: 40
                horizontalCenter: parent.horizontalCenter
            }
            text: "PySide6 + QML UI — Phase 3+"
            font.pixelSize: 14
            color: "#999"
        }
    }
}
