import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property int noteId: -1
    property string title: ""
    property string content: ""
    property string tags: ""
    property string updated: ""
    property string source: ""
    property color cardColor: "#FFF6CC"
    property bool selected: false
    property bool multiSelectMode: false
    property bool selectedForBulk: false
    signal clicked()
    color: cardColor
    radius: 18
    border.color: selected || selectedForBulk ? "#4F7CFF" : "transparent"
    border.width: selected || selectedForBulk ? 2 : 0
    implicitHeight: 118
    clip: true
    RowLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12
        Rectangle { visible: root.multiSelectMode; width: 22; height: 22; radius: 11; color: root.selectedForBulk ? "#4F7CFF" : "#FFFFFF"; border.color: root.selectedForBulk ? "#4F7CFF" : "#CBD5E1"; border.width: 1; Text { anchors.centerIn: parent; text: "✓"; visible: root.selectedForBulk; color: "#FFFFFF"; font.pixelSize: 13; font.bold: true } }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: root.title; color: "#111827"; font.pixelSize: 15; font.bold: true; elide: Text.ElideRight } Text { text: root.updated; color: "#9CA3AF"; font.pixelSize: 11 } }
            Text { Layout.fillWidth: true; text: root.content; color: "#4B5563"; font.pixelSize: 12; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
            RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: root.tags; color: "#6B7280"; font.pixelSize: 11; elide: Text.ElideRight } Rectangle { visible: root.source === "语音" || root.source === "移动端语音"; radius: 999; color: "#FFFFFF"; implicitWidth: 62; implicitHeight: 24; Text { anchors.centerIn: parent; text: "来自语音"; color: "#4F7CFF"; font.pixelSize: 11 } } }
        }
    }
    MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked() }
}
