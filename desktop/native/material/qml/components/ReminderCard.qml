import QtQuick

// A reminder kept on screen: the notice's own words with Snooze and Close. It is not a sheet, so Esc
// does nothing here, and it never takes the keyboard when it appears (a screen reader is told by the bridge).
Rectangle {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false

    property string title: ""
    property string body: ""

    signal snoozed()
    signal closed()

    property real maxWidth: 560
    width: Math.min(maxWidth, 560)
    height: content.implicitHeight + 24
    radius: 12
    color: palette.secondaryContainer
    border.width: root.highContrast ? 2 : 1
    border.color: root.highContrast ? palette.inkSurface : palette.outlineVariant
    Accessible.role: Accessible.Pane
    Accessible.name: root.title + (root.body !== "" ? ", " + root.body : "")

    M3Palette { id: palette; theme: root.theme }

    Column {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: 16
        spacing: 8

        Text {
            objectName: "reminderCardTitle"
            width: parent.width
            text: root.title
            color: palette.inkSecondaryContainer
            font.family: M3Font.family
            font.pixelSize: M3Font.px(16)
            font.weight: Font.Medium
            wrapMode: Text.WordWrap
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
        Text {
            objectName: "reminderCardBody"
            width: parent.width
            visible: root.body !== ""
            text: root.body
            color: palette.inkSecondaryContainer
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            wrapMode: Text.WordWrap
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
        Row {
            anchors.right: parent.right
            spacing: 8
            Button {
                objectName: "reminderCardSnooze"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "tonal"
                text: "Snooze"
                accessName: "Snooze"
                onClicked: root.snoozed()
            }
            Button {
                objectName: "reminderCardClose"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                text: "Close"
                accessName: "Close"
                onClicked: root.closed()
            }
        }
    }
}
