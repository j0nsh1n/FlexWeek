import QtQuick
import components 1.0

Column {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string scope: "day"
    property string title: ""
    property string line: ""
    signal startFocus()

    spacing: 8
    width: parent ? parent.width : implicitWidth

    M3Palette { id: palette; theme: root.theme }

    Text {
        text: "Now"
        color: palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: 12
        font.weight: 500
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }

    Rectangle {
        id: card
        objectName: root.scope + "Now"
        width: parent.width
        implicitHeight: column.implicitHeight + pad * 2
        height: implicitHeight
        radius: 28
        color: palette.primaryContainer
        Accessible.role: Accessible.Grouping
        Accessible.name: root.title + ", " + root.line

        readonly property int pad: root.density === "compact" ? 16 : 24

        Column {
            id: column
            x: card.pad
            y: card.pad
            width: card.width - card.pad * 2
            spacing: 0

            Column {
                width: parent.width
                spacing: 4
                Text {
                    objectName: root.scope + "NowTitle"
                    width: parent.width
                    text: root.title
                    wrapMode: Text.WordWrap
                    color: palette.inkPrimaryContainer
                    font.family: M3Font.family
                    font.pixelSize: 24
                    font.weight: 400
                }
                Text {
                    objectName: root.scope + "NowLine"
                    width: parent.width
                    text: root.line
                    color: palette.inkPrimaryContainer
                    font.family: M3Font.family
                    font.pixelSize: 16
                    font.weight: 400
                }
            }
            Item { width: 1; height: 12 }
            Button {
                objectName: root.scope + "StartFocus"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                text: "Start focus"
                icon: "play_arrow"
                accessName: "Start focus"
                onClicked: root.startFocus()
            }
        }
    }
}
