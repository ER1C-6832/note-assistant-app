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
            loginPrewarmBox.checked = loginPrewarmController.loginPrewarmEnabled
        }
        if (voiceModeController !== null && !continuousConversationBox.activeFocus) {
            continuousConversationBox.checked = voiceModeController.continuousConversationEnabled
        }
    }

    Connections {
        target: sidecarClient
        function onStatusChanged() { root.syncRuntimeForm() }
    }

    Connections {
        target: loginPrewarmController
        function onStatusChanged() { root.syncRuntimeForm() }
    }

    Connections {
        target: voiceModeController
        function onStatusChanged() { root.syncRuntimeForm() }
    }

    Component.onCompleted: {
        sidecarClient.refreshRuntimeConfig()
        loginPrewarmController.refreshLoginPrewarmStatus()
        if (voiceModeController !== null) {
            voiceModeController.refreshVoiceModeStatus()
        }
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
                implicitHeight: 1510

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

                            Text { text: "连接状态"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                            TextField { Layout.fillWidth: true; text: "http://127.0.0.1:18080"; placeholderText: "便签服务地址"; readOnly: true; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }
                            TextField { Layout.fillWidth: true; text: sidecarClient.wsUrl; placeholderText: "语音桥接地址"; readOnly: true; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }

                            RowLayout {
                                spacing: 12
                                StatusBadge { text: notesController.apiConnected ? "Notes API 已连接" : "Notes API 未连接"; dotColor: notesController.apiConnected ? "#16A34A" : "#EF4444"; bgColor: notesController.apiConnected ? "#ECFDF3" : "#FEF2F2"; textColor: notesController.apiConnected ? "#166534" : "#991B1B" }
                                StatusBadge { text: sidecarClient.connected ? "本地助手已连接" : "本地助手未连接"; dotColor: sidecarClient.connected ? "#16A34A" : "#F59E0B"; bgColor: sidecarClient.connected ? "#ECFDF3" : "#FFF7ED"; textColor: sidecarClient.connected ? "#166534" : "#92400E" }
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
                                Text { Layout.fillWidth: true; text: "语音助手"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                                StatusBadge { text: sidecarClient.pyXiaozhiStatusText; dotColor: sidecarClient.voiceRuntimeReady ? "#16A34A" : "#F59E0B"; bgColor: sidecarClient.voiceRuntimeReady ? "#ECFDF3" : "#FFF7ED"; textColor: sidecarClient.voiceRuntimeReady ? "#166534" : "#92400E" }
                            }

                            Text { Layout.fillWidth: true; text: "高级配置：" + (sidecarClient.runtimeConfigEnvPath.length > 0 ? sidecarClient.runtimeConfigEnvPath : "pc-app-build\\.env"); color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; text: "普通演示无需修改路径；只有移动语音助手目录或 Python 环境时才需要调整。"; color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { text: "语音助手程序目录"; color: "#374151"; font.pixelSize: 13; font.bold: true }
                            TextField { id: rootField; Layout.fillWidth: true; placeholderText: "默认自动检测，也可指定语音助手目录"; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }
                            Text { text: "启动程序，可留空自动检测"; color: "#374151"; font.pixelSize: 13; font.bold: true }
                            TextField { id: pythonField; Layout.fillWidth: true; placeholderText: "留空时自动使用内置虚拟环境或系统 Python"; background: Rectangle { color: "#FFFFFF"; radius: 14; border.color: "#E5E7EB" } }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 16
                                ColumnLayout { Layout.fillWidth: true; Text { text: "运行方式"; color: "#374151"; font.pixelSize: 13; font.bold: true } ComboBox {
                                        id: runtimeModeBox
                                        Layout.fillWidth: true
                                        model: ["headless", "gui", "cli"]
                                        onActivated: {
                                            if (currentText === "gui") {
                                                startModeBox.currentIndex = modeIndex("normal", "start")
                                                windowModeBox.currentIndex = modeIndex("normal", "window")
                                            }
                                        }
                                    } }
                                ColumnLayout { Layout.fillWidth: true; Text { text: "启动窗口"; color: "#374151"; font.pixelSize: 13; font.bold: true } ComboBox { id: startModeBox; Layout.fillWidth: true; model: ["normal", "minimized", "hidden", "debug"] } }
                                ColumnLayout { Layout.fillWidth: true; Text { text: "运行窗口"; color: "#374151"; font.pixelSize: 13; font.bold: true } ComboBox { id: windowModeBox; Layout.fillWidth: true; model: ["normal", "minimized", "hidden"] } }
                                ColumnLayout { Layout.preferredWidth: 190; Text { text: "自动准备"; color: "#374151"; font.pixelSize: 13; font.bold: true } CheckBox { id: autoStartBox; text: "打开应用时准备语音" } }
                            }

                            RowLayout {
                                spacing: 12
                                AppButton { text: "保存设置"; variant: "primary"; enabled: sidecarClient.connected; onClicked: sidecarClient.savePyXiaozhiRuntimeConfig(rootField.text, pythonField.text, runtimeModeBox.currentText, startModeBox.currentText, windowModeBox.currentText, autoStartBox.checked) }
                                AppButton { text: "重新读取"; variant: "secondary"; enabled: sidecarClient.connected; onClicked: sidecarClient.refreshRuntimeConfig() }
                                AppButton { text: "刷新状态"; variant: "ghost"; enabled: sidecarClient.connected; onClicked: sidecarClient.refreshStatus() }
                            }

                            Text { Layout.fillWidth: true; visible: sidecarClient.lastRuntimeConfigText.length > 0; text: "保存结果：" + sidecarClient.lastRuntimeConfigText; color: "#075985"; font.pixelSize: 13; wrapMode: Text.WordWrap }
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

                            Text { text: "开机后后台准备"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                            Text { Layout.fillWidth: true; text: "默认关闭。开启后，Windows 登录时会在后台准备语音助手，之后打开应用会更快；关闭后不会常驻后台 Python 进程。"; color: "#6B7280"; font.pixelSize: 13; wrapMode: Text.WordWrap }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                CheckBox { id: loginPrewarmBox; text: "登录 Windows 后自动准备语音助手" }
                                AppButton { text: "应用"; variant: "primary"; compact: true; enabled: sidecarClient.connected; onClicked: loginPrewarmController.setLoginPrewarmEnabled(loginPrewarmBox.checked) }
                                AppButton { text: "刷新状态"; variant: "ghost"; compact: true; enabled: sidecarClient.connected; onClicked: loginPrewarmController.refreshLoginPrewarmStatus() }
                            }

                            Text { Layout.fillWidth: true; text: loginPrewarmController.loginPrewarmStatusText; color: loginPrewarmController.loginPrewarmEnabled ? "#166534" : "#92400E"; font.pixelSize: 13; wrapMode: Text.WordWrap }
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

                            Text { text: "连续对话"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                            Text { Layout.fillWidth: true; text: "开启后，点击说话会进入免按住连续对话；助手播报结束后会继续聆听。关闭后仍是单轮语音操作。唤醒词保持关闭。"; color: "#6B7280"; font.pixelSize: 13; wrapMode: Text.WordWrap }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                CheckBox { id: continuousConversationBox; text: "点击说话后保持连续聆听" }
                                AppButton { text: "应用"; variant: "primary"; compact: true; onClicked: voiceModeController.setContinuousConversationEnabled(continuousConversationBox.checked) }
                                AppButton { text: "刷新状态"; variant: "ghost"; compact: true; onClicked: voiceModeController.refreshVoiceModeStatus() }
                            }

                            Text { Layout.fillWidth: true; text: voiceModeController.continuousConversationStatusText; color: voiceModeController.continuousConversationEnabled ? "#166534" : "#92400E"; font.pixelSize: 13; wrapMode: Text.WordWrap }
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
                                Text { Layout.fillWidth: true; text: "语音助手状态"; color: "#111827"; font.pixelSize: 18; font.bold: true }
                                StatusBadge { text: sidecarClient.voiceRuntimeReady ? "可用" : sidecarClient.pyXiaozhiRunning ? "启动中" : "未运行"; dotColor: sidecarClient.voiceRuntimeReady ? "#16A34A" : "#F59E0B"; bgColor: sidecarClient.voiceRuntimeReady ? "#ECFDF3" : "#FFF7ED"; textColor: sidecarClient.voiceRuntimeReady ? "#166534" : "#92400E" }
                            }

                            Text { Layout.fillWidth: true; text: sidecarClient.notesToolStatusText; color: "#4B5563"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; text: "程序目录：" + (sidecarClient.pyXiaozhiRootText.length > 0 ? sidecarClient.pyXiaozhiRootText : "未确认"); color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; text: "启动程序：" + (sidecarClient.pyXiaozhiPythonText.length > 0 ? sidecarClient.pyXiaozhiPythonText : "未确认"); color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; text: sidecarClient.pyXiaozhiPidsText.length > 0 ? "后台进程：" + sidecarClient.pyXiaozhiPidsText : "后台进程：暂无"; color: "#6B7280"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            Text { Layout.fillWidth: true; visible: sidecarClient.lastRuntimeActionText.length > 0; text: "最近操作：" + sidecarClient.lastRuntimeActionText; color: "#075985"; font.pixelSize: 13; wrapMode: Text.WordWrap }

                            RowLayout {
                                spacing: 12
                                AppButton { text: sidecarClient.pyXiaozhiRunning && !sidecarClient.voiceRuntimeReady ? "修复并重启" : "启动语音助手"; variant: "primary"; enabled: sidecarClient.connected && !sidecarClient.voiceRuntimeReady && sidecarClient.pyXiaozhiLaunchable; onClicked: sidecarClient.startPyXiaozhi() }
                                AppButton { text: "重启助手"; variant: "secondary"; enabled: sidecarClient.connected && sidecarClient.pyXiaozhiLaunchable; onClicked: sidecarClient.restartPyXiaozhi() }
                                AppButton { text: "停止助手"; variant: "softDanger"; enabled: sidecarClient.connected && (sidecarClient.pyXiaozhiRunning || sidecarClient.voiceRuntimeReady); onClicked: sidecarClient.stopPyXiaozhi() }
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

                    Text { Layout.fillWidth: true; text: sidecarClient.userVoiceEventText.length > 0 ? "最近语音提示：" + sidecarClient.userVoiceEventText : "最近语音提示：暂无"; color: "#6B7280"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                }
            }
        }
    }
}
