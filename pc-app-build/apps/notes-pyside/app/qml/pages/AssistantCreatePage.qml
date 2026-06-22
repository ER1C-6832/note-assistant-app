import QtQuick
import QtQuick.Controls
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
            radius: 18

            Text {
                anchors.centerIn: parent
                text: "便签列表新增：明天上午十点联系王总（来自语音）"
                color: "#1A1A1A"
                font.pixelSize: 22
                font.bold: true
            }
        }

        AssistantPanel {
            Layout.preferredWidth: 460
            Layout.fillHeight: true
            statusText: "已执行"
            transcript: "帮我记录，明天上午十点联系王总，确认项目报价"
            reply: "已为你创建便签：明天上午十点联系王总，确认项目报价。"
            resultTitle: "工具执行结果：create_note 成功"
            resultText: "source=voice_pc，note_id=12。Phase 3 为静态演示，Phase 5/6 接入真实 Sidecar 和 Notes Tool。"
        }
    }

    Button {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 24
        anchors.bottomMargin: 24
        text: "返回语音助手"
        onClicked: root.backRequested()
    }
}
