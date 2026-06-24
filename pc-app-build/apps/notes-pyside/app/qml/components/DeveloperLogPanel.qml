import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var sidecarClientRef: null
    readonly property bool hasSidecar: sidecarClientRef !== null

    color: "#111827"
    radius: 18
    border.color: "#374151"
    border.width: 1
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                Layout.fillWidth: true
                text: "开发者日志"
                color: "#F9FAFB"
                font.pixelSize: 16
                font.bold: true
            }

            Rectangle {
                width: 9
                height: 9
                radius: 4.5
                color: root.hasSidecar && sidecarClientRef.voiceRuntimeReady ? "#22C55E" : "#F97316"
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Ctrl+Shift+L 隐藏/显示 · 记录启动 py-xiaozhi 到空闲可用的时间线"
            color: "#9CA3AF"
            font.pixelSize: 11
            wrapMode: Text.Wrap
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#374151"
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextArea {
                readOnly: true
                selectByMouse: true
                wrapMode: TextArea.Wrap
                color: "#D1D5DB"
                selectedTextColor: "#111827"
                selectionColor: "#93C5FD"
                font.family: "Consolas"
                font.pixelSize: 11
                background: Rectangle { color: "transparent" }
                text: root.hasSidecar ? sidecarClientRef.developerLogText : "SidecarClient 未绑定"

                onTextChanged: {
                    cursorPosition = length
                }
            }
        }
    }
}
