import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property var notesModel
    property int selectedIndex: -1
    property string activeCategory: "all"

    signal noteSelected(int index)
    signal createRequested()

    function categoryTitle() {
        if (activeCategory === "pinned") return "置顶便签"
        if (activeCategory === "customer") return "客户便签"
        if (activeCategory === "meeting") return "会议便签"
        if (activeCategory === "todo") return "待办便签"
        if (activeCategory === "search") return "搜索结果"
        return "全部便签"
    }

    color: "#FFFFFF"
    radius: 20

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: root.categoryTitle()
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
                text: "+ 新建"
                variant: "primary"
                compact: true
                onClicked: root.createRequested()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: notesController.errorMessage.length > 0
            radius: 14
            color: "#FEF2F2"
            implicitHeight: 44

            Text {
                anchors.centerIn: parent
                text: notesController.errorMessage
                color: "#991B1B"
                font.pixelSize: 12
                elide: Text.ElideRight
                width: parent.width - 24
            }
        }

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.notesModel
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
                selected: index === root.selectedIndex
                onClicked: root.noteSelected(index)
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
                    text: "暂无便签"
                    color: "#111827"
                    font.pixelSize: 18
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    text: "点击“新建”创建第一条便签。"
                    color: "#6B7280"
                    font.pixelSize: 13
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
