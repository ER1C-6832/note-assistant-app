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
                spacing: 14

                Text {
                    text: "语音查询结果"
                    color: "#111827"
                    font.pixelSize: 24
                    font.bold: true
                }

                Text {
                    text: "找到 2 条和“王总”相关的便签"
                    color: "#4B5563"
                    font.pixelSize: 15
                }

                NoteCard {
                    Layout.fillWidth: true
                    title: "联系王总"
                    content: "明天上午十点联系王总，确认项目报价。"
                    tags: "客户 · 跟进"
                    updated: "今天 09:20"
                    cardColor: "#FFF6CC"
                }

                NoteCard {
                    Layout.fillWidth: true
                    title: "王总项目报价"
                    content: "和王总确认 27 寸屏幕报价区间，以及演示安排。"
                    tags: "客户 · 报价"
                    updated: "昨天 18:40"
                    cardColor: "#E9F2FF"
                }
            }
        }

        AssistantPanel {
            Layout.preferredWidth: 460
            Layout.fillHeight: true
            statusText: "已执行"
            transcript: "查一下王总相关便签"
            reply: "找到 2 条相关便签。"
            resultTitle: "查询完成"
            resultText: "你可以选择其中一条继续查看、编辑或删除。"
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
