import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    signal newRequested()
    signal searchRequested(string keyword)
    signal settingsRequested()

    color: "#FFFFFF"
    radius: 18
    height: 76

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        spacing: 16

        RowLayout {
            Layout.preferredWidth: 260
            spacing: 12

            Rectangle {
                width: 34
                height: 34
                radius: 17
                color: "#4F7CFF"

                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: "#FFFFFF"
                    anchors.centerIn: parent
                }
            }

            ColumnLayout {
                spacing: 2

                Text {
                    text: "小智便签"
                    color: "#1A1A1A"
                    font.pixelSize: 18
                    font.bold: true
                }

                Text {
                    text: "便签 App 与语音助手"
                    color: "#4B5563"
                    font.pixelSize: 12
                }
            }
        }

        Rectangle {
            Layout.preferredWidth: 520
            height: 44
            color: "#F7F8FA"
            radius: 14

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 8
                spacing: 10

                Rectangle {
                    width: 18
                    height: 18
                    radius: 9
                    border.color: "#9CA3AF"
                    border.width: 1
                    color: "transparent"
                }

                TextField {
                    id: searchField
                    Layout.fillWidth: true
                    placeholderText: "搜索标题、正文、标签……"
                    text: ""
                    background: null
                    font.pixelSize: 13
                    color: "#1A1A1A"
                    onAccepted: root.searchRequested(searchField.text)
                }

                Button {
                    text: "搜索"
                    onClicked: root.searchRequested(searchField.text)
                }
            }
        }

        Button {
            text: "+ 新建便签"
            onClicked: root.newRequested()
        }

        Item {
            Layout.fillWidth: true
        }

        StatusBadge {
            text: "Notes API 已连接"
        }

        StatusBadge {
            text: "语音助手待接入"
            dotColor: "#F59E0B"
            bgColor: "#FFF7ED"
        }

        Button {
            text: "设置"
            onClicked: root.settingsRequested()
        }
    }
}
