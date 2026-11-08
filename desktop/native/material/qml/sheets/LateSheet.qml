import QtQuick
import components 1.0

SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "lateSheet"
    initialFocus: minutes
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Text {
        width: parent.width
        text: root.f.intro ? root.f.intro : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Text {
        objectName: "lateContext"
        width: parent.width
        text: root.f.context ? root.f.context : ""
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    PickerField {
        id: minutes
        objectName: "lateMinutes"
        width: parent.width
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        label: "How late"
        enabled: !root.f.previewed
        options: root.f.choices ? root.f.choices : []
        value: root.f.minutes
        onPicked: (v) => root.sheets.setLate(v)
    }
    Text {
        objectName: "lateSummary"
        visible: !!root.f.previewed
        width: parent.width
        text: root.f.summary ? root.f.summary : ""
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
        wrapMode: Text.WordWrap
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    Column {
        visible: !!root.f.previewed
        width: parent.width
        spacing: 8
        Repeater {
            model: root.f.changes ? root.f.changes : []
            delegate: Rectangle {
                objectName: "lateChange"
                width: parent.width
                height: line.implicitHeight + 16
                radius: 12
                color: pal.surfaceContainerLow
                Text {
                    id: line
                    x: 12
                    y: 8
                    width: parent.width - 24
                    text: modelData
                    color: pal.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                    wrapMode: Text.WordWrap
                    Accessible.role: Accessible.StaticText
                    Accessible.name: text
                }
            }
        }
    }
    FieldNote {
        objectName: "lateError"
        theme: root.theme
        problem: true
        text: root.f.error ? root.f.error : ""
    }
    FieldNote {
        theme: root.theme
        text: root.f.previewed ? "" : (root.f.wait ? root.f.wait : "")
    }

    trailing: [
        Button {
            objectName: "lateCancel"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Cancel"
            accessName: "Cancel"
            onClicked: root.sheets.closeSheet()
        },
        Button {
            objectName: "latePreview"
            enabled: !root.f.busy && !root.f.previewed
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "tonal"
            text: "Preview"
            accessName: "Preview"
            onClicked: root.sheets.preview()
        },
        Button {
            objectName: "lateAccept"
            enabled: !!root.f.previewed
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            text: "Accept late start"
            accessName: "Accept late start"
            onClicked: root.sheets.acceptLate()
        }
    ]
}
