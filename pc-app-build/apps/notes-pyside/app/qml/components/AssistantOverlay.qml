import QtQuick

Item {
    id: root

    property var viewModelRef: null
    property bool windowActive: true
    property bool expanded: false
    property int safeMargin: 24
    property int launcherSize: 80
    readonly property bool ready: viewModelRef !== null

    function clamp(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value))
    }

    function restoreLauncherPosition() {
        var availableWidth = Math.max(1, width - launcher.width - safeMargin * 2)
        var availableHeight = Math.max(1, height - launcher.height - safeMargin * 2)
        var xRatio = ready ? viewModelRef.launcherXRatio : 1.0
        var yRatio = ready ? viewModelRef.launcherYRatio : 1.0
        launcher.x = safeMargin + clamp(xRatio, 0, 1) * availableWidth
        launcher.y = safeMargin + clamp(yRatio, 0, 1) * availableHeight
        placePanelNearLauncher()
    }

    function persistLauncherPosition() {
        if (!ready) return
        var availableWidth = Math.max(1, width - launcher.width - safeMargin * 2)
        var availableHeight = Math.max(1, height - launcher.height - safeMargin * 2)
        var xRatio = clamp((launcher.x - safeMargin) / availableWidth, 0, 1)
        var yRatio = clamp((launcher.y - safeMargin) / availableHeight, 0, 1)
        viewModelRef.requestLauncherPosition(xRatio, yRatio)
    }

    function placePanelNearLauncher() {
        if (!expanded || !floatingPanel.visible) return
        var preferLeft = launcher.x > width / 2
        var preferredX = preferLeft
                         ? launcher.x - floatingPanel.width - 12
                         : launcher.x + launcher.width + 12
        var preferredY = launcher.y + launcher.height - floatingPanel.height
        floatingPanel.x = clamp(
            preferredX,
            safeMargin,
            Math.max(safeMargin, width - floatingPanel.width - safeMargin)
        )
        floatingPanel.y = clamp(
            preferredY,
            safeMargin,
            Math.max(safeMargin, height - floatingPanel.height - safeMargin)
        )
    }

    function setExpanded(value) {
        expanded = Boolean(value)
    }

    function handleLauncherActivation() {
        if (ready
                && viewModelRef.voiceInteractionMode === "streaming_conversation"
                && (viewModelRef.streamingConversationActive
                    || viewModelRef.canStartStreamingConversation)) {
            viewModelRef.requestStreamingConversationToggle()
            return
        }
        expanded = !expanded
    }

    onWidthChanged: restoreLauncherPosition()
    onHeightChanged: restoreLauncherPosition()
    onReadyChanged: restoreLauncherPosition()
    onExpandedChanged: {
        if (expanded) Qt.callLater(placePanelNearLauncher)
    }
    Component.onCompleted: Qt.callLater(restoreLauncherPosition)

    Item {
        id: launcher
        objectName: "assistantLauncher"
        width: root.launcherSize
        height: root.launcherSize
        z: 42

        AuroraAssistantButton {
            anchors.fill: parent
            viewModelRef: root.viewModelRef
            animationEnabled: root.windowActive
            onActivated: root.handleLauncherActivation()
        }

        TapHandler {
            acceptedButtons: Qt.RightButton
            onTapped: root.expanded = !root.expanded
        }

        DragHandler {
            id: launcherDrag
            target: launcher
            xAxis.minimum: root.safeMargin
            xAxis.maximum: Math.max(root.safeMargin, root.width - launcher.width - root.safeMargin)
            yAxis.minimum: root.safeMargin
            yAxis.maximum: Math.max(root.safeMargin, root.height - launcher.height - root.safeMargin)
            onActiveChanged: {
                if (!active) {
                    root.persistLauncherPosition()
                    if (root.expanded) root.placePanelNearLauncher()
                }
            }
        }
    }

    AssistantFloatingPanel {
        id: floatingPanel
        viewModelRef: root.viewModelRef
        visible: root.expanded
        z: 41
        onCloseRequested: root.expanded = false
    }

    Keys.onEscapePressed: function(event) {
        if (root.expanded) {
            root.expanded = false
            event.accepted = true
        }
    }
}
