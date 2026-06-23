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
                implicitHeight: 370

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

                    Text {
                        Layout.fillWidth: true
                        text: sidecarClient.pyXiaozhiStatusText + " · " + sidecarClient.notesToolStatusText
                        color: "#4B5563"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: sidecarClient.lastEventText.length > 0 ? "最近事件：" + sidecarClient.lastEventText : "最近事件：暂无"
                        color: "#6B7280"
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

            Item {
                Layout.fillHeight: true
            }
        }
    }
}
