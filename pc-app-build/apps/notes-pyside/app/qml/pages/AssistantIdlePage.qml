import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    signal backRequested()
    signal demoCreateRequested()
    signal demoSearchRequested()
    signal demoUpdateRequested()
    signal demoDeleteRequested()

    RowLayout {
        anchors.fill: parent
        spacing: 20

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#FFFFFF"
            radius: 20

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 16

                Text {
                    text: "语音助手"
                    color: "#111827"
                    font.pixelSize: 26
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: "当前阶段使用独立运行的 py-xiaozhi。你可以在 py-xiaozhi GUI 中说便签指令；本 App 通过 Sidecar 监听便签变化并自动刷新。"
                    color: "#4B5563"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    spacing: 12

                    AppButton {
                        text: "刷新状态"
                        variant: "primary"
                        onClicked: sidecarClient.refreshStatus()
                    }

                    AppButton {
                        text: "语音新增"
                        variant: "secondary"
                        onClicked: root.demoCreateRequested()
                    }

                    AppButton {
                        text: "语音查询"
                        variant: "secondary"
                        onClicked: root.demoSearchRequested()
                    }

                    AppButton {
                        text: "语音修改"
                        variant: "secondary"
                        onClicked: root.demoUpdateRequested()
                    }

                    AppButton {
                        text: "语音删除"
                        variant: "softDanger"
                        onClicked: root.demoDeleteRequested()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 16
                    color: "#F7F8FA"
                    implicitHeight: promptText.implicitHeight + 28

                    Text {
                        id: promptText
                        anchors.fill: parent
                        anchors.margins: 14
                        text: "测试建议：保持 Notes API、Sidecar、PC App 都运行，然后在 py-xiaozhi GUI 中说“帮我新增一条便签，标题是 Sidecar 自动刷新测试，标签测试”。"
                        color: "#374151"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }
                }

                AppButton {
                    text: "返回首页"
                    variant: "ghost"
                    onClicked: root.backRequested()
                }

                Item {
                    Layout.fillHeight: true
                }
            }
        }

        AssistantPanel {
            Layout.preferredWidth: 460
            Layout.fillHeight: true
        }
    }
}
