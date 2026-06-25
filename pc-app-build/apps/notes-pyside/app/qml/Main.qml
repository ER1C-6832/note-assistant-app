import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "components"
import "pages"

ApplicationWindow {
    id: root

    width: 1440
    height: 960
    minimumWidth: 1180
    minimumHeight: 760
    visible: true
    title: "小智便签"
    color: "#F4F7FB"

    onClosing: function(close) {
        // Phase 8.9.3:
        // Do not synchronously stop py-xiaozhi or join SidecarClient here.
        // Python bootstrap already handles App-exit runtime stop in a non-blocking
        // fire-and-forget path. The visible window should close immediately.
        developerLogPanelVisible = false
        voicePanelVisible = false
        root.visible = false
        Qt.callLater(Qt.quit)
    }


    property string currentPage: "home"
    property string currentCategory: "all"
    property string pendingCategory: "all"
    property bool developerLogPanelVisible: false

    property bool voicePanelVisible: false
    property string voicePanelMode: "hidden"
    property string voicePanelTitle: ""
    property string voicePanelMessage: ""
    property string voicePanelActionType: ""
    property var voicePanelCandidates: []
    property int voicePanelNoteId: -1
    property string voicePanelNoteTitle: ""
    property string voicePanelNoteContent: ""
    property bool voicePanelDanger: false
    property bool voicePanelSuccess: true
    property int searchResetToken: 0
    property bool voiceRuntimeWarmupDone: false
    property int voiceRuntimeWarmupAttempts: 0

    function createInitialTags() {
        if (currentCategory === "todo") {
            return "待办"
        }
        if (currentCategory.indexOf("tag:") === 0) {
            return currentCategory.substring(4)
        }
        return ""
    }

    function createInitialPinned() {
        return currentCategory === "pinned"
    }


    function voiceAvailable() {
        return sidecarClient !== null
            && sidecarClient.connected
            && sidecarClient.voiceRuntimeReady
    }

    function voiceCanRequestStartup() {
        return sidecarClient !== null
            && sidecarClient.connected
            && !sidecarClient.voiceRuntimeReady
            && !sidecarClient.pyXiaozhiRunning
    }

    function currentVoiceState() {
        if (sidecarClient !== null && (sidecarClient.assistantState === "starting" || (sidecarClient.pyXiaozhiRunning && !sidecarClient.voiceRuntimeReady))) {
            return "starting"
        }

        if (!voiceAvailable()) {
            return "offline"
        }

        if (sidecarClient.voiceButtonState !== undefined && sidecarClient.voiceButtonState.length > 0) {
            return sidecarClient.voiceButtonState
        }

        return "idle"
    }

    function voiceButtonText() {
        var state = currentVoiceState()

        if (state === "offline") {
            return voiceCanRequestStartup() ? "启动语音" : "未启动"
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
            if (voiceCanRequestStartup()) {
                root.voiceRuntimeWarmupDone = false
                sidecarClient.startPyXiaozhi()
            }
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

    function reloadCurrentContext() {
        if (currentCategory === "pinned") {
            notesController.loadCategory("pinned")
        } else if (currentCategory === "todo") {
            notesController.loadCategory("todo")
        } else if (currentCategory.indexOf("tag:") === 0) {
            notesController.loadTag(currentCategory.substring(4))
        } else if (currentCategory === "deleted") {
            notesController.loadDeleted()
        } else if (currentCategory === "search" && notesController.searchKeyword.length > 0) {
            notesController.searchNotes(notesController.searchKeyword)
        } else {
            notesController.loadAll()
        }
    }

    function openPage(pageName) {
        currentPage = pageName
    }

    function selectNote(index) {
        notesController.selectNote(index)
        currentPage = "home"
    }

    function openCategory(categoryKey) {
        currentCategory = categoryKey
        pendingCategory = categoryKey
        currentPage = categoryKey === "deleted" ? "deletedList" : "home"
        categoryLoadTimer.restart()
    }

    function openTag(tagName) {
        currentCategory = "tag:" + tagName
        currentPage = "home"
        tagLoadTimer.tagName = tagName
        tagLoadTimer.restart()
    }


    function showVoicePanel(mode, title, message, actionType) {
        voicePanelMode = mode
        voicePanelTitle = title || "语音操作"
        voicePanelMessage = message || ""
        voicePanelActionType = actionType || ""
        voicePanelVisible = true
    }

    function showVoiceResult(title, message, success) {
        voicePanelCandidates = []
        voicePanelNoteId = -1
        voicePanelDanger = false
        voicePanelSuccess = success === undefined ? true : success
        showVoicePanel(success === false ? "failure" : "result", title || (success === false ? "操作失败" : "操作完成"), message || "", "")
    }

    function showVoiceCandidates(payload) {
        voicePanelCandidates = payload.candidates || payload.items || []
        voicePanelDanger = payload.action_type === "delete" || payload.action_type === "hard_delete"
        voicePanelSuccess = true
        showVoicePanel(
            "candidates",
            payload.title || "请选择一条便签",
            payload.message || "语音助手找到了多条可能匹配的便签，请选择要操作的那一条。",
            payload.action_type || "select"
        )
    }

    function showVoiceDeleteConfirm(payload) {
        voicePanelCandidates = []
        voicePanelNoteId = Number(payload.note_id || payload.id || -1)
        voicePanelNoteTitle = String(payload.title || payload.note_title || "")
        voicePanelNoteContent = String(payload.content || payload.note_content || "")
        voicePanelDanger = true
        voicePanelSuccess = true
        showVoicePanel(
            "confirm_delete",
            payload.title_text || "确认删除便签",
            payload.message || "为了防止误删，请确认是否删除这条便签。",
            payload.action_type || "delete"
        )
    }

    function handleVoiceUiAction(action, payloadJson) {
        var payload = {}
        try {
            payload = JSON.parse(payloadJson)
        } catch (e) {
            payload = {}
        }

        if (action === "voice_result") {
            showVoiceResult(payload.title || "操作完成", payload.message || "", payload.success !== false)
            return
        }

        if (action === "voice_failure") {
            showVoiceResult(payload.title || "操作失败", payload.message || "语音操作失败，请重试。", false)
            return
        }

        if (action === "voice_candidates") {
            showVoiceCandidates(payload)
            return
        }

        if (action === "voice_confirm_delete") {
            showVoiceDeleteConfirm(payload)
            return
        }

        if (action === "show_search") {
            var query = String(payload.query || "").trim()
            if (query.length > 0) {
                root.currentCategory = "search"
                root.currentPage = "search"
                notesController.searchNotes(query)
            }
            return
        }

        if (action === "show_deleted") {
            root.openCategory("deleted")
            return
        }

        if (action === "show_pinned") {
            root.openCategory("pinned")
            return
        }

        if (action === "refresh_notes") {
            root.reloadCurrentContext()
            return
        }

        if (action === "add_tag") {
            var tag = String(payload.tag || "").trim()
            if (tag.length > 0) {
                notesController.addCustomTag(tag)
                root.showVoiceResult("标签已新增", "已新增标签：" + tag, true)
            }
            return
        }

        if (action === "delete_empty_tag") {
            var tagToDelete = String(payload.tag || "").trim()
            if (tagToDelete.length > 0) {
                notesController.deleteTag(tagToDelete)
                root.reloadCurrentContext()
                root.showVoiceResult("标签已删除", "已删除空标签：" + tagToDelete, true)
            }
            return
        }
    }

    Timer {
        id: startupTimer
        interval: 260
        repeat: false
        onTriggered: notesController.loadAll()
    }

    Timer {
        id: categoryLoadTimer
        interval: 30
        repeat: false
        onTriggered: {
            if (root.pendingCategory === "deleted") {
                notesController.loadDeleted()
            } else {
                notesController.loadCategory(root.pendingCategory)
            }
        }
    }

    Timer {
        id: tagLoadTimer
        property string tagName: ""
        interval: 30
        repeat: false
        onTriggered: notesController.loadTag(tagName)
    }

    Timer {
        id: liveSearchTimer
        property string keyword: ""
        interval: 220
        repeat: false
        onTriggered: {
            var text = String(keyword).trim()
            if (text.length === 0) {
                root.currentCategory = "all"
                root.currentPage = "home"
                notesController.loadAll()
            } else {
                root.currentCategory = "search"
                root.currentPage = "search"
                notesController.searchNotes(text)
            }
        }
    }


    Timer {
        id: voiceRuntimeWarmupTimer
        interval: 900
        repeat: true
        running: false

        onTriggered: {
            if (root.voiceRuntimeWarmupDone) {
                stop()
                return
            }

            root.voiceRuntimeWarmupAttempts += 1

            if (sidecarClient !== null && sidecarClient.connected) {
                if (sidecarClient.voiceRuntimeReady) {
                    root.voiceRuntimeWarmupDone = true
                    stop()
                    return
                }

                sidecarClient.prewarmPyXiaozhi()

                if (sidecarClient.voiceRuntimeReady || sidecarClient.pyXiaozhiRunning) {
                    root.voiceRuntimeWarmupDone = true
                    stop()
                    return
                }

                return
            }

            if (root.voiceRuntimeWarmupAttempts > 20) {
                stop()
            }
        }
    }

    Connections {
        target: sidecarClient
        function onUiActionRequested(action, payloadJson) {
            root.handleVoiceUiAction(action, payloadJson)
        }
    }

    Shortcut {
        sequence: "Ctrl+Shift+L"
        onActivated: root.developerLogPanelVisible = !root.developerLogPanelVisible
    }

    Component.onCompleted: {
        startupTimer.start()
        voiceRuntimeWarmupTimer.start()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        TopBar {
            Layout.fillWidth: true
            notesControllerRef: notesController
            sidecarClientRef: sidecarClient
            searchResetToken: root.searchResetToken

            onSearchRequested: function(keyword) {
                liveSearchTimer.keyword = keyword
                liveSearchTimer.restart()
            }

            onSearchTextChanged: function(keyword) {
                liveSearchTimer.keyword = keyword
                liveSearchTimer.restart()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            Sidebar {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                currentPage: root.currentPage
                activeCategory: root.currentCategory
                notesControllerRef: notesController
                sidecarClientRef: sidecarClient

                onCategoryRequested: function(categoryKey) {
                    root.openCategory(categoryKey)
                }

                onTagRequested: function(tagName) {
                    root.openTag(tagName)
                }

                onDeletedRequested: {
                    root.openCategory("deleted")
                }

                onPageRequested: function(pageName) {
                    if (pageName.indexOf("assistant") === 0) {
                        return
                    }
                    root.currentCategory = pageName
                    root.openPage(pageName)
                }
            }

            Loader {
                id: pageLoader
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceComponent: {
                    if (root.currentPage === "create") return createPage
                    if (root.currentPage === "edit") return editPage
                    if (root.currentPage === "deleteConfirm") return deleteConfirmPage
                    if (root.currentPage === "deletedList") return deletedListPage
                    if (root.currentPage === "search") return searchPage
                    if (root.currentPage === "settings") return settingsPage
                    return homePage
                }
            }
        }
    }




    VoiceButton {
        id: globalVoiceButton

        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 28
        anchors.bottomMargin: 28

        connected: sidecarClient !== null && sidecarClient.connected
        enabledForControl: root.voiceAvailable() || root.voiceCanRequestStartup()
        unavailableText: root.currentVoiceState() === "starting" ? "请稍后" : sidecarClient !== null && sidecarClient.connected ? "点击启动语音" : "Sidecar 未连接"
        voiceState: root.currentVoiceState()
        statusText: root.voiceButtonText()

        z: 180

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

    VoiceInteractionPanel {
        id: voiceInteractionPanel

        visible: root.voicePanelVisible
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 28
        anchors.bottomMargin: 92

        mode: root.voicePanelMode
        title: root.voicePanelTitle
        message: root.voicePanelMessage
        actionType: root.voicePanelActionType
        candidates: root.voicePanelCandidates
        noteId: root.voicePanelNoteId
        noteTitle: root.voicePanelNoteTitle
        noteContent: root.voicePanelNoteContent
        danger: root.voicePanelDanger
        success: root.voicePanelSuccess

        onClosed: {
            root.voicePanelVisible = false
        }

        onCandidateSelected: function(noteId, title, content) {
            if (root.voicePanelActionType === "delete" || root.voicePanelActionType === "hard_delete") {
                root.showVoiceDeleteConfirm({
                    "note_id": noteId,
                    "title": title,
                    "content": content,
                    "action_type": root.voicePanelActionType,
                    "message": root.voicePanelActionType === "hard_delete"
                        ? "该操作会永久删除，无法还原。请再次确认。"
                        : "该操作会把便签移入“已删除”，之后可还原。"
                })
                return
            }

            if (root.voicePanelActionType === "pin") {
                notesController.bulkPinNotesByIds([noteId])
                root.showVoiceResult("已置顶", "已置顶：" + title, true)
                return
            }

            if (root.voicePanelActionType === "unpin") {
                notesController.bulkUnpinNotesByIds([noteId])
                root.showVoiceResult("已取消置顶", "已取消置顶：" + title, true)
                return
            }

            root.voicePanelVisible = false
        }

        onConfirmRequested: function(noteId, actionType) {
            var ok = false

            if (actionType === "hard_delete") {
                ok = notesController.bulkHardDeleteDeletedNotesByIds([noteId])
                root.showVoiceResult(ok ? "已彻底删除" : "彻底删除失败",
                                     ok ? "便签已彻底删除，无法还原。" : notesController.errorMessage,
                                     ok)
                return
            }

            ok = notesController.bulkDeleteNotesByIds([noteId])
            root.showVoiceResult(ok ? "已删除" : "删除失败",
                                 ok ? "便签已移入“已删除”，可在已删除中还原。" : notesController.errorMessage,
                                 ok)
        }

        onRetryRequested: function(actionType) {
            root.voicePanelVisible = false
            if (root.currentCategory === "search" && notesController.searchKeyword.length > 0) {
                notesController.searchNotes(notesController.searchKeyword)
            } else {
                root.reloadCurrentContext()
            }
        }
    }

    Window {
        id: developerLogWindow

        visible: root.developerLogPanelVisible
        title: "开发者日志 - 小智便签"
        width: 440
        height: Math.max(720, root.height)
        x: root.x + root.width + 8
        y: root.y
        flags: Qt.Tool

        onClosing: function(close) {
            close.accepted = false
            root.developerLogPanelVisible = false
        }

        DeveloperLogPanel {
            anchors.fill: parent
            anchors.margins: 0
            sidecarClientRef: sidecarClient
        }
    }

    Component {
        id: homePage

        HomePage {
            notesModel: notesListModel
            notesControllerRef: notesController
            selectedIndex: notesController !== null ? notesController.selectedIndex : -1
            activeCategory: root.currentCategory

            onNoteSelected: function(index) {
                root.selectNote(index)
            }

            onCreateRequested: {
                root.openPage("create")
            }

            onEditRequested: {
                root.openPage("edit")
            }

            onDeleteRequested: {
                root.openPage("deleteConfirm")
            }

            onPinRequested: {
                notesController.toggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                notesController.bulkDeleteNotesByIds(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                notesController.bulkPinNotesByIds(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                notesController.bulkUnpinNotesByIds(noteIds)
            }

            onAssistantRequested: {
                // The old assistant demo page has been retired.
            }
        }
    }

    Component {
        id: createPage

        CreateNotePage {
            initialTags: root.createInitialTags()
            initialPinned: root.createInitialPinned()

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText, isPinned) {
                if (notesController.createNote(titleText, contentText, tagsText, isPinned)) {
                    root.openPage("home")
                    root.reloadCurrentContext()
                }
            }
        }
    }

    Component {
        id: editPage

        EditNotePage {
            noteTitle: notesController.selectedTitle
            noteContent: notesController.selectedContent
            noteTags: notesController.selectedTagsText

            onBackRequested: {
                root.openPage("home")
            }

            onSaved: function(titleText, contentText, tagsText) {
                if (notesController.updateSelectedNote(titleText, contentText, tagsText)) {
                    root.currentCategory = "all"
                    root.openPage("home")
                }
            }
        }
    }

    Component {
        id: deleteConfirmPage

        DeleteConfirmPage {
            noteTitle: notesController.selectedTitle

            onBackRequested: {
                root.openPage("home")
            }

            onDeleted: {
                if (notesController.deleteSelectedNote()) {
                    root.currentCategory = "all"
                    root.openPage("home")
                }
            }
        }
    }

    Component {
        id: deletedListPage

        DeletedNotesPage {
            deletedNotesModel: deletedNotesListModel

            onBackRequested: {
                root.currentCategory = "all"
                notesController.loadAll()
                root.openPage("home")
            }
        }
    }

    Component {
        id: searchPage

        SearchPage {
            keyword: notesController.searchKeyword
            notesModel: notesListModel
            selectedIndex: notesController !== null ? notesController.selectedIndex : -1

            onNoteSelected: function(index) {
                root.selectNote(index)
            }

            onBackRequested: {
                root.currentCategory = "all"
                notesController.loadAll()
                root.openPage("home")
            }

            onResetRequested: {
                root.currentCategory = "all"
                notesController.loadAll()
                root.searchResetToken += 1
                root.openPage("home")
                root.showVoiceResult("已重置搜索", "已返回全部便签。", true)
            }

            onEditRequested: {
                root.openPage("edit")
            }

            onDeleteSelectedRequested: {
                root.openPage("deleteConfirm")
            }

            onPinRequested: {
                notesController.toggleSelectedPin()
            }

            onBulkDeleteRequested: function(noteIds) {
                notesController.bulkDeleteNotesByIds(noteIds)
            }

            onBulkPinRequested: function(noteIds) {
                notesController.bulkPinNotesByIds(noteIds)
            }

            onBulkUnpinRequested: function(noteIds) {
                notesController.bulkUnpinNotesByIds(noteIds)
            }
        }
    }

    Component {
        id: settingsPage

        SettingsPage {
            onBackRequested: {
                root.currentCategory = "all"
                root.openPage("home")
            }
        }
    }
}
