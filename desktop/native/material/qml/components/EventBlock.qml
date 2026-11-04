import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    // school, sports (soccer), study (bio reading), or homework.
    property string category: "homework"
    property string title: ""
    property string detail: ""
    property bool past: false
    property string accessName: ""

    // Absent keys keep the block the gallery measures: radius 12, pad 6, no shadow, an edge bar.
    readonly property int pad: (theme && theme.cardPad !== undefined) ? theme.cardPad : 6
    readonly property int shadowPx: (theme && theme.shadow !== undefined) ? theme.shadow : 0
    readonly property string blockStyle: (theme && theme.blockStyle) ? theme.blockStyle : "Edge"
    readonly property int cornerRadius: (theme && theme.corner !== undefined) ? theme.corner : 12
    readonly property string fillOverride: {
        if (!theme)
            return ""
        if (category === "school" && theme.catSchool)
            return theme.catSchool
        if (category === "sports" && theme.catSports)
            return theme.catSports
        if (category === "study" && theme.catStudy)
            return theme.catStudy
        if (category === "homework" && theme.catHomework)
            return theme.catHomework
        return ""
    }

    opacity: past ? 0.65 : 1
    implicitWidth: 160
    implicitHeight: Math.max(44, body.implicitHeight + pad * 2)
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    readonly property bool darkSurface: {
        var tone = palette.surface
        return tone.r * 0.2126 + tone.g * 0.7152 + tone.b * 0.0722 < 0.4
    }

    function tones() {
        var dark = darkSurface
        if (category === "school")
            return dark ? ["#2A244D", "#E4DEFF", "#9B8CF0"] : ["#EAE6FA", "#2A2160", "#7C6CD6"]
        if (category === "sports")
            return dark ? ["#1B3B2B", "#C9F2DA", "#5CCB8F"] : ["#E2F5EA", "#0E4A2C", "#2E9E63"]
        if (category === "study")
            return dark ? ["#3D2232", "#FFD9EC", "#E58ABB"] : ["#F9E6F0", "#6B1F49", "#C2528E"]
        return dark ? ["#4A3219", "#FFE3BF", "#E8B268"] : ["#F7EBD9", "#5C3A0B", "#C98A2B"]
    }

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
              : (root.fillOverride !== "" ? root.fillOverride : root.tones()[0])
        clip: true
        border.width: root.blockStyle === "Outline"
                      ? (root.highContrast ? 1.5 : 1)
                      : (root.highContrast ? 1.5 : 0)
        border.color: root.tones()[1]
        Rectangle {
            objectName: "bar"
            visible: root.blockStyle === "Edge"
            width: 4
            height: parent.height
            color: root.tones()[2]
        }
        Column {
            id: body
            objectName: "body"
            x: 12
            y: root.pad
            width: parent.width - 20
            spacing: 0
            Text {
                objectName: "title"
                width: parent.width
                text: root.title
                color: root.tones()[1]
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.family: M3Font.family
                font.pixelSize: 12 * ((root.theme && root.theme.typeScale) ? root.theme.typeScale : 1)
                font.weight: 600
                lineHeight: 1.25
                lineHeightMode: Text.ProportionalHeight
            }
            Text {
                objectName: "detail"
                width: parent.width
                visible: root.detail !== ""
                text: root.detail
                color: root.tones()[1]
                font.family: M3Font.family
                font.pixelSize: 11
                font.weight: 400
                elide: Text.ElideRight
            }
        }
    }

    Accessible.role: Accessible.StaticText
    Accessible.name: accessName !== "" ? accessName : (title + (detail !== "" ? ", " + detail : ""))
}
