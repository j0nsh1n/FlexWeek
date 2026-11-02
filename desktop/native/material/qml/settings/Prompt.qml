import QtQuick
import components 1.0

// A dialog with up to three buttons, an optional one-line field, and an optional read-only text area.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool open: false
    property string title: ""
    property string body: ""
    property string error: ""
    property bool showField: false
    property string fieldLabel: ""
    property string fieldText: ""
    property string shownText: ""
    property var buttons: []
    signal picked(string value, string text)
    signal dismissed()

    anchors.fill: parent
    visible: open
    z: 30

    M3Palette { id: palette; theme: root.theme }

    function copyShown() {
        shownArea.selectAll()
        shownArea.copy()
        shownArea.deselect()
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.32
        TapHandler { onTapped: root.dismissed() }
    }
    Rectangle {
        id: card
        objectName: "promptCard"
        width: Math.min(480, Math.max(0, root.width - 32))
        height: column.implicitHeight + 48
        radius: 28
        anchors.centerIn: parent
        color: palette.surfaceContainerHigh
        Column {
            id: column
            x: 24
            y: 24
            width: card.width - 48
            spacing: 16
            Text {
                width: parent.width
                text: root.title
                color: palette.inkSurface
                font.family: M3Font.family
                font.pixelSize: 24
                wrapMode: Text.WordWrap
            }
            Text {
                visible: root.body !== ""
                width: parent.width
                text: root.body
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            OutlinedField {
                id: field
                objectName: "promptField"
                visible: root.showField
                width: parent.width
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: root.fieldLabel
                text: root.fieldText
                accessName: root.fieldLabel
            }
            Rectangle {
                visible: root.shownText !== ""
                width: parent.width
                height: 160
                radius: 8
                color: palette.surfaceContainerLowest
                border.width: 1
                border.color: palette.outlineVariant
                clip: true
                Flickable {
                    anchors.fill: parent
                    anchors.margins: 8
                    contentWidth: width
                    contentHeight: shownArea.implicitHeight
                    clip: true
                    TextEdit {
                        id: shownArea
                        objectName: "promptShown"
                        width: parent.width
                        readOnly: true
                        selectByMouse: true
                        text: root.shownText
                        wrapMode: TextEdit.WrapAnywhere
                        color: palette.inkSurface
                        font.family: "monospace"
                        font.pixelSize: 12
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Exported look"
                    }
                }
            }
            Text {
                objectName: "promptError"
                visible: root.error !== ""
                width: parent.width
                text: root.error
                color: palette.error
                font.family: M3Font.family
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            Item {
                width: parent.width
                height: actions.implicitHeight
                Row {
                    id: actions
                    anchors.right: parent.right
                    spacing: 8
                    Repeater {
                        model: root.buttons
                        delegate: Button {
                            objectName: "prompt_" + modelData.value
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: modelData.kind || "text"
                            text: modelData.label
                            accessName: modelData.label
                            onClicked: root.picked(modelData.value, field.text)
                        }
                    }
                }
            }
        }
    }
    activeFocusOnTab: open
    Accessible.role: Accessible.Dialog
    Accessible.name: root.title
    onOpenChanged: if (open) forceActiveFocus()
    Keys.onEscapePressed: (event) => {
        root.dismissed()
        event.accepted = true
    }
}
