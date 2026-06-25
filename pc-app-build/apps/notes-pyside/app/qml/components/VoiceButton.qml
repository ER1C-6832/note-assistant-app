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

    readonly property bool starting: voiceState === "starting"
    readonly property bool available: connected && enabledForControl
    readonly property bool active: voiceState === "listening" || voiceState === "speaking" || voiceState === "starting"

    width: root.starting ? 176 : 156
    height: 50
    radius: 25
    color: root.starting ? "#EAF0FF"
           : !root.available ? "#F3F4F6"
           : voiceState === "speaking" ? "#FFF7ED"
           : voiceState === "listening" ? "#ECFDF3"
           : mouse.containsMouse ? "#F7F8FA"
           : "#FFFFFF"
    border.color: root.starting ? "#4F7CFF"
                  : !root.available ? "#E5E7EB"
                  : voiceState === "speaking" ? "#F97316"
                  : voiceState === "listening" ? "#19B7A8"
                  : "#E5E7EB"
    border.width: (root.available && active) || root.starting ? 2 : 1
    z: 50
    clip: true

    RowLayout {
        anchors.centerIn: parent
        spacing: 10

        Rectangle {
            id: iconCircle
            width: 26
            height: 26
            radius: 13
            color: root.starting ? "#2563EB"
                   : !root.available ? "#9CA3AF"
                   : root.voiceState === "speaking" ? "#F97316"
                   : root.voiceState === "listening" ? "#16A34A"
                   : root.voiceState === "stopping" ? "#F97316"
                   : root.voiceState === "aborting" ? "#F97316"
                   : "#19B7A8"

            Rectangle {
                anchors.centerIn: parent
                width: root.voiceState === "listening" ? 11 : 8
                height: root.voiceState === "listening" ? 11 : 8
                radius: 5.5
                color: "#FFFFFF"
                opacity: root.starting ? 0 : (root.available ? 1 : 0.75)
            }

            Rectangle {
                id: spinner
                visible: root.starting
                anchors.centerIn: parent
                width: 18
                height: 18
                radius: 9
                color: "transparent"
                border.width: 2
                border.color: "#FFFFFF"

                Rectangle {
                    width: 5
                    height: 5
                    radius: 2.5
                    color: "#2563EB"
                    anchors.top: parent.top
                    anchors.horizontalCenter: parent.horizontalCenter
                }

                NumberAnimation on rotation {
                    running: root.starting
                    from: 0
                    to: 360
                    duration: 900
                    loops: Animation.Infinite
                }
            }
        }

        ColumnLayout {
            spacing: 0

            Text {
                text: root.statusText
                color: root.starting ? "#1E3A8A" : root.available ? "#111827" : "#6B7280"
                font.pixelSize: 14
                font.bold: true
                elide: Text.ElideRight
                Layout.maximumWidth: root.starting ? 116 : 96
            }

            Text {
                text: root.starting ? "请稍后，正在准备" : root.available ? "单击开始/停止/打断" : root.unavailableText
                color: root.starting ? "#64748B" : "#9CA3AF"
                font.pixelSize: 10
                elide: Text.ElideRight
                Layout.maximumWidth: root.starting ? 120 : 100
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
            if (!root.available || mouseEvent.button !== Qt.LeftButton) return
            pressAndHoldActive = true
            suppressNextClick = true
            root.pressStarted()
        }

        onReleased: function(mouseEvent) {
            if (!root.available) return
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
            if (!root.available) return
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
