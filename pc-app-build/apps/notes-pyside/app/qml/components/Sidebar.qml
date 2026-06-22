import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string currentPage: "home"
    signal pageRequested(string pageName)

    color: "#FFFFFF"
    radius: 18

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        Text {
            text: "分类"
            color: "#9CA3AF"
            font.pixelSize: 13
        }

        Repeater {
            model: [
                {"label": "全部", "page": "home"},
                {"label": "置顶", "page": "home"},
                {"label": "客户", "page": "search"},
                {"label": "会议", "page": "home"},
                {"label": "待办", "page": "home"},
                {"label": "已删除", "page": "delete"}
            ]

            delegate: Rectangle {
                Layout.fillWidth: true
                height: 40
                radius: 12
                color: modelData.page === root.currentPage ? "#EAF0FF" : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Text {
                        Layout.fillWidth: true
                        text: modelData.label
                        color: "#374151"
                        font.pixelSize: 14
                    }

                    Rectangle {
                        visible: modelData.page === root.currentPage
                        width: 8
                        height: 8
                        radius: 4
                        color: "#4F7CFF"
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.pageRequested(modelData.page)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#EEF2F7"
        }

        Button {
            Layout.fillWidth: true
            text: "语音助手"
            onClicked: root.pageRequested("assistantIdle")
        }

        Button {
            Layout.fillWidth: true
            text: "设置"
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
