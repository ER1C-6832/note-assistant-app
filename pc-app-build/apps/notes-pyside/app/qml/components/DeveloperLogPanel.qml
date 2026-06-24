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

    function valueOrDash(value) {
        var text = String(value === undefined || value === null ? "" : value)
        return text.length > 0 ? text : "-"
    }

    function rowText(label, value) {
        return label + ": " + valueOrDash(value)
    }

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
            text: "Ctrl+Shift+L 隐藏/显示 · 观测语音助手、工具和 Sidecar 事件"
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
                text: root.hasSidecar ? [
                    root.rowText("Sidecar", sidecarClientRef.statusText),
                    root.rowText("语音状态", sidecarClientRef.assistantStatusText),
                    root.rowText("voiceButtonState", sidecarClientRef.voiceButtonState),
                    root.rowText("runtimeReady", sidecarClientRef.voiceRuntimeReady),
                    "",
                    root.rowText("最近事件", sidecarClientRef.lastEventText),
                    root.rowText("运行时状态", sidecarClientRef.lastRuntimeStateText),
                    root.rowText("控制命令", sidecarClientRef.lastControlText),
                    root.rowText("音频通道", sidecarClientRef.lastAudioChannelText),
                    "",
                    root.rowText("识别文本", sidecarClientRef.lastTranscriptText),
                    root.rowText("助手回复", sidecarClientRef.lastAssistantReplyText),
                    "",
                    root.rowText("工具调用", sidecarClientRef.lastToolEventText),
                    root.rowText("工具结果", sidecarClientRef.lastToolResultText),
                    root.rowText("工具名", sidecarClientRef.lastToolName),
                    root.rowText("工具状态", sidecarClientRef.lastToolStatus),
                    "",
                    root.rowText("py-xiaozhi", sidecarClientRef.pyXiaozhiStatusText),
                    root.rowText("PID", sidecarClientRef.pyXiaozhiPidsText),
                    root.rowText("运行时操作", sidecarClientRef.lastRuntimeActionText),
                    root.rowText("运行时配置", sidecarClientRef.lastRuntimeConfigText),
                    "",
                    root.rowText("runtime log", sidecarClientRef.lastRuntimeLogText),
                    root.rowText("error", sidecarClientRef.errorMessage)
                ].join("\n") : "SidecarClient 未绑定"
            }
        }
    }
}
