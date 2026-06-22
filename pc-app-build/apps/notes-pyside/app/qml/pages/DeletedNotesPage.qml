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
            Layout.fillWidth: true
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
                            text: notesController.deletedResultCount + " 条便签"
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

                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 128
                        radius: 18
                        color: "#F3F4F6"
                        border.color: notesController.deletedSelectedIndex === index ? "#4F7CFF" : "transparent"
                        border.width: notesController.deletedSelectedIndex === index ? 2 : 0

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 14

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 7

                                Text {
                                    Layout.fillWidth: true
                                    text: model.title
                                    color: "#111827"
                                    font.pixelSize: 15
                                    font.bold: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: model.content
                                    color: "#4B5563"
                                    font.pixelSize: 12
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: model.tagsText + " · " + model.updatedText
                                    color: "#6B7280"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                }
                            }

                            AppButton {
                                text: "还原"
                                variant: "secondary"
                                compact: true
                                onClicked: notesController.restoreDeletedNoteAt(index)
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            anchors.rightMargin: 92
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: notesController.selectDeletedNote(index)
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: notesController.deletedResultCount === 0
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
    }
}
