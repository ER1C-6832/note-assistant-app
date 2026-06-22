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
    signal saved(string titleText, string contentText, string tagsText)

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
                        text: "修改内容后点击保存。"
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
                    onClicked: root.saved(titleField.text, contentArea.text, tagsField.text)
                }
            }

            TextField {
                id: titleField
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
                id: contentArea
                Layout.fillWidth: true
                Layout.preferredHeight: 260
                text: root.noteContent
                wrapMode: TextArea.Wrap
                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 16
                    border.color: "#E5E7EB"
                }
            }

            TextField {
                id: tagsField
                Layout.fillWidth: true
                height: 48
                text: root.noteTags
                placeholderText: "标签，例如：客户、跟进"
                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 14
                    border.color: "#E5E7EB"
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
