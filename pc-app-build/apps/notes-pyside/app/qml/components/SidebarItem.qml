import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string text: ""
    property string countText: ""
    property bool active: false
    property string iconText: ""

    signal clicked()

    height: 42
    radius: 14
    color: active ? "#EAF0FF" : mouse.containsMouse ? "#F7F8FA" : "transparent"

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 10

        Text {
            visible: root.iconText.length > 0
            text: root.iconText
            color: root.active ? "#4F7CFF" : "#6B7280"
            font.pixelSize: 14
        }

        Text {
            Layout.fillWidth: true
            text: root.text
            color: root.active ? "#2563EB" : "#374151"
            font.pixelSize: 14
            font.bold: root.active
            elide: Text.ElideRight
        }

        Text {
            visible: root.countText.length > 0
            text: root.countText
            color: root.active ? "#2563EB" : "#9CA3AF"
            font.pixelSize: 12
        }

        Rectangle {
            visible: root.active
            width: 8
            height: 8
            radius: 4
            color: "#4F7CFF"
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
