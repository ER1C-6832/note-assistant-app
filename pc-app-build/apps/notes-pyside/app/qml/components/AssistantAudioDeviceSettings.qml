import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var viewModelRef: null
    readonly property bool ready: viewModelRef !== null
    readonly property var model: ready ? viewModelRef : fallbackModel

    QtObject {
        id: fallbackModel
        readonly property var audioInputDeviceItems: []
        readonly property var audioOutputDeviceItems: []
        readonly property string audioRouteState: "resolving"
        readonly property string audioRouteErrorCode: ""
        readonly property string selectedInputDevicePublicName: ""
        readonly property string selectedOutputDevicePublicName: ""
        readonly property string microphoneTestStatus: "not_run"
        readonly property string microphoneTestText: "尚未测试"
        readonly property bool offlineKwsEnabled: false
        readonly property string offlineKwsStatusText: "已关闭"
        readonly property bool offlineKwsModelReady: false
        readonly property string offlineKwsModelSummary: "尚未检查"
        readonly property string offlineKwsWakePhrase: "小智"
        readonly property string offlineKwsErrorCode: ""
        readonly property bool commandBusy: false
        readonly property bool assistantAutoConnectEnabled: true
        function requestRefreshAudioDevices() {}
        function requestSelectAudioDevice(direction, mode, key) {}
        function requestMicrophoneTest() {}
        function requestOfflineKwsEnabled(enabled) {}
        function requestAssistantAutoConnectEnabled(enabled) {}
    }

    function selectedIndex(items) {
        for (let index = 0; index < items.length; ++index) {
            if (items[index].selected) return index
        }
        return 0
    }

    implicitHeight: deviceColumn.implicitHeight + 20
    radius: 12
    color: "#F8FAFC"
    border.color: "#E2E8F0"
    border.width: 1

    ColumnLayout {
        id: deviceColumn
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                text: "语音与设备"
                color: "#334155"
                font.pixelSize: 12
                font.bold: true
            }

            Button {
                text: "刷新"
                enabled: root.ready && !root.model.commandBusy
                onClicked: root.model.requestRefreshAudioDevices()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: "#E2E8F0"
        }

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Label {
                    text: "离线唤醒 · “" + root.model.offlineKwsWakePhrase + "”"
                    color: "#334155"
                    font.pixelSize: 11
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    text: root.model.offlineKwsStatusText
                          + " · " + root.model.offlineKwsModelSummary
                    color: root.model.offlineKwsModelReady ? "#64748B" : "#B45309"
                    font.pixelSize: 10
                    elide: Text.ElideRight
                }
            }

            Switch {
                id: offlineKwsSwitch
                objectName: "assistantOfflineKwsSwitch"
                checked: root.model.offlineKwsEnabled
                enabled: root.ready && !root.model.commandBusy
                onToggled: {
                    if (root.ready && checked !== root.model.offlineKwsEnabled)
                        root.model.requestOfflineKwsEnabled(checked)
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1

                Label {
                    text: "启动时自动连接助手"
                    color: "#334155"
                    font.pixelSize: 11
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    text: "助手默认启用；关闭此项后仅不再自动连接"
                    color: "#64748B"
                    font.pixelSize: 10
                    wrapMode: Text.Wrap
                }
            }

            Switch {
                objectName: "assistantAutoConnectSwitch"
                checked: root.model.assistantAutoConnectEnabled
                enabled: root.ready && !root.model.commandBusy
                onToggled: {
                    if (root.ready && checked !== root.model.assistantAutoConnectEnabled)
                        root.model.requestAssistantAutoConnectEnabled(checked)
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.model.offlineKwsErrorCode.length > 0
            text: "离线唤醒提示：" + root.model.offlineKwsErrorCode
            color: "#B45309"
            font.pixelSize: 10
            wrapMode: Text.Wrap
        }

        Label {
            Layout.fillWidth: true
            text: root.model.audioRouteState === "ready"
                  ? "当前路由可用"
                  : "路由状态：" + root.model.audioRouteState
            color: root.model.audioRouteState === "ready" ? "#047857" : "#B45309"
            font.pixelSize: 10
        }

        Label {
            text: "麦克风"
            color: "#475569"
            font.pixelSize: 11
        }

        ComboBox {
            id: inputSelector
            objectName: "assistantInputDeviceSelector"
            Layout.fillWidth: true
            model: root.model.audioInputDeviceItems
            textRole: "label"
            enabled: root.ready && !root.model.commandBusy && count > 0
            onModelChanged: currentIndex = root.selectedIndex(model)
            onActivated: function(index) {
                const item = model[index]
                root.model.requestSelectAudioDevice("input", item.mode, item.key)
            }
        }

        Label {
            text: "扬声器"
            color: "#475569"
            font.pixelSize: 11
        }

        ComboBox {
            id: outputSelector
            objectName: "assistantOutputDeviceSelector"
            Layout.fillWidth: true
            model: root.model.audioOutputDeviceItems
            textRole: "label"
            enabled: root.ready && !root.model.commandBusy && count > 0
            onModelChanged: currentIndex = root.selectedIndex(model)
            onActivated: function(index) {
                const item = model[index]
                root.model.requestSelectAudioDevice("output", item.mode, item.key)
            }
        }

        RowLayout {
            Layout.fillWidth: true

            Button {
                objectName: "assistantMicrophoneTestButton"
                text: "测试麦克风"
                enabled: root.ready && !root.model.commandBusy
                onClicked: root.model.requestMicrophoneTest()
            }

            Label {
                Layout.fillWidth: true
                text: root.model.microphoneTestText
                color: "#64748B"
                font.pixelSize: 10
                elide: Text.ElideRight
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.model.audioRouteErrorCode.length > 0
            text: "设备提示：" + root.model.audioRouteErrorCode
            color: "#B45309"
            font.pixelSize: 10
            wrapMode: Text.Wrap
        }
    }
}
