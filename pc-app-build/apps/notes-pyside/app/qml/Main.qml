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
    property int searchResetToken: 0

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
        notesViewModel.selectNote(index)
        currentPage = "home"
    }

    function openCategory(categoryKey) {
        currentCategory = categoryKey
        currentPage = categoryKey === "deleted" ? "deletedList" : "home"
        if (categoryKey === "deleted") {
            notesViewModel.loadDeleted()
        } else {
            notesViewModel.loadCategory(categoryKey)
        }
    }

    function openTag(tagName) {
        currentCategory = "tag:" + tagName
        currentPage = "home"
        notesViewModel.loadTag(tagName)
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
                notesViewModel.loadAll()
            } else {
                root.currentCategory = "search"
                root.currentPage = "search"
                notesViewModel.searchNotes(text)
            }
        }
    }

    Connections {
        target: notesViewModel

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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        TopBar {
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
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            Sidebar {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                activeCategory: root.currentCategory
                notesViewModelRef: notesViewModel

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
                Layout.fillWidth: true
                Layout.fillHeight: true
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

    Component {
        id: homePage

        HomePage {
            notesModel: notesListModel
            notesViewModelRef: notesViewModel
            selectedIndex: notesViewModel.selectedIndex
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
                notesViewModel.requestToggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                notesViewModel.requestBulkDelete(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                notesViewModel.requestBulkPin(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                notesViewModel.requestBulkUnpin(noteIds)
            }
        }
    }

    Component {
        id: createPage

        CreateNotePage {
            notesViewModelRef: notesViewModel
            initialTags: root.createInitialTags()
            initialPinned: root.createInitialPinned()

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText, isPinned) {
                notesViewModel.requestCreateNote(titleText, contentText, tagsText, isPinned)
            }
        }
    }

    Component {
        id: editPage

        EditNotePage {
            notesViewModelRef: notesViewModel
            noteTitle: notesViewModel.selectedTitle
            noteContent: notesViewModel.selectedContent
            noteTags: notesViewModel.selectedTagsText

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText) {
                notesViewModel.requestUpdateSelectedNote(titleText, contentText, tagsText)
            }
        }
    }

    Component {
        id: deleteConfirmPage

        DeleteConfirmPage {
            noteTitle: notesViewModel.selectedTitle
            mutationBusy: notesViewModel.mutationBusy
            errorMessage: notesViewModel.errorMessage

            onBackRequested: {
                root.openPage("home")
            }

            onDeleted: {
                notesViewModel.requestDeleteSelectedNote()
            }
        }
    }

    Component {
        id: deletedListPage

        DeletedNotesPage {
            deletedNotesModel: deletedNotesListModel
            notesViewModelRef: notesViewModel

            onBackRequested: {
                root.currentCategory = "all"
                notesViewModel.loadAll()
                root.openPage("home")
            }
        }
    }

    Component {
        id: searchPage

        SearchPage {
            notesViewModelRef: notesViewModel
            keyword: notesViewModel.searchKeyword
            notesModel: notesListModel
            selectedIndex: notesViewModel.selectedIndex

            onNoteSelected: function(index) {
                root.selectNote(index)
            }

            onBackRequested: {
                root.currentCategory = "all"
                notesViewModel.loadAll()
                root.openPage("home")
            }

            onResetRequested: {
                root.currentCategory = "all"
                notesViewModel.loadAll()
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
                notesViewModel.requestToggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                notesViewModel.requestBulkDelete(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                notesViewModel.requestBulkPin(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                notesViewModel.requestBulkUnpin(noteIds)
            }
        }
    }
}
