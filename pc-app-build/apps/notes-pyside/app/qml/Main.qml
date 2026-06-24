import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "components"
import "pages"

ApplicationWindow {
    id: root

    width: 1440
    height: 960
    minimumWidth: 1180
    minimumHeight: 760
    visible: true
    title: "小智便签"
    color: "#F4F7FB"

    property string currentPage: "home"
    property string currentCategory: "all"
    property string pendingCategory: "all"

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

    function reloadCurrentContext() {
        if (currentCategory === "pinned") {
            notesController.loadCategory("pinned")
        } else if (currentCategory === "todo") {
            notesController.loadCategory("todo")
        } else if (currentCategory.indexOf("tag:") === 0) {
            notesController.loadTag(currentCategory.substring(4))
        } else if (currentCategory === "deleted") {
            notesController.loadDeleted()
        } else if (currentCategory === "search" && notesController.searchKeyword.length > 0) {
            notesController.searchNotes(notesController.searchKeyword)
        } else {
            notesController.loadAll()
        }
    }

    function openPage(pageName) {
        currentPage = pageName
    }

    function selectNote(index) {
        notesController.selectNote(index)
        currentPage = "home"
    }

    function openCategory(categoryKey) {
        currentCategory = categoryKey
        pendingCategory = categoryKey
        currentPage = categoryKey === "deleted" ? "deletedList" : "home"
        categoryLoadTimer.restart()
    }

    function openTag(tagName) {
        currentCategory = "tag:" + tagName
        currentPage = "home"
        tagLoadTimer.tagName = tagName
        tagLoadTimer.restart()
    }

    function handleVoiceUiAction(action, payloadJson) {
        var payload = {}
        try {
            payload = JSON.parse(payloadJson)
        } catch (e) {
            payload = {}
        }

        if (action === "show_search") {
            var query = String(payload.query || "").trim()
            if (query.length > 0) {
                root.currentCategory = "search"
                root.currentPage = "search"
                notesController.searchNotes(query)
            }
            return
        }

        if (action === "show_deleted") {
            root.openCategory("deleted")
            return
        }

        if (action === "show_pinned") {
            root.openCategory("pinned")
            return
        }

        if (action === "refresh_notes") {
            root.reloadCurrentContext()
            return
        }

        if (action === "add_tag") {
            var tag = String(payload.tag || "").trim()
            if (tag.length > 0) {
                notesController.addCustomTag(tag)
                root.openTag(tag)
            }
            return
        }

        if (action === "delete_empty_tag") {
            var tagToDelete = String(payload.tag || "").trim()
            if (tagToDelete.length > 0) {
                notesController.deleteTag(tagToDelete)
                root.currentCategory = "all"
                notesController.loadAll()
                root.openPage("home")
            }
            return
        }
    }

    Timer {
        id: startupTimer
        interval: 260
        repeat: false
        onTriggered: notesController.loadAll()
    }

    Timer {
        id: categoryLoadTimer
        interval: 30
        repeat: false
        onTriggered: {
            if (root.pendingCategory === "deleted") {
                notesController.loadDeleted()
            } else {
                notesController.loadCategory(root.pendingCategory)
            }
        }
    }

    Timer {
        id: tagLoadTimer
        property string tagName: ""
        interval: 30
        repeat: false
        onTriggered: notesController.loadTag(tagName)
    }

    Timer {
        id: liveSearchTimer
        property string keyword: ""
        interval: 220
        repeat: false
        onTriggered: {
            var text = String(keyword).trim()
            if (text.length === 0) {
                root.currentCategory = "all"
                root.currentPage = "home"
                notesController.loadAll()
            } else {
                root.currentCategory = "search"
                root.currentPage = "search"
                notesController.searchNotes(text)
            }
        }
    }

    Connections {
        target: sidecarClient
        function onUiActionRequested(action, payloadJson) {
            root.handleVoiceUiAction(action, payloadJson)
        }
    }

    Component.onCompleted: startupTimer.start()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        TopBar {
            Layout.fillWidth: true
            notesControllerRef: notesController
            sidecarClientRef: sidecarClient

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
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            Sidebar {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                currentPage: root.currentPage
                activeCategory: root.currentCategory
                notesControllerRef: notesController
                sidecarClientRef: sidecarClient

                onCategoryRequested: function(categoryKey) {
                    root.openCategory(categoryKey)
                }

                onTagRequested: function(tagName) {
                    root.openTag(tagName)
                }

                onDeletedRequested: {
                    root.openCategory("deleted")
                }

                onPageRequested: function(pageName) {
                    root.currentCategory = pageName
                    root.openPage(pageName)
                }
            }

            Loader {
                id: pageLoader
                Layout.fillWidth: true
                Layout.fillHeight: true

                sourceComponent: {
                    if (root.currentPage === "create") return createPage
                    if (root.currentPage === "edit") return editPage
                    if (root.currentPage === "deleteConfirm") return deleteConfirmPage
                    if (root.currentPage === "deletedList") return deletedListPage
                    if (root.currentPage === "search") return searchPage
                    if (root.currentPage === "assistantIdle") return assistantIdlePage
                    if (root.currentPage === "assistantCreate") return assistantCreatePage
                    if (root.currentPage === "assistantSearch") return assistantSearchPage
                    if (root.currentPage === "assistantUpdate") return assistantUpdatePage
                    if (root.currentPage === "assistantDelete") return assistantDeletePage
                    if (root.currentPage === "settings") return settingsPage
                    return homePage
                }
            }
        }
    }

    Component {
        id: homePage

        HomePage {
            notesModel: notesListModel
            notesControllerRef: notesController
            selectedIndex: notesController !== null ? notesController.selectedIndex : -1
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
                notesController.toggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                notesController.bulkDeleteNotesByIds(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                notesController.bulkPinNotesByIds(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                notesController.bulkUnpinNotesByIds(noteIds)
            }

            onAssistantRequested: {
                root.currentCategory = "assistantIdle"
                root.openPage("assistantIdle")
            }
        }
    }

    Component {
        id: createPage

        CreateNotePage {
            initialTags: root.createInitialTags()
            initialPinned: root.createInitialPinned()

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText, isPinned) {
                if (notesController.createNote(titleText, contentText, tagsText, isPinned)) {
                    root.openPage("home")
                    root.reloadCurrentContext()
                }
            }
        }
    }

    Component {
        id: editPage

        EditNotePage {
            noteTitle: notesController.selectedTitle
            noteContent: notesController.selectedContent
            noteTags: notesController.selectedTagsText

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText) {
                if (notesController.updateSelectedNote(titleText, contentText, tagsText)) {
                    root.currentCategory = "all"
                    root.openPage("home")
                }
            }
        }
    }

    Component {
        id: deleteConfirmPage

        DeleteConfirmPage {
            noteTitle: notesController.selectedTitle

            onBackRequested: {
                root.openPage("home")
            }

            onDeleted: {
                if (notesController.deleteSelectedNote()) {
                    root.currentCategory = "all"
                    root.openPage("home")
                }
            }
        }
    }

    Component {
        id: deletedListPage

        DeletedNotesPage {
            deletedNotesModel: deletedNotesListModel

            onBackRequested: {
                root.currentCategory = "all"
                notesController.loadAll()
                root.openPage("home")
            }
        }
    }

    Component {
        id: searchPage

        SearchPage {
            keyword: notesController.searchKeyword
            notesModel: notesListModel
            selectedIndex: notesController !== null ? notesController.selectedIndex : -1

            onNoteSelected: function(index) {
                root.selectNote(index)
            }

            onBackRequested: {
                root.currentCategory = "all"
                notesController.loadAll()
                root.openPage("home")
            }

            onEditRequested: {
                root.openPage("edit")
            }

            onDeleteSelectedRequested: {
                root.openPage("deleteConfirm")
            }

            onPinRequested: {
                notesController.toggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                notesController.bulkDeleteNotesByIds(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                notesController.bulkPinNotesByIds(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                notesController.bulkUnpinNotesByIds(noteIds)
            }
        }
    }

    Component {
        id: assistantIdlePage

        AssistantIdlePage {
            onBackRequested: {
                root.currentCategory = "all"
                root.openPage("home")
            }

            onDemoCreateRequested: {
                root.openPage("assistantCreate")
            }

            onDemoSearchRequested: {
                root.openPage("assistantSearch")
            }

            onDemoUpdateRequested: {
                root.openPage("assistantUpdate")
            }

            onDemoDeleteRequested: {
                root.openPage("assistantDelete")
            }
        }
    }

    Component {
        id: assistantCreatePage

        AssistantCreatePage {
            onBackRequested: {
                root.openPage("assistantIdle")
            }
        }
    }

    Component {
        id: assistantSearchPage

        AssistantSearchPage {
            onBackRequested: {
                root.openPage("assistantIdle")
            }
        }
    }

    Component {
        id: assistantUpdatePage

        AssistantUpdatePage {
            onBackRequested: {
                root.openPage("assistantIdle")
            }
        }
    }

    Component {
        id: assistantDeletePage

        AssistantDeletePage {
            onBackRequested: {
                root.openPage("assistantIdle")
            }
        }
    }

    Component {
        id: settingsPage

        SettingsPage {
            onBackRequested: {
                root.currentCategory = "all"
                root.openPage("home")
            }
        }
    }
}
