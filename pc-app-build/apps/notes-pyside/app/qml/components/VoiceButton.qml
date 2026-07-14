import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property bool available: false
    property string label: "助手"
    property string detailText: "暂未启用"

    signal clicked()

    width: 148
    height: 50
    radius: 25
    color: root.available ? "#FFFFFF" : "#F3F4F6"
    border.color: root.available ? "#E5E7EB" : "#D1D5DB"
    border.width: 1
    clip: true

    RowLayout {
        anchors.centerIn: parent
        spacing: 10

        Rectangle {
            width: 26
            height: 26
            radius: 13
            color: root.available ? "#19B7A8" : "#9CA3AF"

            Rectangle {
                anchors.centerIn: parent
                width: 8
                height: 8
                radius: 4
                color: "#FFFFFF"
                opacity: root.available ? 1 : 0.75
            }
        }

        ColumnLayout {
            spacing: 0

            Text {
                text: root.label
                color: root.available ? "#111827" : "#6B7280"
                font.pixelSize: 14
                font.bold: true
                elide: Text.ElideRight
                Layout.maximumWidth: 88
            }

            Text {
                text: root.detailText
                color: "#9CA3AF"
                font.pixelSize: 10
                elide: Text.ElideRight
                Layout.maximumWidth: 92
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.available ? Qt.PointingHandCursor : Qt.ArrowCursor

        onClicked: {
            if (root.available) {
                root.clicked()
            }
        }
    }
}
