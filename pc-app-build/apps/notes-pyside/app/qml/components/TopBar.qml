import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    signal searchRequested(string keyword)

    color: "#FFFFFF"
    radius: 20
    height: 76

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        spacing: 18

        RowLayout {
            Layout.preferredWidth: 282
            spacing: 12

            Rectangle {
                width: 36
                height: 36
                radius: 18
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
                    color: "#111827"
                    font.pixelSize: 18
                    font.bold: true
                }

                Text {
                    text: "便签 App 与语音助手"
                    color: "#6B7280"
                    font.pixelSize: 12
                }
            }
        }

        SearchBox {
            Layout.preferredWidth: 560
            onSearchRequested: function(keyword) {
                root.searchRequested(keyword)
            }
        }

        Item {
            Layout.fillWidth: true
        }

        StatusBadge {
            text: notesController.isBusy ? "正在同步" : notesController.apiConnected ? "Notes API 已连接" : "Notes API 未连接"
            dotColor: notesController.isBusy ? "#4F7CFF" : notesController.apiConnected ? "#16A34A" : "#EF4444"
            bgColor: notesController.isBusy ? "#EAF0FF" : notesController.apiConnected ? "#ECFDF3" : "#FEF2F2"
            textColor: notesController.isBusy ? "#1E3A8A" : notesController.apiConnected ? "#166534" : "#991B1B"
        }

        StatusBadge {
            text: "语音助手待接入"
            dotColor: "#F59E0B"
            bgColor: "#FFF7ED"
            textColor: "#92400E"
        }
    }
}
