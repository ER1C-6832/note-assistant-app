import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var notesModel
    property var notesViewModelRef: null
    property int selectedIndex: -1
    property string activeCategory: "all"

    readonly property bool viewModelReady: root.notesViewModelRef !== null
    readonly property bool mutationBusy: root.viewModelReady && root.notesViewModelRef.mutationBusy

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
            hasSelection: root.viewModelReady && root.notesViewModelRef.hasSelection
            isPinned: root.viewModelReady && root.notesViewModelRef.selectedIsPinned
            actionsEnabled: root.viewModelReady && !root.mutationBusy
            title: root.viewModelReady ? root.notesViewModelRef.selectedTitle : ""
            content: root.viewModelReady ? root.notesViewModelRef.selectedContent : ""
            tags: root.viewModelReady ? root.notesViewModelRef.selectedTagsText : ""
            updated: root.viewModelReady ? root.notesViewModelRef.selectedUpdatedText : ""
            source: root.viewModelReady ? root.notesViewModelRef.selectedSourceText : ""

            onEditRequested: root.editRequested()
            onDeleteRequested: root.deleteRequested()
            onPinRequested: root.pinRequested()
        }
    }
}
