import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string text: ""
    property bool active: false
    property bool deletable: false

    signal clicked()
    signal deleteRequested()

    height: 38
    radius: 13
    color: active ? "#EAF0FF" : mouse.containsMouse ? "#F7F8FA" : "transparent"

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 8
        spacing: 8

        Text {
            text: "#"
            color: root.active ? "#4F7CFF" : "#9CA3AF"
            font.pixelSize: 13
        }

        Text {
            Layout.fillWidth: true
            text: root.text
            color: root.active ? "#2563EB" : "#374151"
            font.pixelSize: 13
            font.bold: root.active
            elide: Text.ElideRight
        }

        Rectangle {
            visible: root.deletable
            width: 22
            height: 22
            radius: 11
            color: deleteMouse.containsMouse ? "#FEE2E2" : "transparent"

            Text {
                anchors.centerIn: parent
                text: "×"
                color: "#DC2626"
                font.pixelSize: 16
            }

            MouseArea {
                id: deleteMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.deleteRequested()
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        anchors.rightMargin: root.deletable ? 28 : 0
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
