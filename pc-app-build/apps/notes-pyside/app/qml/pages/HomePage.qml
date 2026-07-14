import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var notesModel
    property var notesViewModelRef: null
    property int selectedIndex: -1
    property string activeCategory: "all"

    signal noteSelected(int index)
    signal createRequested()
    signal editRequested()
    signal deleteRequested()
    signal pinRequested()
    signal bulkDeleteRequested(var noteIds)
    signal bulkPinRequested(var noteIds)
    signal bulkUnpinRequested(var noteIds)

    RowLayout {
        anchors.fill: parent
        spacing: 20

        NoteList {
            Layout.preferredWidth: 500
            Layout.fillHeight: true
            notesModel: root.notesModel
            notesViewModelRef: root.notesViewModelRef
            selectedIndex: root.selectedIndex
            activeCategory: root.activeCategory

            onNoteSelected: function(index) { root.noteSelected(index) }
            onCreateRequested: root.createRequested()
            onBulkDeleteRequested: function(noteIds) { root.bulkDeleteRequested(noteIds) }
            onBulkPinRequested: function(noteIds) { root.bulkPinRequested(noteIds) }
            onBulkUnpinRequested: function(noteIds) { root.bulkUnpinRequested(noteIds) }
        }

        DetailPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            hasSelection: root.notesViewModelRef !== null && root.notesViewModelRef.hasSelection
            isPinned: root.notesViewModelRef !== null && root.notesViewModelRef.selectedIsPinned
            title: root.notesViewModelRef !== null ? root.notesViewModelRef.selectedTitle : ""
            content: root.notesViewModelRef !== null ? root.notesViewModelRef.selectedContent : ""
            tags: root.notesViewModelRef !== null ? root.notesViewModelRef.selectedTagsText : ""
            updated: root.notesViewModelRef !== null ? root.notesViewModelRef.selectedUpdatedText : ""
            source: root.notesViewModelRef !== null ? root.notesViewModelRef.selectedSourceText : ""

            onEditRequested: root.editRequested()
            onDeleteRequested: root.deleteRequested()
            onPinRequested: root.pinRequested()
        }
    }
}
