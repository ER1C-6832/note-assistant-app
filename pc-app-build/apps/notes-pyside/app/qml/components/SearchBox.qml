import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    signal searchRequested(string keyword)
    signal searchTextChanged(string keyword)
    color: "#F7F8FA"
    radius: 16
    height: 46
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 8
        spacing: 10
        Text { text: "⌕"; color: "#6B7280"; font.pixelSize: 18 }
        TextField {
            id: searchField
            Layout.fillWidth: true
            placeholderText: "搜索标题、正文、标签……"
            background: null
            font.pixelSize: 14
            color: "#1A1A1A"
            placeholderTextColor: "#9CA3AF"
            selectByMouse: true
            onTextChanged: root.searchTextChanged(searchField.text)
            onAccepted: root.searchRequested(searchField.text)
        }
        AppButton { text: "搜索"; variant: "secondary"; compact: true; onClicked: root.searchRequested(searchField.text) }
    }
}
