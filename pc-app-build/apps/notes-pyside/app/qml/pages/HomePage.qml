import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var notesModel
    property int selectedIndex: 0

    signal noteSelected(int index)
    signal createRequested()
    signal editRequested()
    signal deleteRequested()
    signal searchRequested()
    signal assistantRequested()

    RowLayout {
        anchors.fill: parent
        spacing: 20

        NoteList {
            Layout.preferredWidth: 500
            Layout.fillHeight: true
            notesModel: root.notesModel
            selectedIndex: root.selectedIndex
            onNoteSelected: function(index) {
                root.noteSelected(index)
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            DetailPanel {
                anchors.fill: parent
                title: root.notesModel.get(root.selectedIndex).title
                content: root.notesModel.get(root.selectedIndex).content
                tags: root.notesModel.get(root.selectedIndex).tags
                updated: root.notesModel.get(root.selectedIndex).updated
                source: root.notesModel.get(root.selectedIndex).source
                onEditRequested: root.editRequested()
                onDeleteRequested: root.deleteRequested()
            }

            VoiceButton {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 24
                anchors.bottomMargin: 24
                onClicked: root.assistantRequested()
            }
        }
    }
}
