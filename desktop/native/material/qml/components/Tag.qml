import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    // plain, tight, plenty, or cutting.
    property string kind: "plain"
    property string text: ""

    implicitHeight: 20
    height: 20
    implicitWidth: label.implicitWidth + 16
    width: implicitWidth

    M3Palette { id: palette; theme: root.theme }

    readonly property color fill: {
        if (root.kind === "tight")
            return palette.errorContainer
        if (root.kind === "plenty")
            return palette.secondaryContainer
        if (root.kind === "cutting")
            return palette.tertiaryContainer
        return palette.surfaceVariant
    }
    readonly property color ink: {
        if (root.kind === "tight")
            return palette.inkErrorContainer
        if (root.kind === "plenty")
            return palette.inkSecondaryContainer
        if (root.kind === "cutting")
            return palette.inkTertiaryContainer
        return palette.inkMuted
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 6
        color: root.fill
        border.width: root.highContrast ? 1.5 : 0
        border.color: root.ink
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.ink
        font.family: M3Font.family
        font.pixelSize: 11
        font.weight: 500
    }
    Accessible.role: Accessible.StaticText
    Accessible.name: text
}
