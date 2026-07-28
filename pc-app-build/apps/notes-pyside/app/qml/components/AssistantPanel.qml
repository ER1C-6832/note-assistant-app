import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var viewModelRef: null
    readonly property bool ready: viewModelRef !== null
    readonly property var model: ready ? viewModelRef : fallbackModel
    property bool pttPressOwned: false

    QtObject {
        id: fallbackModel
        readonly property string statusText: "Runtime 未就绪"
        readonly property bool commandBusy: false
        readonly property bool enabled: false
        readonly property bool connected: false
        readonly property bool reconnecting: false
        readonly property bool hasRuntimeError: false
        readonly property bool canConnect: false
        readonly property bool canDisconnect: false
        readonly property bool canRetry: false
        readonly property bool canSendText: false
        readonly property bool canPushToTalk: false
        readonly property bool pushToTalkActive: false
        readonly property bool pushToTalkRecording: false
        readonly property bool pushToTalkStopping: false
        readonly property bool streamingConversationActive: false
        readonly property string streamingConversationState: "inactive"
        readonly property int streamingTurnIndex: 0
        readonly property string vadState: "disabled"
        readonly property string vadStatusText: "VAD 未启用"
        readonly property bool canStartStreamingConversation: false
        readonly property bool canStopStreamingConversation: false
        readonly property string phaseText: "未初始化"
        readonly property string connectionStatusText: "未连接"
        readonly property string runtimeMode: "real"
        readonly property string runtimeModeText: "真实"
        readonly property string voiceInteractionMode: "hold_to_talk"
        readonly property string operationError: ""
        readonly property string errorCode: ""
        readonly property string errorMessage: ""
        readonly property string lastUserText: ""
        readonly property string lastAssistantText: ""
        readonly property string deviceIdMasked: ""
        readonly property string clientIdMasked: ""
        readonly property string sessionIdMasked: ""
        readonly property int reconnectAttempt: 0
        readonly property string reconnectDecision: ""
        readonly property string activationStatus: "unknown"
        readonly property string activationCode: ""
        readonly property string activationMessage: ""
        readonly property string lastProtocolEvent: ""
        readonly property string lastClientJsonRedacted: ""
        readonly property string lastServerJsonRedacted: ""
        readonly property string lastProtocolError: ""
        readonly property var capabilityItems: []
        property bool developerExpanded: false
        function requestSetEnabled(value) {}
        function requestConnect() {}
        function requestDisconnect() {}
        function requestRetry() {}
        function requestSendText(value) {}
        function requestRuntimeMode(value) {}
        function requestRunActivation() {}
        function requestResetIdentity() {}
        function requestSimulateAbnormalClose() {}
        function requestSimulateFailure() {}
        function requestPushToTalkStart() {}
        function requestPushToTalkStop() {}
        function requestStreamingConversationStart() {}
        function requestStreamingConversationStop() {}
        function requestStreamingConversationToggle() {}
    }
    signal textSubmitted(string text)

    radius: 18
    color: "#FFFFFF"
    border.color: "#DCE5F0"
    border.width: 1
    clip: true

    function releaseOwnedPtt() {
        if (!pttPressOwned) return
        pttPressOwned = false
        model.requestPushToTalkStop()
    }

    onVisibleChanged: {
        if (!visible) releaseOwnedPtt()
    }

    Component.onDestruction: releaseOwnedPtt()

    function submitText() {
        if (!ready) return
        var clean = String(messageInput.text).trim()
        if (clean.length === 0) return
        root.model.requestSendText(clean)
        root.textSubmitted(clean)
        messageInput.clear()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Rectangle {
                width: 38
                height: 38
                radius: 12
                color: "#E8F1FF"

                Label {
                    anchors.centerIn: parent
                    text: "智"
                    color: "#2563EB"
                    font.pixelSize: 18
                    font.bold: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Label {
                    text: "小智助手"
                    color: "#172033"
                    font.pixelSize: 18
                    font.bold: true
                }

                Label {
                    text: root.ready ? root.model.statusText : "Runtime 未就绪"
                    color: "#64748B"
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            Label {
                text: root.ready && root.model.enabled ? "已启用" : "初始化中"
                color: root.ready && root.model.enabled ? "#047857" : "#64748B"
                font.pixelSize: 11
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 76
            radius: 14
            color: "#F8FAFC"
            border.color: "#E2E8F0"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true

                    Rectangle {
                        width: 9
                        height: 9
                        radius: 5
                        color: !root.ready ? "#94A3B8"
                                               : root.model.connected ? "#22C55E"
                                               : root.model.reconnecting ? "#F59E0B"
                                               : root.model.hasRuntimeError ? "#EF4444"
                                               : "#94A3B8"
                    }

                    Label {
                        Layout.fillWidth: true
                        text: root.ready
                              ? root.model.phaseText + " · " + root.model.connectionStatusText
                              : "未初始化"
                        color: "#334155"
                        font.pixelSize: 13
                        font.bold: true
                    }

                    Label {
                        text: root.ready ? root.model.runtimeModeText : ""
                        color: "#2563EB"
                        font.pixelSize: 11
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Button {
                        Layout.fillWidth: true
                        text: root.ready && root.model.connected ? "断开" : "连接"
                        enabled: root.ready
                                 && !root.model.commandBusy
                                 && (root.model.connected
                                     ? root.model.canDisconnect
                                     : root.model.canConnect)
                        onClicked: {
                            if (root.model.connected) {
                                root.model.requestDisconnect()
                            } else {
                                root.model.requestConnect()
                            }
                        }
                    }

                    Button {
                        text: "重试"
                        visible: root.ready && root.model.canRetry
                        enabled: visible && !root.model.commandBusy
                        onClicked: root.model.requestRetry()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.ready
                     && (root.model.hasRuntimeError
                         || root.model.operationError.length > 0)
            implicitHeight: errorColumn.implicitHeight + 20
            radius: 12
            color: "#FFF1F2"
            border.color: "#FECDD3"

            ColumnLayout {
                id: errorColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 4

                Label {
                    Layout.fillWidth: true
                    text: root.model.operationError.length > 0
                          ? root.model.operationError
                          : root.model.errorMessage
                    wrapMode: Text.Wrap
                    color: "#BE123C"
                    font.pixelSize: 12
                }

                Label {
                    visible: root.model.errorCode.length > 0
                    text: root.model.errorCode
                    color: "#9F1239"
                    font.pixelSize: 10
                }
            }
        }

        Button {
            id: pushToTalkButton
            objectName: "assistantPushToTalkButton"
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            visible: root.model.voiceInteractionMode === "hold_to_talk"
            enabled: root.ready
                     && !root.model.pushToTalkStopping
                     && (root.model.canPushToTalk || root.model.pushToTalkActive)
            text: root.model.pushToTalkRecording
                  ? "正在聆听 · 松开提交"
                  : root.model.pushToTalkStopping
                    ? "正在提交语音…"
                    : "按住说话"
            Accessible.name: "按住说话"

            onPressed: {
                if (!root.model.canPushToTalk || root.pttPressOwned) return
                root.pttPressOwned = true
                root.model.requestPushToTalkStart()
            }
            onReleased: root.releaseOwnedPtt()
            onCanceled: root.releaseOwnedPtt()
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: root.model.voiceInteractionMode === "streaming_conversation"

            Button {
                id: streamingConversationButton
                objectName: "assistantStreamingConversationButton"
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                enabled: root.ready
                         && !root.model.commandBusy
                         && (root.model.streamingConversationActive
                             ? root.model.canStopStreamingConversation
                             : root.model.canStartStreamingConversation)
                text: root.model.streamingConversationActive
                      ? "停止连续对话"
                      : "开始连续对话"
                Accessible.name: text
                onClicked: root.model.requestStreamingConversationToggle()
            }

            Label {
                objectName: "assistantStreamingVadStatus"
                Layout.fillWidth: true
                visible: root.model.streamingConversationActive
                text: root.model.vadStatusText
                      + (root.model.streamingTurnIndex > 0
                         ? " · 第 " + root.model.streamingTurnIndex + " 轮"
                         : "")
                color: root.model.vadState === "speech_active"
                       || root.model.vadState === "speech_detected"
                       ? "#C2410C"
                       : "#64748B"
                font.pixelSize: 11
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }
        }

        Label {
            text: "最近对话"
            color: "#334155"
            font.pixelSize: 13
            font.bold: true
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 150
            clip: true

            Column {
                width: parent.width
                spacing: 10

                Rectangle {
                    width: parent.width
                    visible: root.ready && root.model.lastUserText.length > 0
                    implicitHeight: userText.implicitHeight + 20
                    radius: 12
                    color: "#E8F1FF"

                    Label {
                        id: userText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                        text: root.ready ? root.model.lastUserText : ""
                        wrapMode: Text.Wrap
                        color: "#1E3A8A"
                        font.pixelSize: 13
                    }
                }

                Rectangle {
                    width: parent.width
                    visible: root.ready && root.model.lastAssistantText.length > 0
                    implicitHeight: assistantText.implicitHeight + 20
                    radius: 12
                    color: "#F1F5F9"

                    Label {
                        id: assistantText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                        text: root.ready ? root.model.lastAssistantText : ""
                        wrapMode: Text.Wrap
                        color: "#334155"
                        font.pixelSize: 13
                    }
                }

                Label {
                    width: parent.width
                    visible: root.ready
                             && root.model.lastUserText.length === 0
                             && root.model.lastAssistantText.length === 0
                    text: "连接后可直接输入文本与小智对话。"
                    wrapMode: Text.Wrap
                    color: "#94A3B8"
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextArea {
                id: messageInput
                Layout.fillWidth: true
                Layout.preferredHeight: 68
                placeholderText: root.ready && root.model.connected
                                 ? "输入消息，Ctrl+Enter 发送"
                                 : "请先启用并连接助手"
                enabled: root.ready && root.model.canSendText
                wrapMode: TextEdit.Wrap
                selectByMouse: true

                Keys.onPressed: function(event) {
                    if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Return) {
                        root.submitText()
                        event.accepted = true
                    }
                }
            }

            Button {
                text: "发送"
                enabled: root.ready
                         && root.model.canSendText
                         && !root.model.commandBusy
                         && String(messageInput.text).trim().length > 0
                onClicked: root.submitText()
            }
        }

        ToolButton {
            Layout.fillWidth: true
            text: root.ready && root.model.developerExpanded
                  ? "收起 Developer 诊断"
                  : "展开 Developer 诊断"
            enabled: root.ready
            onClicked: root.model.developerExpanded = !root.model.developerExpanded
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: root.ready && root.model.developerExpanded ? 310 : 0
            visible: root.ready && root.model.developerExpanded
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 10

                Label {
                    text: "Runtime"
                    color: "#334155"
                    font.bold: true
                }

                RowLayout {
                    Layout.fillWidth: true

                    Button {
                        Layout.fillWidth: true
                        text: "真实"
                        enabled: !root.model.commandBusy
                                 && root.model.runtimeMode !== "real"
                        onClicked: root.model.requestRuntimeMode("real")
                    }

                    Button {
                        Layout.fillWidth: true
                        text: "Fake"
                        enabled: !root.model.commandBusy
                                 && root.model.runtimeMode !== "fake"
                        onClicked: root.model.requestRuntimeMode("fake")
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 8
                    rowSpacing: 4

                    Label { text: "Device"; color: "#64748B" }
                    Label {
                        Layout.fillWidth: true
                        text: root.model.deviceIdMasked || "未就绪"
                        color: "#334155"
                        elide: Text.ElideMiddle
                    }
                    Label { text: "Client"; color: "#64748B" }
                    Label {
                        Layout.fillWidth: true
                        text: root.model.clientIdMasked || "未就绪"
                        color: "#334155"
                        elide: Text.ElideMiddle
                    }
                    Label { text: "Session"; color: "#64748B" }
                    Label {
                        Layout.fillWidth: true
                        text: root.model.sessionIdMasked || "无"
                        color: "#334155"
                        elide: Text.ElideMiddle
                    }
                    Label { text: "重连"; color: "#64748B" }
                    Label {
                        Layout.fillWidth: true
                        text: String(root.model.reconnectAttempt)
                              + " · " + (root.model.reconnectDecision || "无")
                        color: "#334155"
                        elide: Text.ElideRight
                    }
                }

                RowLayout {
                    Layout.fillWidth: true

                    Button {
                        Layout.fillWidth: true
                        text: "运行激活"
                        enabled: !root.model.commandBusy
                        onClicked: root.model.requestRunActivation()
                    }

                    Button {
                        Layout.fillWidth: true
                        text: "重置身份"
                        enabled: !root.model.commandBusy
                        onClicked: root.model.requestResetIdentity()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: root.model.activationStatus !== "unknown"
                    implicitHeight: activationColumn.implicitHeight + 16
                    radius: 10
                    color: "#F8FAFC"
                    border.color: "#E2E8F0"

                    ColumnLayout {
                        id: activationColumn
                        anchors.fill: parent
                        anchors.margins: 8

                        Label {
                            Layout.fillWidth: true
                            text: "Activation: " + root.model.activationStatus
                            color: "#334155"
                            font.bold: true
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: root.model.activationCode.length > 0
                            text: "验证码：" + root.model.activationCode
                            color: "#2563EB"
                            font.bold: true
                        }
                        Label {
                            Layout.fillWidth: true
                            text: root.model.activationMessage
                            wrapMode: Text.Wrap
                            color: "#64748B"
                            font.pixelSize: 11
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true

                    Button {
                        Layout.fillWidth: true
                        text: "模拟异常断线"
                        enabled: root.model.connected && !root.model.commandBusy
                        onClicked: root.model.requestSimulateAbnormalClose()
                    }

                    Button {
                        Layout.fillWidth: true
                        text: "模拟失败"
                        enabled: root.model.enabled && !root.model.commandBusy
                        onClicked: root.model.requestSimulateFailure()
                    }
                }

                Label {
                    text: "Token 与预算"
                    color: "#334155"
                    font.bold: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: tokenBudgetColumn.implicitHeight + 16
                    radius: 10
                    color: root.model.tokenUsageAvailable
                           ? (root.model.tokenBudgetStatus === "已阻断"
                              ? "#FEF2F2" : "#F8FAFC")
                           : "#F8FAFC"
                    border.color: root.model.tokenBudgetStatus === "已阻断"
                                  ? "#FCA5A5" : "#E2E8F0"

                    ColumnLayout {
                        id: tokenBudgetColumn
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true

                            Label {
                                Layout.fillWidth: true
                                text: root.model.tokenBudgetStatus
                                color: root.model.tokenBudgetStatus === "已阻断"
                                       ? "#B91C1C" : "#334155"
                                font.bold: true
                            }

                            Label {
                                text: String(root.model.tokenBudgetProgress) + "%"
                                color: "#64748B"
                                font.pixelSize: 11
                            }
                        }

                        ProgressBar {
                            Layout.fillWidth: true
                            from: 0
                            to: 100
                            value: root.model.tokenBudgetProgress
                            visible: root.model.tokenUsageAvailable
                        }

                        Label {
                            Layout.fillWidth: true
                            text: root.model.tokenUsageSummary
                            wrapMode: Text.Wrap
                            color: "#475569"
                            font.pixelSize: 10
                        }
                    }
                }

                Label {
                    text: "协议（已脱敏）"
                    color: "#334155"
                    font.bold: true
                }

                TextArea {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 92
                    readOnly: true
                    wrapMode: TextEdit.WrapAnywhere
                    text: "event: " + (root.model.lastProtocolEvent || "-")
                          + "\nclient: " + (root.model.lastClientJsonRedacted || "-")
                          + "\nserver: " + (root.model.lastServerJsonRedacted || "-")
                          + "\nerror: " + (root.model.lastProtocolError || "-")
                    font.pixelSize: 10
                }

                Label {
                    text: "能力状态"
                    color: "#334155"
                    font.bold: true
                }

                Repeater {
                    model: root.model.capabilityItems

                    delegate: RowLayout {
                        required property var modelData
                        width: parent.width

                        Label {
                            Layout.fillWidth: true
                            text: modelData.name + " · Gate " + modelData.targetGate
                            color: "#475569"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }

                        Label {
                            text: modelData.status
                            color: modelData.status === "active" ? "#15803D" : "#94A3B8"
                            font.pixelSize: 10
                        }
                    }
                }
            }
        }
    }
}
