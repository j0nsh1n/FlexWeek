import QtQuick
import components 1.0

SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "unfinishedSheet"
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Text {
        width: parent.width
        text: root.f.intro ? root.f.intro : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: 14
        wrapMode: Text.WordWrap
    }
    Text {
        objectName: "unfinishedEmpty"
        visible: text !== ""
        width: parent.width
        text: root.f.empty ? root.f.empty : ""
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: 16
    }
    Repeater {
        model: root.f.rows ? root.f.rows : []
        delegate: Rectangle {
            id: card
            objectName: "unfinishedRow"
            width: parent.width
            height: words.implicitHeight + actions.height + 28
            radius: 12
            color: pal.surfaceContainerLow
            Column {
                id: words
                x: 12
                y: 10
                width: parent.width - 24
                Text {
                    width: parent.width
                    text: modelData.title
                    color: pal.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: 16
                    font.weight: 500
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: modelData.detail
                    color: modelData.overdue ? pal.error : pal.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    Accessible.role: Accessible.StaticText
                    Accessible.name: modelData.title + ", " + text
                }
            }
            Row {
                id: actions
                x: 12
                anchors.top: words.bottom
                anchors.topMargin: 8
                height: 40
                spacing: 8
                Button {
                    objectName: "planUnfinished-" + modelData.id
                    visible: modelData.plannable
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "tonal"
                    text: "Find a time"
                    accessName: "Find a time for " + modelData.title
                    onClicked: root.sheets.findTime(modelData.id)
                }
                Button {
                    objectName: "deleteUnfinished-" + modelData.id
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "outlined"
                    text: "Delete"
                    accessName: "Delete " + modelData.title
                    onClicked: root.sheets.askDeleteUnfinished(modelData.id)
                }
            }
        }
    }
    trailing: Button {
        objectName: "unfinishedClose"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: "Close"
        accessName: "Close"
        onClicked: root.sheets.closeSheet()
    }
}
