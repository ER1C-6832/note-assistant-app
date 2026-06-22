import QtQuick
import QtQuick.Controls
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
            radius: 18

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 16

                Text {
                    text: "语音助手演示入口"
                    color: "#1A1A1A"
                    font.pixelSize: 26
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: "Phase 3 展示语音助手 UI 状态；Phase 5 后通过 Sidecar 接收真实 transcript / reply / tool_result。"
                    color: "#4B5563"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    spacing: 12

                    Button {
                        text: "演示语音新增"
                        onClicked: root.demoCreateRequested()
                    }

                    Button {
                        text: "演示语音查询"
                        onClicked: root.demoSearchRequested()
                    }

                    Button {
                        text: "演示语音修改"
                        onClicked: root.demoUpdateRequested()
                    }

                    Button {
                        text: "演示语音删除"
                        onClicked: root.demoDeleteRequested()
                    }
                }

                Button {
                    text: "返回首页"
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
