import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root

    property var deletedNotesModel

    signal backRequested()

    RowLayout {
        anchors.fill: parent
        spacing: 20

        Rectangle {
            Layout.preferredWidth: 540
            Layout.fillHeight: true
            color: "#FFFFFF"
            radius: 20

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: "已删除"
                            color: "#111827"
                            font.pixelSize: 18
                            font.bold: true
                        }

                        Text {
                            text: "软删除便签列表，Phase 4 后接入真实 is_deleted 数据。"
                            color: "#9CA3AF"
                            font.pixelSize: 12
                        }
                    }

                    AppButton {
                        text: "返回全部"
                        variant: "secondary"
                        compact: true
                        onClicked: root.backRequested()
                    }
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: root.deletedNotesModel
                    spacing: 12
                    clip: true

                    delegate: NoteCard {
                        width: ListView.view.width
                        title: model.title
                        content: model.content
                        tags: model.tags
                        updated: model.updated
                        source: model.source
                        cardColor: model.cardColor
                        selected: false
                    }
                }
            }
        }

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
                    text: "已删除不是删除确认页"
                    color: "#111827"
                    font.pixelSize: 24
                    font.bold: true
                }

                Text {
                    Layout.fillWidth: true
                    text: "这里展示被软删除的便签。点击右侧详情里的“删除”才会进入删除确认页。Phase 3.1 已将 deletedList 和 deleteConfirm 分开。"
                    color: "#4B5563"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 16
                    color: "#F7F8FA"
                    implicitHeight: 130

                    Text {
                        anchors.fill: parent
                        anchors.margins: 18
                        text: "后续 Phase 4 可接入：\nGET /api/notes?include_deleted=true\nPATCH 恢复接口或单独 restore API。"
                        color: "#374151"
                        font.pixelSize: 15
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
