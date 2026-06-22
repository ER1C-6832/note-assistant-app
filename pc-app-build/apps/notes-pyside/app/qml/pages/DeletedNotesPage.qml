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
                            text: notesController.resultCount + " 条便签"
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
                        tags: model.tagsText
                        updated: model.updatedText
                        source: model.sourceText
                        cardColor: model.cardColor
                        selected: false
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: notesController.resultCount === 0
                    radius: 18
                    color: "#F7F8FA"

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 10

                        Text {
                            text: "暂无已删除便签"
                            color: "#111827"
                            font.pixelSize: 18
                            font.bold: true
                        }

                        Text {
                            text: "删除后的便签会显示在这里。"
                            color: "#6B7280"
                            font.pixelSize: 13
                        }
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
                anchors.centerIn: parent
                spacing: 12

                Text {
                    text: "已删除便签"
                    color: "#111827"
                    font.pixelSize: 24
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: "这里集中展示已删除的便签。"
                    color: "#6B7280"
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
