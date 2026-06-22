import QtQuick
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
    radius: 20

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    Layout.fillWidth: true
                    text: root.title
                    color: "#111827"
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

            AppButton {
                text: "编辑"
                variant: "secondary"
                compact: true
                onClicked: root.editRequested()
            }

            AppButton {
                text: "删除"
                variant: "softDanger"
                compact: true
                onClicked: root.deleteRequested()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 18
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
                Layout.fillWidth: true
                text: root.tags
                color: "#4B5563"
                font.pixelSize: 13
            }

            AppButton {
                text: "增加闹钟"
                variant: "secondary"
                compact: true
            }
        }
    }
}
