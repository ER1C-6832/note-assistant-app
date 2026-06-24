import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property bool connected: true
    property bool enabledForControl: true
    property string voiceState: "idle"
    property string statusText: "点击说话"
    property string unavailableText: "请先在设置启动"

    signal clicked()
    signal pressStarted()
    signal pressEnded()
    signal abortRequested()

    readonly property bool available: connected && enabledForControl
    readonly property bool active: voiceState === "listening" || voiceState === "starting"

    width: 156
    height: 50
    radius: 25
    color: !root.available ? "#F3F4F6"
           : root.voiceState === "listening" ? "#ECFDF3"
           : mouse.containsMouse ? "#F7F8FA"
           : "#FFFFFF"
    border.color: !root.available ? "#E5E7EB"
                 : root.voiceState === "listening" ? "#19B7A8"
                 : "#E5E7EB"
    border.width: root.available && active ? 2 : 1
    z: 50
    clip: true

    RowLayout {
        anchors.centerIn: parent
        spacing: 10

        Rectangle {
            width: 26
            height: 26
            radius: 13
            color: !root.available ? "#9CA3AF"
                   : root.voiceState === "listening" ? "#16A34A"
                   : root.voiceState === "starting" ? "#2563EB"
                   : root.voiceState === "stopping" ? "#F97316"
                   : root.voiceState === "aborting" ? "#F97316"
                   : "#19B7A8"

            Rectangle {
                anchors.centerIn: parent
                width: root.voiceState === "listening" ? 11 : 8
                height: root.voiceState === "listening" ? 11 : 8
                radius: 5.5
                color: "#FFFFFF"
                opacity: root.available ? 1 : 0.75
            }
        }

        ColumnLayout {
            spacing: 0

            Text {
                text: root.statusText
                color: root.available ? "#111827" : "#6B7280"
                font.pixelSize: 14
                font.bold: true
                elide: Text.ElideRight
                Layout.maximumWidth: 96
            }

            Text {
                text: root.available ? "单击开始/停止 · 右键打断" : root.unavailableText
                color: "#9CA3AF"
                font.pixelSize: 10
                elide: Text.ElideRight
                Layout.maximumWidth: 100
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.available ? Qt.PointingHandCursor : Qt.ArrowCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        pressAndHoldInterval: 520

        property bool pressAndHoldActive: false
        property bool suppressNextClick: false

        onPressAndHold: function(mouseEvent) {
            if (!root.available || mouseEvent.button !== Qt.LeftButton) {
                return
            }

            pressAndHoldActive = true
            suppressNextClick = true
            root.pressStarted()
        }

        onReleased: function(mouseEvent) {
            if (!root.available) {
                return
            }

            if (pressAndHoldActive && mouseEvent.button === Qt.LeftButton) {
                pressAndHoldActive = false
                root.pressEnded()
            }
        }

        onCanceled: {
            if (pressAndHoldActive) {
                pressAndHoldActive = false
                root.pressEnded()
            }
        }

        onClicked: function(mouseEvent) {
            if (!root.available) {
                return
            }

            if (mouseEvent.button === Qt.RightButton) {
                root.abortRequested()
                return
            }

            if (suppressNextClick) {
                suppressNextClick = false
                return
            }

            root.clicked()
        }
    }
}
