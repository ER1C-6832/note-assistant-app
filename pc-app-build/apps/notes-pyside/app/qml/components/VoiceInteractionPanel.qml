import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string mode: "hidden"       // candidates / confirm_delete / result / failure
    property string title: ""
    property string message: ""
    property string actionType: ""
    property var candidates: []
    property int noteId: -1
    property string noteTitle: ""
    property string noteContent: ""
    property bool danger: false
    property bool success: true
    property int autoCloseSeconds: 3
    property int countdown: autoCloseSeconds
    readonly property bool autoCloseEnabled: visible && (mode === "result" || mode === "failure")

    signal closed()
    signal candidateSelected(int noteId, string title, string content)
    signal confirmRequested(int noteId, string actionType)
    signal retryRequested(string actionType)

    width: 390
    implicitHeight: Math.min(520, contentColumn.implicitHeight + 28)
    radius: 22
    color: "#FFFFFF"
    border.color: root.danger ? "#FCA5A5" : root.mode === "failure" ? "#FCA5A5" : "#DDE7FF"
    border.width: 1
    z: 200

    layer.enabled: true

    onVisibleChanged: resetAutoClose()
    onModeChanged: resetAutoClose()
    onMessageChanged: resetAutoClose()
    onTitleChanged: resetAutoClose()

    function resetAutoClose() {
        countdown = autoCloseSeconds
        if (autoCloseEnabled) {
            autoCloseTimer.restart()
        } else {
            autoCloseTimer.stop()
        }
    }

    Timer {
        id: autoCloseTimer
        interval: 1000
        repeat: true
        running: root.autoCloseEnabled

        onTriggered: {
            if (!root.autoCloseEnabled) {
                stop()
                return
            }

            root.countdown -= 1
            if (root.countdown <= 0) {
                stop()
                root.closed()
            }
        }
    }

    ColumnLayout {
        id: contentColumn
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                width: 28
                height: 28
                radius: 14
                color: root.mode === "failure" ? "#FEF2F2"
                     : root.danger ? "#FFF1F2"
                     : root.mode === "result" ? (root.success ? "#ECFDF3" : "#FEF2F2")
                     : "#EEF4FF"

                Text {
                    anchors.centerIn: parent
                    text: root.mode === "failure" ? "!" : root.danger ? "删" : root.mode === "result" ? "✓" : "?"
                    color: root.mode === "failure" || root.danger ? "#DC2626" : root.mode === "result" ? "#16A34A" : "#2563EB"
                    font.pixelSize: 13
                    font.bold: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Text {
                    Layout.fillWidth: true
                    text: root.title || "语音操作"
                    color: "#0F172A"
                    font.pixelSize: 16
                    font.bold: true
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    text: root.message
                    color: "#64748B"
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                    visible: text.length > 0
                }
            }

            AppButton {
                text: "×"
                variant: "ghost"
                implicitWidth: 34
                implicitHeight: 34
                onClicked: root.closed()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#EEF2F7"
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: root.mode === "candidates" ? 285 : 0
            visible: root.mode === "candidates"
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 8

                Repeater {
                    model: root.candidates || []

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: Math.max(78, itemColumn.implicitHeight + 18)
                        radius: 14
                        color: "#F8FAFC"
                        border.color: "#E2E8F0"
                        border.width: 1

                        ColumnLayout {
                            id: itemColumn
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Rectangle {
                                    width: 24
                                    height: 24
                                    radius: 12
                                    color: "#E0EAFF"

                                    Text {
                                        anchors.centerIn: parent
                                        text: String(index + 1)
                                        color: "#2563EB"
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.title || "未命名便签"
                                    color: "#111827"
                                    font.pixelSize: 14
                                    font.bold: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    text: "#" + String(modelData.id || "")
                                    color: "#94A3B8"
                                    font.pixelSize: 11
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.content || ""
                                color: "#475569"
                                font.pixelSize: 12
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                wrapMode: Text.Wrap
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.tags ? ("标签：" + modelData.tags) : ""
                                visible: text.length > 3
                                color: "#94A3B8"
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.candidateSelected(
                                    Number(modelData.id || -1),
                                    String(modelData.title || ""),
                                    String(modelData.content || "")
                                )
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.mode === "confirm_delete"
            implicitHeight: confirmColumn.implicitHeight + 20
            radius: 16
            color: "#FFF7ED"
            border.color: "#FDBA74"

            ColumnLayout {
                id: confirmColumn
                anchors.fill: parent
                anchors.margins: 12
                spacing: 6

                Text {
                    Layout.fillWidth: true
                    text: root.noteTitle || ("#" + root.noteId)
                    color: "#111827"
                    font.pixelSize: 15
                    font.bold: true
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    text: root.noteContent || "该操作会把便签移入“已删除”，之后仍可还原。"
                    color: "#475569"
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                    maximumLineCount: 4
                    elide: Text.ElideRight
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: root.mode === "result" || root.mode === "failure"
            text: root.message
            color: root.mode === "failure" ? "#991B1B" : "#334155"
            font.pixelSize: 13
            wrapMode: Text.Wrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppButton {
                visible: root.mode === "confirm_delete"
                text: "取消"
                variant: "secondary"
                Layout.fillWidth: true
                onClicked: root.closed()
            }

            AppButton {
                visible: root.mode === "confirm_delete"
                text: root.actionType === "hard_delete" ? "彻底删除" : "确认删除"
                variant: "danger"
                Layout.fillWidth: true
                onClicked: root.confirmRequested(root.noteId, root.actionType || "delete")
            }

            AppButton {
                visible: root.mode === "failure"
                text: "重试"
                variant: "secondary"
                Layout.fillWidth: true
                onClicked: root.retryRequested(root.actionType)
            }

            AppButton {
                visible: root.mode === "result" || root.mode === "failure" || root.mode === "candidates"
                text: root.mode === "candidates"
                      ? "稍后处理"
                      : ("知道了（" + Math.max(0, root.countdown) + "）")
                variant: root.mode === "failure" ? "secondary" : "primary"
                Layout.fillWidth: true
                onClicked: root.closed()
            }
        }
    }
}
