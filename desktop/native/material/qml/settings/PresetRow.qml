import QtQuick
import components 1.0

// Six circular quadrant swatches for the colour presets.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string title: "Preset"
    property string subtitle: ""
    property var swatches: []
    property string current: ""
    signal chosen(string name)
    objectName: "row_preset"

    implicitHeight: 16 + 24 + 20 + 12 + flow.implicitHeight + 16
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    Column {
        x: 16
        y: 16
        width: root.width - 32
        spacing: 0
        Text {
            width: parent.width
            height: 24
            verticalAlignment: Text.AlignVCenter
            text: root.title
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: 16
            font.weight: 500
        }
        Text {
            width: parent.width
            height: 20
            text: root.subtitle
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: 14
        }
        Item { width: 1; height: 12 }
        Flow {
            id: flow
            width: parent.width
            spacing: 16
            Repeater {
                model: root.swatches
                delegate: PresetSwatch {
                    objectName: "preset_" + modelData.name
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    label: modelData.name
                    selected: modelData.name === root.current
                    quadrantPrimary: modelData.primary
                    quadrantTertiary: modelData.tertiary
                    quadrantSecondary: modelData.secondaryContainer
                    quadrantPrimaryContainer: modelData.primaryContainer
                    onClicked: root.chosen(modelData.name)
                }
            }
        }
    }
}
