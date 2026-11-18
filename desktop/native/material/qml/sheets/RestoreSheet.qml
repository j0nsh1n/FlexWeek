import QtQuick
import components 1.0

// Restore points, from More's Copies of this week: the saved copies with their times, a name for a new
// one, a preview of what going back would change, and Restore, which asks first.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "restoreSheet"
    initialFocus: nameField
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Text {
        objectName: "storageLocation"
        width: parent.width
        text: root.f.where ? root.f.where : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    SyncField {
        id: nameField
        objectName: "restoreLabel"
        width: parent.width
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        label: "Restore point name"
        wanted: root.f.label ? root.f.label : ""
        onTextEdited: (value) => root.sheets.setRestoreLabel(value)
        Keys.onReturnPressed: root.sheets.createRestore()
        Keys.onEnterPressed: root.sheets.createRestore()
    }
    Button {
        objectName: "restoreCreate"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "tonal"
        text: "Save restore point"
        accessName: "Save restore point"
        onClicked: root.sheets.createRestore()
    }
    Repeater {
        model: root.f.points ? root.f.points : []
        delegate: ListRow {
            objectName: "restorePoint"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            icon: modelData.id === root.f.selected ? "check" : ""
            title: modelData.title
            subtitle: modelData.detail
            accessName: modelData.text + (modelData.id === root.f.selected ? ", chosen" : "")
            onClicked: root.sheets.selectRestore(modelData.id)
        }
    }
    Text {
        objectName: "restorePreviewSummary"
        visible: text !== ""
        width: parent.width
        text: root.f.summary ? root.f.summary : ""
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    FieldNote { objectName: "restoreNote"; theme: root.theme; text: root.f.note ? root.f.note : "" }
    leading: Button {
        objectName: "restorePreview"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: "Preview"
        accessName: "Preview"
        onClicked: root.sheets.previewRestore()
    }
    trailing: [
        Button {
            objectName: "restoreClose"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Close"
            accessName: "Close"
            onClicked: root.sheets.closeSheet()
        },
        Button {
            objectName: "restoreApply"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            text: "Restore"
            accessName: "Restore"
            onClicked: root.sheets.restoreSelected()
        }
    ]
}
