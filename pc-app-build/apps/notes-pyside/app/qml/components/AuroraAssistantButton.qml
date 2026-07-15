import QtQuick
import QtQuick.Controls

Item {
    id: root

    property var viewModelRef: null
    property bool animationEnabled: true
    readonly property bool ready: viewModelRef !== null
    readonly property color colorA: ready ? viewModelRef.auroraColorA : "#5B8DEF"
    readonly property color colorB: ready ? viewModelRef.auroraColorB : "#6B7280"
    readonly property color colorC: ready ? viewModelRef.auroraColorC : "transparent"
    readonly property color borderColor: ready ? viewModelRef.auroraBorderColor : "#9AA5B5"
    readonly property real targetScale: ready ? viewModelRef.auroraScale : 0.88
    readonly property real motionSpeed: ready ? viewModelRef.auroraSpeed : 0.18
    readonly property real targetAlpha: ready ? viewModelRef.auroraAlpha : 0.78
    readonly property string compactLabel: ready ? viewModelRef.compactStatusLabel : "待命"
    readonly property string visualState: ready ? viewModelRef.auroraVisualState : "idle"

    signal activated()

    implicitWidth: 80
    implicitHeight: 80
    Accessible.name: "小智助手 " + compactLabel
    Accessible.role: Accessible.Button

    property real animatedScale: targetScale
    property real animatedAlpha: targetAlpha
    property real motionPhase: 0

    Behavior on animatedScale {
        NumberAnimation { duration: 650; easing.type: Easing.InOutCubic }
    }
    Behavior on animatedAlpha {
        NumberAnimation { duration: 650; easing.type: Easing.InOutCubic }
    }

    onTargetScaleChanged: animatedScale = targetScale
    onTargetAlphaChanged: animatedAlpha = targetAlpha

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Qt.rgba(1, 1, 1, 0.10)
        border.width: 1
        border.color: root.borderColor
    }

    Canvas {
        id: auroraCanvas
        anchors.fill: parent
        renderTarget: Canvas.FramebufferObject

        function drawBlob(context, x, y, radius, colorValue, alphaValue) {
            if (colorValue.a <= 0.001) return
            var gradient = context.createRadialGradient(x, y, radius * 0.08, x, y, radius)
            gradient.addColorStop(0.0, Qt.rgba(colorValue.r, colorValue.g, colorValue.b, 0.88 * alphaValue))
            gradient.addColorStop(0.52, Qt.rgba(colorValue.r, colorValue.g, colorValue.b, 0.46 * alphaValue))
            gradient.addColorStop(1.0, Qt.rgba(colorValue.r, colorValue.g, colorValue.b, 0.0))
            context.fillStyle = gradient
            context.beginPath()
            context.arc(x, y, radius, 0, Math.PI * 2)
            context.fill()
        }

        onPaint: {
            var context = getContext("2d")
            context.clearRect(0, 0, width, height)
            var centerX = width / 2
            var centerY = height / 2
            var phase = root.motionPhase * Math.PI / 180
            var radius = Math.min(width, height) * 0.31 * root.animatedScale
            var orbit = Math.min(width, height) * 0.105
            drawBlob(
                context,
                centerX + Math.cos(phase) * orbit,
                centerY + Math.sin(phase * 0.82) * orbit * 0.84,
                radius * 1.08,
                root.colorA,
                root.animatedAlpha
            )
            drawBlob(
                context,
                centerX + Math.sin(phase * 0.91 + 1.2) * orbit,
                centerY + Math.cos(phase) * orbit * 0.9,
                radius,
                root.colorB,
                root.animatedAlpha
            )
            drawBlob(
                context,
                centerX + Math.cos(phase * 0.72 + 2.1) * orbit * 0.78,
                centerY + Math.sin(phase * 1.08 + 0.4) * orbit,
                radius * 0.92,
                root.colorC,
                root.animatedAlpha * 0.92
            )
        }

        Connections {
            target: root
            function onColorAChanged() { auroraCanvas.requestPaint() }
            function onColorBChanged() { auroraCanvas.requestPaint() }
            function onColorCChanged() { auroraCanvas.requestPaint() }
            function onAnimatedScaleChanged() { auroraCanvas.requestPaint() }
            function onAnimatedAlphaChanged() { auroraCanvas.requestPaint() }
            function onMotionPhaseChanged() { auroraCanvas.requestPaint() }
        }
    }

    Rectangle {
        anchors.centerIn: parent
        width: 54
        height: 54
        radius: 27
        color: Qt.rgba(0.06, 0.08, 0.14, 0.36)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.18)

        Column {
            anchors.centerIn: parent
            spacing: 0

            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "小智"
                color: Qt.rgba(1, 1, 1, 0.92)
                font.pixelSize: 13
                font.bold: true
            }
            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.compactLabel
                color: Qt.rgba(1, 1, 1, 0.70)
                font.pixelSize: 10
            }
        }
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: root.activated()
    }

    NumberAnimation on motionPhase {
        from: 0
        to: 360
        duration: Math.max(2400, Math.round(12000 / Math.max(0.1, root.motionSpeed)))
        loops: Animation.Infinite
        running: root.visible && root.animationEnabled
    }
}
