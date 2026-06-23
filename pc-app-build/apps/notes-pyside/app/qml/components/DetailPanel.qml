import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string content: ""
    property string tags: ""
    property string updated: ""
    property string source: ""
    property bool hasSelection: false
    property bool isPinned: false

    signal editRequested()
    signal deleteRequested()
    signal pinRequested()

    color: "#FFFFFF"
    radius: 20

    Item {
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 18
            visible: root.hasSelection

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            Layout.fillWidth: true
                            text: root.title
                            color: "#111827"
                            font.pixelSize: 26
                            font.bold: true
                            wrapMode: Text.WordWrap
                        }

                        Rectangle {
                            visible: root.isPinned
                            radius: 999
                            color: "#FFF7ED"
                            implicitWidth: 48
                            implicitHeight: 24

                            Text {
                                anchors.centerIn: parent
                                text: "置顶"
                                color: "#92400E"
                                font.pixelSize: 12
                            }
                        }
                    }

                    Text {
                        text: "更新时间：" + root.updated + "  ·  来源：" + root.source
                        color: "#9CA3AF"
                        font.pixelSize: 12
                    }
                }

                AppButton {
                    text: root.isPinned ? "取消置顶" : "置顶"
                    variant: root.isPinned ? "ghost" : "secondary"
                    compact: true
                    onClicked: root.pinRequested()
                }

                AppButton {
                    text: "编辑"
                    variant: "secondary"
                    compact: true
                    onClicked: root.editRequested()
                }

                AppButton {
                    text: "删除"
                    variant: "softDanger"
                    compact: true
                    onClicked: root.deleteRequested()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 18
                color: "#F7F8FA"

                Flickable {
                    anchors.fill: parent
                    anchors.margins: 18
                    contentWidth: width
                    contentHeight: detailText.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.DragOverBounds

                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                    }

                    Text {
                        id: detailText
                        width: parent.width
                        text: root.content
                        color: "#374151"
                        font.pixelSize: 16
                        wrapMode: Text.WordWrap
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "标签："
                    color: "#9CA3AF"
                    font.pixelSize: 13
                }

                Text {
                    Layout.fillWidth: true
                    text: root.tags
                    color: "#4B5563"
                    font.pixelSize: 13
                }
            }
        }

        ColumnLayout {
            anchors.centerIn: parent
            visible: !root.hasSelection
            spacing: 10

            Text {
                text: "请选择一条便签"
                color: "#111827"
                font.pixelSize: 22
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
            }

            Text {
                text: "在左侧列表中选择便签后，可查看详情、编辑或删除。"
                color: "#6B7280"
                font.pixelSize: 14
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
}
