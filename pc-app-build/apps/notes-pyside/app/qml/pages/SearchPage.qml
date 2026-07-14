import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property string keyword: ""
    property var notesModel
    property var notesViewModelRef: null
    property int selectedIndex: -1

    readonly property bool viewModelReady: root.notesViewModelRef !== null
    readonly property bool mutationBusy: root.viewModelReady && root.notesViewModelRef.mutationBusy

    signal noteSelected(int index)
    signal backRequested()
    signal resetRequested()
    signal editRequested()
    signal deleteSelectedRequested()
    signal pinRequested()
    signal bulkDeleteRequested(var noteIds)
    signal bulkPinRequested(var noteIds)
    signal bulkUnpinRequested(var noteIds)

    RowLayout {
        anchors.fill: parent
        spacing: 20

        Item {
            Layout.preferredWidth: 560
            Layout.fillHeight: true

            NoteList {
                anchors.fill: parent
                notesModel: root.notesModel
                notesViewModelRef: root.notesViewModelRef
                selectedIndex: root.selectedIndex
                activeCategory: "search"
                showCreateButton: false

                onNoteSelected: function(index) { root.noteSelected(index) }
                onBulkDeleteRequested: function(noteIds) { root.bulkDeleteRequested(noteIds) }
                onBulkPinRequested: function(noteIds) { root.bulkPinRequested(noteIds) }
                onBulkUnpinRequested: function(noteIds) { root.bulkUnpinRequested(noteIds) }
            }

            AppButton {
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: 20
                anchors.rightMargin: 20
                text: "重置搜索"
                variant: "secondary"
                implicitWidth: 96
                implicitHeight: 38
                enabled: root.viewModelReady && !root.mutationBusy
                onClicked: root.resetRequested()
            }
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
            onDeleteRequested: root.deleteSelectedRequested()
            onPinRequested: root.pinRequested()
        }
    }
}
