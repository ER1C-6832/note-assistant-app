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

    function voiceAvailable() {
        return sidecarClient !== null
            && sidecarClient.connected
            && sidecarClient.pyXiaozhiRunning
    }

    function currentVoiceState() {
        if (!voiceAvailable()) {
            return "offline"
        }

        if (sidecarClient.assistantState !== undefined && sidecarClient.assistantState.length > 0) {
            return sidecarClient.assistantState
        }

        if (sidecarClient.assistantStatusText.indexOf("聆听") >= 0 || sidecarClient.lastRuntimeStateText.indexOf("listening") >= 0) {
            return "listening"
        }

        if (sidecarClient.assistantStatusText.indexOf("播报") >= 0 || sidecarClient.lastRuntimeStateText.indexOf("speaking") >= 0) {
            return "speaking"
        }

        return "idle"
    }

    function voiceButtonText() {
        var state = currentVoiceState()

        if (state === "offline") {
            return "未启动"
        }

        if (state === "starting") {
            return "正在启动"
        }

        if (state === "stopping") {
            return "正在停止"
        }

        if (state === "aborting") {
            return "正在打断"
        }

        if (state === "listening") {
            return "点击停止"
        }

        if (state === "speaking") {
            return "点击打断"
        }

        return "点击说话"
    }

    function handleVoiceClick() {
        if (!voiceAvailable()) {
            return
        }

        var state = currentVoiceState()

        if (state === "speaking") {
            sidecarClient.abortSpeaking()
            return
        }

        if (state === "listening" || state === "starting") {
            sidecarClient.stopListen()
            return
        }

        sidecarClient.startListen()
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
                connected: root.voiceAvailable()
                voiceState: root.currentVoiceState()
                statusText: root.voiceButtonText()

                onClicked: root.handleVoiceClick()

                onPressStarted: {
                    if (root.voiceAvailable() && sidecarClient !== null) {
                        sidecarClient.startListen()
                    }
                }

                onPressEnded: {
                    if (root.voiceAvailable() && sidecarClient !== null) {
                        sidecarClient.stopListen()
                    }
                }

                onAbortRequested: {
                    if (root.voiceAvailable() && sidecarClient !== null) {
                        sidecarClient.abortSpeaking()
                    }
                }
            }
        }
    }
}
