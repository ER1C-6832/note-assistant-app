import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string content: ""
    property string tags: ""
    property string updated: ""
    property string source: ""

    signal editRequested()
    signal deleteRequested()

    color: "#FFFFFF"
    radius: 18

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 18

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: root.title
                    color: "#1A1A1A"
                    font.pixelSize: 26
                    font.bold: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: "更新时间：" + root.updated + "  ·  来源：" + root.source
                    color: "#9CA3AF"
                    font.pixelSize: 12
                }
            }

            Button {
                text: "编辑"
                onClicked: root.editRequested()
            }

            Button {
                text: "删除"
                onClicked: root.deleteRequested()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 16
            color: "#F7F8FA"

            Text {
                anchors.fill: parent
                anchors.margins: 18
                text: root.content
                color: "#374151"
                font.pixelSize: 16
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "标签："
                color: "#9CA3AF"
                font.pixelSize: 13
            }

            Text {
                text: root.tags
                color: "#4B5563"
                font.pixelSize: 13
            }

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: "增加闹钟"
            }
        }
    }
}
