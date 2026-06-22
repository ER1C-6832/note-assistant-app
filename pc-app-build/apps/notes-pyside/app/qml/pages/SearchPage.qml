import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property string keyword: "王总"
    property var notesModel

    signal noteSelected(int index)
    signal backRequested()
    signal deleteSelectedRequested()

    RowLayout {
        anchors.fill: parent
        spacing: 20

        Rectangle {
            Layout.preferredWidth: 560
            Layout.fillHeight: true
            color: "#FFFFFF"
            radius: 18

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true

                    ColumnLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "找到 2 条相关便签"
                            color: "#1A1A1A"
                            font.pixelSize: 18
                            font.bold: true
                        }

                        Text {
                            text: "搜索关键词：“" + root.keyword + "”，命中标题、正文、标签"
                            color: "#6B7280"
                            font.pixelSize: 12
                        }
                    }

                    Button {
                        text: "重置搜索"
                        onClicked: root.backRequested()
                    }
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 12
                    clip: true
                    model: 2

                    delegate: NoteCard {
                        width: ListView.view.width
                        title: root.notesModel.get(index).title
                        content: root.notesModel.get(index).content
                        tags: root.notesModel.get(index).tags
                        updated: root.notesModel.get(index).updated
                        source: root.notesModel.get(index).source
                        cardColor: root.notesModel.get(index).cardColor
                        selected: true
                        onClicked: root.noteSelected(index)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        Layout.fillWidth: true
                        text: "已勾选 2 条便签"
                        color: "#4B5563"
                        font.pixelSize: 13
                    }

                    Button {
                        text: "删除所选"
                        onClicked: root.deleteSelectedRequested()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#FFFFFF"
            radius: 18

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 16

                Text {
                    text: "模糊查找说明"
                    color: "#1A1A1A"
                    font.pixelSize: 24
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: "Phase 3 先展示搜索 UI 和结果状态。Phase 4 接入 GET /api/notes/search?q=" + root.keyword + " 后，列表将使用真实 Notes API 数据。"
                    color: "#4B5563"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 16
                    color: "#F7F8FA"
                    implicitHeight: 160

                    Text {
                        anchors.fill: parent
                        anchors.margins: 18
                        text: "搜索范围：\n- 标题\n- 正文\n- 标签\n\n当前策略：SQLite LIKE 基础模糊查找"
                        color: "#374151"
                        font.pixelSize: 15
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
