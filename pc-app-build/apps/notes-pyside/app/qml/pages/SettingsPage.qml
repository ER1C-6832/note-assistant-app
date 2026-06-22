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
                        placeholderText: "PC Assistant Sidecar 地址"
                        background: Rectangle {
                            color: "#FFFFFF"
                            radius: 14
                            border.color: "#E5E7EB"
                        }
                    }

                    RowLayout {
                        spacing: 12

                        StatusBadge {
                            text: "Notes API 已连接"
                            dotColor: "#16A34A"
                            bgColor: "#ECFDF3"
                            textColor: "#166534"
                        }

                        StatusBadge {
                            text: "Sidecar 待接入"
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
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: "Phase 3.1 为静态设置页。Phase 4 开始读取 Notes API 状态，Phase 5 接入 Sidecar 状态。"
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
