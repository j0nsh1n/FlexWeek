import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    // class, exercise, extra, assignments, study, or other.
    property string category: "assignments"
    property string title: ""
    property string detail: ""
    property bool past: false
    property string accessName: ""
    property int rightInset: 0
    // Room kept free at the right of the time line, for a circle that lies beside it.
    property int detailInset: 0
    // The time line when its whole range does not fit beside that circle: the start alone.
    property string detailStart: ""
    property alias trailingInset: root.rightInset
    // Week and Day set a block's height from its time. Its words then fit that height: the title
    // gives up its second line first, then the time line goes, so nothing is drawn past the border.
    property bool fitToHeight: false
    // When another block lies on part of this one, the words go where they show: `wordsTop` down from
    // the block's top, within `wordsRoom` (-1: the whole height). `showWords` false leaves them out.
    property real wordsTop: 0
    property real wordsRoom: -1
    property bool showWords: true

    // Absent keys keep the block default: radius 6, pad 6, no shadow, an edge bar.
    readonly property int pad: (theme && theme.cardPad !== undefined) ? theme.cardPad : 6
    readonly property int shadowPx: (theme && theme.shadow !== undefined) ? theme.shadow : 0
    readonly property string blockStyle: (theme && theme.blockStyle) ? theme.blockStyle : "Edge"
    readonly property int cornerRadius: (theme && theme.corner !== undefined) ? theme.corner : 6
    readonly property string fillOverride: {
        if (!theme)
            return ""
        if ((category === "class" || category === "school") && theme.catSchool)
            return theme.catSchool
        if ((category === "exercise" || category === "sports") && theme.catSports)
            return theme.catSports
        if (category === "study" && theme.catStudy)
            return theme.catStudy
        if ((category === "assignments" || category === "homework") && theme.catHomework)
            return theme.catHomework
        return ""
    }

    implicitWidth: 160
    implicitHeight: Math.max(44, body.implicitHeight + pad * 2)
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    FontMetrics { id: titleFont; font: title.font }
    FontMetrics { id: detailFont; font: detail.font }
    TextMetrics { id: wholeDetail; font: detail.font; text: root.detail }
    TextMetrics { id: startDetail; font: detail.font; text: root.detailStart }
    // A time line is never cut part-way (Jonathan, 2026-11-09): where the whole range does not fit the
    // line, it reads as the start alone. The column's width does not depend on the lines in it, so this
    // cannot loop with the circle's room.
    readonly property bool detailCut: root.detailStart !== ""
                                      && wholeDetail.advanceWidth > body.width - root.detailInset
    // Where even the start alone does not fit the whole column, the line is left out; the time is still
    // read out and shown in Edit. This reads the column, never the circle's room, so it cannot loop.
    readonly property bool detailLost: root.detailStart !== "" && startDetail.advanceWidth > body.width
    // So a block can tell whether the start alone would fit beside something it puts at the line's end.
    readonly property real startWidth: startDetail.advanceWidth
    readonly property real lineRoom: body.width
    readonly property bool detailShown: detail.visible
    readonly property real titleLine: Math.ceil(titleFont.height * title.lineHeight)
    readonly property real detailLine: root.detail !== "" && !root.detailLost ? Math.ceil(detailFont.height) : 0
    readonly property real room: (root.wordsRoom >= 0 ? root.wordsRoom : root.height) - root.pad
                                 - (root.highContrast ? 2 : 1)
    // How many lines the title may take: two when they and the time line fit, else one.
    readonly property int titleLines: !root.fitToHeight || 2 * root.titleLine + root.detailLine <= root.room ? 2 : 1
    // Where the last drawn line ends, so a block can place something below its words.
    readonly property real contentBottom: body.y + body.height
    readonly property real titleBottom: body.y + title.height

    readonly property bool darkSurface: palette.dark

    readonly property var classData: palette.classFor(category)
    readonly property color classBar: classData ? classData.bar : "#64748b"
    readonly property color classFill: classData ? classData.fill : (darkSurface ? "#272d37" : "#e9ecef")
    readonly property color classInk: classData ? classData.ink : (darkSurface ? "#ececec" : "#0f172a")
    readonly property color textInk: root.past ? palette.inkMuted : classInk

    Rectangle {
        objectName: "shadow"
        visible: root.shadowPx > 0
        z: -1
        x: -root.shadowPx
        y: -root.shadowPx
        width: parent.width + root.shadowPx * 2
        height: parent.height + root.shadowPx * 2
        radius: root.cornerRadius + root.shadowPx
        color: "#000000"
        opacity: 0.18
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: root.cornerRadius
        color: root.blockStyle === "Outline"
              ? "transparent"
              : (root.fillOverride !== "" ? root.fillOverride : root.classFill)
        clip: true
        opacity: root.past ? 0.55 : 1
        border.width: root.blockStyle === "Outline"
                      ? (root.highContrast ? 1.5 : 1)
                      : (root.highContrast ? 1.5 : 0)
        border.color: root.classBar
    }

    Rectangle {
        id: bar
        objectName: "bar"
        visible: root.blockStyle === "Edge"
        width: 4
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        color: root.classBar
        opacity: root.past ? 0.55 : 1
        topLeftRadius: root.cornerRadius
        bottomLeftRadius: root.cornerRadius
    }

    // The words clip to the block, so a short block never paints them into the next hour.
    Item {
        objectName: "words"
        anchors.fill: parent
        clip: true
        visible: root.showWords
        Column {
            id: body
            objectName: "body"
            x: 12
            y: root.wordsTop + root.pad
            width: parent.width - 20
            spacing: 0
            Text {
                id: title
                objectName: "title"
                width: Math.max(0, parent.width - root.rightInset)
                text: root.title
                color: root.textInk
                opacity: 1
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                maximumLineCount: root.titleLines
                elide: Text.ElideRight
                font.family: M3Font.family
                font.pixelSize: M3Font.px(12)
                font.weight: 600
                lineHeight: 1.25
                lineHeightMode: Text.ProportionalHeight
            }
            Text {
                id: detail
                objectName: "detail"
                width: Math.max(0, parent.width - root.detailInset)
                visible: root.detail !== "" && !root.detailLost && (!root.fitToHeight || title.height + root.detailLine <= root.room)
                text: root.detailCut ? root.detailStart : root.detail
                color: root.textInk
                opacity: 1
                font.family: M3Font.family
                font.pixelSize: M3Font.px(11)
                font.weight: 400
                elide: Text.ElideRight
            }
        }
    }

    Accessible.role: Accessible.StaticText
    Accessible.name: accessName !== "" ? accessName : (title + (detail !== "" ? ", " + detail : ""))
}
