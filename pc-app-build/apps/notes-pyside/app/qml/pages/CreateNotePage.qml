import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var notesViewModelRef: null
    property string initialTags: ""
    property bool initialPinned: false

    readonly property bool viewModelReady: root.notesViewModelRef !== null
    readonly property bool mutationBusy: root.viewModelReady && root.notesViewModelRef.mutationBusy
    readonly property string errorMessage: root.viewModelReady ? root.notesViewModelRef.errorMessage : ""

    signal backRequested()
    signal saved(string titleText, string contentText, string tagsText, bool isPinned)

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
                    Text { text: "新建便签"; color: "#111827"; font.pixelSize: 26; font.bold: true }
                    Text {
                        text: root.initialTags.length > 0 || root.initialPinned ? "已根据当前分类预填默认属性。" : "记录新的想法、客户事项或待办。"
                        color: "#6B7280"
                        font.pixelSize: 13
                    }
                }

                AppButton {
                    text: "返回"
                    variant: "ghost"
                    compact: true
                    enabled: !root.mutationBusy
                    onClicked: root.backRequested()
                }
                AppButton {
                    text: root.mutationBusy ? "保存中…" : "保存"
                    variant: "primary"
                    compact: true
                    enabled: root.viewModelReady && !root.mutationBusy
                    onClicked: root.saved(
                        titleField.text,
                        contentArea.text,
                        tagsField.text,
                        pinnedCheck.checked
                    )
                }
            }

            TextField {
                id: titleField
                Layout.fillWidth: true
                height: 48
                placeholderText: "标题"
                enabled: !root.mutationBusy
                background: Rectangle { color: "#F7F8FA"; radius: 14; border.color: "#E5E7EB" }
            }

            TextArea {
                id: contentArea
                Layout.fillWidth: true
                Layout.preferredHeight: 220
                placeholderText: "正文"
                wrapMode: TextArea.Wrap
                enabled: !root.mutationBusy
                background: Rectangle { color: "#F7F8FA"; radius: 16; border.color: "#E5E7EB" }
            }

            TextField {
                id: tagsField
                Layout.fillWidth: true
                height: 48
                text: root.initialTags
                placeholderText: "标签，例如：客户、跟进"
                enabled: !root.mutationBusy
                background: Rectangle { color: "#F7F8FA"; radius: 14; border.color: "#E5E7EB" }
            }

            CheckBox {
                id: pinnedCheck
                text: "置顶"
                checked: root.initialPinned
                enabled: !root.mutationBusy
                font.pixelSize: 14
            }

            Rectangle {
                Layout.fillWidth: true
                visible: root.errorMessage.length > 0
                radius: 14
                color: "#FEF2F2"
                implicitHeight: 48
                Text {
                    anchors.centerIn: parent
                    text: root.errorMessage
                    color: "#991B1B"
                    font.pixelSize: 13
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
