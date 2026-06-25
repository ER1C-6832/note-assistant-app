import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    signal backRequested()

    function modeIndex(value, modeKind) {
        var model = ["normal", "minimized", "hidden", "debug"]
        if (modeKind === "runtime") {
            model = ["headless", "gui", "cli"]
        } else if (modeKind === "window") {
            model = ["normal", "minimized", "hidden"]
        }
        var idx = model.indexOf(value)
        return idx >= 0 ? idx : 0
    }

    function syncRuntimeForm() {
        if (!rootField.activeFocus && sidecarClient.runtimeConfigRootText.length > 0) {
            rootField.text = sidecarClient.runtimeConfigRootText
        }
        if (!pythonField.activeFocus) {
            pythonField.text = sidecarClient.runtimeConfigPythonText
        }
        if (!runtimeModeBox.activeFocus) {
            runtimeModeBox.currentIndex = modeIndex(sidecarClient.runtimeConfigRuntimeMode, "runtime")
        }
        if (!startModeBox.activeFocus) {
            startModeBox.currentIndex = modeIndex(sidecarClient.runtimeConfigStartMode, "start")
        }
        if (!windowModeBox.activeFocus) {
            windowModeBox.currentIndex = modeIndex(sidecarClient.runtimeConfigWindowMode, "window")
        }
        if (!autoStartBox.activeFocus) {
            autoStartBox.checked = sidecarClient.runtimeConfigAutoStart
        }
        if (!loginPrewarmBox.activeFocus) {
            loginPrewarmBox.checked = sidecarClient.loginPrewarmEnabled
        }
    }

    Connections {
        target: sidecarClient
        function onStatusChanged() { root.syncRuntimeForm() }
    }

    Component.onCompleted: {
        sidecarClient.refreshRuntimeConfig()
        sidecarClient.refreshLoginPrewarmStatus()
        sidecarClient.refreshStatus()
        root.syncRuntimeForm()
    }

    ScrollView {
        id: scrollView
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 18

            Rectangle {
                Layout.fillWidth: true
                radius: 20
                color: "#FFFFFF"
                implicitHeight: 1320

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 28
                    spacing: 18

                    RowLayout {
                        Layout.fillWidth: true
                        Text { Layout.fillWidth: true; text: "设置"; color: "#111827"; font.pixelSize: 26; font.bold: true }
                        AppButton { text: "返回"; variant: "ghost"; compact: true; onClicked: root.backRequested() }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 18
                        color: "#F7F8FA"
                        implicitHeight: 180

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 12

                            Text { text: "基础服务"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                            TextField { Layout.fillWidth: true; text: "http://127.0.0.1:18080"; placeholderText: "Notes API 地址"; readOnly: true; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }
                            TextField { Layout.fillWidth: true; text: sidecarClient.wsUrl; placeholderText: "Sidecar WebSocket 地址"; readOnly: true; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }

                            RowLayout {
                                spacing: 12
                                StatusBadge { text: notesController.apiConnected ? "Notes API 已连接" : "Notes API 未连接"; dotColor: notesController.apiConnected ? "#16A34A" : "#EF4444"; bgColor: notesController.apiConnected ? "#ECFDF3" : "#FEF2F2"; textColor: notesController.apiConnected ? "#166534" : "#991B1B" }
                                StatusBadge { text: sidecarClient.connected ? "Sidecar 已连接" : "Sidecar 未连接"; dotColor: sidecarClient.connected ? "#16A34A" : "#F59E0B"; bgColor: sidecarClient.connected ? "#ECFDF3" : "#FFF7ED"; textColor: sidecarClient.connected ? "#166534" : "#92400E" }
                                StatusBadge { text: sidecarClient.voiceRuntimeReady ? "语音助手已就绪" : sidecarClient.pyXiaozhiRunning ? "语音助手启动中" : "语音助手未启动"; dotColor: sidecarClient.voiceRuntimeReady ? "#16A34A" : "#F59E0B"; bgColor: sidecarClient.voiceRuntimeReady ? "#ECFDF3" : "#FFF7ED"; textColor: sidecarClient.voiceRuntimeReady ? "#166534" : "#92400E" }
                                AppButton { text: "刷新"; variant: "secondary"; compact: true; enabled: sidecarClient.connected; onClicked: sidecarClient.refreshStatus() }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 18
                        color: "#F8FAFC"
                        implicitHeight: 520

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                Text { Layout.fillWidth: true; text: "语音助手运行时"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                                StatusBadge { text: sidecarClient.pyXiaozhiStatusText; dotColor: sidecarClient.voiceRuntimeReady ? "#16A34A" : "#F59E0B"; bgColor: sidecarClient.voiceRuntimeReady ? "#ECFDF3" : "#FFF7ED"; textColor: sidecarClient.voiceRuntimeReady ? "#166534" : "#92400E" }
                            }

                            Text { Layout.fillWidth: true; text: "配置文件：" + (sidecarClient.runtimeConfigEnvPath.length > 0 ? sidecarClient.runtimeConfigEnvPath : "pc-app-build\\.env"); color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { text: "py-xiaozhi 根目录"; color: "#374151"; font.pixelSize: 13; font.bold: true }
                            TextField { id: rootField; Layout.fillWidth: true; placeholderText: "C:\\yuyinzhushou\\py-xiaozhi-tao"; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }
                            Text { text: "Python 解释器，可留空自动检测"; color: "#374151"; font.pixelSize: 13; font.bold: true }
                            TextField { id: pythonField; Layout.fillWidth: true; placeholderText: "留空自动检测 .venv / venv / PATH"; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 16
                                ColumnLayout { Layout.fillWidth: true; Text { text: "运行时模式"; color: "#374151"; font.pixelSize: 13; font.bold: true } ComboBox { id: runtimeModeBox; Layout.fillWidth: true; model: ["headless", "gui", "cli"] } }
                                ColumnLayout { Layout.fillWidth: true; Text { text: "启动模式"; color: "#374151"; font.pixelSize: 13; font.bold: true } ComboBox { id: startModeBox; Layout.fillWidth: true; model: ["normal", "minimized", "hidden", "debug"] } }
                                ColumnLayout { Layout.fillWidth: true; Text { text: "窗口模式"; color: "#374151"; font.pixelSize: 13; font.bold: true } ComboBox { id: windowModeBox; Layout.fillWidth: true; model: ["normal", "minimized", "hidden"] } }
                                ColumnLayout { Layout.preferredWidth: 190; Text { text: "自动拉起"; color: "#374151"; font.pixelSize: 13; font.bold: true } CheckBox { id: autoStartBox; text: "Sidecar 启动时自动启动" } }
                            }

                            RowLayout {
                                spacing: 12
                                AppButton { text: "保存到 .env"; variant: "primary"; enabled: sidecarClient.connected; onClicked: sidecarClient.savePyXiaozhiRuntimeConfig(rootField.text, pythonField.text, runtimeModeBox.currentText, startModeBox.currentText, windowModeBox.currentText, autoStartBox.checked) }
                                AppButton { text: "重新读取配置"; variant: "secondary"; enabled: sidecarClient.connected; onClicked: sidecarClient.refreshRuntimeConfig() }
                                AppButton { text: "刷新诊断"; variant: "ghost"; enabled: sidecarClient.connected; onClicked: sidecarClient.refreshStatus() }
                            }

                            Text { Layout.fillWidth: true; visible: sidecarClient.lastRuntimeConfigText.length > 0; text: "配置状态：" + sidecarClient.lastRuntimeConfigText; color: "#075985"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 18
                        color: "#F8FAFC"
                        implicitHeight: 150

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 12

                            Text { text: "Windows 登录预热"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                            Text { Layout.fillWidth: true; text: "默认关闭。开启后，Windows 登录时会后台启动 Sidecar + py-xiaozhi，打开 App 时可直接复用。"; color: "#6B7280"; font.pixelSize: 13; wrapMode: Text.WordWrap }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                CheckBox { id: loginPrewarmBox; text: "登录后后台预热语音助手" }
                                AppButton { text: "应用"; variant: "primary"; compact: true; enabled: sidecarClient.connected; onClicked: sidecarClient.setLoginPrewarmEnabled(loginPrewarmBox.checked) }
                                AppButton { text: "刷新状态"; variant: "ghost"; compact: true; enabled: sidecarClient.connected; onClicked: sidecarClient.refreshLoginPrewarmStatus() }
                            }

                            Text { Layout.fillWidth: true; text: sidecarClient.loginPrewarmStatusText; color: sidecarClient.loginPrewarmEnabled ? "#166534" : "#92400E"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 18
                        color: "#F8FAFC"
                        implicitHeight: 260

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                Text { Layout.fillWidth: true; text: "运行时诊断"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                                StatusBadge { text: sidecarClient.voiceRuntimeReady ? "可用" : sidecarClient.pyXiaozhiRunning ? "启动中" : "未运行"; dotColor: sidecarClient.voiceRuntimeReady ? "#16A34A" : "#F59E0B"; bgColor: sidecarClient.voiceRuntimeReady ? "#ECFDF3" : "#FFF7ED"; textColor: sidecarClient.voiceRuntimeReady ? "#166534" : "#92400E" }
                            }

                            Text { Layout.fillWidth: true; text: sidecarClient.notesToolStatusText; color: "#4B5563"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; text: "Root: " + (sidecarClient.pyXiaozhiRootText.length > 0 ? sidecarClient.pyXiaozhiRootText : "未确认"); color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; text: "Python: " + (sidecarClient.pyXiaozhiPythonText.length > 0 ? sidecarClient.pyXiaozhiPythonText : "未确认"); color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; text: sidecarClient.pyXiaozhiPidsText.length > 0 ? "PID: " + sidecarClient.pyXiaozhiPidsText : "PID: 暂无"; color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; visible: sidecarClient.lastRuntimeActionText.length > 0; text: "最近运行时操作：" + sidecarClient.lastRuntimeActionText; color: "#075985"; font.pixelSize: 13; wrapMode: Text.WordWrap }

                            RowLayout {
                                spacing: 12
                                AppButton { text: sidecarClient.pyXiaozhiRunning && !sidecarClient.voiceRuntimeReady ? "清理并重启" : "启动 py-xiaozhi"; variant: "primary"; enabled: sidecarClient.connected && !sidecarClient.voiceRuntimeReady && sidecarClient.pyXiaozhiLaunchable; onClicked: sidecarClient.startPyXiaozhi() }
                                AppButton { text: "重启"; variant: "secondary"; enabled: sidecarClient.connected && sidecarClient.pyXiaozhiLaunchable; onClicked: sidecarClient.restartPyXiaozhi() }
                                AppButton { text: "停止"; variant: "softDanger"; enabled: sidecarClient.connected && (sidecarClient.pyXiaozhiRunning || sidecarClient.voiceRuntimeReady); onClicked: sidecarClient.stopPyXiaozhi() }
                                AppButton { text: "刷新"; variant: "ghost"; enabled: sidecarClient.connected; onClicked: sidecarClient.refreshStatus() }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        visible: notesController.errorMessage.length > 0 || sidecarClient.errorMessage.length > 0
                        radius: 14
                        color: "#FEF2F2"
                        implicitHeight: 48
                        Text { anchors.centerIn: parent; text: notesController.errorMessage.length > 0 ? notesController.errorMessage : sidecarClient.errorMessage; color: "#991B1B"; font.pixelSize: 13 }
                    }

                    Text { Layout.fillWidth: true; text: sidecarClient.userVoiceEventText.length > 0 ? "最近语音事件：" + sidecarClient.userVoiceEventText : "最近语音事件：暂无"; color: "#6B7280"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                }
            }
        }
    }
}
