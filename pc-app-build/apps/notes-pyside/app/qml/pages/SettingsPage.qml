import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    signal backRequested()

    Rectangle {
        anchors.fill: parent
        color: "#FFFFFF"
        radius: 20

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 18

            RowLayout {
                Layout.fillWidth: true

                Text {
                    Layout.fillWidth: true
                    text: "设置"
                    color: "#111827"
                    font.pixelSize: 26
                    font.bold: true
                }

                AppButton {
                    text: "返回"
                    variant: "ghost"
                    compact: true
                    onClicked: root.backRequested()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 18
                color: "#F7F8FA"
                implicitHeight: 360

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 14

                    Text {
                        text: "服务地址"
                        color: "#111827"
                        font.pixelSize: 18
                        font.bold: true
                    }

                    TextField {
                        Layout.fillWidth: true
                        text: "http://127.0.0.1:18080"
                        placeholderText: "Notes API 地址"
                        readOnly: true

                        background: Rectangle {
                            color: "#FFFFFF"
                            radius: 14
                            border.color: "#E5E7EB"
                        }
                    }

                    TextField {
                        Layout.fillWidth: true
                        text: sidecarClient.wsUrl
                        placeholderText: "Sidecar WebSocket 地址"
                        readOnly: true

                        background: Rectangle {
                            color: "#FFFFFF"
                            radius: 14
                            border.color: "#E5E7EB"
                        }
                    }

                    RowLayout {
                        spacing: 12

                        StatusBadge {
                            text: notesController.apiConnected ? "Notes API 已连接" : "Notes API 未连接"
                            dotColor: notesController.apiConnected ? "#16A34A" : "#EF4444"
                            bgColor: notesController.apiConnected ? "#ECFDF3" : "#FEF2F2"
                            textColor: notesController.apiConnected ? "#166534" : "#991B1B"
                        }

                        StatusBadge {
                            text: sidecarClient.statusText
                            dotColor: sidecarClient.connected ? "#16A34A" : "#F59E0B"
                            bgColor: sidecarClient.connected ? "#ECFDF3" : "#FFF7ED"
                            textColor: sidecarClient.connected ? "#166534" : "#92400E"
                        }

                        StatusBadge {
                            text: "搜索模式：LIKE"
                            dotColor: "#4F7CFF"
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: sidecarClient.notesApiStatusText
                        color: "#4B5563"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        spacing: 12

                        AppButton {
                            text: "测试 Notes API"
                            variant: "secondary"
                            onClicked: notesController.testConnection()
                        }

                        AppButton {
                            text: "刷新 Sidecar 状态"
                            variant: "secondary"
                            onClicked: sidecarClient.refreshStatus()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 18
                color: "#F8FAFC"
                implicitHeight: 300

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            Layout.fillWidth: true
                            text: "py-xiaozhi 运行时"
                            color: "#111827"
                            font.pixelSize: 18
                            font.bold: true
                        }

                        StatusBadge {
                            text: sidecarClient.pyXiaozhiRunning ? "运行中" : "未运行"
                            dotColor: sidecarClient.pyXiaozhiRunning ? "#16A34A" : "#F59E0B"
                            bgColor: sidecarClient.pyXiaozhiRunning ? "#ECFDF3" : "#FFF7ED"
                            textColor: sidecarClient.pyXiaozhiRunning ? "#166534" : "#92400E"
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: sidecarClient.pyXiaozhiStatusText + " · " + sidecarClient.notesToolStatusText
                        color: "#4B5563"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Root: " + (sidecarClient.pyXiaozhiRootText.length > 0 ? sidecarClient.pyXiaozhiRootText : "未确认")
                        color: "#6B7280"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Python: " + (sidecarClient.pyXiaozhiPythonText.length > 0 ? sidecarClient.pyXiaozhiPythonText : "未确认")
                        color: "#6B7280"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: sidecarClient.pyXiaozhiPidsText.length > 0 ? "PID: " + sidecarClient.pyXiaozhiPidsText : "PID: 暂无"
                        color: "#6B7280"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: sidecarClient.lastRuntimeActionText.length > 0
                        text: "最近运行时操作：" + sidecarClient.lastRuntimeActionText
                        color: "#075985"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        spacing: 12

                        AppButton {
                            text: "启动 py-xiaozhi"
                            variant: "primary"
                            enabled: sidecarClient.connected && !sidecarClient.pyXiaozhiRunning && sidecarClient.pyXiaozhiLaunchable
                            onClicked: sidecarClient.startPyXiaozhi()
                        }

                        AppButton {
                            text: "重启"
                            variant: "secondary"
                            enabled: sidecarClient.connected && sidecarClient.pyXiaozhiLaunchable
                            onClicked: sidecarClient.restartPyXiaozhi()
                        }

                        AppButton {
                            text: "停止"
                            variant: "softDanger"
                            enabled: sidecarClient.connected && sidecarClient.pyXiaozhiRunning
                            onClicked: sidecarClient.stopPyXiaozhi()
                        }

                        AppButton {
                            text: "刷新"
                            variant: "ghost"
                            enabled: sidecarClient.connected
                            onClicked: sidecarClient.refreshStatus()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: notesController.errorMessage.length > 0 || sidecarClient.errorMessage.length > 0
                radius: 14
                color: "#FEF2F2"
                implicitHeight: 48

                Text {
                    anchors.centerIn: parent
                    text: notesController.errorMessage.length > 0 ? notesController.errorMessage : sidecarClient.errorMessage
                    color: "#991B1B"
                    font.pixelSize: 13
                }
            }

            Text {
                Layout.fillWidth: true
                text: sidecarClient.lastEventText.length > 0 ? "最近事件：" + sidecarClient.lastEventText : "最近事件：暂无"
                color: "#6B7280"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }

            Item {
                Layout.fillHeight: true
            }
        }
    }
}
