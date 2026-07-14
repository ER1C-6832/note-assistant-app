import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string activeCategory: "all"
    property var notesViewModelRef: null

    readonly property bool viewModelReady: root.notesViewModelRef !== null
    readonly property bool mutationBusy: root.viewModelReady && root.notesViewModelRef.mutationBusy

    signal categoryRequested(string categoryKey)
    signal tagRequested(string tagName)
    signal deletedRequested()

    color: "#FFFFFF"
    radius: 20

    Connections {
        target: root.notesViewModelRef
        ignoreUnknownSignals: true

        function onTagAdded(tag) {
            if (String(tagInput.text).trim() === String(tag).trim()) {
                tagInput.text = ""
            }
        }
    }

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
                enabled: root.viewModelReady && !root.mutationBusy
                background: Rectangle { color: "#F7F8FA"; radius: 12; border.color: "#E5E7EB" }

                onAccepted: {
                    if (root.viewModelReady && !root.mutationBusy) {
                        root.notesViewModelRef.requestAddCustomTag(tagInput.text)
                    }
                }
            }

            AppButton {
                text: "+"
                compact: true
                variant: "secondary"
                enabled: root.viewModelReady && !root.mutationBusy
                onClicked: root.notesViewModelRef.requestAddCustomTag(tagInput.text)
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
                    model: root.viewModelReady ? root.notesViewModelRef.tagItems : []

                    SidebarTagItem {
                        Layout.fillWidth: true
                        text: modelData.name
                        active: root.activeCategory === "tag:" + modelData.name
                        deletable: modelData.deletable && !root.mutationBusy
                        onClicked: root.tagRequested(modelData.name)
                        onDeleteRequested: {
                            if (root.viewModelReady && !root.mutationBusy) {
                                root.notesViewModelRef.requestDeleteTag(modelData.name)
                            }
                        }
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: "#EEF2F7" }
    }
}
