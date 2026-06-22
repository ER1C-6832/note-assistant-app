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
    property int selectedIndex: 0
    property string searchKeyword: "王总"

    ListModel {
        id: notesModel

        ListElement {
            title: "联系王总"
            content: "明天上午十点联系王总，确认项目报价。"
            tags: "客户 · 跟进"
            updated: "今天 09:20"
            source: "手动"
            cardColor: "#FFF6CC"
        }

        ListElement {
            title: "王总项目报价"
            content: "和王总确认 27 寸屏幕报价区间，以及演示安排。"
            tags: "客户 · 报价"
            updated: "昨天 18:40"
            source: "手动"
            cardColor: "#E9F2FF"
        }

        ListElement {
            title: "项目会议纪要"
            content: "讨论 PC 端 PySide6 + QML 落地，以及 py-xiaozhi sidecar 接入方式。"
            tags: "会议 · 语音助手"
            updated: "昨天 11:05"
            source: "手动"
            cardColor: "#E8F9F1"
        }

        ListElement {
            title: "报销材料"
            content: "下周提交差旅报销单，需要整理发票。"
            tags: "财务 · 待办"
            updated: "6 月 20 日"
            source: "手动"
            cardColor: "#FCE9F3"
        }

        ListElement {
            title: "小智服务部署"
            content: "后续内网部署 xiaozhi-esp32-server，测试 ASR、LLM、TTS 链路。"
            tags: "技术 · 部署"
            updated: "6 月 18 日"
            source: "手动"
            cardColor: "#EEF2FF"
        }
    }

    function openPage(pageName) {
        currentPage = pageName
    }

    function selectNote(index) {
        selectedIndex = index
        currentPage = "home"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        TopBar {
            id: topBar
            Layout.fillWidth: true
            onNewRequested: root.openPage("create")
            onSearchRequested: function(keyword) {
                root.searchKeyword = keyword.length > 0 ? keyword : "王总"
                root.openPage("search")
            }
            onSettingsRequested: root.openPage("settings")
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            Sidebar {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                currentPage: root.currentPage
                onPageRequested: function(pageName) {
                    root.openPage(pageName)
                }
            }

            Loader {
                id: pageLoader
                Layout.fillWidth: true
                Layout.fillHeight: true

                sourceComponent: {
                    if (root.currentPage === "create") {
                        return createPage
                    }
                    if (root.currentPage === "edit") {
                        return editPage
                    }
                    if (root.currentPage === "delete") {
                        return deletePage
                    }
                    if (root.currentPage === "search") {
                        return searchPage
                    }
                    if (root.currentPage === "assistantIdle") {
                        return assistantIdlePage
                    }
                    if (root.currentPage === "assistantCreate") {
                        return assistantCreatePage
                    }
                    if (root.currentPage === "assistantSearch") {
                        return assistantSearchPage
                    }
                    if (root.currentPage === "assistantUpdate") {
                        return assistantUpdatePage
                    }
                    if (root.currentPage === "assistantDelete") {
                        return assistantDeletePage
                    }
                    if (root.currentPage === "settings") {
                        return settingsPage
                    }
                    return homePage
                }
            }
        }
    }

    Component {
        id: homePage
        HomePage {
            notesModel: notesModel
            selectedIndex: root.selectedIndex
            onNoteSelected: function(index) {
                root.selectNote(index)
            }
            onCreateRequested: root.openPage("create")
            onEditRequested: root.openPage("edit")
            onDeleteRequested: root.openPage("delete")
            onSearchRequested: root.openPage("search")
            onAssistantRequested: root.openPage("assistantIdle")
        }
    }

    Component {
        id: createPage
        CreateNotePage {
            onBackRequested: root.openPage("home")
            onSaved: root.openPage("home")
        }
    }

    Component {
        id: editPage
        EditNotePage {
            noteTitle: notesModel.get(root.selectedIndex).title
            noteContent: notesModel.get(root.selectedIndex).content
            noteTags: notesModel.get(root.selectedIndex).tags
            onBackRequested: root.openPage("home")
            onSaved: root.openPage("home")
        }
    }

    Component {
        id: deletePage
        DeleteConfirmPage {
            noteTitle: notesModel.get(root.selectedIndex).title
            onBackRequested: root.openPage("home")
            onDeleted: root.openPage("home")
        }
    }

    Component {
        id: searchPage
        SearchPage {
            keyword: root.searchKeyword
            notesModel: notesModel
            onNoteSelected: function(index) {
                root.selectNote(index)
            }
            onBackRequested: root.openPage("home")
            onDeleteSelectedRequested: root.openPage("delete")
        }
    }

    Component {
        id: assistantIdlePage
        AssistantIdlePage {
            onBackRequested: root.openPage("home")
            onDemoCreateRequested: root.openPage("assistantCreate")
            onDemoSearchRequested: root.openPage("assistantSearch")
            onDemoUpdateRequested: root.openPage("assistantUpdate")
            onDemoDeleteRequested: root.openPage("assistantDelete")
        }
    }

    Component {
        id: assistantCreatePage
        AssistantCreatePage {
            onBackRequested: root.openPage("assistantIdle")
        }
    }

    Component {
        id: assistantSearchPage
        AssistantSearchPage {
            onBackRequested: root.openPage("assistantIdle")
        }
    }

    Component {
        id: assistantUpdatePage
        AssistantUpdatePage {
            onBackRequested: root.openPage("assistantIdle")
        }
    }

    Component {
        id: assistantDeletePage
        AssistantDeletePage {
            onBackRequested: root.openPage("assistantIdle")
        }
    }

    Component {
        id: settingsPage
        SettingsPage {
            onBackRequested: root.openPage("home")
        }
    }
}
