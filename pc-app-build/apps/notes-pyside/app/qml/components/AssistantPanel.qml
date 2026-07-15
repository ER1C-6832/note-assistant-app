import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var viewModelRef: null
    readonly property bool ready: viewModelRef !== null
    signal textSubmitted(string text)

    radius: 18
    color: "#FFFFFF"
    border.color: "#DCE5F0"
    border.width: 1
    clip: true

    function submitText() {
        if (!ready) return
        var clean = String(messageInput.text).trim()
        if (clean.length === 0) return
        viewModelRef.requestSendText(clean)
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
                    text: root.ready ? root.viewModelRef.statusText : "Runtime 未就绪"
                    color: "#64748B"
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            Switch {
                id: enabledSwitch
                enabled: root.ready && !root.viewModelRef.commandBusy
                checked: root.ready && root.viewModelRef.enabled
                Accessible.name: "启用小智助手"
                onToggled: {
                    if (!root.ready) return
                    if (checked !== root.viewModelRef.enabled) {
                        root.viewModelRef.requestSetEnabled(checked)
                    }
                }
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
                                               : root.viewModelRef.connected ? "#22C55E"
                                               : root.viewModelRef.reconnecting ? "#F59E0B"
                                               : root.viewModelRef.hasRuntimeError ? "#EF4444"
                                               : "#94A3B8"
                    }

                    Label {
                        Layout.fillWidth: true
                        text: root.ready
                              ? root.viewModelRef.phaseText + " · " + root.viewModelRef.connectionStatusText
                              : "未初始化"
                        color: "#334155"
                        font.pixelSize: 13
                        font.bold: true
                    }

                    Label {
                        text: root.ready ? root.viewModelRef.runtimeModeText : ""
                        color: "#2563EB"
                        font.pixelSize: 11
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Button {
                        Layout.fillWidth: true
                        text: root.ready && root.viewModelRef.connected ? "断开" : "连接"
                        enabled: root.ready
                                 && !root.viewModelRef.commandBusy
                                 && (root.viewModelRef.connected
                                     ? root.viewModelRef.canDisconnect
                                     : root.viewModelRef.canConnect)
                        onClicked: {
                            if (root.viewModelRef.connected) {
                                root.viewModelRef.requestDisconnect()
                            } else {
                                root.viewModelRef.requestConnect()
                            }
                        }
                    }

                    Button {
                        text: "重试"
                        visible: root.ready && root.viewModelRef.canRetry
                        enabled: visible && !root.viewModelRef.commandBusy
                        onClicked: root.viewModelRef.requestRetry()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.ready
                     && (root.viewModelRef.hasRuntimeError
                         || root.viewModelRef.operationError.length > 0)
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
                    text: root.viewModelRef.operationError.length > 0
                          ? root.viewModelRef.operationError
                          : root.viewModelRef.errorMessage
                    wrapMode: Text.Wrap
                    color: "#BE123C"
                    font.pixelSize: 12
                }

                Label {
                    visible: root.viewModelRef.errorCode.length > 0
                    text: root.viewModelRef.errorCode
                    color: "#9F1239"
                    font.pixelSize: 10
                }
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
                    visible: root.ready && root.viewModelRef.lastUserText.length > 0
                    implicitHeight: userText.implicitHeight + 20
                    radius: 12
                    color: "#E8F1FF"

                    Label {
                        id: userText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                        text: root.ready ? root.viewModelRef.lastUserText : ""
                        wrapMode: Text.Wrap
                        color: "#1E3A8A"
                        font.pixelSize: 13
                    }
                }

                Rectangle {
                    width: parent.width
                    visible: root.ready && root.viewModelRef.lastAssistantText.length > 0
                    implicitHeight: assistantText.implicitHeight + 20
                    radius: 12
                    color: "#F1F5F9"

                    Label {
                        id: assistantText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                        text: root.ready ? root.viewModelRef.lastAssistantText : ""
                        wrapMode: Text.Wrap
                        color: "#334155"
                        font.pixelSize: 13
                    }
                }

                Label {
                    width: parent.width
                    visible: root.ready
                             && root.viewModelRef.lastUserText.length === 0
                             && root.viewModelRef.lastAssistantText.length === 0
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
                placeholderText: root.ready && root.viewModelRef.connected
                                 ? "输入消息，Ctrl+Enter 发送"
                                 : "请先启用并连接助手"
                enabled: root.ready && root.viewModelRef.canSendText
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
                         && root.viewModelRef.canSendText
                         && !root.viewModelRef.commandBusy
                         && String(messageInput.text).trim().length > 0
                onClicked: root.submitText()
            }
        }

        ToolButton {
            Layout.fillWidth: true
            text: root.ready && root.viewModelRef.developerExpanded
                  ? "收起 Developer 诊断"
                  : "展开 Developer 诊断"
            enabled: root.ready
            onClicked: root.viewModelRef.developerExpanded = !root.viewModelRef.developerExpanded
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: root.ready && root.viewModelRef.developerExpanded ? 310 : 0
            visible: root.ready && root.viewModelRef.developerExpanded
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
                        enabled: !root.viewModelRef.commandBusy
                                 && root.viewModelRef.runtimeMode !== "real"
                        onClicked: root.viewModelRef.requestRuntimeMode("real")
                    }

                    Button {
                        Layout.fillWidth: true
                        text: "Fake"
                        enabled: !root.viewModelRef.commandBusy
                                 && root.viewModelRef.runtimeMode !== "fake"
                        onClicked: root.viewModelRef.requestRuntimeMode("fake")
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
                        text: root.viewModelRef.deviceIdMasked || "未就绪"
                        color: "#334155"
                        elide: Text.ElideMiddle
                    }
                    Label { text: "Client"; color: "#64748B" }
                    Label {
                        Layout.fillWidth: true
                        text: root.viewModelRef.clientIdMasked || "未就绪"
                        color: "#334155"
                        elide: Text.ElideMiddle
                    }
                    Label { text: "Session"; color: "#64748B" }
                    Label {
                        Layout.fillWidth: true
                        text: root.viewModelRef.sessionIdMasked || "无"
                        color: "#334155"
                        elide: Text.ElideMiddle
                    }
                    Label { text: "重连"; color: "#64748B" }
                    Label {
                        Layout.fillWidth: true
                        text: String(root.viewModelRef.reconnectAttempt)
                              + " · " + (root.viewModelRef.reconnectDecision || "无")
                        color: "#334155"
                        elide: Text.ElideRight
                    }
                }

                RowLayout {
                    Layout.fillWidth: true

                    Button {
                        Layout.fillWidth: true
                        text: "运行激活"
                        enabled: !root.viewModelRef.commandBusy
                        onClicked: root.viewModelRef.requestRunActivation()
                    }

                    Button {
                        Layout.fillWidth: true
                        text: "重置身份"
                        enabled: !root.viewModelRef.commandBusy
                        onClicked: root.viewModelRef.requestResetIdentity()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: root.viewModelRef.activationStatus !== "unknown"
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
                            text: "Activation: " + root.viewModelRef.activationStatus
                            color: "#334155"
                            font.bold: true
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: root.viewModelRef.activationCode.length > 0
                            text: "验证码：" + root.viewModelRef.activationCode
                            color: "#2563EB"
                            font.bold: true
                        }
                        Label {
                            Layout.fillWidth: true
                            text: root.viewModelRef.activationMessage
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
                        enabled: root.viewModelRef.connected && !root.viewModelRef.commandBusy
                        onClicked: root.viewModelRef.requestSimulateAbnormalClose()
                    }

                    Button {
                        Layout.fillWidth: true
                        text: "模拟失败"
                        enabled: root.viewModelRef.enabled && !root.viewModelRef.commandBusy
                        onClicked: root.viewModelRef.requestSimulateFailure()
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
                    text: "event: " + (root.viewModelRef.lastProtocolEvent || "-")
                          + "\nclient: " + (root.viewModelRef.lastClientJsonRedacted || "-")
                          + "\nserver: " + (root.viewModelRef.lastServerJsonRedacted || "-")
                          + "\nerror: " + (root.viewModelRef.lastProtocolError || "-")
                    font.pixelSize: 10
                }

                Label {
                    text: "能力状态"
                    color: "#334155"
                    font.bold: true
                }

                Repeater {
                    model: root.viewModelRef.capabilityItems

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
