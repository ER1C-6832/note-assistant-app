import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property bool connected: true
    property bool active: false
    property string statusText: active ? "正在聆听" : "语音助手"

    signal clicked()
    signal pressStarted()
    signal pressEnded()
    signal abortRequested()

    width: active ? 148 : 136
    height: 48
    radius: 24
    color: !connected ? "#F3F4F6" : mouse.containsMouse ? "#F7F8FA" : "#FFFFFF"
    border.color: active ? "#19B7A8" : "#E5E7EB"
    border.width: active ? 2 : 1
    z: 50
    clip: true

    Behavior on width {
        NumberAnimation { duration: 120 }
    }

    RowLayout {
        anchors.centerIn: parent
        spacing: 10

        Rectangle {
            width: 26
            height: 26
            radius: 13
            color: !root.connected ? "#9CA3AF" : root.active ? "#EF4444" : "#19B7A8"

            Rectangle {
                anchors.centerIn: parent
                width: root.active ? 10 : 8
                height: root.active ? 10 : 8
                radius: 5
                color: "#FFFFFF"
                opacity: root.connected ? 1 : 0.75
            }
        }

        Text {
            text: root.statusText
            color: root.connected ? "#111827" : "#6B7280"
            font.pixelSize: 14
            font.bold: true
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.connected ? Qt.PointingHandCursor : Qt.ArrowCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        pressAndHoldInterval: 450

        property bool ignoreNextClick: false
        property bool holding: false

        onPressAndHold: function(mouseEvent) {
            if (!root.connected || mouseEvent.button !== Qt.LeftButton) {
                return
            }
            holding = true
            ignoreNextClick = true
            root.pressStarted()
        }

        onReleased: {
            if (!root.connected) {
                return
            }
            if (holding) {
                holding = false
                root.pressEnded()
            }
        }

        onClicked: function(mouseEvent) {
            if (!root.connected) {
                return
            }

            if (mouseEvent.button === Qt.RightButton) {
                root.abortRequested()
                return
            }

            if (ignoreNextClick) {
                ignoreNextClick = false
                return
            }

            root.clicked()
        }
    }
}
