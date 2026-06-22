import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    signal clicked()

    width: 138
    height: 48
    radius: 24
    color: "#FFFFFF"

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
            color: "#1A1A1A"
            font.pixelSize: 14
            font.bold: true
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.clicked()
    }
}
