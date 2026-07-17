import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "components"
import "pages"

ApplicationWindow {
    id: root

    width: 1520
    height: 960
    minimumWidth: 1280
    minimumHeight: 760
    visible: true
    title: "小智便签"
    color: "#F4F7FB"

    property string currentPage: "home"
    property string currentCategory: "all"
    property int searchResetToken: 0
    property var pendingConfirmation: ({})
    property string confirmationStatus: ""

    readonly property var viewModel: notesViewModel
    readonly property bool viewModelReady: root.viewModel !== null
    readonly property var assistantModel: assistantViewModel
    readonly property bool assistantModelReady: root.assistantModel !== null
    readonly property var mcpUiAdapter: (typeof uiCommandAdapter !== "undefined") ? uiCommandAdapter : null
    property alias assistantOverlayItem: assistantOverlay

    function createInitialTags() {
        if (currentCategory === "todo") {
            return "待办"
        }
        if (currentCategory.indexOf("tag:") === 0) {
            return currentCategory.substring(4)
        }
        return ""
    }

    function createInitialPinned() {
        return currentCategory === "pinned"
    }

    function openPage(pageName) {
        currentPage = pageName
    }

    function selectNote(index) {
        if (!root.viewModelReady) return
        root.viewModel.selectNote(index)
        currentPage = "home"
    }

    function openCategory(categoryKey) {
        if (!root.viewModelReady) return
        currentCategory = categoryKey
        currentPage = categoryKey === "deleted" ? "deletedList" : "home"
        if (categoryKey === "deleted") {
            root.viewModel.loadDeleted()
        } else {
            root.viewModel.loadCategory(categoryKey)
        }
    }

    function openTag(tagName) {
        if (!root.viewModelReady) return
        currentCategory = "tag:" + tagName
        currentPage = "home"
        root.viewModel.loadTag(tagName)
    }

    Timer {
        id: liveSearchTimer
        property string keyword: ""
        interval: 220
        repeat: false
        onTriggered: {
            if (!root.viewModelReady) return
            var text = String(keyword).trim()
            if (text.length === 0) {
                root.currentCategory = "all"
                root.currentPage = "home"
                root.viewModel.loadAll()
            } else {
                root.currentCategory = "search"
                root.currentPage = "search"
                root.viewModel.searchNotes(text)
            }
        }
    }

    Connections {
        target: root.viewModel
        ignoreUnknownSignals: true

        function onNoteCreated(noteId) {
            root.openPage("home")
        }

        function onNoteUpdated(noteId) {
            root.openPage("home")
        }

        function onNotesSoftDeleted(noteIds) {
            root.openPage("home")
        }
    }

    Connections {
        target: root.mcpUiAdapter
        ignoreUnknownSignals: true

        function onNavigationRequested(command, payload) {
            if (command === "open_note") {
                root.currentCategory = "all"
                root.currentPage = "home"
            } else if (command === "show_search") {
                var query = String(payload.query || "")
                root.currentCategory = "search"
                root.currentPage = "search"
                topBar.setSearchQueryAndFocus(query)
            } else if (command === "show_note_list") {
                root.currentCategory = "all"
                root.currentPage = "home"
            } else if (command === "show_tag") {
                root.currentCategory = "tag:" + String(payload.tag)
                root.currentPage = "home"
            } else if (command === "show_trash") {
                root.currentCategory = "deleted"
                root.currentPage = "deletedList"
            } else if (command === "show_pinned") {
                root.currentCategory = "pinned"
                root.currentPage = "home"
            } else if (command === "show_todos") {
                root.currentCategory = "todo"
                root.currentPage = "home"
            } else if (command === "show_confirmation") {
                root.pendingConfirmation = payload
                root.confirmationStatus = ""
                confirmationDialog.open()
            }
        }
    }

    Connections {
        target: root.mcpUiAdapter
        ignoreUnknownSignals: true

        function onConfirmationActionFinished(confirmationId, status, message) {
            if (String(root.pendingConfirmation.confirmation_id || "") !== String(confirmationId)) return
            root.confirmationStatus = message
            if (status === "success" || status === "partial_success") {
                confirmationDialog.close()
                root.pendingConfirmation = ({})
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        TopBar {
            id: topBar
            Layout.fillWidth: true
            searchResetToken: root.searchResetToken

            onSearchRequested: function(keyword) {
                liveSearchTimer.keyword = keyword
                liveSearchTimer.restart()
            }

            onSearchTextChanged: function(keyword) {
                liveSearchTimer.keyword = keyword
                liveSearchTimer.restart()
            }
        }

        RowLayout {
            id: notesMainRow
            objectName: "notesMainRow"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            Sidebar {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                activeCategory: root.currentCategory
                notesViewModelRef: root.viewModel

                onCategoryRequested: function(categoryKey) {
                    root.openCategory(categoryKey)
                }

                onTagRequested: function(tagName) {
                    root.openTag(tagName)
                }

                onDeletedRequested: {
                    root.openCategory("deleted")
                }
            }

            Loader {
                id: pageLoader
                objectName: "pageLoader"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 520
                sourceComponent: {
                    if (root.currentPage === "create") return createPage
                    if (root.currentPage === "edit") return editPage
                    if (root.currentPage === "deleteConfirm") return deleteConfirmPage
                    if (root.currentPage === "deletedList") return deletedListPage
                    if (root.currentPage === "search") return searchPage
                    return homePage
                }
            }
        }
    }

    AssistantOverlay {
        id: assistantOverlay
        objectName: "assistantOverlay"
        anchors.fill: parent
        viewModelRef: root.assistantModel
        windowActive: root.visible && root.visibility !== Window.Minimized
        z: 40
    }

    Dialog {
        id: confirmationDialog
        objectName: "mcpConfirmationDialog"
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.width - 80, 560)
        title: "请确认助手操作"
        closePolicy: Popup.NoAutoClose
        standardButtons: Dialog.NoButton
        z: 60

        contentItem: ColumnLayout {
            spacing: 14

            Label {
                Layout.fillWidth: true
                text: "工具：" + String(root.pendingConfirmation.tool_name || "")
                font.bold: true
                wrapMode: Text.Wrap
            }

            Label {
                Layout.fillWidth: true
                text: {
                    var preview = root.pendingConfirmation.preview || {}
                    var operation = String(preview.operation || "高风险操作")
                    var noteCount = Number(preview.note_count || 0)
                    var tagCount = Number(preview.tag_count || 0)
                    var summary = "操作：" + operation
                    if (noteCount > 0) summary += "；便签数量：" + noteCount
                    if (tagCount > 0) summary += "；标签数量：" + tagCount
                    return summary
                }
                wrapMode: Text.Wrap
            }

            Label {
                Layout.fillWidth: true
                text: "便签 ID：" + String((root.pendingConfirmation.affected_note_ids || []).join(", "))
                visible: (root.pendingConfirmation.affected_note_ids || []).length > 0
                wrapMode: Text.Wrap
            }

            Label {
                Layout.fillWidth: true
                text: "标签：" + String((root.pendingConfirmation.affected_tags || []).join("、"))
                visible: (root.pendingConfirmation.affected_tags || []).length > 0
                wrapMode: Text.Wrap
            }

            Label {
                Layout.fillWidth: true
                text: root.confirmationStatus
                color: "#B42318"
                visible: text.length > 0
                wrapMode: Text.Wrap
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 12

                Button {
                    text: "拒绝"
                    onClicked: root.mcpUiAdapter.rejectPending(
                        String(root.pendingConfirmation.confirmation_id || "")
                    )
                }

                Button {
                    text: "确认执行"
                    highlighted: true
                    onClicked: root.mcpUiAdapter.confirmPending(
                        String(root.pendingConfirmation.confirmation_id || "")
                    )
                }
            }
        }
    }

    Component {
        id: homePage

        HomePage {
            notesModel: notesListModel
            notesViewModelRef: root.viewModel
            selectedIndex: root.viewModelReady ? root.viewModel.selectedIndex : -1
            activeCategory: root.currentCategory

            onNoteSelected: function(index) {
                root.selectNote(index)
            }

            onCreateRequested: {
                root.openPage("create")
            }

            onEditRequested: {
                root.openPage("edit")
            }

            onDeleteRequested: {
                root.openPage("deleteConfirm")
            }

            onPinRequested: {
                root.viewModel.requestToggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                root.viewModel.requestBulkDelete(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                root.viewModel.requestBulkPin(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                root.viewModel.requestBulkUnpin(noteIds)
            }
        }
    }

    Component {
        id: createPage

        CreateNotePage {
            notesViewModelRef: root.viewModel
            initialTags: root.createInitialTags()
            initialPinned: root.createInitialPinned()

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText, isPinned) {
                root.viewModel.requestCreateNote(titleText, contentText, tagsText, isPinned)
            }
        }
    }

    Component {
        id: editPage

        EditNotePage {
            notesViewModelRef: root.viewModel
            noteTitle: root.viewModelReady ? root.viewModel.selectedTitle : ""
            noteContent: root.viewModelReady ? root.viewModel.selectedContent : ""
            noteTags: root.viewModelReady ? root.viewModel.selectedTagsText : ""

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText) {
                root.viewModel.requestUpdateSelectedNote(titleText, contentText, tagsText)
            }
        }
    }

    Component {
        id: deleteConfirmPage

        DeleteConfirmPage {
            noteTitle: root.viewModelReady ? root.viewModel.selectedTitle : ""
            mutationBusy: root.viewModelReady && root.viewModel.mutationBusy
            errorMessage: root.viewModelReady ? root.viewModel.errorMessage : ""

            onBackRequested: {
                root.openPage("home")
            }

            onDeleted: {
                root.viewModel.requestDeleteSelectedNote()
            }
        }
    }

    Component {
        id: deletedListPage

        DeletedNotesPage {
            deletedNotesModel: deletedNotesListModel
            notesViewModelRef: root.viewModel

            onBackRequested: {
                root.currentCategory = "all"
                root.viewModel.loadAll()
                root.openPage("home")
            }
        }
    }

    Component {
        id: searchPage

        SearchPage {
            notesViewModelRef: root.viewModel
            keyword: root.viewModelReady ? root.viewModel.searchKeyword : ""
            notesModel: notesListModel
            selectedIndex: root.viewModelReady ? root.viewModel.selectedIndex : -1

            onNoteSelected: function(index) {
                root.selectNote(index)
            }

            onBackRequested: {
                root.currentCategory = "all"
                root.viewModel.loadAll()
                root.openPage("home")
            }

            onResetRequested: {
                root.currentCategory = "all"
                root.viewModel.loadAll()
                root.searchResetToken += 1
                root.openPage("home")
            }

            onEditRequested: {
                root.openPage("edit")
            }

            onDeleteSelectedRequested: {
                root.openPage("deleteConfirm")
            }

            onPinRequested: {
                root.viewModel.requestToggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                root.viewModel.requestBulkDelete(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                root.viewModel.requestBulkPin(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                root.viewModel.requestBulkUnpin(noteIds)
            }
        }
    }
}
