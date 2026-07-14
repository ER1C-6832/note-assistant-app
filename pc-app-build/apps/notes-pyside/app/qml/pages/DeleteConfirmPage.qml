import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property string noteTitle: "便签"
    property bool mutationBusy: false
    property string errorMessage: ""

    signal backRequested()
    signal deleted()

    Rectangle {
        anchors.fill: parent
        color: "#FFFFFF"
        radius: 20

        Rectangle {
            width: 520
            height: 330
            anchors.centerIn: parent
            color: "#FFFFFF"
            radius: 24
            border.color: "#FECACA"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 18

                Text {
                    Layout.fillWidth: true
                    text: "确认删除这条便签吗？"
                    color: "#111827"
                    font.pixelSize: 24
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    Layout.fillWidth: true
                    text: "“" + root.noteTitle + "” 将被移入已删除。"
                    color: "#4B5563"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: root.errorMessage.length > 0
                    radius: 12
                    color: "#FEF2F2"
                    implicitHeight: 42
                    Text {
                        anchors.centerIn: parent
                        width: parent.width - 20
                        text: root.errorMessage
                        color: "#991B1B"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item {
                    Layout.fillHeight: true
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 14

                    AppButton {
                        text: "取消"
                        variant: "secondary"
                        enabled: !root.mutationBusy
                        onClicked: root.backRequested()
                    }

                    AppButton {
                        text: root.mutationBusy ? "删除中…" : "确认删除"
                        variant: "danger"
                        enabled: !root.mutationBusy
                        onClicked: root.deleted()
                    }
                }
            }
        }
    }
}
