import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string currentPage: "home"
    property string activeCategory: "all"

    signal categoryRequested(string categoryKey)
    signal pageRequested(string pageName)

    color: "#FFFFFF"
    radius: 20

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        Text {
            text: "分类"
            color: "#9CA3AF"
            font.pixelSize: 13
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "全部"
            countText: "5"
            iconText: "•"
            active: root.activeCategory === "all"
            onClicked: root.categoryRequested("all")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "置顶"
            countText: "1"
            iconText: "•"
            active: root.activeCategory === "pinned"
            onClicked: root.categoryRequested("pinned")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "客户"
            countText: "2"
            iconText: "•"
            active: root.activeCategory === "customer"
            onClicked: root.categoryRequested("customer")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "会议"
            countText: "1"
            iconText: "•"
            active: root.activeCategory === "meeting"
            onClicked: root.categoryRequested("meeting")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "待办"
            countText: "1"
            iconText: "•"
            active: root.activeCategory === "todo"
            onClicked: root.categoryRequested("todo")
        }

        SidebarItem {
            Layout.fillWidth: true
            text: "已删除"
            countText: "1"
            iconText: "•"
            active: root.activeCategory === "deleted"
            onClicked: root.categoryRequested("deleted")
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

        Item {
            Layout.fillHeight: true
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 16
            color: "#F7F8FA"
            implicitHeight: 116

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

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
                        color: "#16A34A"
                    }

                    Text {
                        text: "Notes API 已连接"
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
                        color: "#F59E0B"
                    }

                    Text {
                        text: "Sidecar 待接入"
                        color: "#4B5563"
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
