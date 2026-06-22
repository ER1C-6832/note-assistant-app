import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    signal backRequested()

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
                    text: "语音删除确认"
                    color: "#111827"
                    font.pixelSize: 24
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: "我找到 3 条和王总相关的便签，请选择要删除哪一条。"
                    color: "#4B5563"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 16
                    color: "#F7F8FA"
                    implicitHeight: 170

                    Text {
                        anchors.fill: parent
                        anchors.margins: 18
                        text: "1. 明天下午三点联系王总，确认项目报价\n2. 王总项目报价\n3. 客户跟进：王总需求确认\n\n确认删除“明天下午三点联系王总，确认项目报价”吗？"
                        color: "#374151"
                        font.pixelSize: 15
                        wrapMode: Text.WordWrap
                    }
                }

                RowLayout {
                    spacing: 12

                    AppButton {
                        text: "取消"
                        variant: "secondary"
                    }

                    AppButton {
                        text: "确认删除"
                        variant: "danger"
                    }
                }
            }
        }

        AssistantPanel {
            Layout.preferredWidth: 460
            Layout.fillHeight: true
            statusText: "等待确认"
            transcript: "删除王总那条"
            reply: "我找到 3 条候选，请确认要删除哪一条。"
            resultTitle: "等待确认"
            resultText: "确认后将删除选中的便签。"
        }
    }

    AppButton {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 24
        anchors.bottomMargin: 24
        text: "返回语音助手"
        variant: "secondary"
        onClicked: root.backRequested()
    }
}
