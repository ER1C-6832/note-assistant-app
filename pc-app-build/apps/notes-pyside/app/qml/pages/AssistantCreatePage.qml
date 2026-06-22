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

            Text {
                anchors.centerIn: parent
                text: "已创建便签：明天上午十点联系王总"
                color: "#111827"
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
            resultTitle: "便签已创建"
            resultText: "你可以在便签列表中查看这条记录。"
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
