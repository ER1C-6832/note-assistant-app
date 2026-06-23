import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string currentPage: "home"
    property string activeCategory: "all"

    signal categoryRequested(string categoryKey)
    signal tagRequested(string tagName)
    signal deletedRequested()
    signal pageRequested(string pageName)

    color: "#FFFFFF"
    radius: 20

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 10

        Text {
            text: "分类"
            color: "#9CA3AF"
            font.pixelSize: 13
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "全部"
            iconText: "•"
            active: root.activeCategory === "all"
            onClicked: root.categoryRequested("all")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "置顶"
            iconText: "•"
            active: root.activeCategory === "pinned"
            onClicked: root.categoryRequested("pinned")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "待办"
            iconText: "•"
            active: root.activeCategory === "todo"
            onClicked: root.categoryRequested("todo")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "已删除"
            iconText: "•"
            active: root.activeCategory === "deleted"
            onClicked: root.deletedRequested()
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#EEF2F7"
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            TextField {
                id: tagInput
                Layout.fillWidth: true
                height: 34
                placeholderText: "新增标签"
                font.pixelSize: 12
                selectByMouse: true

                background: Rectangle {
                    color: "#F7F8FA"
                    radius: 12
                    border.color: "#E5E7EB"
                }

                onAccepted: {
                    if (notesController.addCustomTag(tagInput.text)) {
                        tagInput.text = ""
                    }
                }
            }

            AppButton {
                text: "+"
                compact: true
                variant: "secondary"

                onClicked: {
                    if (notesController.addCustomTag(tagInput.text)) {
                        tagInput.text = ""
                    }
                }
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 6

                Repeater {
                    model: notesController.tagItems

                    SidebarTagItem {
                        Layout.fillWidth: true
                        text: modelData.name
                        active: root.activeCategory === "tag:" + modelData.name
                        deletable: modelData.deletable
                        onClicked: root.tagRequested(modelData.name)
                        onDeleteRequested: notesController.deleteTag(modelData.name)
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#EEF2F7"
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "语音助手"
            iconText: "●"
            active: root.activeCategory === "assistantIdle" || root.currentPage.indexOf("assistant") === 0
            onClicked: root.pageRequested("assistantIdle")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "设置"
            iconText: "⚙"
            active: root.activeCategory === "settings" || root.currentPage === "settings"
            onClicked: root.pageRequested("settings")
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 16
            color: "#F7F8FA"
            implicitHeight: 146

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 9

                Text {
                    text: "服务状态"
                    color: "#9CA3AF"
                    font.pixelSize: 13
                }

                RowLayout {
                    spacing: 8

                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: notesController.isBusy ? "#4F7CFF" : notesController.apiConnected ? "#16A34A" : "#EF4444"
                    }

                    Text {
                        text: notesController.isBusy ? "正在同步" : notesController.apiConnected ? "Notes API 已连接" : "Notes API 未连接"
                        color: "#4B5563"
                        font.pixelSize: 12
                    }
                }

                RowLayout {
                    spacing: 8

                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: sidecarClient.connected ? "#16A34A" : "#F59E0B"
                    }

                    Text {
                        text: sidecarClient.assistantStatusText
                        color: "#4B5563"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: sidecarClient.lastEventText.length > 0 ? sidecarClient.lastEventText : notesController.statusMessage
                    color: "#9CA3AF"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }
        }
    }
}
