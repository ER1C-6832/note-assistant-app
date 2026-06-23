import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var notesModel
    property var notesControllerRef: null
    property int selectedIndex: -1
    property string activeCategory: "all"
    property bool showCreateButton: true
    property bool multiSelectMode: false
    property var selectedIds: []

    readonly property bool controllerReady: root.notesControllerRef !== null
    readonly property int safeResultCount: root.controllerReady ? root.notesControllerRef.resultCount : 0
    readonly property string safeErrorMessage: root.controllerReady ? root.notesControllerRef.errorMessage : ""

    signal noteSelected(int index)
    signal createRequested()
    signal bulkDeleteRequested(var noteIds)
    signal bulkPinRequested(var noteIds)
    signal bulkUnpinRequested(var noteIds)

    function categoryTitle() {
        if (activeCategory === "pinned") {
            return "置顶便签"
        }
        if (activeCategory === "todo") {
            return "待办便签"
        }
        if (activeCategory === "search") {
            return "搜索结果"
        }
        if (activeCategory.indexOf("tag:") === 0) {
            return activeCategory.substring(4)
        }
        return "全部便签"
    }

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
        return root.safeResultCount > 0 && selectedIds.length === root.safeResultCount
    }

    function toggleSelectAll() {
        if (allVisibleSelected()) {
            selectedIds = []
        } else if (root.controllerReady) {
            selectedIds = root.notesControllerRef.currentNoteIds()
        } else {
            selectedIds = []
        }
    }

    function exitMultiSelect() {
        multiSelectMode = false
        selectedIds = []
    }

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
                    text: root.categoryTitle()
                    color: "#111827"
                    font.pixelSize: 18
                    font.bold: true
                }

                Text {
                    text: root.multiSelectMode ? "已选择 " + root.selectedIds.length + " 条便签" : root.safeResultCount + " 条便签"
                    color: "#9CA3AF"
                    font.pixelSize: 12
                }
            }

            AppButton {
                visible: !root.multiSelectMode
                text: "多选"
                variant: "secondary"
                compact: true
                enabled: root.controllerReady
                onClicked: {
                    root.multiSelectMode = true
                    root.selectedIds = []
                }
            }

            AppButton {
                visible: !root.multiSelectMode && root.showCreateButton
                text: "+ 新建"
                variant: "primary"
                compact: true
                onClicked: root.createRequested()
            }

            AppButton {
                visible: root.multiSelectMode
                text: root.allVisibleSelected() ? "全不选" : "全选"
                variant: "secondary"
                compact: true
                enabled: root.safeResultCount > 0
                onClicked: root.toggleSelectAll()
            }

            AppButton {
                visible: root.multiSelectMode
                text: "置顶"
                variant: "secondary"
                compact: true
                enabled: root.selectedIds.length > 0
                onClicked: {
                    root.bulkPinRequested(root.selectedIds)
                    root.exitMultiSelect()
                }
            }

            AppButton {
                visible: root.multiSelectMode
                text: "取消置顶"
                variant: "secondary"
                compact: true
                enabled: root.selectedIds.length > 0
                onClicked: {
                    root.bulkUnpinRequested(root.selectedIds)
                    root.exitMultiSelect()
                }
            }

            AppButton {
                visible: root.multiSelectMode
                text: "删除"
                variant: "softDanger"
                compact: true
                enabled: root.selectedIds.length > 0
                onClicked: {
                    root.bulkDeleteRequested(root.selectedIds)
                    root.exitMultiSelect()
                }
            }

            AppButton {
                visible: root.multiSelectMode
                text: "取消"
                variant: "ghost"
                compact: true
                onClicked: root.exitMultiSelect()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.safeErrorMessage.length > 0
            radius: 14
            color: "#FEF2F2"
            implicitHeight: 44

            Text {
                anchors.centerIn: parent
                text: root.safeErrorMessage
                color: "#991B1B"
                font.pixelSize: 12
                elide: Text.ElideRight
                width: parent.width - 24
            }
        }

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.notesModel
            spacing: 12
            clip: true
            boundsBehavior: Flickable.DragOverBounds
            rightMargin: 10

            ScrollBar.vertical: SlimScrollBar {
                anchors.right: parent.right
            }

            delegate: NoteCard {
                width: ListView.view.width - 14
                noteId: model.noteId
                title: model.title
                content: model.content
                tags: model.tagsText
                updated: model.updatedText
                source: model.sourceText
                cardColor: model.cardColor
                selected: !root.multiSelectMode && index === root.selectedIndex
                multiSelectMode: root.multiSelectMode
                selectedForBulk: root.hasSelected(model.noteId)

                onClicked: {
                    if (root.multiSelectMode) {
                        root.toggleSelected(model.noteId)
                    } else {
                        root.noteSelected(index)
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.safeResultCount === 0
            radius: 18
            color: "#F7F8FA"

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 10

                Text {
                    text: "暂无便签"
                    color: "#111827"
                    font.pixelSize: 18
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: "点击“新建”创建第一条便签。"
                    color: "#6B7280"
                    font.pixelSize: 13
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
