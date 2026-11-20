import QtQuick
import components 1.0

// Help from More or F1: how planning works, the four screens, and the keys this look answers to.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "helpSheet"
    initialFocus: closeButton
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Keys.onUpPressed: (event) => { root.scrollBy(-48); event.accepted = true }
    Keys.onDownPressed: (event) => { root.scrollBy(48); event.accepted = true }
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_PageUp) {
            root.scrollBy(-300)
            event.accepted = true
        } else if (event.key === Qt.Key_PageDown) {
            root.scrollBy(300)
            event.accepted = true
        }
    }

    Text {
        width: parent.width
        text: "How planning works"
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Text {
        objectName: "helpPlanning"
        width: parent.width
        text: root.f.planning ? root.f.planning : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Text {
        width: parent.width
        text: "The screens"
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Grid {
        width: parent.width
        columns: root.phone ? 1 : 2
        spacing: 12
        Repeater {
            model: root.f.screens ? root.f.screens : []
            delegate: Rectangle {
                objectName: "helpScreen"
                width: (parent.width - (root.phone ? 0 : 12)) / (root.phone ? 1 : 2)
                height: cardText.implicitHeight + 24
                radius: 12
                color: pal.surfaceContainerLow
                border.width: root.highContrast ? 1.5 : 0
                border.color: pal.outline
                Column {
                    id: cardText
                    x: 12
                    y: 12
                    width: parent.width - 24
                    spacing: 2
                    Text {
                        width: parent.width
                        text: modelData.name
                        color: pal.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        font.weight: 500
                    }
                    Text {
                        width: parent.width
                        text: modelData.words
                        color: pal.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        wrapMode: Text.WordWrap
                    }
                }
                Accessible.role: Accessible.StaticText
                Accessible.name: modelData.name + ". " + modelData.words
            }
        }
    }
    Text {
        width: parent.width
        text: "Keyboard shortcuts"
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Column {
        id: keyList
        objectName: "helpKeys"
        width: parent.width
        spacing: 10
        Repeater {
            model: root.f.keys ? root.f.keys : []
            delegate: Item {
                id: keyRow
                objectName: "helpKey"
                readonly property real keysWidth: root.phone ? 150 : 200
                width: keyList.width
                height: Math.max(caps.height, does.implicitHeight)
                Accessible.role: Accessible.StaticText
                Accessible.name: modelData.spoken + ": " + modelData.words
                Flow {
                    id: caps
                    width: keyRow.keysWidth
                    spacing: 4
                    Repeater {
                        model: modelData.parts
                        delegate: Item {
                            width: modelData.cap ? keyText.implicitWidth + 12 : keyText.implicitWidth
                            height: 24
                            Accessible.ignored: true
                            Rectangle {
                                visible: modelData.cap
                                anchors.fill: parent
                                radius: 4
                                color: pal.surfaceContainerHighest
                                border.width: 1
                                border.color: pal.outlineVariant
                            }
                            Text {
                                id: keyText
                                anchors.centerIn: parent
                                text: modelData.text
                                color: modelData.cap ? pal.inkSurface : pal.inkMuted
                                font.family: M3Font.family
                                font.pixelSize: M3Font.px(12)
                                font.weight: modelData.cap ? 500 : 400
                            }
                        }
                    }
                }
                Text {
                    id: does
                    x: keyRow.keysWidth + 16
                    width: parent.width - x
                    text: modelData.words
                    color: pal.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                    wrapMode: Text.WordWrap
                    Accessible.ignored: true
                }
            }
        }
    }
    trailing: Button {
        id: closeButton
        objectName: "helpClose"
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
