import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var viewModelRef: null
    signal closeRequested()

    objectName: "assistantFloatingPanel"
    width: 390
    height: Math.min(parent ? parent.height - 48 : 760, 760)
    radius: 18
    color: "#FFFFFF"
    border.color: "#CBD5E1"
    border.width: 1
    clip: true

    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        z: -1
        radius: root.radius + 4
        color: Qt.rgba(0.12, 0.18, 0.28, 0.10)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        Rectangle {
            id: dragHeader
            Layout.fillWidth: true
            Layout.preferredHeight: 42
            color: "#F8FAFC"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 8

                Label {
                    Layout.fillWidth: true
                    text: "小智助手 · 拖动此处移动"
                    color: "#334155"
                    font.pixelSize: 12
                    font.bold: true
                }

                ToolButton {
                    text: "收起"
                    Accessible.name: "收起小智助手面板"
                    onClicked: root.closeRequested()
                }
            }

            DragHandler {
                target: root
                xAxis.minimum: 24
                xAxis.maximum: Math.max(24, root.parent.width - root.width - 24)
                yAxis.minimum: 24
                yAxis.maximum: Math.max(24, root.parent.height - root.height - 24)
            }
        }

        AssistantVoiceModeSettings {
            Layout.fillWidth: true
            Layout.leftMargin: 10
            Layout.rightMargin: 10
            viewModelRef: root.viewModelRef
        }

        AssistantPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 8
            Layout.rightMargin: 8
            Layout.bottomMargin: 8
            viewModelRef: root.viewModelRef
        }
    }
}
