import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property string keyword: ""
    property var notesModel
    property int selectedIndex: -1

    signal noteSelected(int index)
    signal backRequested()
    signal editRequested()
    signal deleteSelectedRequested()
    signal pinRequested()
    signal bulkDeleteRequested(var noteIds)
    signal bulkPinRequested(var noteIds)
    signal bulkUnpinRequested(var noteIds)

    RowLayout {
        anchors.fill: parent
        spacing: 20

        NoteList {
            Layout.preferredWidth: 560
            Layout.fillHeight: true
            notesModel: root.notesModel
            selectedIndex: root.selectedIndex
            activeCategory: "search"
            showCreateButton: false

            onNoteSelected: function(index) {
                root.noteSelected(index)
            }

            onBulkDeleteRequested: function(noteIds) {
                root.bulkDeleteRequested(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                root.bulkPinRequested(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                root.bulkUnpinRequested(noteIds)
            }
        }

        DetailPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            hasSelection: notesController.hasSelection
            isPinned: notesController.selectedIsPinned
            title: notesController.selectedTitle
            content: notesController.selectedContent
            tags: notesController.selectedTagsText
            updated: notesController.selectedUpdatedText
            source: notesController.selectedSourceText

            onEditRequested: root.editRequested()
            onDeleteRequested: root.deleteSelectedRequested()
            onPinRequested: root.pinRequested()
        }
    }
}
