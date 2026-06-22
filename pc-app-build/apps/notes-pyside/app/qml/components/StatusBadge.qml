import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string text: "已连接"
    property color dotColor: "#16A34A"
    property color bgColor: "#EAF0FF"
    property color textColor: "#374151"

    color: bgColor
    radius: 999
    height: 32
    implicitWidth: row.implicitWidth + 28

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 8

        Rectangle {
            width: 8
            height: 8
            radius: 4
            color: root.dotColor
        }

        Text {
            text: root.text
            color: root.textColor
            font.pixelSize: 12
        }
    }
}
