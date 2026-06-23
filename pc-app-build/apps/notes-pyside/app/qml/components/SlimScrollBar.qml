import QtQuick
import QtQuick.Controls

ScrollBar {
    id: root
    policy: ScrollBar.AsNeeded
    width: 7
    padding: 1

    background: Rectangle {
        implicitWidth: 7
        radius: 4
        color: "transparent"
    }

    contentItem: Rectangle {
        implicitWidth: 5
        radius: 3
        color: root.pressed ? "#6B7280" : root.active ? "#9CA3AF" : "#CBD5E1"
        opacity: root.active || root.pressed ? 0.95 : 0.45
    }
}
