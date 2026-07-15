import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var viewModelRef: null
    readonly property bool ready: viewModelRef !== null
    readonly property bool streamingSelected: ready
                                               && viewModelRef.voiceInteractionMode === "streaming_conversation"

    implicitHeight: settingsColumn.implicitHeight + 20
    radius: 12
    color: "#F8FAFC"
    border.color: "#E2E8F0"
    border.width: 1

    ColumnLayout {
        id: settingsColumn
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        Label {
            text: "语音模式"
            color: "#334155"
            font.pixelSize: 12
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Button {
                Layout.fillWidth: true
                text: "按住说话"
                checkable: true
                checked: root.ready
                         && root.viewModelRef.voiceInteractionMode === "hold_to_talk"
                enabled: root.ready && !root.viewModelRef.commandBusy
                onClicked: root.viewModelRef.requestVoiceInteractionMode("hold_to_talk")
            }

            Button {
                Layout.fillWidth: true
                text: "连续对话"
                checkable: true
                checked: root.streamingSelected
                enabled: root.ready && !root.viewModelRef.commandBusy
                onClicked: root.viewModelRef.requestVoiceInteractionMode("streaming_conversation")
            }
        }

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Label {
                    text: "允许插话"
                    color: root.streamingSelected ? "#334155" : "#94A3B8"
                    font.pixelSize: 12
                }
                Label {
                    Layout.fillWidth: true
                    text: root.ready && root.viewModelRef.streamingCapabilityReady
                          ? "回复播放时允许直接说话打断"
                          : "Gate 4.2 激活；当前只保存默认偏好"
                    color: "#94A3B8"
                    font.pixelSize: 10
                    wrapMode: Text.Wrap
                }
            }

            Switch {
                enabled: root.ready
                         && root.streamingSelected
                         && !root.viewModelRef.commandBusy
                checked: root.ready && root.viewModelRef.streamingBargeInEnabled
                onToggled: {
                    if (!root.ready) return
                    if (checked !== root.viewModelRef.streamingBargeInEnabled) {
                        root.viewModelRef.requestStreamingBargeInEnabled(checked)
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.streamingSelected
                     && root.ready
                     && !root.viewModelRef.streamingCapabilityReady
            text: "连续模式已设为默认；真实连续会话将在 Gate 3.3 接通。"
            color: "#B45309"
            font.pixelSize: 10
            wrapMode: Text.Wrap
        }
    }
}
