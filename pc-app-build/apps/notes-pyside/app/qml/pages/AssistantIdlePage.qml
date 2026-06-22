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
                    text: "语音助手演示入口"
                    color: "#111827"
                    font.pixelSize: 26
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: "Phase 3.1 展示语音助手 UI 状态；Phase 5 后通过 Sidecar 接收真实 transcript / reply / tool_result。"
                    color: "#4B5563"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    spacing: 12

                    AppButton {
                        text: "语音新增"
                        variant: "primary"
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

                AppButton {
                    text: "返回首页"
                    variant: "ghost"
                    onClicked: root.backRequested()
                }
            }
        }

        AssistantPanel {
            Layout.preferredWidth: 460
            Layout.fillHeight: true
            statusText: "待机中"
        }
    }
}
