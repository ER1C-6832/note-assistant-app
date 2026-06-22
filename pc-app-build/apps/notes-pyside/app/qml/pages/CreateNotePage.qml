import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    signal backRequested()
    signal saved()

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
                spacing: 12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "新建便签"
                        color: "#111827"
                        font.pixelSize: 26
                        font.bold: true
                    }

                    Text {
                        text: "填写标题、正文和标签后保存。Phase 3.1 仍为静态 UI，真实写入在 Phase 4 接入。"
                        color: "#6B7280"
                        font.pixelSize: 13
                    }
                }

                AppButton {
                    text: "返回"
                    variant: "ghost"
                    compact: true
                    onClicked: root.backRequested()
                }

                AppButton {
                    text: "保存"
                    variant: "primary"
                    compact: true
                    onClicked: root.saved()
                }
            }

            TextField {
                Layout.fillWidth: true
                height: 48
                placeholderText: "标题"
                text: "屏幕校色记录"
                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 14
                    border.color: "#E5E7EB"
                }
            }

            TextArea {
                Layout.fillWidth: true
                Layout.preferredHeight: 180
                placeholderText: "正文"
                text: "记录 27 寸屏幕亮度、色温和边框间隙。"
                wrapMode: TextArea.Wrap
                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 16
                    border.color: "#E5E7EB"
                }
            }

            TextField {
                Layout.fillWidth: true
                height: 48
                placeholderText: "标签，例如：客户、跟进"
                text: "屏幕, 待办"
                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 14
                    border.color: "#E5E7EB"
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 16
                color: "#E8F9F1"
                implicitHeight: 56

                Text {
                    anchors.centerIn: parent
                    text: "已写入：屏幕校色记录（静态演示状态）"
                    color: "#166534"
                    font.pixelSize: 14
                }
            }

            Item {
                Layout.fillHeight: true
            }
        }
    }
}
