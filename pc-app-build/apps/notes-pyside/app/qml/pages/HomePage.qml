import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var notesModel
    property int selectedIndex: -1
    property string activeCategory: "all"

    signal noteSelected(int index)
    signal createRequested()
    signal editRequested()
    signal deleteRequested()
    signal pinRequested()
    signal assistantRequested()

    RowLayout {
        anchors.fill: parent
        spacing: 20

        NoteList {
            Layout.preferredWidth: 500
            Layout.fillHeight: true
            notesModel: root.notesModel
            selectedIndex: root.selectedIndex
            activeCategory: root.activeCategory
            onNoteSelected: function(index) {
                root.noteSelected(index)
            }
            onCreateRequested: root.createRequested()
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            DetailPanel {
                anchors.fill: parent
                hasSelection: notesController.hasSelection
                isPinned: notesController.selectedIsPinned
                title: notesController.selectedTitle
                content: notesController.selectedContent
                tags: notesController.selectedTagsText
                updated: notesController.selectedUpdatedText
                source: notesController.selectedSourceText
                onEditRequested: root.editRequested()
                onDeleteRequested: root.deleteRequested()
                onPinRequested: root.pinRequested()
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
