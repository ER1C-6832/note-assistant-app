import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: "小智语音助手"
    property string statusText: "待机中"
    property string transcript: ""
    property string reply: ""
    property string resultTitle: ""
    property string resultText: ""

    color: "#FFFFFF"
    radius: 20

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        RowLayout {
            Layout.fillWidth: true

            Text {
                Layout.fillWidth: true
                text: root.title
                color: "#111827"
                font.pixelSize: 22
                font.bold: true
            }

            StatusBadge {
                text: root.statusText
                dotColor: sidecarClient.connected ? "#16A34A" : "#F59E0B"
                bgColor: sidecarClient.connected ? "#ECFDF3" : "#FFF7ED"
                textColor: sidecarClient.connected ? "#166534" : "#92400E"
            }
        }

        Rectangle {
            width: 96
            height: 96
            radius: 48
            color: sidecarClient.connected ? "#DBEAFE" : "#F3F4F6"
            Layout.alignment: Qt.AlignHCenter

            Text {
                anchors.centerIn: parent
                text: "语音"
                color: sidecarClient.connected ? "#2563EB" : "#6B7280"
                font.pixelSize: 18
                font.bold: true
            }
        }

        Text {
            Layout.fillWidth: true
            text: "可以继续在 py-xiaozhi 中说：帮我记录、查一下王总、修改或删除便签。"
            color: "#4B5563"
            font.pixelSize: 14
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 16
            color: "#F7F8FA"
            implicitHeight: statusColumn.implicitHeight + 28

            ColumnLayout {
                id: statusColumn
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8

                Text {
                    text: "连接状态"
                    color: "#111827"
                    font.pixelSize: 14
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: sidecarClient.statusText + " · " + sidecarClient.wsUrl
                    color: "#374151"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    text: sidecarClient.notesApiStatusText
                    color: "#374151"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    text: sidecarClient.pyXiaozhiStatusText + " · " + sidecarClient.notesToolStatusText
                    color: "#374151"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: sidecarClient.lastEventText.length > 0
            radius: 16
            color: "#EAF0FF"
            implicitHeight: eventText.implicitHeight + 28

            Text {
                id: eventText
                anchors.fill: parent
                anchors.margins: 14
                text: "最近事件：" + sidecarClient.lastEventText
                color: "#1E3A8A"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: sidecarClient.errorMessage.length > 0
            radius: 16
            color: "#FEF2F2"
            implicitHeight: errorText.implicitHeight + 28

            Text {
                id: errorText
                anchors.fill: parent
                anchors.margins: 14
                text: "错误：" + sidecarClient.errorMessage
                color: "#991B1B"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
        }

        Item {
            Layout.fillHeight: true
        }
    }
}
