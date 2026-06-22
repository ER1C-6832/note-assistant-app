import QtQuick
import QtQuick.Controls
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
    radius: 18

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        RowLayout {
            Layout.fillWidth: true

            Text {
                Layout.fillWidth: true
                text: root.title
                color: "#1A1A1A"
                font.pixelSize: 22
                font.bold: true
            }

            StatusBadge {
                text: root.statusText
                dotColor: root.statusText === "待机中" ? "#19B7A8" : "#4F7CFF"
            }
        }

        Rectangle {
            width: 96
            height: 96
            radius: 48
            color: "#DBEAFE"
            Layout.alignment: Qt.AlignHCenter

            Text {
                anchors.centerIn: parent
                text: "语音"
                color: "#2563EB"
                font.pixelSize: 18
                font.bold: true
            }
        }

        Text {
            Layout.fillWidth: true
            text: "可以说：帮我记录、查一下王总、修改或删除。"
            color: "#4B5563"
            font.pixelSize: 14
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.transcript.length > 0
            radius: 14
            color: "#F7F8FA"
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
            radius: 14
            color: "#EAF0FF"
            implicitHeight: replyText.implicitHeight + 28

            Text {
                id: replyText
                anchors.fill: parent
                anchors.margins: 14
                text: "助手回复：" + root.reply
                color: "#1E3A8A"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.resultTitle.length > 0
            radius: 14
            color: "#E8F9F1"
            implicitHeight: resultColumn.implicitHeight + 28

            ColumnLayout {
                id: resultColumn
                anchors.fill: parent
                anchors.margins: 14
                spacing: 6

                Text {
                    text: root.resultTitle
                    color: "#166534"
                    font.pixelSize: 14
                    font.bold: true
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

        Item {
            Layout.fillHeight: true
        }
    }
}
