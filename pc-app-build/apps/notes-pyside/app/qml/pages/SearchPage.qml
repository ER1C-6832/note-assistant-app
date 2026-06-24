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
                notesControllerRef: notesController
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

            AppButton {
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: 20
                anchors.rightMargin: 20
                text: "重置搜索"
                variant: "secondary"
                implicitWidth: 96
                implicitHeight: 38
                onClicked: root.resetRequested()
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
