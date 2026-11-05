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

    M3Palette { id: palette; theme: root.theme }

    readonly property color fill: {
        if (root.kind === "plenty")
            return palette.statusDoneTint
        if (root.kind === "tight")
            return palette.statusDueSoonTint
        if (root.kind === "cutting")
            return palette.statusOverdueTint
        return palette.surfaceVariant
    }
    readonly property color ink: {
        if (root.kind === "plenty")
            return palette.statusDone
        if (root.kind === "tight")
            return palette.statusDueSoon
        if (root.kind === "cutting")
            return palette.statusOverdue
        return palette.inkMuted
    }
    readonly property string iconName: {
        if (root.kind === "plenty")
            return "check"
        if (root.kind === "tight")
            return "schedule"
        if (root.kind === "cutting")
            return "warning"
        return ""
    }

    implicitWidth: Math.max(20, content.implicitWidth + 16)
    width: implicitWidth

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: height / 2
        color: root.fill
        border.width: root.highContrast ? 1.5 : 0
        border.color: root.ink
    }

    Row {
        id: content
        objectName: "content"
        anchors.centerIn: parent
        spacing: 4

        M3Icon {
            id: chipIcon
            objectName: "icon"
            visible: root.iconName !== ""
            name: root.iconName
            width: 12
            height: 12
            anchors.verticalCenter: parent.verticalCenter
            color: root.ink
        }

        Text {
            id: label
            objectName: "label"
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: root.ink
            font.family: M3Font.family
            font.pixelSize: 11
            font.weight: 500
        }
    }

    Accessible.role: Accessible.StaticText
    Accessible.name: text
}
