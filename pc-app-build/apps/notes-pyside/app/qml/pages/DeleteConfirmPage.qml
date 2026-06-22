import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string noteTitle: "联系王总"

    signal backRequested()
    signal deleted()

    Rectangle {
        anchors.fill: parent
        color: "#FFFFFF"
        radius: 18

        Rectangle {
            width: 520
            height: 300
            anchors.centerIn: parent
            color: "#FFFFFF"
            radius: 22
            border.color: "#FEE2E2"
            border.width: 2

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 18

                Text {
                    Layout.fillWidth: true
                    text: "确认删除这条便签吗？"
                    color: "#1A1A1A"
                    font.pixelSize: 24
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    Layout.fillWidth: true
                    text: "“" + root.noteTitle + "” 将被移入已删除，后续可做恢复入口。"
                    color: "#4B5563"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }

                Item {
                    Layout.fillHeight: true
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 14

                    Button {
                        text: "取消"
                        onClicked: root.backRequested()
                    }

                    Button {
                        text: "确认删除"
                        onClicked: root.deleted()
                    }
                }
            }
        }
    }
}
