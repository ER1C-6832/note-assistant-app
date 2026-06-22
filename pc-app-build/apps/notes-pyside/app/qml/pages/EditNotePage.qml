import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property string noteTitle: ""
    property string noteContent: ""
    property string noteTags: ""

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
                        text: "编辑便签"
                        color: "#111827"
                        font.pixelSize: 26
                        font.bold: true
                    }

                    Text {
                        text: "Phase 3.1 展示编辑 UI；Phase 4 接入 PATCH /api/notes/{id}。"
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
                    text: "保存修改"
                    variant: "primary"
                    compact: true
                    onClicked: root.saved()
                }
            }

            TextField {
                Layout.fillWidth: true
                height: 48
                text: root.noteTitle
                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 14
                    border.color: "#E5E7EB"
                }
            }

            TextArea {
                Layout.fillWidth: true
                Layout.preferredHeight: 220
                text: root.noteContent + "\n\n备注：这里是编辑后的静态演示内容。"
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
                text: root.noteTags
                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 14
                    border.color: "#E5E7EB"
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 16
                color: "#EAF0FF"
                implicitHeight: 56

                Text {
                    anchors.centerIn: parent
                    text: "修改已保存（静态演示状态）"
                    color: "#1E3A8A"
                    font.pixelSize: 14
                }
            }

            Item {
                Layout.fillHeight: true
            }
        }
    }
}
