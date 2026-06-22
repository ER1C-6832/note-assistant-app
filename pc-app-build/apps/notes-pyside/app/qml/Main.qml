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

    function openPage(pageName) {
        currentPage = pageName
    }

    function selectNote(index) {
        notesController.selectNote(index)
        currentPage = "home"
    }

    function openCategory(categoryKey) {
        currentCategory = categoryKey
        notesController.loadCategory(categoryKey)
        currentPage = "home"
    }

    Component.onCompleted: {
        notesController.testConnection()
        notesController.loadAll()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        TopBar {
            Layout.fillWidth: true
            onSearchRequested: function(keyword) {
                notesController.searchNotes(keyword)
                root.currentCategory = "search"
                root.openPage("search")
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

                onCategoryRequested: function(categoryKey) {
                    root.openCategory(categoryKey)
                }

                onDeletedRequested: {
                    root.currentCategory = "deleted"
                    notesController.loadDeleted()
                    root.openPage("deletedList")
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
            selectedIndex: notesController.selectedIndex
            activeCategory: root.currentCategory
            onNoteSelected: function(index) {
                root.selectNote(index)
            }
            onCreateRequested: root.openPage("create")
            onEditRequested: root.openPage("edit")
            onDeleteRequested: root.openPage("deleteConfirm")
            onAssistantRequested: {
                root.currentCategory = "assistantIdle"
                root.openPage("assistantIdle")
            }
        }
    }

    Component {
        id: createPage

        CreateNotePage {
            onBackRequested: root.openPage("home")
            onSaved: {
                notesController.createNote(titleText, contentText, tagsText)
                root.currentCategory = "all"
                root.openPage("home")
            }
        }
    }

    Component {
        id: editPage

        EditNotePage {
            noteTitle: notesController.selectedTitle
            noteContent: notesController.selectedContent
            noteTags: notesController.selectedTagsText
            onBackRequested: root.openPage("home")
            onSaved: function(titleText, contentText, tagsText) {
                notesController.updateSelectedNote(titleText, contentText, tagsText)
                root.currentCategory = "all"
                root.openPage("home")
            }
        }
    }

    Component {
        id: deleteConfirmPage

        DeleteConfirmPage {
            noteTitle: notesController.selectedTitle
            onBackRequested: root.openPage("home")
            onDeleted: {
                notesController.deleteSelectedNote()
                root.currentCategory = "all"
                root.openPage("home")
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
            selectedIndex: notesController.selectedIndex
            onNoteSelected: function(index) {
                root.selectNote(index)
            }
            onBackRequested: {
                root.currentCategory = "all"
                notesController.loadAll()
                root.openPage("home")
            }
            onDeleteSelectedRequested: root.openPage("deleteConfirm")
        }
    }

    Component {
        id: assistantIdlePage

        AssistantIdlePage {
            onBackRequested: {
                root.currentCategory = "all"
                root.openPage("home")
            }
            onDemoCreateRequested: root.openPage("assistantCreate")
            onDemoSearchRequested: root.openPage("assistantSearch")
            onDemoUpdateRequested: root.openPage("assistantUpdate")
            onDemoDeleteRequested: root.openPage("assistantDelete")
        }
    }

    Component {
        id: assistantCreatePage
        AssistantCreatePage { onBackRequested: root.openPage("assistantIdle") }
    }

    Component {
        id: assistantSearchPage
        AssistantSearchPage { onBackRequested: root.openPage("assistantIdle") }
    }

    Component {
        id: assistantUpdatePage
        AssistantUpdatePage { onBackRequested: root.openPage("assistantIdle") }
    }

    Component {
        id: assistantDeletePage
        AssistantDeletePage { onBackRequested: root.openPage("assistantIdle") }
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
