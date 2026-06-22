import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string text: ""
    property string variant: "primary" // primary, secondary, ghost, danger, softDanger
    property int buttonRadius: 14
    property int buttonHorizontalPadding: 18
    property bool compact: false

    signal clicked()

    implicitWidth: Math.max(label.implicitWidth + buttonHorizontalPadding * 2, compact ? 72 : 96)
    implicitHeight: compact ? 36 : 42

    radius: buttonRadius
    color: {
        if (!root.enabled) return "#F3F4F6"
        if (mouse.pressed) return "#DDE7FF"
        if (mouse.containsMouse && root.variant === "primary") return "#3F6AF2"
        if (mouse.containsMouse && root.variant === "danger") return "#DC2626"
        if (mouse.containsMouse && root.variant === "softDanger") return "#FEE2E2"
        if (mouse.containsMouse && root.variant === "secondary") return "#EAF0FF"
        if (mouse.containsMouse && root.variant === "ghost") return "#F3F4F6"
        if (root.variant === "primary") return "#4F7CFF"
        if (root.variant === "danger") return "#EF4444"
        if (root.variant === "softDanger") return "#FEF2F2"
        if (root.variant === "ghost") return "transparent"
        return "#F4F7FF"
    }

    border.color: {
        if (root.variant === "secondary") return "#D6E1FF"
        if (root.variant === "softDanger") return "#FECACA"
        return "transparent"
    }
    border.width: root.variant === "secondary" || root.variant === "softDanger" ? 1 : 0

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: {
            if (!root.enabled) return "#9CA3AF"
            if (root.variant === "primary") return "#FFFFFF"
            if (root.variant === "danger") return "#FFFFFF"
            if (root.variant === "softDanger") return "#DC2626"
            if (root.variant === "ghost") return "#4B5563"
            return "#2563EB"
        }
        font.pixelSize: root.compact ? 13 : 14
        font.bold: root.variant === "primary" || root.variant === "danger"
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
