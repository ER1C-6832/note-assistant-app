import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property int searchResetToken: 0

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
                    text: "本地便签工作区"
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
    }
}
