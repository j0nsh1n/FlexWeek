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

    opacity: past ? 0.65 : 1
    implicitWidth: 160
    implicitHeight: Math.max(44, body.implicitHeight + 12)
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
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 12
        color: root.tones()[0]
        clip: true
        border.width: root.highContrast ? 1.5 : 0
        border.color: root.tones()[1]
        Rectangle {
            objectName: "bar"
            width: 4
            height: parent.height
            color: root.tones()[2]
        }
        Column {
            id: body
            objectName: "body"
            x: 12
            y: 6
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
                font.pixelSize: 12
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
