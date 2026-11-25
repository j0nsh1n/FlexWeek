import QtQuick
import components 1.0

// The week as far as the student has said it, drawn with the real block look, and a short list of what is
// picked. It shows nothing the student did not enter: a week with nothing in it says so.
Column {
    id: root
    objectName: "setupPreview"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property int gridHeight: 280
    readonly property var shown: bridge ? bridge.preview : ({})
    readonly property var days: shown.days || []
    readonly property var blocks: shown.blocks || []
    readonly property var hours: shown.hours || []
    readonly property int firstMinute: (shown.from === undefined ? 8 : shown.from) * 60
    readonly property int spanMinutes: ((shown.to === undefined ? 16 : shown.to) * 60) - firstMinute
    readonly property int axisWidth: 48
    readonly property int headHeight: 28
    spacing: 12

    M3Palette { id: m3Palette; theme: root.theme }

    Rectangle {
        width: parent.width
        height: weekBox.implicitHeight + 24
        radius: m3Palette.cornerFor(16)
        color: m3Palette.cardSurface
        border.width: root.highContrast ? 1.5 : 1
        border.color: root.highContrast ? m3Palette.outline : m3Palette.outlineVariant

        Column {
            id: weekBox
            x: 12
            y: 12
            width: parent.width - 24
            spacing: 8
            Text {
                objectName: "setupPreviewNote"
                width: parent.width
                text: bridge ? bridge.previewNote : ""
                wrapMode: Text.WordWrap
                color: m3Palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(13)
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
            Item {
                id: grid
                objectName: "setupPreviewWeek"
                width: parent.width
                height: root.headHeight + root.gridHeight
                readonly property real columnWidth: root.days.length > 0 ? (width - root.axisWidth) / root.days.length : 0

                Repeater {
                    model: root.hours
                    Item {
                        required property var modelData
                        y: root.headHeight + (modelData.hour * 60 - root.firstMinute) / root.spanMinutes * root.gridHeight
                        width: grid.width
                        height: 1
                        Rectangle {
                            x: root.axisWidth
                            width: parent.width - root.axisWidth
                            height: 1
                            color: m3Palette.outlineVariant
                        }
                        Text {
                            x: 0
                            y: 2
                            width: root.axisWidth - 8
                            horizontalAlignment: Text.AlignRight
                            text: modelData.label
                            color: m3Palette.inkMuted
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(11)
                        }
                    }
                }
                Repeater {
                    model: root.days
                    Text {
                        required property var modelData
                        required property int index
                        x: root.axisWidth + index * grid.columnWidth
                        width: grid.columnWidth
                        height: root.headHeight
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        text: modelData.short
                        color: m3Palette.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(12)
                        font.weight: 500
                    }
                }
                Repeater {
                    model: root.blocks
                    EventBlock {
                        required property var modelData
                        objectName: "setupPreviewBlock"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        fitToHeight: true
                        // A name that would break mid-word is left out; Chosen so far says it.
                        showWords: width >= M3Font.px(52)
                        category: modelData.category
                        title: modelData.title
                        detail: grid.columnWidth / modelData.lanes >= 110 ? modelData.detail : ""
                        x: root.axisWidth + modelData.column * grid.columnWidth + 2 + modelData.lane * (grid.columnWidth - 4) / modelData.lanes
                        y: root.headHeight + (modelData.start - root.firstMinute) / root.spanMinutes * root.gridHeight
                        width: (grid.columnWidth - 4) / modelData.lanes - (modelData.lanes > 1 ? 2 : 0)
                        height: Math.max(20, (modelData.end - modelData.start) / root.spanMinutes * root.gridHeight)
                    }
                }
            }
        }
    }

    Rectangle {
        width: parent.width
        height: chosen.implicitHeight + 24
        radius: m3Palette.cornerFor(16)
        color: m3Palette.cardSurface
        border.width: root.highContrast ? 1.5 : 1
        border.color: root.highContrast ? m3Palette.outline : m3Palette.outlineVariant
        Column {
            id: chosen
            x: 12
            y: 12
            width: parent.width - 24
            spacing: 4
            Text {
                text: "Chosen so far"
                color: m3Palette.inkSurface
                font.family: M3Font.family
                font.pixelSize: M3Font.px(14)
                font.weight: 500
            }
            Repeater {
                model: bridge ? bridge.chosenSoFar : []
                Text {
                    required property string modelData
                    objectName: "setupChosen"
                    width: chosen.width
                    text: modelData
                    wrapMode: Text.WordWrap
                    color: m3Palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(13)
                }
            }
        }
    }
}
