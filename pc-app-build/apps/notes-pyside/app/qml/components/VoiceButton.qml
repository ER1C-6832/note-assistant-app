import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    signal clicked()

    width: 136
    height: 48
    radius: 24
    color: mouse.containsMouse ? "#F7F8FA" : "#FFFFFF"
    border.color: "#E5E7EB"
    border.width: 1
    z: 20
    clip: true

    RowLayout {
        anchors.centerIn: parent
        spacing: 10

        Rectangle {
            width: 26
            height: 26
            radius: 13
            color: "#19B7A8"
        }

        Text {
            text: "语音助手"
            color: "#111827"
            font.pixelSize: 14
            font.bold: true
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
