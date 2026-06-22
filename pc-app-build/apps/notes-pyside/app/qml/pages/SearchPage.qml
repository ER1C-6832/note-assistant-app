import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property string keyword: ""
    property var notesModel
    property int selectedIndex: -1

    signal noteSelected(int index)
    signal backRequested()
    signal deleteSelectedRequested()

    RowLayout {
        anchors.fill: parent
        spacing: 20

        Rectangle {
            Layout.preferredWidth: 560
            Layout.fillHeight: true
            color: "#FFFFFF"
            radius: 20

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true

                    ColumnLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "找到 " + notesController.resultCount + " 条相关便签"
                            color: "#111827"
                            font.pixelSize: 18
                            font.bold: true
                        }

                        Text {
                            text: "搜索关键词：“" + root.keyword + "”"
                            color: "#6B7280"
                            font.pixelSize: 12
                        }
                    }

                    AppButton {
                        text: "重置搜索"
                        variant: "secondary"
                        compact: true
                        onClicked: root.backRequested()
                    }
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 12
                    clip: true
                    model: root.notesModel

                    delegate: NoteCard {
                        width: ListView.view.width
                        title: model.title
                        content: model.content
                        tags: model.tagsText
                        updated: model.updatedText
                        source: model.sourceText
                        cardColor: model.cardColor
                        selected: index === root.selectedIndex
                        onClicked: root.noteSelected(index)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        Layout.fillWidth: true
                        text: notesController.hasSelection ? "已选择 1 条便签" : "请选择便签"
                        color: "#4B5563"
                        font.pixelSize: 13
                    }

                    AppButton {
                        text: "删除所选"
                        variant: "softDanger"
                        compact: true
                        enabled: notesController.hasSelection
                        onClicked: root.deleteSelectedRequested()
                    }
                }
            }
        }

        DetailPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            hasSelection: notesController.hasSelection
            title: notesController.selectedTitle
            content: notesController.selectedContent
            tags: notesController.selectedTagsText
            updated: notesController.selectedUpdatedText
            source: notesController.selectedSourceText
            onEditRequested: root.noteSelected(notesController.selectedIndex)
            onDeleteRequested: root.deleteSelectedRequested()
        }
    }
}
