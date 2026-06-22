import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property var notesModel
    property int selectedIndex: 0
    property string activeCategory: "all"

    signal noteSelected(int index)
    signal createRequested()
    signal searchRequested()

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
                    text: notesModel ? notesModel.count + " 条便签" : "0 条便签"
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
                tags: model.tags
                updated: model.updated
                source: model.source
                cardColor: model.cardColor
                selected: index === root.selectedIndex
                onClicked: root.noteSelected(index)
            }
        }
    }
}
