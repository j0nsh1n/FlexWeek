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
    property alias trailingInset: root.rightInset
    // Week and Day set a block's height from its time. Its words then fit that height: the title
    // gives up its second line first, then the time line goes, so nothing is drawn past the border.
    property bool fitToHeight: false

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
    readonly property real titleLine: Math.ceil(titleFont.height * title.lineHeight)
    readonly property real detailLine: root.detail !== "" ? Math.ceil(detailFont.height) : 0
    readonly property real room: root.height - root.pad - (root.highContrast ? 2 : 1)

    readonly property bool darkSurface: {
        var tone = palette.surface
        return tone.r * 0.2126 + tone.g * 0.7152 + tone.b * 0.0722 < 0.4
    }

    readonly property var defaultClasses: {
        var dark = darkSurface
        return {
            "class": {
                bar: "#3d6fc4",
                fill: dark ? "#1e2c44" : "#e4ebf7",
                ink: dark ? "#ececec" : "#0f172a"
            },
            "exercise": {
                bar: "#2b9665",
                fill: dark ? "#1a352e" : "#e1f0e9",
                ink: dark ? "#ececec" : "#0f172a"
            },
            "extra": {
                bar: "#0f8a8a",
                fill: dark ? "#133336" : "#ddefef",
                ink: dark ? "#ececec" : "#0f172a"
            },
            "assignments": {
                bar: "#a87512",
                fill: dark ? "#382e1a" : "#f3ecde",
                ink: dark ? "#ececec" : "#0f172a"
            },
            "study": {
                bar: "#c2557a",
                fill: dark ? "#3e2633" : "#f6e7ec",
                ink: dark ? "#ececec" : "#0f172a"
            },
            "other": {
                bar: "#64748b",
                fill: dark ? "#272d37" : "#e9ecef",
                ink: dark ? "#ececec" : "#0f172a"
            }
        }
    }

    readonly property var classData: {
        var cls = (theme && theme.classes) ? theme.classes : palette.classes
        var key = category
        if (key === "school") key = "class"
        else if (key === "sports") key = "exercise"
        else if (key === "homework") key = "assignments"
        else if (key === "clubs") key = "extra"
        if (cls && cls[key])
            return cls[key]
        if (cls && cls["other"])
            return cls["other"]
        if (defaultClasses[key])
            return defaultClasses[key]
        return defaultClasses["other"]
    }
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
        Column {
            id: body
            objectName: "body"
            x: 12
            y: root.pad
            width: parent.width - 20
            spacing: 0
            Text {
                id: title
                objectName: "title"
                width: Math.max(0, parent.width - root.rightInset)
                text: root.title
                color: root.textInk
                opacity: 1
                wrapMode: Text.WordWrap
                maximumLineCount: !root.fitToHeight || 2 * root.titleLine + root.detailLine <= root.room ? 2 : 1
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
                width: parent.width
                visible: root.detail !== "" && (!root.fitToHeight || title.height + root.detailLine <= root.room)
                text: root.detail
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
