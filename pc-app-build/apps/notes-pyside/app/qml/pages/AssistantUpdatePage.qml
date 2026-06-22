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
                    text: "语音修改便签"
                    color: "#111827"
                    font.pixelSize: 24
                    font.bold: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 16
                    color: "#F7F8FA"
                    implicitHeight: 150

                    Text {
                        anchors.fill: parent
                        anchors.margins: 18
                        text: "原内容：明天上午十点联系王总，确认项目报价。\n\n新内容：明天下午三点联系王总，确认项目报价。"
                        color: "#374151"
                        font.pixelSize: 16
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        AssistantPanel {
            Layout.preferredWidth: 460
            Layout.fillHeight: true
            statusText: "已执行"
            transcript: "把王总那条改成下午三点联系"
            reply: "已将便签更新为：明天下午三点联系王总。"
            resultTitle: "工具执行结果：search_notes + update_note 成功"
            resultText: "先搜索候选，再按 note_id 更新。"
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
