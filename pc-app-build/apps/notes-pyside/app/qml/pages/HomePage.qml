import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var notesModel
    property var notesControllerRef: null
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
    signal assistantRequested()

    function voiceActive() {
        if (sidecarClient === null) {
            return false
        }
        return sidecarClient.assistantStatusText.indexOf("聆听") >= 0
            || sidecarClient.lastRuntimeStateText.indexOf("聆听") >= 0
            || sidecarClient.lastRuntimeStateText.indexOf("listening") >= 0
    }

    RowLayout {
        anchors.fill: parent
        spacing: 20

        NoteList {
            Layout.preferredWidth: 500
            Layout.fillHeight: true
            notesModel: root.notesModel
            notesControllerRef: root.notesControllerRef
            selectedIndex: root.selectedIndex
            activeCategory: root.activeCategory

            onNoteSelected: function(index) {
                root.noteSelected(index)
            }

            onCreateRequested: root.createRequested()

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

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            DetailPanel {
                anchors.fill: parent
                hasSelection: root.notesControllerRef !== null && root.notesControllerRef.hasSelection
                isPinned: root.notesControllerRef !== null && root.notesControllerRef.selectedIsPinned
                title: root.notesControllerRef !== null ? root.notesControllerRef.selectedTitle : ""
                content: root.notesControllerRef !== null ? root.notesControllerRef.selectedContent : ""
                tags: root.notesControllerRef !== null ? root.notesControllerRef.selectedTagsText : ""
                updated: root.notesControllerRef !== null ? root.notesControllerRef.selectedUpdatedText : ""
                source: root.notesControllerRef !== null ? root.notesControllerRef.selectedSourceText : ""

                onEditRequested: root.editRequested()
                onDeleteRequested: root.deleteRequested()
                onPinRequested: root.pinRequested()
            }

            VoiceButton {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 32
                anchors.bottomMargin: 32
                connected: sidecarClient !== null && sidecarClient.connected
                active: root.voiceActive()
                statusText: active ? "正在聆听" : "语音助手"

                onClicked: {
                    // Do not navigate away from HomePage. The floating voice
                    // button is a runtime control, not a page switch.
                    if (sidecarClient !== null) {
                        sidecarClient.toggleListen()
                    }
                }

                onPressStarted: {
                    // Press-and-hold starts listening in place.
                    if (sidecarClient !== null) {
                        sidecarClient.startListen()
                    }
                }

                onPressEnded: {
                    if (sidecarClient !== null) {
                        sidecarClient.stopListen()
                    }
                }

                onAbortRequested: {
                    // Right-click aborts speaking in place.
                    if (sidecarClient !== null) {
                        sidecarClient.abortSpeaking()
                    }
                }
            }
        }
    }
}
