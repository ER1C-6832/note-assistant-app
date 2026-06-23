import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var deletedNotesModel
    property bool multiSelectMode: false
    property var selectedIds: []
    property bool confirmVisible: false
    property var confirmIds: []
    property string confirmText: ""

    signal backRequested()

    function hasSelected(noteId) {
        return selectedIds.indexOf(noteId) >= 0
    }

    function toggleSelected(noteId) {
        var arr = selectedIds.slice()
        var pos = arr.indexOf(noteId)

        if (pos >= 0) {
            arr.splice(pos, 1)
        } else {
            arr.push(noteId)
        }

        selectedIds = arr
    }

    function allVisibleSelected() {
        return notesController.deletedResultCount > 0 && selectedIds.length === notesController.deletedResultCount
    }

    function toggleSelectAll() {
        if (allVisibleSelected()) {
            selectedIds = []
        } else {
            selectedIds = notesController.currentDeletedNoteIds()
        }
    }

    function exitMultiSelect() {
        multiSelectMode = false
        selectedIds = []
    }

    function askHardDelete(ids, text) {
        confirmIds = ids
        confirmText = text
        confirmVisible = true
    }

    RowLayout {
        anchors.fill: parent
        spacing: 20

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#FFFFFF"
            radius: 20

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: "已删除"
                            color: "#111827"
                            font.pixelSize: 18
                            font.bold: true
                        }

                        Text {
                            text: root.multiSelectMode ? "已选择 " + root.selectedIds.length + " 条便签" : notesController.deletedResultCount + " 条便签"
                            color: "#9CA3AF"
                            font.pixelSize: 12
                        }
                    }

                    AppButton {
                        visible: !root.multiSelectMode
                        text: "多选"
                        variant: "secondary"
                        compact: true
                        onClicked: {
                            root.multiSelectMode = true
                            root.selectedIds = []
                        }
                    }

                    AppButton {
                        visible: !root.multiSelectMode
                        text: "返回全部"
                        variant: "secondary"
                        compact: true
                        onClicked: root.backRequested()
                    }

                    AppButton {
                        visible: root.multiSelectMode
                        text: root.allVisibleSelected() ? "全不选" : "全选"
                        variant: "secondary"
                        compact: true
                        enabled: notesController.deletedResultCount > 0
                        onClicked: root.toggleSelectAll()
                    }

                    AppButton {
                        visible: root.multiSelectMode
                        text: "还原"
                        variant: "secondary"
                        compact: true
                        enabled: root.selectedIds.length > 0
                        onClicked: {
                            notesController.bulkRestoreDeletedNotesByIds(root.selectedIds)
                            root.exitMultiSelect()
                        }
                    }

                    AppButton {
                        visible: root.multiSelectMode
                        text: "彻底删除"
                        variant: "danger"
                        compact: true
                        enabled: root.selectedIds.length > 0
                        onClicked: root.askHardDelete(root.selectedIds, "确认彻底删除选中的 " + root.selectedIds.length + " 条便签吗？")
                    }

                    AppButton {
                        visible: root.multiSelectMode
                        text: "取消"
                        variant: "ghost"
                        compact: true
                        onClicked: root.exitMultiSelect()
                    }
                }

                ListView {
                    id: deletedList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: root.deletedNotesModel
                    spacing: 12
                    clip: true
                    boundsBehavior: Flickable.DragOverBounds
                    rightMargin: 10

                    ScrollBar.vertical: SlimScrollBar {
                        anchors.right: parent.right
                    }

                    delegate: Rectangle {
                        width: ListView.view.width - 14
                        height: 128
                        radius: 18
                        color: "#F3F4F6"
                        border.color: notesController.deletedSelectedIndex === index || root.hasSelected(model.noteId) ? "#4F7CFF" : "transparent"
                        border.width: notesController.deletedSelectedIndex === index || root.hasSelected(model.noteId) ? 2 : 0
                        clip: true

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 14

                            Rectangle {
                                visible: root.multiSelectMode
                                width: 22
                                height: 22
                                radius: 11
                                color: root.hasSelected(model.noteId) ? "#4F7CFF" : "#FFFFFF"
                                border.color: root.hasSelected(model.noteId) ? "#4F7CFF" : "#CBD5E1"
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: "✓"
                                    visible: root.hasSelected(model.noteId)
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 7

                                Text {
                                    Layout.fillWidth: true
                                    text: model.title
                                    color: "#111827"
                                    font.pixelSize: 15
                                    font.bold: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: model.content
                                    color: "#4B5563"
                                    font.pixelSize: 12
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: model.tagsText + " · " + model.updatedText
                                    color: "#6B7280"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }

                            AppButton {
                                visible: !root.multiSelectMode
                                text: "还原"
                                variant: "secondary"
                                compact: true
                                onClicked: notesController.restoreDeletedNoteAt(index)
                            }

                            AppButton {
                                visible: !root.multiSelectMode
                                text: "彻底删除"
                                variant: "danger"
                                compact: true
                                onClicked: root.askHardDelete([model.noteId], "确认彻底删除“" + model.title + "”吗？")
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            anchors.rightMargin: root.multiSelectMode ? 0 : 190
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor

                            onClicked: {
                                if (root.multiSelectMode) {
                                    root.toggleSelected(model.noteId)
                                } else {
                                    notesController.selectDeletedNote(index)
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: notesController.deletedResultCount === 0
                    radius: 18
                    color: "#F7F8FA"

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 10

                        Text {
                            text: "暂无已删除便签"
                            color: "#111827"
                            font.pixelSize: 18
                            font.bold: true
                        }

                        Text {
                            text: "删除后的便签会显示在这里。"
                            color: "#6B7280"
                            font.pixelSize: 13
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.confirmVisible
        color: "#66000000"
        z: 20

        Rectangle {
            width: 460
            height: 230
            radius: 22
            color: "#FFFFFF"
            anchors.centerIn: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 16

                Text {
                    Layout.fillWidth: true
                    text: "彻底删除"
                    color: "#111827"
                    font.pixelSize: 24
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    Layout.fillWidth: true
                    text: root.confirmText
                    color: "#4B5563"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    Layout.fillWidth: true
                    text: "此操作无法恢复。"
                    color: "#DC2626"
                    font.pixelSize: 13
                    horizontalAlignment: Text.AlignHCenter
                }

                Item {
                    Layout.fillHeight: true
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 12

                    AppButton {
                        text: "取消"
                        variant: "secondary"
                        onClicked: root.confirmVisible = false
                    }

                    AppButton {
                        text: "确认彻底删除"
                        variant: "danger"
                        onClicked: {
                            notesController.bulkHardDeleteDeletedNotesByIds(root.confirmIds)
                            root.confirmVisible = false
                            root.exitMultiSelect()
                        }
                    }
                }
            }
        }
    }
}
