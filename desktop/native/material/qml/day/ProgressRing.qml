import QtQuick
import components 1.0

Item {
    id: root
    property var theme
    property real share: 0
    property int count: 0
    property string caption: ""
    property int size: 160
    property string countName: "myDayCount"
    property string captionName: "myDayCaption"

    objectName: "myDayRing"
    implicitWidth: size
    implicitHeight: size
    width: size
    height: size
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
            var lineW = Math.max(10, Math.round(width * 0.085))
            var radius = centre - lineW / 2 - 4
            ctx.lineWidth = lineW
            ctx.lineCap = "round"
            ctx.beginPath()
            ctx.strokeStyle = palette.wellSurface
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
        width: parent.width - 28
        spacing: 0

        Text {
            objectName: root.countName
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.count
            color: palette.inkSurface
            font.family: M3Font.heading
            font.pixelSize: M3Font.px(Math.round(root.size * 0.22))
            font.weight: 700
            Accessible.ignored: true
        }
        Text {
            objectName: root.captionName
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.caption
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(Math.max(11, Math.round(root.size * 0.085)))
            font.weight: 500
            wrapMode: Text.WordWrap
            Accessible.ignored: true
        }
    }

    onShareChanged: canvas.requestPaint()
    onThemeChanged: canvas.requestPaint()
    onSizeChanged: canvas.requestPaint()
    Component.onCompleted: canvas.requestPaint()
}
