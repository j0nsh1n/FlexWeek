import QtQuick
import components 1.0

// Every block of the week, day by day, for a keyboard or a screen reader. Opening one edits it.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "weekListSheet"
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Repeater {
        model: root.f.rows ? root.f.rows : []
        delegate: Item {
            id: entry
            width: parent.width
            height: modelData.type === "item" ? item.height : text.implicitHeight + (modelData.type === "heading" ? 4 : 0)
            Text {
                id: text
                visible: modelData.type !== "item"
                objectName: modelData.type === "heading" ? "weekListDay" : "weekListNone"
                width: parent.width
                topPadding: modelData.type === "heading" ? 4 : 0
                leftPadding: modelData.type === "heading" ? 0 : 4
                text: modelData.type === "item" ? "" : modelData.text
                color: pal.inkMuted
                font.family: M3Font.family
                font.pixelSize: modelData.type === "heading" ? 12 : 14
                font.weight: modelData.type === "heading" ? 500 : 400
            }
            ListRow {
                id: item
                objectName: "weekListItem"
                visible: modelData.type === "item"
                width: parent.width
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                title: modelData.type === "item" ? modelData.title : ""
                subtitle: modelData.type === "item" ? modelData.detail : ""
                accessName: modelData.type === "item" ? modelData.words : ""
                onClicked: root.sheets.openFromList(modelData.blockId, modelData.day)
            }
        }
    }
    trailing: Button {
        objectName: "weekListClose"
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
