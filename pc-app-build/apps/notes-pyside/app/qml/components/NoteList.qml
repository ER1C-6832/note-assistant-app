import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var notesModel
    property int selectedIndex: 0
    signal noteSelected(int index)

    color: "#FFFFFF"
    radius: 18

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        RowLayout {
            Layout.fillWidth: true

            Text {
                Layout.fillWidth: true
                text: "全部便签"
                color: "#1A1A1A"
                font.pixelSize: 18
                font.bold: true
            }

            Text {
                text: notesModel ? notesModel.count + " 条" : "0 条"
                color: "#9CA3AF"
                font.pixelSize: 13
            }
        }

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.notesModel
            spacing: 12
            clip: true

            delegate: NoteCard {
                width: ListView.view.width
                title: model.title
                content: model.content
                tags: model.tags
                updated: model.updated
                source: model.source
                cardColor: model.cardColor
                selected: index === root.selectedIndex
                onClicked: root.noteSelected(index)
            }
        }
    }
}
