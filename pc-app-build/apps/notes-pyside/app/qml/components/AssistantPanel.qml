import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: "小智语音助手"
    property string statusText: sidecarClient !== null ? sidecarClient.assistantStatusText : "待机中"
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
                dotColor: sidecarClient !== null && sidecarClient.connected ? "#16A34A" : "#F59E0B"
                bgColor: sidecarClient !== null && sidecarClient.connected ? "#ECFDF3" : "#FFF7ED"
                textColor: sidecarClient !== null && sidecarClient.connected ? "#166534" : "#92400E"
            }
        }

        Rectangle {
            width: 96
            height: 96
            radius: 48
            color: sidecarClient !== null && sidecarClient.connected ? "#DBEAFE" : "#F3F4F6"
            Layout.alignment: Qt.AlignHCenter

            Text {
                anchors.centerIn: parent
                text: "语音"
                color: sidecarClient !== null && sidecarClient.connected ? "#2563EB" : "#6B7280"
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
                    text: sidecarClient !== null ? sidecarClient.statusText + " · " + sidecarClient.wsUrl : "Sidecar 未连接"
                    color: "#374151"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    text: sidecarClient !== null ? sidecarClient.notesApiStatusText : "Notes API 未确认"
                    color: "#374151"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    text: sidecarClient !== null ? sidecarClient.pyXiaozhiStatusText + " · " + sidecarClient.notesToolStatusText : "py-xiaozhi 未确认"
                    color: "#374151"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: sidecarClient !== null && (sidecarClient.lastToolEventText.length > 0 || sidecarClient.lastToolResultText.length > 0)
            radius: 16
            color: "#EAF0FF"
            implicitHeight: toolColumn.implicitHeight + 28

            ColumnLayout {
                id: toolColumn
                anchors.fill: parent
                anchors.margins: 14
                spacing: 6

                Text {
                    Layout.fillWidth: true
                    text: sidecarClient !== null && sidecarClient.lastToolName.length > 0
                          ? "工具调用：" + sidecarClient.lastToolName + " · " + sidecarClient.lastToolStatus
                          : "工具调用"
                    color: "#1E3A8A"
                    font.pixelSize: 14
                    font.bold: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    visible: sidecarClient !== null && sidecarClient.lastToolEventText.length > 0
                    text: sidecarClient !== null ? sidecarClient.lastToolEventText : ""
                    color: "#1E3A8A"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    visible: sidecarClient !== null && sidecarClient.lastToolResultText.length > 0
                    text: sidecarClient !== null ? sidecarClient.lastToolResultText : ""
                    color: "#1E3A8A"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.transcript.length > 0
            radius: 16
            color: "#F8FAFC"
            implicitHeight: transcriptText.implicitHeight + 28

            Text {
                id: transcriptText
                anchors.fill: parent
                anchors.margins: 14
                text: "识别文本：" + root.transcript
                color: "#374151"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.reply.length > 0
            radius: 16
            color: "#F7F8FA"
            implicitHeight: replyText.implicitHeight + 28

            Text {
                id: replyText
                anchors.fill: parent
                anchors.margins: 14
                text: "助手回复：" + root.reply
                color: "#374151"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.resultTitle.length > 0 || root.resultText.length > 0
            radius: 16
            color: "#ECFDF3"
            implicitHeight: resultColumn.implicitHeight + 28

            ColumnLayout {
                id: resultColumn
                anchors.fill: parent
                anchors.margins: 14
                spacing: 6

                Text {
                    Layout.fillWidth: true
                    text: root.resultTitle.length > 0 ? root.resultTitle : "执行结果"
                    color: "#166534"
                    font.pixelSize: 14
                    font.bold: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    Layout.fillWidth: true
                    text: root.resultText
                    color: "#166534"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: sidecarClient !== null && sidecarClient.lastEventText.length > 0
            radius: 16
            color: "#FFF7ED"
            implicitHeight: eventText.implicitHeight + 28

            Text {
                id: eventText
                anchors.fill: parent
                anchors.margins: 14
                text: "最近事件：" + (sidecarClient !== null ? sidecarClient.lastEventText : "")
                color: "#92400E"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: sidecarClient !== null && sidecarClient.errorMessage.length > 0
            radius: 16
            color: "#FEF2F2"
            implicitHeight: errorText.implicitHeight + 28

            Text {
                id: errorText
                anchors.fill: parent
                anchors.margins: 14
                text: "错误：" + (sidecarClient !== null ? sidecarClient.errorMessage : "")
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
