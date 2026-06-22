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
            text: "Notes API 已连接"
            dotColor: "#16A34A"
            bgColor: "#ECFDF3"
            textColor: "#166534"
        }

        StatusBadge {
            text: "Sidecar 待接入"
            dotColor: "#F59E0B"
            bgColor: "#FFF7ED"
            textColor: "#92400E"
        }
    }
}
