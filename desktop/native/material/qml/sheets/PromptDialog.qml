import QtQuick
import components 1.0

// A question with buttons: "Discard what you typed?", a delete that asks first.
SheetFrame {
    id: root
    property var sheets
    readonly property var ask: sheets ? sheets.ask : ({})
    heading: ask.title ? ask.title : ""
    initialFocus: firstButton
    objectName: "sheetPrompt"
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    // Modal input catcher under the dialog card: absorbs clicks across the screen
    MouseArea {
        parent: root
        anchors.fill: parent
        z: 0
        preventStealing: true
        onClicked: root.closeRequested()
    }

    Text {
        width: parent.width
        text: root.ask.body ? root.ask.body : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    trailing: Repeater {
        model: root.ask.answers ? root.ask.answers : []
        delegate: Button {
            id: choice
            objectName: "prompt_" + modelData.id
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: modelData.kind
            text: modelData.label
            accessName: modelData.label
            onClicked: root.sheets.answer(modelData.id)
            Component.onCompleted: if (index === 0) root.firstButton = choice
        }
    }
    property Item firstButton: null
}
