import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property var notesControllerRef: null
    property var sidecarClientRef: null
    property int searchResetToken: 0

    readonly property bool apiBusy: notesControllerRef !== null && notesControllerRef.isBusy
    readonly property bool apiConnected: notesControllerRef !== null && notesControllerRef.apiConnected
    readonly property bool sidecarConnected: sidecarClientRef !== null && sidecarClientRef.connected

    signal searchRequested(string keyword)
    signal searchTextChanged(string keyword)

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
                    text: "EHOME便签"
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
            Layout.preferredWidth: 520
            resetToken: root.searchResetToken

            onSearchRequested: function(keyword) {
                root.searchRequested(keyword)
            }

            onSearchTextChanged: function(keyword) {
                root.searchTextChanged(keyword)
            }
        }

        Item {
            Layout.fillWidth: true
        }

        StatusBadge {
            text: root.apiConnected ? "Notes API 已连接" : root.apiBusy ? "Notes API 正在连接" : "Notes API 未连接"
            dotColor: root.apiConnected ? "#16A34A" : root.apiBusy ? "#4F7CFF" : "#EF4444"
            bgColor: root.apiConnected ? "#ECFDF3" : root.apiBusy ? "#EAF0FF" : "#FEF2F2"
            textColor: root.apiConnected ? "#166534" : root.apiBusy ? "#1E3A8A" : "#991B1B"
        }

        StatusBadge {
            text: root.sidecarClientRef !== null ? root.sidecarClientRef.assistantStatusText : "语音助手未连接"
            dotColor: root.sidecarConnected ? "#16A34A" : "#F59E0B"
            bgColor: root.sidecarConnected ? "#ECFDF3" : "#FFF7ED"
            textColor: root.sidecarConnected ? "#166534" : "#92400E"
        }
    }
}
