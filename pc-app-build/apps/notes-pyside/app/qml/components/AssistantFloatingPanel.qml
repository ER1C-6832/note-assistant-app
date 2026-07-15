import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var viewModelRef: null
    property bool settingsOpen: false
    signal closeRequested()

    objectName: "assistantFloatingPanel"
    width: 390
    height: Math.min(parent ? parent.height - 48 : 760, 760)
    radius: 18
    color: "#FFFFFF"
    border.color: "#CBD5E1"
    border.width: 1
    clip: true

    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        z: -1
        radius: root.radius + 4
        color: Qt.rgba(0.12, 0.18, 0.28, 0.10)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: dragHeader
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            color: "#F8FAFC"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 8
                spacing: 4

                Label {
                    Layout.fillWidth: true
                    text: root.settingsOpen ? "小智助手设置" : "小智助手 · 拖动此处移动"
                    color: "#334155"
                    font.pixelSize: 12
                    font.bold: true
                }

                ToolButton {
                    id: settingsButton
                    objectName: "assistantSettingsButton"
                    text: root.settingsOpen ? "←" : "⚙"
                    font.pixelSize: root.settingsOpen ? 18 : 17
                    Accessible.name: root.settingsOpen ? "返回小智助手" : "打开小智助手设置"
                    onClicked: root.settingsOpen = !root.settingsOpen
                }

                ToolButton {
                    text: "收起"
                    Accessible.name: "收起小智助手面板"
                    onClicked: root.closeRequested()
                }
            }

            DragHandler {
                target: root
                xAxis.minimum: 24
                xAxis.maximum: Math.max(24, root.parent.width - root.width - 24)
                yAxis.minimum: 24
                yAxis.maximum: Math.max(24, root.parent.height - root.height - 24)
            }
        }

        StackLayout {
            id: contentStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.settingsOpen ? 1 : 0

            Item {
                AssistantPanel {
                    objectName: "assistantPrimaryPanel"
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    anchors.bottomMargin: 8
                    anchors.topMargin: 8
                    viewModelRef: root.viewModelRef
                }
            }

            Item {
                objectName: "assistantSettingsPage"

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 10
                    clip: true

                    ColumnLayout {
                        width: parent.width
                        spacing: 12

                        Label {
                            Layout.fillWidth: true
                            text: "语音交互"
                            color: "#172033"
                            font.pixelSize: 16
                            font.bold: true
                        }

                        Label {
                            Layout.fillWidth: true
                            text: "选择悬浮按钮未来使用的默认语音方式。切换偏好不会立即启动麦克风。"
                            color: "#64748B"
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                        }

                        AssistantVoiceModeSettings {
                            objectName: "assistantVoiceModeSettings"
                            Layout.fillWidth: true
                            viewModelRef: root.viewModelRef
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: gestureNote.implicitHeight + 24
                            radius: 12
                            color: "#FFF7ED"
                            border.color: "#FED7AA"

                            Label {
                                id: gestureNote
                                anchors.fill: parent
                                anchors.margins: 12
                                text: "悬浮按钮的拖动与按住说话手势仍在设计评审中；Gate 3.1 不绑定真实 PTT 手势。"
                                color: "#9A3412"
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                            }
                        }

                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}
