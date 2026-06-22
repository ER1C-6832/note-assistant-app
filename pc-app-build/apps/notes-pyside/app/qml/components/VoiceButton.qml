import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    signal clicked()

    width: 142
    height: 50
    radius: 25
    color: "#FFFFFF"
    border.color: "#E5E7EB"
    border.width: 1

    RowLayout {
        anchors.centerIn: parent
        spacing: 10

        Rectangle {
            width: 28
            height: 28
            radius: 14
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
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
