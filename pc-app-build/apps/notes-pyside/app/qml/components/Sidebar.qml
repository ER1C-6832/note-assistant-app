import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string currentPage: "home"
    property string activeCategory: "all"
    property var notesControllerRef: null

    signal categoryRequested(string categoryKey)
    signal tagRequested(string tagName)
    signal deletedRequested()
    signal pageRequested(string pageName)

    color: "#FFFFFF"
    radius: 20

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 10

        Text { text: "分类"; color: "#9CA3AF"; font.pixelSize: 13 }

        SidebarItem { Layout.fillWidth: true; text: "全部"; iconText: "•"; active: root.activeCategory === "all"; onClicked: root.categoryRequested("all") }
        SidebarItem { Layout.fillWidth: true; text: "置顶"; iconText: "•"; active: root.activeCategory === "pinned"; onClicked: root.categoryRequested("pinned") }
        SidebarItem { Layout.fillWidth: true; text: "待办"; iconText: "•"; active: root.activeCategory === "todo"; onClicked: root.categoryRequested("todo") }
        SidebarItem { Layout.fillWidth: true; text: "已删除"; iconText: "•"; active: root.activeCategory === "deleted"; onClicked: root.deletedRequested() }

        Rectangle { Layout.fillWidth: true; height: 1; color: "#EEF2F7" }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            TextField {
                id: tagInput
                Layout.fillWidth: true
                height: 34
                placeholderText: "新增标签"
                font.pixelSize: 12
                selectByMouse: true
                background: Rectangle { color: "#F7F8FA"; radius: 12; border.color: "#E5E7EB" }

                onAccepted: {
                    if (root.notesControllerRef !== null && root.notesControllerRef.addCustomTag(tagInput.text)) {
                        tagInput.text = ""
                    }
                }
            }

            AppButton {
                text: "+"
                compact: true
                variant: "secondary"
                onClicked: {
                    if (root.notesControllerRef !== null && root.notesControllerRef.addCustomTag(tagInput.text)) {
                        tagInput.text = ""
                    }
                }
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 6

                Repeater {
                    model: root.notesControllerRef !== null ? root.notesControllerRef.tagItems : []

                    SidebarTagItem {
                        Layout.fillWidth: true
                        text: modelData.name
                        active: root.activeCategory === "tag:" + modelData.name
                        deletable: modelData.deletable
                        onClicked: root.tagRequested(modelData.name)
                        onDeleteRequested: {
                            if (root.notesControllerRef !== null) {
                                root.notesControllerRef.deleteTag(modelData.name)
                            }
                        }
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: "#EEF2F7" }
    }
}
