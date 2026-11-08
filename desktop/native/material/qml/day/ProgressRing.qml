import QtQuick
import components 1.0

Item {
    id: root
    property var theme
    property real share: 0
    property int count: 0
    property string caption: ""

    objectName: "myDayRing"
    implicitWidth: 200
    implicitHeight: 200
    width: 200
    height: 200
    Accessible.role: Accessible.Indicator
    Accessible.name: count + " " + caption

    M3Palette { id: palette; theme: root.theme }

    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var centre = width / 2
            var radius = 84
            ctx.lineWidth = 14
            ctx.lineCap = "round"
            ctx.beginPath()
            ctx.strokeStyle = palette.surfaceContainerHighest
            ctx.arc(centre, centre, radius, 0, Math.PI * 2)
            ctx.stroke()
            if (root.share <= 0)
                return
            ctx.beginPath()
            ctx.strokeStyle = palette.primary
            var start = -Math.PI / 2
            ctx.arc(centre, centre, radius, start, start + Math.min(1, root.share) * Math.PI * 2)
            ctx.stroke()
        }
    }

    Column {
        anchors.centerIn: parent
        width: parent.width
        spacing: 0

        Text {
            objectName: "myDayCount"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.count
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: M3Font.px(36)
            font.weight: 400
            Accessible.ignored: true
        }
        Text {
            objectName: "myDayCaption"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.caption
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            font.weight: 400
            Accessible.ignored: true
        }
    }

    onShareChanged: canvas.requestPaint()
    onThemeChanged: canvas.requestPaint()
    Component.onCompleted: canvas.requestPaint()
}
