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
                implicitHeight: 300

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
                        background: Rectangle {
                            color: "#FFFFFF"
                            radius: 14
                            border.color: "#E5E7EB"
                        }
                    }

                    TextField {
                        Layout.fillWidth: true
                        text: "ws://127.0.0.1:17890/assistant"
                        placeholderText: "语音助手地址"
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
                            text: "语音助手待接入"
                            dotColor: "#F59E0B"
                            bgColor: "#FFF7ED"
                            textColor: "#92400E"
                        }

                        StatusBadge {
                            text: "搜索模式：LIKE"
                            dotColor: "#4F7CFF"
                        }
                    }

                    AppButton {
                        text: "测试连接"
                        variant: "secondary"
                        onClicked: notesController.testConnection()
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: notesController.errorMessage.length > 0
                radius: 14
                color: "#FEF2F2"
                implicitHeight: 48

                Text {
                    anchors.centerIn: parent
                    text: notesController.errorMessage
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
